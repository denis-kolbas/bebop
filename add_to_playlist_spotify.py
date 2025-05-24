import os
import json
import datetime
import time
from google.cloud import storage
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import gspread
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Spotify API credentials from environment variables
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_PLAYLIST_ID = "23jlRqLpPrVUPhMuGGtfX9"
SPOTIFY_REFRESH_TOKEN = os.environ.get("SPOTIFY_REFRESH_TOKEN")

# Spreadsheet configuration
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')

# Number of days to keep songs in playlist
DAYS_TO_KEEP_SONGS = 7

def initialize_gcp():
    """Initialize GCP credentials from environment variable"""
    gcp_sa_content = os.environ.get("GCP_SA_KEY")
    temp_sa_file = "/tmp/gcp_sa.json"
    with open(temp_sa_file, "w") as f:
        f.write(gcp_sa_content)
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_sa_file
    logging.info("GCP credentials initialized")

def get_spotify_client():
    """Create an authenticated Spotify client using refresh token"""
    try:
        scope = "playlist-modify-public playlist-read-private playlist-modify-private"
        
        auth_manager = spotipy.oauth2.SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=scope,
            cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path="/tmp/spotify_cache")
        )
        
        token_info = auth_manager.refresh_access_token(SPOTIFY_REFRESH_TOKEN)
        auth_manager.cache_handler.save_token_to_cache(token_info)
        
        sp = spotipy.Spotify(auth_manager=auth_manager)
        logging.info("Spotify client authenticated successfully")
        return sp
    except Exception as e:
        logging.error(f"Failed to authenticate with Spotify: {str(e)}")
        raise

def fix_encoding(text):
    """Fix double-encoded UTF-8 characters in text"""
    if not text:
        return ""
    
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeError, UnicodeDecodeError):
        return text

def fetch_songs_from_spreadsheet():
    """Fetch songs data from Google Spreadsheet"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            '/tmp/gcp_sa.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly', 
                    'https://www.googleapis.com/auth/drive.readonly']
        )
        gc = gspread.authorize(credentials)
        
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1
        
        all_values = worksheet.get_all_values()
        
        if not all_values:
            logging.warning("Spreadsheet is empty")
            return []
        
        headers = all_values[0]
        data = all_values[1:]
        
        songs_data = []
        for row in data:
            song = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    if header == 'create_video':
                        song[header] = row[i].upper() == 'TRUE'
                    else:
                        song[header] = fix_encoding(row[i])
            songs_data.append(song)
        
        logging.info(f"Successfully fetched {len(songs_data)} songs from spreadsheet")
        return songs_data
        
    except Exception as e:
        logging.error(f"Failed to fetch songs from spreadsheet: {str(e)}")
        raise

def get_current_date():
    """Get current date in YYYY-MM-DD format"""
    return datetime.datetime.now().strftime("%Y-%m-%d")

def search_spotify_track(sp, song_name, artist_name):
    """Search for a track on Spotify and return its ID"""
    query = f"track:{song_name} artist:{artist_name}"
    try:
        results = sp.search(q=query, type="track", limit=1)
        
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            logging.info(f"Found track: {track['name']} by {track['artists'][0]['name']} (ID: {track['id']})")
            return track['id']
        else:
            # Try more lenient search
            results = sp.search(q=f"{song_name} {artist_name}", type="track", limit=5)
            
            if results['tracks']['items']:
                for track in results['tracks']['items']:
                    track_artists = [artist['name'].lower() for artist in track['artists']]
                    if any(artist_name.lower() in artist for artist in track_artists):
                        logging.info(f"Found close match: {track['name']} by {track['artists'][0]['name']} (ID: {track['id']})")
                        return track['id']
            
            logging.warning(f"Track not found: {song_name} by {artist_name}")
            return None
    except Exception as e:
        logging.error(f"Error searching for track {song_name} by {artist_name}: {str(e)}")
        return None

def get_existing_playlist_tracks(sp):
    """Get existing tracks in the playlist with their add dates"""
    tracks = []
    results = sp.playlist_items(SPOTIFY_PLAYLIST_ID, fields="items.track.id,items.added_at,next", limit=100)
    
    while results:
        for item in results['items']:
            if item['track']:
                tracks.append({
                    'id': item['track']['id'],
                    'added_at': item['added_at']
                })
        
        if results['next']:
            results = sp.next(results)
        else:
            break
    
    logging.info(f"Retrieved {len(tracks)} existing tracks from playlist")
    return tracks

def get_tracks_to_remove(existing_tracks):
    """Identify tracks to remove based on age"""
    tracks_to_remove = []
    today = datetime.datetime.now(datetime.timezone.utc)
    
    for track in existing_tracks:
        added_date = datetime.datetime.fromisoformat(track['added_at'].replace('Z', '+00:00'))
        age_days = (today - added_date).days
        
        if age_days > DAYS_TO_KEEP_SONGS:
            tracks_to_remove.append(track['id'])
            logging.info(f"Track {track['id']} will be removed (age: {age_days} days)")
    
    return tracks_to_remove

def update_playlist(sp, today_songs):
    """Update the playlist with today's songs and remove old ones"""
    # Get existing playlist tracks
    existing_tracks = get_existing_playlist_tracks(sp)
    existing_track_ids = [track['id'] for track in existing_tracks]
    
    # Process today's songs
    new_track_ids = []
    for song in today_songs:
        track_id = search_spotify_track(sp, song['song_name'], song['artist'])
        
        if track_id and track_id not in existing_track_ids and track_id not in new_track_ids:
            new_track_ids.append(track_id)
        
        time.sleep(0.5)
    
    # Add new tracks to playlist
    # Add new tracks to playlist
    if new_track_ids:
        try:
            sp.playlist_add_items(SPOTIFY_PLAYLIST_ID, new_track_ids)
            logging.info(f"Added {len(new_track_ids)} new tracks to playlist")
            
            # Move new tracks to top
            playlist_info = sp.playlist(SPOTIFY_PLAYLIST_ID, fields="tracks.total")
            total_tracks = playlist_info['tracks']['total']
            
            sp.playlist_reorder_items(
                SPOTIFY_PLAYLIST_ID,
                range_start=total_tracks - len(new_track_ids),
                insert_before=0,
                range_length=len(new_track_ids)
            )
            logging.info(f"Moved {len(new_track_ids)} new tracks to top")
            
        except Exception as e:
            logging.error(f"Failed to add/reorder tracks: {str(e)}")
    
    # Remove old tracks
    tracks_to_remove = get_tracks_to_remove(existing_tracks)
    if tracks_to_remove:
        try:
            for i in range(0, len(tracks_to_remove), 100):
                batch = tracks_to_remove[i:i+100]
                sp.playlist_remove_all_occurrences_of_items(SPOTIFY_PLAYLIST_ID, batch)
            
            logging.info(f"Removed {len(tracks_to_remove)} tracks from playlist")
        except Exception as e:
            logging.error(f"Failed to remove tracks from playlist: {str(e)}")
    else:
        logging.info("No tracks to remove from playlist")
    
    # Update playlist description
    update_playlist_description(sp)

def update_playlist_description(sp):
    """Update the playlist description with current information"""
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    description = f"Your daily discovery of new music. Newest releases added daily, removed after 7 days. Updated on {current_date}."
    
    try:
        sp.playlist_change_details(
            playlist_id=SPOTIFY_PLAYLIST_ID,
            description=description
        )
        logging.info("Updated playlist description")
    except Exception as e:
        logging.error(f"Failed to update playlist description: {str(e)}")

def main():
    try:
        # Initialize GCP
        initialize_gcp()
        
        # Get Spotify client
        sp = get_spotify_client()
        
        # Fetch songs from spreadsheet
        all_songs = fetch_songs_from_spreadsheet()
        
        # Get today's date
        today = get_current_date()
        
        # Filter for today's songs where create_video = True
        today_songs = [
            song for song in all_songs 
            if song.get('selected_date') == today and song.get('create_video') == True
        ]
        logging.info(f"Found {len(today_songs)} songs for today ({today}) with create_video=True")
        
        # Update the playlist
        update_playlist(sp, today_songs)
        
        logging.info("Script completed successfully")
        
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")

if __name__ == "__main__":
    main()
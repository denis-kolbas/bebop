import os
import json
import datetime
import time
import logging
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# YouTube API credentials from environment variables
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_PLAYLIST_ID = os.environ.get("YOUTUBE_PLAYLIST_ID")  # Your YT Music playlist ID

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

def get_youtube_client():
    """Create an authenticated YouTube client using refresh token"""
    try:
        creds = Credentials(
            token=None,
            refresh_token=YOUTUBE_REFRESH_TOKEN,
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token"
        )
        
        # Refresh the token
        creds.refresh(Request())
        
        youtube = build('youtube', 'v3', credentials=creds)
        logging.info("YouTube client authenticated successfully")
        return youtube
    except Exception as e:
        logging.error(f"Failed to authenticate with YouTube: {str(e)}")
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

def search_youtube_music_track(youtube, song_name, artist_name):
    """Search for a track on YouTube Music and return its video ID"""
    # Search for music videos specifically
    query = f"{song_name} {artist_name} music"
    
    try:
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            type='video',
            videoCategoryId='10',  # Music category
            maxResults=10
        ).execute()
        
        for item in search_response['items']:
            title = item['snippet']['title'].lower()
            description = item['snippet']['description'].lower()
            channel = item['snippet']['channelTitle'].lower()
            
            # Check if this looks like the official track
            song_lower = song_name.lower()
            artist_lower = artist_name.lower()
            
            if (song_lower in title and 
                (artist_lower in title or artist_lower in channel or artist_lower in description)):
                
                video_id = item['id']['videoId']
                logging.info(f"Found track: {item['snippet']['title']} by {item['snippet']['channelTitle']} (ID: {video_id})")
                return video_id
        
        # If no exact match, try the first result that contains the song name
        for item in search_response['items']:
            title = item['snippet']['title'].lower()
            if song_name.lower() in title:
                video_id = item['id']['videoId']
                logging.info(f"Found approximate match: {item['snippet']['title']} (ID: {video_id})")
                return video_id
        
        logging.warning(f"Track not found: {song_name} by {artist_name}")
        return None
        
    except Exception as e:
        logging.error(f"Error searching for track {song_name} by {artist_name}: {str(e)}")
        return None

def get_existing_playlist_videos(youtube):
    """Get existing videos in the playlist"""
    videos = []
    next_page_token = None
    
    try:
        while True:
            request = youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=YOUTUBE_PLAYLIST_ID,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response['items']:
                videos.append({
                    'video_id': item['contentDetails']['videoId'],
                    'playlist_item_id': item['id'],
                    'published_at': item['snippet']['publishedAt']
                })
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
                
        logging.info(f"Retrieved {len(videos)} existing videos from playlist")
        return videos
        
    except Exception as e:
        logging.error(f"Error fetching playlist videos: {str(e)}")
        return []

def get_videos_to_remove(existing_videos):
    """Identify videos to remove based on age"""
    videos_to_remove = []
    today = datetime.datetime.now(datetime.timezone.utc)
    
    for video in existing_videos:
        published_date = datetime.datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        age_days = (today - published_date).days
        
        if age_days > DAYS_TO_KEEP_SONGS:
            videos_to_remove.append(video['playlist_item_id'])
            logging.info(f"Video {video['video_id']} will be removed (age: {age_days} days)")
    
    return videos_to_remove

def update_playlist(youtube, today_songs):
    """Update the playlist with today's songs and remove old ones"""
    # Get existing playlist videos
    existing_videos = get_existing_playlist_videos(youtube)
    existing_video_ids = [video['video_id'] for video in existing_videos]
    
    # Process today's songs
    new_video_ids = []
    for song in today_songs:
        video_id = search_youtube_music_track(youtube, song['song_name'], song['artist'])
        
        if video_id and video_id not in existing_video_ids and video_id not in new_video_ids:
            new_video_ids.append(video_id)
        
        time.sleep(1)  # Rate limiting
    
    # Add new videos to playlist
    if new_video_ids:
        try:
            for video_id in new_video_ids:
                youtube.playlistItems().insert(
                    part='snippet',
                    body={
                        'snippet': {
                            'playlistId': YOUTUBE_PLAYLIST_ID,
                            'resourceId': {
                                'kind': 'youtube#video',
                                'videoId': video_id
                            },
                            'position': 0  # Add to top of playlist
                        }
                    }
                ).execute()
                
                logging.info(f"Added video {video_id} to playlist")
                time.sleep(0.5)  # Rate limiting
                
            logging.info(f"Added {len(new_video_ids)} new videos to playlist")
            
        except Exception as e:
            logging.error(f"Failed to add videos to playlist: {str(e)}")
    
    # Remove old videos
    videos_to_remove = get_videos_to_remove(existing_videos)
    if videos_to_remove:
        try:
            for playlist_item_id in videos_to_remove:
                youtube.playlistItems().delete(id=playlist_item_id).execute()
                time.sleep(0.5)  # Rate limiting
            
            logging.info(f"Removed {len(videos_to_remove)} videos from playlist")
        except Exception as e:
            logging.error(f"Failed to remove videos from playlist: {str(e)}")
    else:
        logging.info("No videos to remove from playlist")
    
    # Update playlist description
    update_playlist_description(youtube)

def update_playlist_description(youtube):
    """Update the playlist description with current information"""
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    description = f"Your daily discovery of new music. Newest releases added daily, removed after 7 days. Updated on {current_date}."
    
    try:
        youtube.playlists().update(
            part='snippet',
            body={
                'id': YOUTUBE_PLAYLIST_ID,
                'snippet': {
                    'title': 'Daily Music Discoveries',
                    'description': description
                }
            }
        ).execute()
        logging.info("Updated playlist description")
    except Exception as e:
        logging.error(f"Failed to update playlist description: {str(e)}")

def main():
    try:
        # Initialize GCP
        initialize_gcp()
        
        # Get YouTube client
        youtube = get_youtube_client()
        
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
        update_playlist(youtube, today_songs)
        
        logging.info("Script completed successfully")
        
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")

if __name__ == "__main__":
    main()
import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
import time
import json

# Configuration
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

def init_gcp():
    service_account_json = os.environ.get('GCP_SA_KEY')
    with open('gcp_credentials.json', 'w') as f:
        f.write(service_account_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def fetch_songs_from_spreadsheet():
    """Fetch songs from Google Spreadsheet"""
    try:
        init_gcp()
        credentials = service_account.Credentials.from_service_account_file(
            'gcp_credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly']
        )
        gc = gspread.authorize(credentials)
        
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1
        
        all_values = worksheet.get_all_values()
        
        if not all_values:
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
                        song[header] = row[i]
            songs_data.append(song)
        
        return songs_data
        
    except Exception as e:
        print(f"Error fetching songs: {e}", flush=True)
        return []

def get_today_songs():
    """Get today's songs with create_video = TRUE"""
    songs = fetch_songs_from_spreadsheet()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    today_songs = [
        song for song in songs 
        if song.get('selected_date') == today and song.get('create_video') == True
    ]
    
    print(f"Found {len(today_songs)} songs for today", flush=True)
    return today_songs

def get_stitched_video_url():
    """Get today's stitched video URL"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"stitched_reel_full_{today}.mp4"
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/videos/{today}/stitched/{filename}"

def create_post_text(songs):
    """Create text for the main post"""
    today_formatted = datetime.datetime.now().strftime("%B %d, %Y")
    
    if not songs:
        return f"Top new releases - {today_formatted} 🎵 #newmusic"
    
    text = f"Top new releases - {today_formatted}:\n\n"
    for i, song in enumerate(songs, 1):
        text += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    text += "\n#newmusic"
    return text[:500]  # Threads 500 char limit

def create_individual_post_text(song):
    """Create text for individual song post"""
    text = f"🎵 {song['song_name']} - {song['artist']}\n\n#newmusic"
    return text[:500]

def create_threads_container(media_type, video_url=None, text=None):
    """Create a Threads media container"""
    url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    
    payload = {
        'media_type': media_type,
        'access_token': THREADS_ACCESS_TOKEN
    }
    
    if video_url:
        payload['video_url'] = video_url
    
    if text:
        payload['text'] = text
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        container_id = result['id']
        print(f"Threads container created: {container_id}", flush=True)
        return container_id
    else:
        print(f"Error creating container: {response.text}", flush=True)
        return None

def publish_threads_container(container_id):
    """Publish a Threads media container"""
    url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    
    payload = {
        'creation_id': container_id,
        'access_token': THREADS_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        media_id = result['id']
        print(f"Threads post published: {media_id}", flush=True)
        return media_id
    else:
        print(f"Error publishing: {response.text}", flush=True)
        return None

def post_individual_videos(songs):
    """Post individual song videos"""
    successful_posts = 0
    
    for i, song in enumerate(songs):
        video_url = song.get('video_url')
        if not video_url:
            continue
            
        print(f"Posting video {i+1}/{len(songs)}: {song['song_name']}", flush=True)
        
        # Create post text
        text = create_individual_post_text(song)
        
        # Create container
        container_id = create_threads_container('VIDEO', video_url, text)
        if not container_id:
            continue
        
        # Wait 30 seconds for processing (Threads recommendation)
        print(f"Waiting 30 seconds for processing...", flush=True)
        time.sleep(30)
        
        # Publish
        media_id = publish_threads_container(container_id)
        if media_id:
            successful_posts += 1
            print(f"✅ Posted video for {song['song_name']}", flush=True)
        else:
            print(f"❌ Failed to post video for {song['song_name']}", flush=True)
            
        # Rate limiting between posts (be conservative)
        time.sleep(60)
    
    return successful_posts

def main():
    # Check required environment variables
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        print("Error: Missing THREADS_ACCESS_TOKEN or THREADS_USER_ID", flush=True)
        return
    
    print(f"Threads User ID: {THREADS_USER_ID}", flush=True)
    print(f"Token: {'Set' if THREADS_ACCESS_TOKEN else 'Not set'}", flush=True)
    
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs found for today", flush=True)
        return
    
    print(f"Processing {len(songs)} songs...", flush=True)
    
    # Post stitched video only
    print("\n--- Posting Stitched Video to Threads ---", flush=True)
    
    # Get stitched video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}", flush=True)
    
    # Create post text
    text = create_post_text(songs)
    print(f"Text: {text[:100]}...", flush=True)
    
    # Create container
    container_id = create_threads_container('VIDEO', video_url, text)
    if not container_id:
        print("❌ Failed to create stitched video container", flush=True)
        return
    
    # Wait for processing
    print("Waiting 60 seconds for processing...", flush=True)
    time.sleep(60)
    
    # Publish
    media_id = publish_threads_container(container_id)
    if media_id:
        print(f"✅ Successfully posted stitched video to Threads", flush=True)
    else:
        print("❌ Failed to post stitched video", flush=True)
    
    print(f"\n🎉 Summary: Stitched video posted to Threads", flush=True)

if __name__ == "__main__":
    main()
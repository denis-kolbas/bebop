import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
import time
import json

# Configuration
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")
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
        print(f"Error fetching songs: {e}")
        return []

def get_today_songs():
    """Get today's songs with create_video = TRUE"""
    songs = fetch_songs_from_spreadsheet()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    today_songs = [
        song for song in songs 
        if song.get('selected_date') == today and song.get('create_video') == True
    ]
    
    print(f"Found {len(today_songs)} songs for today")
    return today_songs

def get_stitched_video_url():
    """Get today's stitched video URL"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"stitched_reel_{today}.mp4"
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/videos/{today}/stitched/{filename}"

def create_caption(songs):
    """Create caption for the reel"""
    if not songs:
        return "🎵 New music compilation! #newmusic #music #playlist #trending"
    
    caption = "Top new releases:\n\n"
    for i, song in enumerate(songs, 1):
        caption += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    caption += "\n#newmusic #music #playlist #trending #reel #discover"
    return caption

def create_reel_container(video_url, caption):
    """Create Instagram Reel container"""
    url = f"https://graph.instagram.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media"
    
    payload = {
        'video_url': video_url,
        'media_type': 'REELS',
        'caption': caption,
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        container_id = response.json()['id']
        print(f"Reel container created: {container_id}")
        return container_id
    else:
        print(f"Error creating container: {response.text}")
        return None

def create_story_container(video_url):
    """Create Instagram story container"""
    url = f"https://graph.instagram.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media"
    
    payload = {
        'video_url': video_url,
        'media_type': 'STORIES',
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        container_id = response.json()['id']
        print(f"Story container created: {container_id}")
        return container_id
    else:
        print(f"Error creating story container: {response.text}")
        return None

def check_container_status(container_id):
    """Check container processing status"""
    url = f"https://graph.instagram.com/v18.0/{container_id}"
    params = {
        'fields': 'status_code',
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        status = response.json().get('status_code')
        print(f"Container status: {status}")
        return status
    else:
        print(f"Error checking status: {response.text}")
        return None

def publish_reel(container_id):
    """Publish the reel"""
    url = f"https://graph.instagram.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    
    payload = {
        'creation_id': container_id,
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        media_id = response.json()['id']
        print(f"Reel published: {media_id}")
        return media_id
    else:
        print(f"Error publishing: {response.text}")
        return None

def publish_story(container_id):
    """Publish the story"""
    url = f"https://graph.instagram.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    
    payload = {
        'creation_id': container_id,
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        media_id = response.json()['id']
        print(f"Story published: {media_id}")
        return media_id
    else:
        print(f"Error publishing story: {response.text}")
        return None

def post_individual_stories(songs):
    """Post individual videos as stories"""
    successful_stories = 0
    
    for i, song in enumerate(songs):
        video_url = song.get('video_url')
        if not video_url:
            continue
            
        print(f"Posting story {i+1}/{len(songs)}: {song['song_name']}")
        
        # Create story container
        container_id = create_story_container(video_url)
        if not container_id:
            continue
        
        # Wait for processing
        for attempt in range(10):  # Max 5 minutes per story
            time.sleep(30)
            status = check_container_status(container_id)
            
            if status == 'FINISHED':
                break
            elif status == 'ERROR':
                print(f"Story processing failed for {song['song_name']}")
                break
            elif attempt == 9:
                print(f"Story processing timeout for {song['song_name']}")
                break
        
        # Publish story
        if status == 'FINISHED':
            media_id = publish_story(container_id)
            if media_id:
                successful_stories += 1
                print(f"✅ Posted story for {song['song_name']}")
            
        # Rate limiting between stories
        time.sleep(60)
    
    return successful_stories

def main():
    # Get today's songs for caption
    songs = get_today_songs()
    if not songs:
        print("No songs found for today")
        return
    
    print(f"Processing {len(songs)} songs...")
    
    # Post individual stories first
    print("\n--- Posting Individual Stories ---")
    stories_posted = post_individual_stories(songs)
    print(f"Posted {stories_posted}/{len(songs)} individual stories")
    
    # Post stitched reel
    print("\n--- Posting Stitched Reel ---")
    
    # Get stitched video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}")
    
    # Create caption
    caption = create_caption(songs)
    print(f"Caption: {caption[:100]}...")
    
    # Create reel container
    container_id = create_reel_container(video_url, caption)
    if not container_id:
        print("❌ Failed to create reel container")
        return
    
    # Wait for processing
    print("Waiting for video processing...")
    for attempt in range(20):  # Max 10 minutes
        time.sleep(30)
        status = check_container_status(container_id)
        
        if status == 'FINISHED':
            print("Video processing complete")
            break
        elif status == 'ERROR':
            print("Video processing failed")
            return
        elif attempt == 19:
            print("Processing timeout")
            return
    
    # Publish reel
    media_id = publish_reel(container_id)
    if media_id:
        print(f"✅ Successfully posted Instagram reel: {media_id}")
    else:
        print("❌ Failed to post reel")
    
    print(f"\n🎉 Summary: {stories_posted} stories + 1 reel posted")

if __name__ == "__main__":
    main()
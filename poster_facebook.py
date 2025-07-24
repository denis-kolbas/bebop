import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
import time
import json

# Configuration
FACEBOOK_ACCESS_TOKEN = os.environ.get("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")
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
    filename = f"stitched_reel_90s_{today}.mp4"
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/videos/{today}/stitched/{filename}"

def create_description(songs):
    """Create description for the reel"""
    today_formatted = datetime.datetime.now().strftime("%B %d, %Y")
    
    if not songs:
        return f"Top new releases - {today_formatted}: #newmusic #music #playlist #trending"
    
    description = f"Top new releases - {today_formatted}:\n\n"
    for i, song in enumerate(songs, 1):
        description += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    description += "\n#newmusic #music #playlist #trending #reel #discover"
    return description

# REELS API - Following the official documentation
def initialize_reel_upload_session():
    """Step 1: Initialize an upload session for reels"""
    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/video_reels"
    
    payload = {
        'upload_phase': 'start',
        'access_token': FACEBOOK_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        video_id = result['video_id']
        upload_url = result['upload_url']
        print(f"Reel upload session created: {video_id}")
        return video_id, upload_url
    else:
        print(f"Error creating reel upload session: {response.text}")
        return None, None

def upload_reel_video(video_id, video_url):
    """Step 2: Upload the video for reels using hosted file method"""
    upload_url = f"https://rupload.facebook.com/video-upload/v23.0/{video_id}"
    
    headers = {
        'Authorization': f'OAuth {FACEBOOK_ACCESS_TOKEN}',
        'file_url': video_url
    }
    
    response = requests.post(upload_url, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print("Reel video upload successful")
        return True
    else:
        print(f"Reel upload error: {response.text}")
        return False

def get_reel_upload_status(video_id):
    """Get the upload status of the reel"""
    url = f"https://graph.facebook.com/v23.0/{video_id}"
    params = {
        'fields': 'status',
        'access_token': FACEBOOK_ACCESS_TOKEN
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        status_data = response.json().get('status', {})
        video_status = status_data.get('video_status', '')
        uploading_phase = status_data.get('uploading_phase', {}).get('status', '')
        processing_phase = status_data.get('processing_phase', {}).get('status', '')
        print(f"Video Status: {video_status}, Upload: {uploading_phase}, Processing: {processing_phase}")
        return video_status, uploading_phase, processing_phase
    else:
        print(f"Error checking reel status: {response.text}")
        return None, None, None

def publish_reel(video_id, description):
    """Step 3: Publish the reel"""
    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/video_reels"
    
    payload = {
        'access_token': FACEBOOK_ACCESS_TOKEN,
        'video_id': video_id,
        'upload_phase': 'finish',
        'video_state': 'PUBLISHED',
        'description': description
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Reel published successfully: {result}")
        return result
    else:
        print(f"Error publishing reel: {response.text}")
        return None

# STORIES API - Following the official documentation
def initialize_story_upload_session():
    """Step 1: Initialize an upload session for stories"""
    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/video_stories"
    
    payload = {
        'upload_phase': 'start',
        'access_token': FACEBOOK_ACCESS_TOKEN
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        video_id = result['video_id']
        upload_url = result['upload_url']
        print(f"Story upload session created: {video_id}")
        return video_id, upload_url
    else:
        print(f"Error creating story upload session: {response.text}")
        return None, None

def upload_story_video(video_id, video_url):
    """Step 2: Upload the video for stories using hosted file method"""
    upload_url = f"https://rupload.facebook.com/video-upload/v23.0/{video_id}"
    
    headers = {
        'Authorization': f'OAuth {FACEBOOK_ACCESS_TOKEN}',
        'file_url': video_url
    }
    
    response = requests.post(upload_url, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print("Story video upload successful")
        return True
    else:
        print(f"Story upload error: {response.text}")
        return False

def get_story_upload_status(video_id):
    """Get the upload status of the story"""
    url = f"https://graph.facebook.com/v23.0/{video_id}"
    params = {
        'fields': 'status',
        'access_token': FACEBOOK_ACCESS_TOKEN
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        status_data = response.json().get('status', {})
        video_status = status_data.get('video_status', '')
        uploading_phase = status_data.get('uploading_phase', {}).get('status', '')
        processing_phase = status_data.get('processing_phase', {}).get('status', '')
        print(f"Story Status: {video_status}, Upload: {uploading_phase}, Processing: {processing_phase}")
        return video_status, uploading_phase, processing_phase
    else:
        print(f"Error checking story status: {response.text}")
        return None, None, None

def publish_story(video_id):
    """Step 3: Publish the story"""
    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/video_stories"
    
    payload = {
        'access_token': FACEBOOK_ACCESS_TOKEN,
        'video_id': video_id,
        'upload_phase': 'finish'
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        result = response.json()
        post_id = result.get('post_id')
        print(f"Story published: {post_id}")
        return post_id
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
            
        print(f"Posting story {i+1}/{len(songs)}: {song['song_name']}", flush=True)
        
        # Step 1: Initialize story upload session
        video_id, upload_url = initialize_story_upload_session()
        if not video_id:
            continue
        
        # Step 2: Upload story video
        if not upload_story_video(video_id, video_url):
            continue
        
        # Wait for processing (2 minutes max for stories)
        processing_complete = False
        for attempt in range(4):  # 2 minutes total
            time.sleep(30)
            video_status, uploading_phase, processing_phase = get_story_upload_status(video_id)
            
            if video_status == 'ready' or (uploading_phase == 'complete' and processing_phase == 'complete'):
                processing_complete = True
                break
            elif video_status == 'error':
                print(f"Story processing failed for {song['song_name']}")
                break
        
        # Try to publish regardless of processing status after 2 minutes
        if processing_complete:
            print(f"Processing complete for {song['song_name']}")
        else:
            print(f"Processing still pending for {song['song_name']}, attempting to publish anyway...")
            
        # Step 3: Publish story
        post_id = publish_story(video_id)
        if post_id:
            successful_stories += 1
            print(f"✅ Posted story for {song['song_name']}")
        else:
            print(f"❌ Failed to post story for {song['song_name']}")
            
        # Rate limiting between stories
        time.sleep(60)
    
    return successful_stories

def main():
    # Check required environment variables
    if not FACEBOOK_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
        print("Error: Missing FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID")
        return
    
    print(f"Page ID: {FACEBOOK_PAGE_ID}", flush=True)
    print(f"Token: {'Set' if FACEBOOK_ACCESS_TOKEN else 'Not set'}", flush=True)
    
    # Get today's songs for description
    songs = get_today_songs()
    if not songs:
        print("No songs found for today", flush=True)
        return
    
    print(f"Processing {len(songs)} songs...", flush=True)
    
    # Post stitched reel first
    print("\n--- Posting Stitched Reel ---", flush=True)
    
    # Get stitched video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}", flush=True)
    
    # Create description
    description = create_description(songs)
    print(f"Description: {description[:100]}...", flush=True)
    
    # Step 1: Initialize reel upload session
    video_id, upload_url = initialize_reel_upload_session()
    if not video_id:
        print("❌ Failed to create reel upload session")
        return
    
    # Step 2: Upload reel video
    if not upload_reel_video(video_id, video_url):
        print("❌ Failed to upload reel video")
        return
    
    # Wait for processing (5 minutes max)
    processing_complete = False
    for attempt in range(10):  # 5 minutes total
        time.sleep(30)
        video_status, uploading_phase, processing_phase = get_reel_upload_status(video_id)
        
        if video_status == 'ready' or (uploading_phase == 'complete' and processing_phase == 'complete'):
            processing_complete = True
            print("Reel processing complete")
            break
        elif video_status == 'error':
            print("Reel processing failed")
            return
    
    # Try to publish regardless of processing status after 5 minutes
    if not processing_complete:
        print("Processing still pending after 5 minutes, attempting to publish anyway...")
    
    # Step 3: Publish reel
    result = publish_reel(video_id, description)
    if result:
        print(f"✅ Successfully posted Facebook reel")
    else:
        print("❌ Failed to post reel")
    
    # Post individual stories after reel
    print("\n--- Posting Individual Stories ---")
    stories_posted = post_individual_stories(songs)
    print(f"Posted {stories_posted}/{len(songs)} individual stories")
    
    print(f"\n🎉 Summary: {stories_posted} stories + 1 reel posted")

if __name__ == "__main__":
    main()

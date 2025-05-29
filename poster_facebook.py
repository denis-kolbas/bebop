import os
import json
import requests
import time
from datetime import datetime
from google.cloud import storage
from google.oauth2 import service_account
import gspread
from gspread_dataframe import get_as_dataframe

# Configuration
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGE_ID = os.environ.get('FACEBOOK_PAGE_ID')
GCP_SA_KEY = json.loads(os.environ.get('GCP_SA_KEY'))
GCS_BUCKET_NAME = "bebop_data"
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')

# Initialize Google Cloud Storage
storage_credentials = service_account.Credentials.from_service_account_info(GCP_SA_KEY)
storage_client = storage.Client(credentials=storage_credentials)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# Initialize Google Sheets
sheets_credentials = service_account.Credentials.from_service_account_info(
    GCP_SA_KEY,
    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
)
gc = gspread.authorize(sheets_credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

def get_todays_songs():
    """Fetch today's songs from Google Sheets"""
    df = get_as_dataframe(sheet, parse_dates=True, date_parser=lambda x: datetime.strptime(x, '%Y-%m-%d').date() if x else None)
    
    today = datetime.now().date()
    todays_songs = df[(df['selected_date'] == today) & (df['create_video'] == True)]
    
    return todays_songs.to_dict('records')

def download_video_from_gcs(video_path):
    """Download video from GCS to local temp file"""
    temp_file = f"/tmp/temp_video_{int(time.time())}.mp4"
    blob = bucket.blob(video_path)
    blob.download_to_filename(temp_file)
    return temp_file

def initialize_upload_session(page_id, access_token):
    """Step 1: Initialize upload session"""
    url = f"https://graph.facebook.com/v23.0/{page_id}/video_reels"
    data = {
        "upload_phase": "start",
        "access_token": access_token
    }
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()

def upload_video_file(video_id, file_path, access_token):
    """Step 2: Upload video file"""
    url = f"https://rupload.facebook.com/video-upload/v23.0/{video_id}"
    
    file_size = os.path.getsize(file_path)
    
    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(file_size)
    }
    
    with open(file_path, 'rb') as f:
        response = requests.post(url, headers=headers, data=f)
    
    response.raise_for_status()
    return response.json()

def check_upload_status(video_id, access_token):
    """Check video upload and processing status"""
    url = f"https://graph.facebook.com/v23.0/{video_id}"
    params = {
        "fields": "status",
        "access_token": access_token
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def wait_for_processing(video_id, access_token, max_wait=300):
    """Wait for video to finish processing"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = check_upload_status(video_id, access_token)
        video_status = status.get("status", {}).get("video_status", "")
        
        if video_status == "ready":
            return True
        elif video_status == "error":
            error = status.get("status", {}).get("processing_phase", {}).get("error", {})
            raise Exception(f"Video processing error: {error.get('message', 'Unknown error')}")
        
        print(f"Video status: {video_status}. Waiting...")
        time.sleep(5)
    
    return False

def publish_reel(page_id, video_id, description, access_token):
    """Step 3: Publish the reel"""
    url = f"https://graph.facebook.com/v23.0/{page_id}/video_reels"
    params = {
        "access_token": access_token,
        "video_id": video_id,
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": description
    }
    
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()

def create_reel_description(songs):
    """Create description with song list"""
    description = "🎵 Today's Music Discoveries! 🎵\n\n"
    
    for i, song in enumerate(songs, 1):
        description += f"{i}. {song['artist']} - {song['title']}\n"
    
    description += "\n#NewMusic #MusicDiscovery #DailyMusic"
    return description

def post_facebook_reel(video_url=None):
    """Main function to post reel to Facebook"""
    try:
        if video_url:
            # Test mode with hardcoded URL
            print(f"Using hardcoded video URL: {video_url}")
            temp_video_path = download_video_from_gcs(video_url)
            description = "Test reel upload #NewMusic #MusicDiscovery"
        else:
            # Production mode
            today = datetime.now().strftime('%Y-%m-%d')
            video_path = f"videos/{today}/stitched/stitched_reel_{today}.mp4"
            
            print(f"Downloading stitched video from GCS: {video_path}")
            temp_video_path = download_video_from_gcs(video_path)
            
            # Get song list for description
            songs = get_todays_songs()
            description = create_reel_description(songs)
        
        print("Step 1: Initializing upload session...")
        init_response = initialize_upload_session(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
        video_id = init_response['video_id']
        print(f"Video ID: {video_id}")
        
        print("Step 2: Uploading video...")
        upload_response = upload_video_file(video_id, temp_video_path, FACEBOOK_ACCESS_TOKEN)
        print(f"Upload response: {upload_response}")
        
        print("Waiting for processing...")
        if not wait_for_processing(video_id, FACEBOOK_ACCESS_TOKEN):
            raise Exception("Video processing timed out")
        
        print("Step 3: Publishing reel...")
        publish_response = publish_reel(FACEBOOK_PAGE_ID, video_id, description, FACEBOOK_ACCESS_TOKEN)
        print(f"Publish response: {publish_response}")
        
        print("✅ Facebook Reel posted successfully!")
        
    except Exception as e:
        print(f"❌ Error posting to Facebook: {str(e)}")
        raise
    finally:
        # Clean up temp file
        if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
            os.remove(temp_video_path)

if __name__ == "__main__":
    # For testing, you can hardcode a video URL
    # Example: post_facebook_reel("videos/2024-01-15/stitched/stitched_reel_2024-01-15.mp4")
    
    # For production, leave empty to use today's stitched video
    post_facebook_reel("https://storage.googleapis.com/bebop_data/videos/2025-05-28/stitched/stitched_reel_2025-05-28.mp4")
import os
import json
import requests
import time
from datetime import datetime
from google.cloud import storage
from google.oauth2 import service_account
import gspread

# Configuration
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGE_ID = os.environ.get('FACEBOOK_PAGE_ID')
GCP_SA_KEY = os.environ.get('GCP_SA_KEY')
GCS_BUCKET_NAME = "bebop_data"
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')

def init_gcp():
    """Initialize GCP credentials"""
    with open('gcp_credentials.json', 'w') as f:
        f.write(GCP_SA_KEY)
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
    today = datetime.now().strftime("%Y-%m-%d")
    
    today_songs = [
        song for song in songs 
        if song.get('selected_date') == today and song.get('create_video') == True
    ]
    
    print(f"Found {len(today_songs)} songs for today")
    return today_songs

def get_stitched_video_url():
    """Get today's stitched video URL"""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"stitched_reel_{today}.mp4"
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/videos/{today}/stitched/{filename}"

def create_caption(songs):
    """Create caption for the reel"""
    if not songs:
        return "🎵 Today's Music Discoveries! 🎵\n\n#NewMusic #MusicDiscovery #DailyMusic"
    
    caption = "🎵 Today's Music Discoveries! 🎵\n\n"
    for i, song in enumerate(songs, 1):
        caption += f"{i}. {song.get('artist', '')} - {song.get('song_name', '')}\n"
    
    caption += "\n#NewMusic #MusicDiscovery #DailyMusic #FacebookReels"
    return caption

def download_video_from_url(video_url):
    """Download video from URL to local temp file"""
    temp_file = f"/tmp/temp_video_{int(time.time())}.mp4"
    response = requests.get(video_url, stream=True)
    response.raise_for_status()
    
    with open(temp_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
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

def main():
    """Main function to post reel to Facebook"""
    try:
        # Get today's songs for caption
        songs = get_today_songs()
        if not songs:
            print("No songs found for today")
            return
        
        print(f"Processing {len(songs)} songs...")
        
        # Get stitched video URL
        video_url = get_stitched_video_url()
        print(f"Using video: {video_url}")
        
        # Download video
        print("Downloading video...")
        temp_video_path = download_video_from_url(video_url)
        
        # Create caption
        caption = create_caption(songs)
        print(f"Caption: {caption[:100]}...")
        
        # Step 1: Initialize upload session
        print("Step 1: Initializing upload session...")
        init_response = initialize_upload_session(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
        video_id = init_response['video_id']
        print(f"Video ID: {video_id}")
        
        # Step 2: Upload video
        print("Step 2: Uploading video...")
        upload_response = upload_video_file(video_id, temp_video_path, FACEBOOK_ACCESS_TOKEN)
        print(f"Upload response: {upload_response}")
        
        # Wait for processing
        print("Waiting for processing...")
        if not wait_for_processing(video_id, FACEBOOK_ACCESS_TOKEN):
            raise Exception("Video processing timed out")
        
        # Step 3: Publish reel
        print("Step 3: Publishing reel...")
        publish_response = publish_reel(FACEBOOK_PAGE_ID, video_id, caption, FACEBOOK_ACCESS_TOKEN)
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
    import sys
    
    if len(sys.argv) > 1:
        # Test mode with provided video URL
        test_url = sys.argv[1]
        print(f"TEST MODE: Using video URL: {test_url}")
        
        # Download and post the test video
        try:
            temp_video_path = download_video_from_url(test_url)
            
            # Initialize upload
            init_response = initialize_upload_session(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
            video_id = init_response['video_id']
            
            # Upload
            upload_response = upload_video_file(video_id, temp_video_path, FACEBOOK_ACCESS_TOKEN)
            
            # Wait for processing
            if wait_for_processing(video_id, FACEBOOK_ACCESS_TOKEN):
                # Publish with test caption
                publish_reel(FACEBOOK_PAGE_ID, video_id, "Test video upload #TestMode", FACEBOOK_ACCESS_TOKEN)
                print("✅ Test video posted successfully!")
            
            os.remove(temp_video_path)
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
    else:
        # Production mode
        main()
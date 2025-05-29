import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
from google.cloud import storage
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

def create_song_list_caption(songs):
    """Create caption with song list"""
    today = datetime.datetime.now().strftime("%B %d, %Y")
    caption = f"🎵 Daily Music Discovery - {today}\n\n"
    
    for i, song in enumerate(songs, 1):
        artist = song.get('artist', 'Unknown Artist')
        title = song.get('title', 'Unknown Title')
        caption += f"{i}. {artist} - {title}\n"
    
    caption += "\n#NewMusic #MusicDiscovery #DailyPicks"
    return caption

def get_video_url_from_gcs(version="90s"):
    """Get video URL from GCS"""
    try:
        init_gcp()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Choose video version - 90s is good for Facebook Reels
        if version == "60s":
            filename = f"stitched_reel_60s_{today}.mp4"
        elif version == "90s":
            filename = f"stitched_reel_90s_{today}.mp4"
        else:
            filename = f"stitched_reel_full_{today}.mp4"
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"videos/{today}/stitched/{filename}")
        
        if blob.exists():
            # Make sure it's public
            blob.make_public()
            return blob.public_url
        else:
            print(f"Video file not found: {filename}")
            return None
            
    except Exception as e:
        print(f"Error getting video URL: {e}")
        return None

def post_to_facebook_reel(video_url, caption):
    """Post video as Facebook Reel"""
    try:
        # Step 1: Create video container
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_reels"
        
        payload = {
            'upload_phase': 'start',
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        
        response = requests.post(url, data=payload)
        print(f"Reel response status: {response.status_code}")
        print(f"Reel response: {response.text}")
        response.raise_for_status()
        
        video_id = response.json().get('video_id')
        upload_url = response.json().get('upload_url')
        
        if not video_id or not upload_url:
            print("Failed to get video container")
            return False
        
        print(f"Created video container: {video_id}")
        
        # Step 2: Upload video to the upload URL
        video_response = requests.get(video_url)
        video_response.raise_for_status()
        
        upload_response = requests.post(
            upload_url,
            files={'file': ('video.mp4', video_response.content, 'video/mp4')}
        )
        upload_response.raise_for_status()
        
        print("Video uploaded successfully")
        
        # Step 3: Publish the reel
        publish_url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_reels"
        
        publish_payload = {
            'video_id': video_id,
            'upload_phase': 'finish',
            'video_state': 'PUBLISHED',
            'description': caption,
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        
        publish_response = requests.post(publish_url, data=publish_payload)
        publish_response.raise_for_status()
        
        result = publish_response.json()
        print(f"✅ Facebook Reel published successfully: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error posting Facebook Reel: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return False

def post_to_facebook_feed(video_url, caption):
    """Post video to Facebook feed as regular post"""
    try:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/videos"
        
        # Download video content
        video_response = requests.get(video_url)
        print(f"Video download status: {video_response.status_code}")
        video_response.raise_for_status()
        
        # Upload video
        files = {
            'file': ('video.mp4', video_response.content, 'video/mp4')
        }
        
        data = {
            'description': caption,
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        
        response = requests.post(url, files=files, data=data)
        print(f"Feed response status: {response.status_code}")
        print(f"Feed response: {response.text}")
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Facebook feed post published successfully: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error posting to Facebook feed: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return False

def main():
    # First, let's test if we have the right token type
    print("Testing token and getting page info...")
    
    # Test 1: Get page info
    try:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}"
        params = {'access_token': FACEBOOK_ACCESS_TOKEN}
        response = requests.get(url, params=params)
        print(f"Page info status: {response.status_code}")
        print(f"Page info: {response.text}")
    except Exception as e:
        print(f"Page info error: {e}")
    
    # Test 2: Try simple text post first
    print("\nTesting simple text post...")
    try:
        url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
        data = {
            'message': '🎵 Test post from API - Daily Music Discovery',
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        response = requests.post(url, data=data)
        print(f"Text post status: {response.status_code}")
        print(f"Text post response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Text posting works! Token is valid.")
        
    except Exception as e:
        print(f"Text post error: {e}")
    
    # Test 3: Only try video if text post works
    # Hardcoded video URL for testing
    test_video_url = "https://storage.googleapis.com/your-bucket/test-video.mp4"
    
    # Test caption
    caption = "🎵 Daily Music Discovery Test\n\n1. Test Artist - Test Song\n\n#NewMusic #MusicDiscovery #DailyPicks"
    
    print("\nTrying video post...")
    post_to_facebook_feed(test_video_url, caption)

if __name__ == "__main__":
    main()
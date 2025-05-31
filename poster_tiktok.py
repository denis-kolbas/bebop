import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
import tempfile
import hashlib

# Configuration
UPLOAD_POST_API_KEY = os.environ.get("UPLOAD_POST_API_KEY")
UPLOAD_POST_USER = "wkly_rotation"  # TikTok account name
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

def download_video_file(video_url):
    """Download video from URL to local temporary file"""
    try:
        print(f"Downloading video from: {video_url}", flush=True)
        
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        
        # Download file in chunks
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        
        temp_file.close()
        
        file_size = os.path.getsize(temp_file.name)
        print(f"Downloaded video: {file_size} bytes to {temp_file.name}", flush=True)
        
        return temp_file.name
        
    except Exception as e:
        print(f"Error downloading video: {e}", flush=True)
        return None

def should_post_today():
    """Check if we should post to TikTok today (every 3 days, max 10/month)"""
    today = datetime.datetime.now()
    
    # Post on days: 1, 4, 7, 10, 13, 16, 19, 22, 25, 28 (max 10 per month)
    post_days = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28]
    
    should_post = today.day in post_days
    
    print(f"Today is day {today.day} of the month", flush=True)
    print(f"TikTok post scheduled: {'Yes' if should_post else 'No'}", flush=True)
    
    if not should_post:
        next_post_day = None
        for day in post_days:
            if day > today.day:
                next_post_day = day
                break
        
        if next_post_day:
            print(f"Next TikTok post: Day {next_post_day}", flush=True)
        else:
            print("Next TikTok post: Day 1 of next month", flush=True)
    
    return should_post

def create_tiktok_title(songs):
    """Create title for TikTok post"""
    today_formatted = datetime.datetime.now().strftime("%B %d, %Y")
    
    if not songs:
        return f"Top new releases - {today_formatted} #newmusic #musicdiscovery #fyp"
    
    title = f"Top new releases - {today_formatted}:\n\n"
    
    # Add songs list
    for i, song in enumerate(songs, 1):
        title += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    title += "\n#newmusic #musicdiscovery #fyp #viral #trending"
    return title

def upload_to_tiktok(video_path, title):
    """Upload video to TikTok via Upload-Post API"""
    
    url = "https://api.upload-post.com/api/upload"
    
    headers = {
        'Authorization': f'Apikey {UPLOAD_POST_API_KEY}'
    }
    
    # Prepare files and data
    files = {
        'video': ('video.mp4', open(video_path, 'rb'), 'video/mp4')
    }
    
    data = {
        'title': title,
        'user': UPLOAD_POST_USER,
        'platform[]': 'tiktok',
        'privacy_level': 'PUBLIC_TO_EVERYONE',
        'disable_duet': 'false',
        'disable_comment': 'false',
        'disable_stitch': 'false',
        'cover_timestamp': '1000'
    }
    
    try:
        print(f"Uploading to TikTok with title: {title[:100]}...", flush=True)
        
        response = requests.post(url, headers=headers, files=files, data=data)
        
        # Close file
        files['video'][1].close()
        
        print(f"Upload response status: {response.status_code}", flush=True)
        print(f"Upload response: {response.text}", flush=True)
        
        if response.status_code == 200:
            return True
        else:
            print(f"Upload failed: {response.status_code} - {response.text}", flush=True)
            return False
            
    except Exception as e:
        print(f"Error uploading to TikTok: {e}", flush=True)
        # Make sure to close file in case of error
        try:
            files['video'][1].close()
        except:
            pass
        return False

def cleanup_temp_file(file_path):
    """Remove temporary file"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            print(f"Cleaned up temporary file: {file_path}", flush=True)
    except Exception as e:
        print(f"Error cleaning up file {file_path}: {e}", flush=True)

def main():
    # Check if we should post today
    if not should_post_today():
        print("🚫 Not a TikTok posting day - exiting", flush=True)
        return
    
    # Check required environment variables
    if not UPLOAD_POST_API_KEY or not UPLOAD_POST_USER:
        print("Error: Missing Upload-Post API key or user", flush=True)
        return
    
    print(f"Configured for user: {UPLOAD_POST_USER}", flush=True)
    
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs found for today", flush=True)
        return
    
    print(f"Processing {len(songs)} songs...", flush=True)
    
    # Get video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}", flush=True)
    
    # Download video to local file
    video_path = download_video_file(video_url)
    if not video_path:
        print("❌ Failed to download video", flush=True)
        return
    
    try:
        # Create title
        title = create_tiktok_title(songs)
        print(f"Title: {title[:100]}...", flush=True)
        
        # Upload to TikTok
        success = upload_to_tiktok(video_path, title)
        
        if success:
            print(f"✅ Successfully posted to TikTok", flush=True)
        else:
            print(f"❌ Failed to post to TikTok", flush=True)
            
    finally:
        # Always cleanup temp file
        cleanup_temp_file(video_path)
    
    print(f"\n🎉 Summary: TikTok posting completed", flush=True)

if __name__ == "__main__":
    main()
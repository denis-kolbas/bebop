import os
import datetime
import gspread
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests
import tempfile

# Configuration
SCOPES = ['https://www.googleapis.com/auth/youtube']
CLIENT_SECRETS_FILE = "/Users/denisk/Desktop/Projects/Bebop/random/client_secret_YOUR_CLIENT_ID_HERE.json"
SPREADSHEET_ID = "1_SwKCdCIqFlaA2g4aG7pfeXSZpm2if93gCkexpoZOzY"
GCS_BUCKET_NAME = "bebop_data"

def init_gcp():
    credentials_path = "/Users/denisk/Desktop/Larq/Bebop/larq-453712-1e4c65ef0e64.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

def authenticate_youtube():
    """Authenticate and return YouTube API service"""
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    youtube = build('youtube', 'v3', credentials=creds)
    return youtube

def fetch_songs_from_spreadsheet():
    """Fetch songs from Google Spreadsheet"""
    try:
        init_gcp()
        credentials = service_account.Credentials.from_service_account_file(
            '/Users/denisk/Desktop/Larq/Bebop/larq-453712-1e4c65ef0e64.json',
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

def download_video(video_url, temp_dir):
    """Download video from URL"""
    try:
        response = requests.get(video_url, timeout=60)
        response.raise_for_status()
        
        filename = os.path.join(temp_dir, "video.mp4")
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        return filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

def create_description(songs):
    """Create description for YouTube Short"""
    if not songs:
        return "Top new releases! #Shorts #NewMusic #Music"
    
    description = "Top new releases:\n\n"
    for i, song in enumerate(songs, 1):
        description += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    description += "\n#Shorts #NewMusic #Music #Playlist #Discover"
    return description

def upload_short(youtube, video_file, title, description):
    """Upload video as YouTube Short"""
    try:
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['music', 'newmusic', 'shorts', 'playlist'],
                'categoryId': '10'  # Music category
            },
            'status': {
                'privacyStatus': 'public'
            }
        }
        
        media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
        
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
        
        if 'id' in response:
            print(f"✅ Successfully uploaded Short: https://youtube.com/watch?v={response['id']}")
            return response['id']
        else:
            print(f"❌ Upload failed: {response}")
            return None
            
    except Exception as e:
        print(f"Error uploading video: {e}")
        return None

def main():
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs found for today")
        return
    
    # Get stitched video URL
    video_url = get_stitched_video_url()
    print(f"Downloading video: {video_url}")
    
    # Download video
    temp_dir = tempfile.mkdtemp()
    video_file = download_video(video_url, temp_dir)
    if not video_file:
        print("Failed to download video")
        return
    
    # Create title and description
    today = datetime.datetime.now().strftime("%B %d, %Y")
    title = f"🎵 New Music Picks - {today} #Shorts"
    description = create_description(songs)
    
    # Authenticate YouTube
    youtube = authenticate_youtube()
    
    # Upload Short
    video_id = upload_short(youtube, video_file, title, description)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    if video_id:
        print(f"🎉 Successfully posted YouTube Short!")
    else:
        print("❌ Failed to post YouTube Short")

if __name__ == "__main__":
    main()
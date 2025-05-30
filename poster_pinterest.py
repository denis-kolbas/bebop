import os
import requests
import datetime
import gspread
from google.oauth2 import service_account

# Configuration
MAKE_WEBHOOK_URL = "https://hook.eu2.make.com/z5rxxtma5cj6v469pq62ycxf0ihthqq2"
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
    """Get today's stitched video URL for Pinterest"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"stitched_reel_full_{today}.mp4"
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/videos/{today}/stitched/{filename}"

def create_pin_title(songs):
    """Create title for Pinterest pin"""
    today_formatted = datetime.datetime.now().strftime("%B %d, %Y")
    return f"New music releases - {today_formatted}"

def create_pin_description(songs):
    """Create description for Pinterest pin"""
    if not songs:
        return "#newmusic #musicdiscovery #playlist"
    
    description = ""
    for i, song in enumerate(songs, 1):
        description += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    description += "\n#newmusic #musicdiscovery #playlist #trending #newreleases"
    return description[:800]  # Pinterest description limit

def trigger_pinterest_posting(video_url, title, description):
    """Trigger Pinterest posting via Make.com webhook"""
    
    payload = {
        "video_url": video_url,
        "title": title,
        "description": description
    }
    
    try:
        print(f"Triggering Pinterest posting...", flush=True)
        print(f"Video URL: {video_url}", flush=True)
        print(f"Title: {title}", flush=True)
        print(f"Description: {description[:100]}...", flush=True)
        
        response = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            print("✅ Pinterest webhook triggered successfully", flush=True)
            return True
        else:
            print(f"❌ Pinterest webhook failed: {response.status_code} - {response.text}", flush=True)
            return False
            
    except Exception as e:
        print(f"❌ Pinterest webhook error: {e}", flush=True)
        return False

def main():
    print("=== PINTEREST TRIGGER SCRIPT ===", flush=True)
    
    # Check required environment variables
    if not SPREADSHEET_ID or not GCS_BUCKET_NAME:
        print("Error: Missing SPREADSHEET_ID or GCS_BUCKET_NAME", flush=True)
        return
    
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs found for today - creating generic Pinterest post", flush=True)
        songs = []  # Will create generic post
    
    # Get video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}", flush=True)
    
    # Create pin content
    title = create_pin_title(songs)
    description = create_pin_description(songs)
    
    # Trigger Pinterest posting
    success = trigger_pinterest_posting(video_url, title, description)
    
    if success:
        print(f"\n🎉 Pinterest posting triggered successfully!", flush=True)
    else:
        print(f"\n❌ Pinterest posting failed", flush=True)
    
    print(f"Summary: Pinterest webhook called for {len(songs)} songs", flush=True)

if __name__ == "__main__":
    main()
import os
import requests
import datetime
import gspread
from google.oauth2 import service_account
import time
import json

# Configuration
BLUESKY_USERNAME = os.environ.get("BLUESKY_USERNAME")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD")
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

def create_bluesky_session():
    """Create Bluesky session and return access token"""
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": BLUESKY_USERNAME, "password": BLUESKY_APP_PASSWORD},
    )
    resp.raise_for_status()
    session = resp.json()
    print(f"Bluesky session created for {BLUESKY_USERNAME}", flush=True)
    return session

def upload_video_blob(session, video_url):
    """Download video from URL and upload as blob to Bluesky"""
    print(f"Downloading video from: {video_url}", flush=True)
    
    # Download video
    video_resp = requests.get(video_url)
    video_resp.raise_for_status()
    video_bytes = video_resp.content
    
    print(f"Video size: {len(video_bytes)} bytes", flush=True)
    
    # Check size limit (50MB)
    if len(video_bytes) > 50000000:
        raise Exception(f"Video file too large. 50MB maximum, got: {len(video_bytes)} bytes")
    
    # Upload as blob
    blob_resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        headers={
            "Content-Type": "video/mp4",
            "Authorization": "Bearer " + session["accessJwt"],
        },
        data=video_bytes,
    )
    blob_resp.raise_for_status()
    blob = blob_resp.json()["blob"]
    print(f"Video uploaded as blob: {blob['ref']['$link']}", flush=True)
    return blob

def create_post_text(songs):
    """Create text for the post"""
    if not songs:
        return "Top new releases 🎵 #newmusic"
    
    text = "Top new releases:\n\n"
    for i, song in enumerate(songs, 1):
        text += f"{i}. {song['song_name']} - {song['artist']}\n"
    
    text += "\n#newmusic"
    return text[:300]  # Keep it reasonable length

def create_bluesky_post(session, text, video_blob):
    """Create Bluesky post with video"""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    
    post = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "embed": {
            "$type": "app.bsky.embed.video",
            "video": video_blob,
            "alt": "Music discovery video with today's new releases"
        }
    }
    
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + session["accessJwt"]},
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": post,
        },
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"Bluesky post created: {result['uri']}", flush=True)
    return result

def main():
    print("=== BLUESKY POSTER DEBUG ===", flush=True)
    print(f"BLUESKY_USERNAME: {BLUESKY_USERNAME}", flush=True)
    print(f"BLUESKY_APP_PASSWORD: {'***' if BLUESKY_APP_PASSWORD else 'MISSING'}", flush=True)
    print(f"SPREADSHEET_ID: {'***' if SPREADSHEET_ID else 'MISSING'}", flush=True)
    print(f"GCS_BUCKET_NAME: {'***' if GCS_BUCKET_NAME else 'MISSING'}", flush=True)
    
    # Check required environment variables
    if not BLUESKY_USERNAME or not BLUESKY_APP_PASSWORD:
        print("Error: Missing BLUESKY_USERNAME or BLUESKY_APP_PASSWORD", flush=True)
        return
    
    print(f"Bluesky Username: {BLUESKY_USERNAME}", flush=True)
    print(f"App Password: {'Set' if BLUESKY_APP_PASSWORD else 'Not set'}", flush=True)
    
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs found for today", flush=True)
        return
    
    print(f"Processing {len(songs)} songs...", flush=True)
    
    # Create Bluesky session
    try:
        session = create_bluesky_session()
    except Exception as e:
        print(f"Failed to create Bluesky session: {e}", flush=True)
        return
    
    # Post stitched video to Bluesky
    print("\n--- Posting Stitched Video to Bluesky ---", flush=True)
    
    # Get stitched video URL
    video_url = get_stitched_video_url()
    print(f"Using video: {video_url}", flush=True)
    
    # Create post text
    text = create_post_text(songs)
    print(f"Text: {text}", flush=True)
    
    try:
        # Upload video as blob
        video_blob = upload_video_blob(session, video_url)
        
        # Create post
        result = create_bluesky_post(session, text, video_blob)
        
        print(f"✅ Successfully posted to Bluesky: {result['uri']}", flush=True)
        
    except Exception as e:
        print(f"❌ Failed to post to Bluesky: {e}", flush=True)
    
    print(f"\n🎉 Summary: Stitched video posted to Bluesky", flush=True)

if __name__ == "__main__":
    main()
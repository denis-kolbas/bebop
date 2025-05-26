import os
import requests
import tempfile
import datetime
import gspread
from google.oauth2 import service_account
from google.cloud import storage
from moviepy.editor import VideoFileClip, concatenate_videoclips
import shutil
import json

# Configuration
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

def download_video(video_url, temp_dir):
    """Download video from URL"""
    try:
        response = requests.get(video_url, timeout=30)
        response.raise_for_status()
        
        filename = os.path.join(temp_dir, f"video_{hash(video_url)}.mp4")
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        return filename
    except Exception as e:
        print(f"Error downloading video {video_url}: {e}")
        return None

def stitch_videos(video_files, output_path):
    """Stitch videos together"""
    if not video_files:
        return None
    
    try:
        clips = []
        for video_file in video_files:
            clip = VideoFileClip(video_file)
            clips.append(clip)
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Write to output file
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac'
        )
        
        # Clean up
        for clip in clips:
            clip.close()
        final_clip.close()
        
        return output_path
        
    except Exception as e:
        print(f"Error stitching videos: {e}")
        return None

def upload_to_gcs(local_path, gcs_path):
    """Upload stitched video to GCS and make public"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        
        public_url = blob.public_url
        print(f"Uploaded to GCS: {gcs_path}")
        print(f"Public URL: {public_url}")
        return public_url
        
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None

def main():
    init_gcp()
    
    # Get today's songs
    songs = get_today_songs()
    if not songs:
        print("No songs to process today")
        return
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Download videos
        video_files = []
        for song in songs:
            video_url = song.get('video_url')
            if video_url:
                video_file = download_video(video_url, temp_dir)
                if video_file:
                    video_files.append(video_file)
        
        if not video_files:
            print("No videos downloaded")
            return
        
        # Stitch videos
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        output_filename = f"stitched_reel_{today}.mp4"
        output_path = os.path.join(temp_dir, output_filename)
        
        stitched_video = stitch_videos(video_files, output_path)
        if not stitched_video:
            print("Failed to stitch videos")
            return
        
        # Upload to GCS
        gcs_path = f"videos/{today}/stitched/{output_filename}"
        public_url = upload_to_gcs(stitched_video, gcs_path)
        
        if public_url:
            print(f"✅ Successfully created stitched video: {public_url}")
        else:
            print("❌ Failed to upload stitched video")
        
    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
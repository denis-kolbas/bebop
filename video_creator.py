import os
from google.cloud import storage
from moviepy.editor import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, TextClip, AudioFileClip
import requests
from io import BytesIO
from PIL import Image, ImageResampling
import json
import datetime
import numpy as np

def init_gcp():
    service_account_json = os.environ.get('GCP_SA_KEY')
    with open('gcp_credentials.json', 'w') as f:
        f.write(service_account_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def get_latest_json(bucket_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix='apple_music'))
    json_blobs = [b for b in blobs if b.name.endswith('.json')]
    if not json_blobs:
        raise Exception("No JSON files found")
    latest = max(json_blobs, key=lambda x: x.updated)
    print(f"Loading latest JSON: {latest.name}")
    return json.loads(latest.download_as_string())

def parse_views(view_str):
    try:
        if 'M' in view_str:
            return int(float(view_str.replace('M', '')) * 1000000)
        if 'K' in view_str:
            return int(float(view_str.replace('K', '')) * 1000)
        return int(view_str)
    except:
        return 0

def download_preview(url):
    response = requests.get(url)
    return AudioFileClip(BytesIO(response.content))

def create_video(song_data):
    width, height = 1080, 1920
    duration = 15
    
    # Create background
    background = ColorClip((width, height), color=(0,0,0), duration=duration)
    
    # Process artwork
    response = requests.get(song_data['artwork_url'])
    img = Image.open(BytesIO(response.content))
    img = img.convert('RGB')
    artwork_array = np.array(img)
    
    # Create artwork clip
    artwork_clip = ImageClip(artwork_array)
    artwork_clip = artwork_clip.set_duration(duration)
    artwork_size = int(width * 0.8)
    artwork_clip = artwork_clip.resize(width=artwork_size, resample=ImageResampling.LANCZOS)
    artwork_clip = artwork_clip.set_position(('center', height//3))
    
    # Create text clips
    text_clips = []
    texts = [
        (song_data['song_name'], 70),
        (song_data['artist'], 50),
        (song_data['album'], 40)
    ]
    
    for i, (text, size) in enumerate(texts):
        clip = TextClip(text, fontsize=size, color='white', font='Arial')
        clip = clip.set_duration(duration)
        y_pos = height - 300 + (i * 80)
        clip = clip.set_position(('center', y_pos))
        text_clips.append(clip)
    
    # Create audio
    try:
        audio = download_preview(song_data['preview_url'])
        audio = audio.subclip(0, duration)
    except:
        print(f"Error processing audio for {song_data['song_name']}")
        audio = None
    
    # Compose video
    final = CompositeVideoClip([background, artwork_clip] + text_clips)
    if audio:
        final = final.set_audio(audio)
    
    return final

def upload_video(video_path, bucket_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob_name = f'apple_music/videos/{os.path.basename(video_path)}'
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(video_path)
    print(f"Uploaded video: {blob_name}")

def main():
    init_gcp()
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    songs = get_latest_json(bucket_name)
    
    # Sort by views and get top 10
    top_songs = sorted(songs, key=lambda x: parse_views(x['views']), reverse=True)[:3]
    
    for i, song in enumerate(top_songs):
        try:
            print(f"Processing video {i+1}/3: {song['song_name']}")
            video = create_video(song)
            filename = f"song_{i}_{song['song_name'].replace(' ', '_')}.mp4"
            video.write_videofile(filename, fps=24)
            upload_video(filename, bucket_name)
            os.remove(filename)
        except Exception as e:
            print(f"Error processing {song['song_name']}: {e}")

if __name__ == "__main__":
    main()

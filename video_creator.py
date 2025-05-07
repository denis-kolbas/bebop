# video_creator.py
import os
from google.cloud import storage
from moviepy.editor import VideoFileClip, ImageClip, ColorClip, CompositeVideoClip, TextClip, AudioFileClip
import requests
from io import BytesIO
import json
import datetime

def init_gcp():
   service_account_json = os.environ.get('GCP_SA_KEY')
   with open('gcp_credentials.json', 'w') as f:
       f.write(service_account_json)
   os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def get_latest_json(bucket_name, folder):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    # Look for json files specifically
    blobs = list(bucket.list_blobs(prefix=f"{folder}/songs"))
    if not blobs:
        raise Exception("No JSON files found")
    latest = max(blobs, key=lambda x: x.updated)
    return json.loads(latest.download_as_string())

def create_video(song_data):
   width, height = 1080, 1920
   duration = 15
   
   background = ColorClip((width, height), color=(0,0,0), duration=duration)
   
   # Download artwork
   response = requests.get(song_data['artwork_url'])
   img = Image.open(BytesIO(response.content))
   artwork_clip = ImageClip(img).set_duration(duration)
   artwork_clip = artwork_clip.resize(width=width*0.8)
   artwork_clip = artwork_clip.set_position(('center', 'center'))
   
   # Create text
   song_text = TextClip(song_data['song_name'], fontsize=70, color='white')
   artist_text = TextClip(song_data['artist'], fontsize=50, color='white')
   album_text = TextClip(song_data['album'], fontsize=40, color='white')
   
   # Position text at bottom with spacing
   texts = [song_text, artist_text, album_text]
   text_clips = []
   for i, text in enumerate(texts):
       text = text.set_duration(duration)
       text = text.set_position(('center', height - 200 + i*60))
       text_clips.append(text)
   
   # Add audio preview
   audio = AudioFileClip(song_data['preview_url']).subclip(0, 15)
   
   final = CompositeVideoClip([background, artwork_clip] + text_clips)
   final = final.set_audio(audio)
   
   return final

def upload_video(video_path, bucket_name, folder):
   storage_client = storage.Client()
   bucket = storage_client.bucket(bucket_name)
   blob = bucket.blob(f"{folder}/videos/{os.path.basename(video_path)}")
   blob.upload_from_filename(video_path)

def main():
   init_gcp()
   bucket_name = os.environ.get('GCS_BUCKET_NAME')
   folder = 'videos'
   
   songs = get_latest_json(bucket_name, folder)
   top_songs = sorted(songs, key=lambda x: int(x['views'].replace('M','000000')), reverse=True)[:10]
   
   for i, song in enumerate(top_songs):
       try:
           video = create_video(song)
           filename = f"song_{i}_{song['song_name'].replace(' ','_')}.mp4"
           video.write_videofile(filename)
           upload_video(filename, bucket_name, folder)
           os.remove(filename)  # Cleanup local file
       except Exception as e:
           print(f"Error processing {song['song_name']}: {e}")

if __name__ == "__main__":
   main()

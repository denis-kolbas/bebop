# video_creator.py
import os
from google.cloud import storage
from moviepy.editor import *
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
   blobs = bucket.list_blobs(prefix=folder)
   latest = max(blobs, key=lambda x: x.updated)
   json_string = latest.download_as_string()
   return json.loads(json_string)

def create_video(song_data):
   width, height = 1080, 1920
   duration = 15
   
   background = ColorClip((width, height), color=(0,0,0), duration=duration)
   
   # Download artwork
   response = requests.get(song_data['artwork_url'])
   img = Image.open(BytesIO(response.content))
   artwork_clip = ImageClip(img).set_duration(duration)
   artwork_clip = artwork_clip.resize(width=width*0.8)
   artwork_cli

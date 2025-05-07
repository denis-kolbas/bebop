import os
from google.cloud import storage
import requests
from bs4 import BeautifulSoup
import json
import datetime
import time
import re

def init_gcp():
   service_account_json = os.environ.get('GCP_SA_KEY')
   with open('gcp_credentials.json', 'w') as f:
       f.write(service_account_json)
   os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def upload_to_gcs(data, bucket_name, folder):
   storage_client = storage.Client()
   bucket = storage_client.bucket(bucket_name)
   filename = f'songs_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
   blob = bucket.blob(f'{folder}/{filename}')
   blob.upload_from_string(data, content_type='application/json')
   print(f"Uploaded to {bucket_name}/{folder}/{filename}")

def scrape_apple_music():
   init_gcp()
   url = "https://music.apple.com/az/playlist/new-music-daily/pl.2b0e6e332fdf4b7a91164da3162127b5"
   headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
   tracks = []
   scrape_date = datetime.datetime.now().strftime("%Y-%m-%d")

   try:
       response = requests.get(url, headers=headers)
       soup = BeautifulSoup(response.text, 'html.parser')
       schema_script = soup.find('script', {'id': 'schema:music-playlist'})
       playlist_data = json.loads(schema_script.string)

       for i, track in enumerate(playlist_data.get('track', [])):
           try:
               time.sleep(2)
               song_url = track.get('url', '')
               song_response = requests.get(song_url, headers=headers)
               song_soup = BeautifulSoup(song_response.text, 'html.parser')
               
               artwork = song_soup.find('div', {'class': 'artwork-component'})
               colors = {}
               if artwork and artwork.get('style'):
                   bg_color = re.search(r'--artwork-bg-color: (#[A-Fa-f0-9]+)', artwork['style'])
                   if bg_color:
                       colors['artwork_bg_color'] = bg_color.group(1)
               
               song_schema = song_soup.find('script', {'id': 'schema:song'})
               if song_schema:
                   song_data = json.loads(song_schema.string)
                   audio_data = song_data.get('audio', {})
                   
                   track_info = {
                       'song_name': song_data.get('name', ''),
                       'album': audio_data.get('inAlbum', {}).get('name', ''),
                       'artist': audio_data.get('byArtist', [{}])[0].get('name', ''),
                       'preview_url': audio_data.get('audio', {}).get('contentUrl', ''),
                       'release_date': audio_data.get('datePublished'),
                       'song_url': song_url,
                       'artwork_bg_color': colors.get('artwork_bg_color'),
                       'scrape_date': scrape_date
                   }
                   tracks.append(track_info)
                   print(f"Scraped {i+1}/{len(playlist_data.get('track', []))}: {track_info['song_name']}")
           
           except Exception as e:
               print(f"Error scraping track {i+1}: {e}")
               continue

       json_data = json.dumps(tracks, indent=2, ensure_ascii=False)
       bucket_name = os.environ.get('GCS_BUCKET_NAME')
       folder = 'apple_music'
       upload_to_gcs(json_data, bucket_name, folder)

       return tracks

   except Exception as e:
       print(f"Error: {e}")
       return []

if __name__ == "__main__":
   tracks = scrape_apple_music()

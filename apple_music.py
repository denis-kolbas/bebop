import os
from google.cloud import storage
import requests
from bs4 import BeautifulSoup
import json
import datetime
import time
import re
from ytmusicapi import YTMusic, OAuthCredentials
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# OAuth credentials
CLIENT_ID = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"  # Replace with your actual client secret

def init_gcp():
  service_account_json = os.environ.get('GCP_SA_KEY')
  with open('gcp_credentials.json', 'w') as f:
      f.write(service_account_json)
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def get_song_views(song_name, artist_name):
  try:
      ytmusic = YTMusic('oauth.json', oauth_credentials=OAuthCredentials(
          client_id=CLIENT_ID,
          client_secret=CLIENT_SECRET
      ))
      search_query = f"{song_name} {artist_name} official"
      results = ytmusic.search(search_query, filter='videos', limit=1)
      if results and len(results) > 0:
          # Try different field names that might contain view count
          for field in ['videoCountText', 'viewCount', 'views']:
              if field in results[0]:
                  return results[0][field]
      return '0'
  except Exception as e:
      print(f"YouTube search error: {e}")
      return '0'

def upload_to_gcs(data, bucket_name):
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  filename = f'apple_music/songs_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
  blob = bucket.blob(filename)
  blob.upload_from_string(data, content_type='application/json')
  print(f"Uploaded to {bucket_name}/{filename}")

def get_selected_songs(bucket_name):
   storage_client = storage.Client()
   bucket = storage_client.bucket(bucket_name)
   blob = bucket.blob('selected_songs.json')  # No folder, directly in bebop_data
   
   if blob.exists():
       selected_songs = json.loads(blob.download_as_string())
   else:
       selected_songs = []
   
   return selected_songs

def select_new_songs(tracks, bucket_name, num_songs=10):
    # Get previously selected songs
    selected_songs = get_selected_songs(bucket_name)
    selected_song_ids = set(song['song_url'] for song in selected_songs)
    
    # Filter out previously selected songs
    new_tracks = [track for track in tracks if track['song_url'] not in selected_song_ids]
    
    # Parse view counts and add selection date
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    for track in new_tracks:
        track['selected_date'] = current_date
        
        # Parse view count
        view_str = str(track['views'])
        view_str = re.sub(r'[^0-9KMBkmb\.]', '', view_str)
        
        views_int = 0
        try:
            if 'M' in view_str.upper():
                views_int = float(view_str.upper().replace('M', '')) * 1000000
            elif 'K' in view_str.upper():
                views_int = float(view_str.upper().replace('K', '')) * 1000
            elif 'B' in view_str.upper():
                views_int = float(view_str.upper().replace('B', '')) * 1000000000
            else:
                views_int = float(view_str) if view_str else 0
            views_int = int(views_int)
        except ValueError:
            views_int = 0
            
        track['views_int'] = views_int
    
    # Filter out songs with more than 20 million views
    new_tracks = [track for track in new_tracks if track['views_int'] <= 20000000]
    
    # Sort by views (descending)
    new_tracks.sort(key=lambda x: x['views_int'], reverse=True)
    
    # Select top 10 songs by views
    newly_selected = new_tracks[:min(num_songs, len(new_tracks))]
    
    # Add to master list and save
    if newly_selected:
        selected_songs.extend(newly_selected)
        
        # Save updated list
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob('selected_songs.json')
        blob.upload_from_string(json.dumps(selected_songs), content_type='application/json')
        
    return newly_selected

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
              artwork_url = None
              
              if artwork:
                  bg_color = re.search(r'--artwork-bg-color: (#[A-Fa-f0-9]+)', artwork['style'])
                  if bg_color:
                      colors['artwork_bg_color'] = bg_color.group(1)
                  try:
                      style_img = artwork.find('picture').find('source')['srcset']
                      artwork_url = style_img.split(',')[-1].split(' ')[0]
                  except:
                      print(f"Could not extract artwork URL")
              
              song_schema = song_soup.find('script', {'id': 'schema:song'})
              if song_schema:
                  song_data = json.loads(song_schema.string)
                  audio_data = song_data.get('audio', {})
                  song_name = song_data.get('name', '')
                  artist_name = audio_data.get('byArtist', [{}])[0].get('name', '')
                  
                  track_info = {
                      'song_name': song_name,
                      'album': audio_data.get('inAlbum', {}).get('name', ''),
                      'artist': artist_name,
                      'preview_url': audio_data.get('audio', {}).get('contentUrl', ''),
                      'release_date': audio_data.get('datePublished'),
                      'song_url': song_url,
                      'artwork_url': artwork_url,
                      'artwork_bg_color': colors.get('artwork_bg_color'),
                      'views': get_song_views(song_name, artist_name),
                      'scrape_date': scrape_date
                  }
                  tracks.append(track_info)
                  print(f"Scraped {i+1}/{len(playlist_data.get('track', []))}: {track_info['song_name']}")
          
          except Exception as e:
              print(f"Error scraping track {i+1}: {e}")
              continue

      json_data = json.dumps(tracks, indent=2, ensure_ascii=False)
      bucket_name = os.environ.get('GCS_BUCKET_NAME')
      upload_to_gcs(json_data, bucket_name)

      return tracks

  except Exception as e:
      print(f"Error: {e}")
      return []

if __name__ == "__main__":
  tracks = scrape_apple_music()
  bucket_name = os.environ.get('GCS_BUCKET_NAME')
  selected_tracks = select_new_songs(tracks, bucket_name)
  print(f"Selected {len(selected_tracks)} new songs")

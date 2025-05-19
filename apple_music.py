import os
from google.cloud import storage
import requests
from bs4 import BeautifulSoup
import json
import datetime
from datetime import timedelta
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


def fix_encoding(text):
    """Fix double-encoded UTF-8 characters in text"""
    if not text:
        return ""
    
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeError, UnicodeDecodeError):
        return text

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

def select_new_songs(tracks, bucket_name, num_songs=20):
   # Get previously selected songs
   selected_songs = get_selected_songs(bucket_name)
   
   # Identify songs already processed or tagged for video
   selected_song_ids = set()
   for song in selected_songs:
       # Skip songs already tagged for video creation
       selected_song_ids.add(song['song_url'])
   
   # Filter out previously selected songs
   new_tracks = [track for track in tracks if track['song_url'] not in selected_song_ids]
   
   # Also get songs from the last 5 days that weren't selected
   current_date = datetime.datetime.now().strftime("%Y-%m-%d")
   five_days_ago = (datetime.datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
   
   # Get songs from previous scrapes in the last 5 days
   storage_client = storage.Client()
   bucket = storage_client.bucket(bucket_name)
   
   # List all apple_music scrape files from last 5 days
   blobs = list(bucket.list_blobs(prefix='apple_music/'))
   recent_blobs = [b for b in blobs if five_days_ago <= b.name.split('_')[1].split('_')[0] <= current_date]
   
   recent_tracks = []
   for blob in recent_blobs:
       try:
           tracks_data = json.loads(blob.download_as_string())
           recent_tracks.extend(tracks_data)
       except:
           continue
   
   # Filter out previously selected tracks
   recent_tracks = [track for track in recent_tracks if track['song_url'] not in selected_song_ids]
   
   # Combine with new tracks, removing duplicates
   all_tracks = new_tracks.copy()
   existing_urls = set(track['song_url'] for track in all_tracks)
   
   for track in recent_tracks:
       if track['song_url'] not in existing_urls:
           all_tracks.append(track)
           existing_urls.add(track['song_url'])
   
   # Add selection date and normalize views
   for track in all_tracks:
       track['selected_date'] = current_date
       
       # Parse view count
       view_str = str(track.get('views', '0'))
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
       
       # Normalize views based on days since release or scrape
       days_since = 1
       if track.get('release_date'):
           try:
               release_date = datetime.datetime.strptime(track['release_date'][:10], "%Y-%m-%d")
               days_since = max(1, (datetime.datetime.now() - release_date).days)
           except:
               pass
       elif track.get('scrape_date'):
           try:
               scrape_date = datetime.datetime.strptime(track['scrape_date'], "%Y-%m-%d")
               days_since = max(1, (datetime.datetime.now() - scrape_date).days)
           except:
               pass
       
       track['normalized_views'] = track['views_int'] / days_since
   
   # Filter out songs with more than 20 million views
   all_tracks = [track for track in all_tracks if track['views_int'] <= 20000000]
   
   # Sort by normalized views (descending)
   all_tracks.sort(key=lambda x: x.get('normalized_views', 0), reverse=True)
   
   # Select top songs by normalized views
   newly_selected = all_tracks[:min(num_songs, len(all_tracks))]
   
   # Add create_video field (default false)
   for track in newly_selected:
       track['create_video'] = False
   
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
                      'song_name': fix_encoding(song_name),
                      'album': fix_encoding(audio_data.get('inAlbum', {}).get('name', '')),
                      'artist': fix_encoding(artist_name),
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

import requests
from bs4 import BeautifulSoup
import json
import datetime
import random
import time
from fake_useragent import UserAgent

def extract_artwork_colors(artwork_element):
   colors = {}
   if artwork_element:
       style = artwork_element.get('style', '')
       color_matches = re.findall(r'--artwork-bg-color: (#[A-Fa-f0-9]+)', style)
       if color_matches:
           colors['artwork_bg_color'] = color_matches[0]
       placeholder_matches = re.findall(r'--placeholder-bg-color: (#[A-Fa-f0-9]+)', style)
       if placeholder_matches:
           colors['placeholder_bg_color'] = placeholder_matches[0]
   return colors

def get_random_user_agent():
   ua = UserAgent()
   return ua.random

def scrape_apple_music():
   url = "https://music.apple.com/az/playlist/new-music-daily/pl.2b0e6e332fdf4b7a91164da3162127b5"
   headers = {"User-Agent": get_random_user_agent()}
   tracks = []
   scrape_date = datetime.datetime.now().strftime("%Y-%m-%d")

   try:
       playlist_response = requests.get(url, headers=headers)
       playlist_response.raise_for_status()
       soup = BeautifulSoup(playlist_response.text, 'html.parser')

       schema_script = soup.find('script', {'id': 'schema:music-playlist'})
       if not schema_script:
           return []

       playlist_data = json.loads(schema_script.string)

       for i, track in enumerate(playlist_data.get('track', [])):
           time.sleep(random.uniform(1, 3))
           
           song_url = track.get('url', '')
           headers = {"User-Agent": get_random_user_agent()}
           
           song_response = requests.get(song_url, headers=headers)
           song_soup = BeautifulSoup(song_response.text, 'html.parser')
           
           song_schema = song_soup.find('script', {'id': 'schema:song'})
           artwork_element = song_soup.find('div', {'class': 'artwork-component'})
           
           colors = extract_artwork_colors(artwork_element)
           
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
                   'placeholder_bg_color': colors.get('placeholder_bg_color'),
                   'scrape_date': scrape_date
               }
               tracks.append(track_info)
               
               print(f"Scraped {i+1} of {len(playlist_data.get('track', []))} tracks")

       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       filename = f'apple_music_songs_{timestamp}.json'
       
       with open(filename, 'w', encoding='utf-8') as f:
           json.dump(tracks, f, indent=2, ensure_ascii=False)

       return tracks

   except requests.RequestException as e:
       print(f"Error fetching data: {e}")
       return []

if __name__ == "__main__":
   tracks = scrape_apple_music()
   print(f"Scraped {len(tracks)} tracks")

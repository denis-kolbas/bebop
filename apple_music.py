import requests
from bs4 import BeautifulSoup
import json
import datetime
import re

def scrape_apple_music_playlist():
   url = "https://music.apple.com/az/playlist/new-music-daily/pl.2b0e6e332fdf4b7a91164da3162127b5"
   headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

   try:
       response = requests.get(url, headers=headers)
       response.raise_for_status()
       soup = BeautifulSoup(response.text, 'html.parser')

       schema_script = soup.find('script', {'id': 'schema:music-playlist'})
       if not schema_script:
           return []

       playlist_data = json.loads(schema_script.string)
       tracks = []
       scrape_date = datetime.datetime.now().strftime("%Y-%m-%d")

       for track in playlist_data.get('track', []):
           artwork_url = track['audio'].get('thumbnailUrl', '')
           high_res_artwork = re.sub(r'/\d+x\d+bb', '/2000x2000bb', artwork_url)

           track_info = {
               'song_name': track.get('name', ''),
               'song_url': track.get('url', ''),
               'duration': track.get('duration', '').replace('PT', '').replace('M', ':').replace('S', ''),
               'artwork_url': high_res_artwork,
               'scrape_date': scrape_date
           }
           tracks.append(track_info)

       timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
       filename = f'apple_music_playlist_{timestamp}.json'
       
       with open(filename, 'w', encoding='utf-8') as f:
           json.dump(tracks, f, indent=2, ensure_ascii=False)

       return tracks

   except requests.RequestException as e:
       print(f"Error fetching data: {e}")
       return []

if __name__ == "__main__":
   tracks = scrape_apple_music_playlist()
   print(f"Scraped {len(tracks)} tracks")

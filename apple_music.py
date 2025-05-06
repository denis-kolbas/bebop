import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
from typing import Dict, List
import re

class AppleMusicScraper:
    def __init__(self, playlist_url: str):
        self.playlist_url = playlist_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_page_content(self) -> str:
        try:
            response = requests.get(self.playlist_url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching the page: {e}")
            return ""

    def extract_song_info(self, html_content: str) -> List[Dict]:
        soup = BeautifulSoup(html_content, 'html.parser')
        songs_data = []
        
        # Find all song items
        song_items = soup.find_all('div', class_='songs-list-row')
        
        for item in song_items:
            try:
                # Extract song details
                song_name = item.find('div', class_='songs-list-row__song-name').text.strip()
                artist_name = item.find('div', class_='songs-list-row__artist').text.strip()
                album_name = item.find('div', class_='songs-list-row__album').text.strip()
                
                # Extract artwork URL and transform to highest resolution
                artwork_url = item.find('img', class_='songs-list-row__artwork')['src']
                artwork_url = artwork_url.replace('/100x100bb.jpg', '/2000x2000bb.jpg')
                
                # Extract background colors from style attributes
                style_tag = item.find('style')
                if style_tag:
                    style_text = style_tag.string
                    bg_color = re.search(r'background-color:\s*(#[A-Fa-f0-9]{6})', style_text)
                    placeholder_bg_color = re.search(r'placeholder-background-color:\s*(#[A-Fa-f0-9]{6})', style_text)
                
                song_data = {
                    'song_name': song_name,
                    'artist_name': artist_name,
                    'album_name': album_name,
                    'artwork_url': artwork_url,
                    'bg_color': bg_color.group(1) if bg_color else None,
                    'placeholder_bg_color': placeholder_bg_color.group(1) if placeholder_bg_color else None,
                    'date_scraped': datetime.now().strftime('%Y-%m-%d')
                }
                songs_data.append(song_data)
            
            except AttributeError as e:
                print(f"Error extracting song info: {e}")
                continue
        
        return songs_data

    def save_to_json(self, data: List[Dict], filename: str = 'apple_music_data.json'):
        try:
            # Create 'data' directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            filepath = os.path.join('data', filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Data successfully saved to {filepath}")
        
        except Exception as e:
            print(f"Error saving data to JSON: {e}")

def main():
    playlist_url = "https://music.apple.com/us/playlist/new-music-daily/pl.2b0e6e332fdf4b7a91164da3162127b5"
    scraper = AppleMusicScraper(playlist_url)
    
    # Get page content
    html_content = scraper.get_page_content()
    if not html_content:
        return
    
    # Extract song information
    songs_data = scraper.extract_song_info(html_content)
    
    # Save to JSON
    scraper.save_to_json(songs_data)

if __name__ == "__main__":
    main()
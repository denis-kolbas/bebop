import json
import requests
from moviepy.editor import ColorClip, TextClip, ImageClip, CompositeVideoClip
from PIL import Image
from io import BytesIO
import glob
import os

def get_latest_json(directory):
    list_of_files = glob.glob(f'{directory}/songs_*.json')
    latest_file = max(list_of_files, key=os.path.getctime)
    with open(latest_file, 'r') as f:
        return json.load(f)

def download_artwork(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def create_music_preview(song_data):
    # Background
    bg = ColorClip((1920, 1080), color=song_data['artwork_bg_color'])
    bg = bg.set_duration(15)
    
    # Album artwork
    artwork_img = download_artwork(song_data['artwork_url'])
    artwork = ImageClip(numpy.array(artwork_img))
    artwork = artwork.resize(height=600)
    artwork = artwork.set_position(('center', 200))
    artwork = artwork.set_duration(15)
    
    # Text clips
    song_name = TextClip(song_data['song_name'], 
                        font='Arial-Bold', 
                        fontsize=70, 
                        color='white')
    song_name = song_name.set_position(('center', 850))
    song_name = song_name.set_duration(15)
    
    artist_name = TextClip(f"{song_data['artist']} • {song_data['album']}", 
                          font='Arial', 
                          fontsize=40, 
                          color='white')
    artist_name = artist_name.set_position(('center', 950))
    artist_name = artist_name.set_duration(15)
    
    # Combine all elements
    video = CompositeVideoClip([bg, artwork, song_name, artist_name])
    
    # Save video
    output_filename = f"preview_{song_data['song_name'].replace(' ', '_')}.mp4"
    video.write_videofile(output_filename, 
                         fps=24, 
                         codec='libx264', 
                         audio=None)
    return output_filename

def main():
    # Replace with your GCP bucket path
    json_data = get_latest_json('bebop_data/apple_music')
    
    # Process first song in the JSON file
    song_data = json_data[0]
    output_file = create_music_preview(song_data)
    print(f"Created preview video: {output_file}")

if __name__ == "__main__":
    main()

from google.cloud import storage
import json
from datetime import datetime
import requests
from moviepy.editor import ColorClip, TextClip, ImageClip, CompositeVideoClip
from PIL import Image
from io import BytesIO
import glob
import os

def get_latest_json(bucket_name, prefix):
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    
    # List all blobs with the given prefix
    blobs = list(bucket.list_blobs(prefix=prefix))
    latest_blob = max(blobs, key=lambda x: x.name)
    
    # Download and parse JSON
    json_data = json.loads(latest_blob.download_as_string())
    return json_data

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
    json_data = get_latest_json('GCP_BUCKET_NAME', 'bebop_data/apple_music/')
    
    # Process first song in the JSON file
    song_data = json_data[0]
    output_file = create_music_preview(song_data)
    print(f"Created preview video: {output_file}")

if __name__ == "__main__":
    main()

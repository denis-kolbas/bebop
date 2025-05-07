from google.cloud import storage
import json
import requests
from moviepy.editor import ColorClip, TextClip, ImageClip, CompositeVideoClip
from PIL import Image
from io import BytesIO
import numpy
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_latest_json(bucket_name, prefix):
    logging.info(f"Getting latest JSON from {bucket_name}/{prefix}")
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))
    latest_blob = max(blobs, key=lambda x: x.name)
    logging.info(f"Found latest file: {latest_blob.name}")
    
    json_data = json.loads(latest_blob.download_as_string())
    sorted_songs = sorted(json_data, 
                         key=lambda x: int(x['views']), 
                         reverse=True)[:3]
    logging.info(f"Got top 3 songs by views")
    return sorted_songs

def download_artwork(url):
    logging.info(f"Downloading artwork from: {url}")
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def create_music_preview(song_data):
    logging.info(f"Creating preview for: {song_data['song_name']} by {song_data['artist']}")
    
    bg = ColorClip((1920, 1080), color=song_data['artwork_bg_color'])
    bg = bg.set_duration(15)
    
    artwork_img = download_artwork(song_data['artwork_url'])
    artwork = ImageClip(numpy.array(artwork_img))
    artwork = artwork.resize(height=600)
    artwork = artwork.set_position(('center', 200))
    artwork = artwork.set_duration(15)
    
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
    
    video = CompositeVideoClip([bg, artwork, song_name, artist_name])
    
    output_filename = f"preview_{song_data['song_name'].replace(' ', '_')}.mp4"
    logging.info(f"Rendering video to: {output_filename}")
    video.write_videofile(output_filename, 
                         fps=24, 
                         codec='libx264', 
                         audio=None)
    return output_filename

def main():
    logging.info("Starting video creation process")
    bucket_name = 'bebop_data'
    top_songs = get_latest_json(bucket_name, 'bebop_data/apple_music/')
    
    for idx, song in enumerate(top_songs, 1):
        logging.info(f"Processing song {idx} of 3")
        output_file = create_music_preview(song)
        logging.info(f"Completed video: {output_file}")

if __name__ == "__main__":
    main()

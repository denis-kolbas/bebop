from google.cloud import storage
import json
import requests
from moviepy.editor import ColorClip, TextClip, ImageClip, CompositeVideoClip
from PIL import Image
from io import BytesIO
import numpy
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def color_to_rgb(color):
    if color.startswith('#'):
        color = color.lstrip('#')
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)

def get_latest_json(bucket_name, prefix):
    try:
        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        latest_blob = max(blobs, key=lambda x: x.name)
        logging.info(f"Processing: {latest_blob.name}")
        
        json_data = json.loads(latest_blob.download_as_string())
        return sorted(json_data, key=lambda x: int(x['views']), reverse=True)[:3]
    except Exception as e:
        logging.error(f"Error getting JSON: {str(e)}")
        raise

def download_artwork(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logging.error(f"Error downloading artwork: {str(e)}")
        raise

def create_music_preview(song_data):
    try:
        safe_name = "".join(c for c in song_data['song_name'] if c.isalnum() or c in (' ', '-', '_')).strip()
        output_filename = f"preview_{safe_name}.mp4"
        
        bg = ColorClip((1920, 1080), color=color_to_rgb(song_data['artwork_bg_color']))
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
        video.write_videofile(output_filename, 
                            fps=24, 
                            codec='libx264', 
                            audio=None,
                            logger=None)
        return output_filename
    except Exception as e:
        logging.error(f"Error creating preview: {str(e)}")
        raise

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        logging.info(f"Uploaded to GCS: {destination_blob_name}")
    except Exception as e:
        logging.error(f"Upload failed: {str(e)}")
        raise

def main():
    try:
        bucket_name = 'bebop_data'
        top_songs = get_latest_json(bucket_name, 'bebop_data/apple_music/')
        
        for idx, song in enumerate(top_songs, 1):
            logging.info(f"Processing #{idx}: {song['song_name']}")
            output_file = create_music_preview(song)
            upload_to_gcs(bucket_name, output_file, f"videos/{output_file}")
            # Keep local file for GitHub commit
            
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()

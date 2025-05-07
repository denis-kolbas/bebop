import json
from moviepy.editor import *
import requests
from io import BytesIO
from PIL import Image
import os
from google.cloud import storage

def download_image(url):
    # Download artwork and convert to MoviePy-compatible format
    pass

def download_audio(preview_url):
    # Download preview audio from Apple Music
    pass

def create_video(song_data):
    # Video dimensions and duration
    width, height = 1080, 1920
    duration = 15
    
    # Create background (black)
    background = ColorClip((width, height), color=(0,0,0), duration=duration)
    
    # Add centered artwork
    artwork = download_image(song_data['artwork_url'])
    # Resize and position artwork
    
    # Create text overlays
    text_clips = [
        TextClip(song_data['song_name'], fontsize=70, color='white'),
        TextClip(song_data['artist'], fontsize=50, color='white'),
        TextClip(song_data['album'], fontsize=40, color='white')
    ]
    # Position text at bottom
    
    # Add audio
    audio = download_audio(song_data['preview_url'])
    
    # Compose video
    final = CompositeVideoClip([background, artwork] + text_clips)
    final = final.set_audio(audio)
    
    return final

def process_songs(json_file):
    # Load and sort songs by views
    with open(json_file) as f:
        songs = json.load(f)
    
    top_songs = sorted(songs, key=lambda x: int(x['views'].replace('M','000000')), reverse=True)[:10]
    
    for song in top_songs:
        video = create_video(song)
        filename = f"{song['song_name']}_{song['artist']}.mp4"
        video.write_videofile(filename)
        upload_to_gcs(filename)

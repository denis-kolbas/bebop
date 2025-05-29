import os
import requests
import time

# Configuration
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGE_ID = os.environ.get('FACEBOOK_PAGE_ID')

print(f"Page ID: {FACEBOOK_PAGE_ID}")
print(f"Token: {'Set' if FACEBOOK_ACCESS_TOKEN else 'Not set'}")

if not FACEBOOK_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
    print("Error: Missing FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID")
    exit(1)

# Video to upload
VIDEO_URL = "https://storage.googleapis.com/bebop_data/videos/2025-05-29/stitched/stitched_reel_2025-05-29.mp4"

# Step 1: Initialize upload session
print("Step 1: Starting upload session...", flush=True)
try:
    response = requests.post(
        f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_reels",
        data={
            "upload_phase": "start",
            "access_token": FACEBOOK_ACCESS_TOKEN
        },
        timeout=30
    )
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
    exit(1)

if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)

video_id = response.json()['video_id']
upload_url = response.json()['upload_url']
print(f"Video ID: {video_id}")

# Step 2: Upload video from URL
print("Step 2: Uploading video...")
response = requests.post(
    f"https://rupload.facebook.com/video-upload/v18.0/{video_id}",
    headers={
        "Authorization": f"OAuth {FACEBOOK_ACCESS_TOKEN}",
        "file_url": VIDEO_URL
    }
)

if response.status_code != 200:
    print(f"Upload error: {response.text}")
    exit(1)

print("Upload started...")

# Step 3: Check processing status
print("Step 3: Waiting for processing...")
for i in range(60):  # Try for 5 minutes
    response = requests.get(
        f"https://graph.facebook.com/v18.0/{video_id}",
        params={
            "fields": "status",
            "access_token": FACEBOOK_ACCESS_TOKEN
        }
    )
    
    status = response.json()['status']['video_status']
    print(f"Status: {status}")
    
    if status == 'ready':
        break
    elif status == 'error':
        print(f"Processing error: {response.json()}")
        exit(1)
    
    time.sleep(5)

# Step 4: Publish the reel
print("Step 4: Publishing reel...")
response = requests.post(
    f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_reels",
    params={
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "video_id": video_id,
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": "Today's Music Discoveries! 🎵 #NewMusic #MusicDiscovery"
    }
)

if response.status_code == 200:
    print("✅ Reel published successfully!")
else:
    print(f"Publishing error: {response.text}")
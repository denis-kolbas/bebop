import os
import requests
import time

# Configuration
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGE_ID = os.environ.get('FACEBOOK_PAGE_ID')

# Video to upload
VIDEO_URL = "https://storage.googleapis.com/bebop_data/videos/2025-05-29/individual/11_ANDO_XXIL_Feid_2025-05-29.mp4"

# Step 1: Initialize upload session
print("Step 1: Starting story upload session...")
response = requests.post(
    f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_stories",
    data={
        "upload_phase": "start",
        "access_token": FACEBOOK_ACCESS_TOKEN
    }
)

if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)

video_id = response.json()['video_id']
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
    
    status_data = response.json().get('status', {})
    video_status = status_data.get('video_status', '')
    processing_status = status_data.get('processing_phase', {}).get('status', '')
    
    print(f"Status: {video_status}, Processing: {processing_status}")
    
    if video_status == 'ready' or processing_status == 'complete':
        break
    elif video_status == 'error':
        print(f"Processing error: {response.json()}")
        exit(1)
    
    time.sleep(5)

# Step 4: Publish the story
print("Step 4: Publishing story...")
response = requests.post(
    f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/video_stories",
    data={
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "video_id": video_id,
        "upload_phase": "finish"
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Story published successfully! Post ID: {result.get('post_id')}")
else:
    print(f"Publishing error: {response.text}")
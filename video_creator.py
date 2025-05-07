import json
import os
import re
from datetime import datetime
from io import BytesIO

import requests
from google.cloud import storage
from moviepy.editor import (AudioFileClip, ColorClip, CompositeVideoClip,
                            ImageClip, TextClip)
from PIL import Image as PILImage

# --- Configuration ---
BUCKET_NAME = "bebop_data"  # Replace with your bucket name
JSON_FILE_PREFIX = "bebop_data/apple_music/songs_"
VIDEOS_OUTPUT_FOLDER = "videos/"  # Will be created in the bucket if it doesn't exist
VIDEO_DURATION = 15  # seconds
VIDEO_WIDTH = 1080  # pixels
VIDEO_HEIGHT = 1920  # pixels (portrait aspect ratio, common for shorts/reels)
ARTWORK_MAX_WIDTH = int(VIDEO_WIDTH * 0.8)
ARTWORK_MAX_HEIGHT = int(VIDEO_HEIGHT * 0.5)
TEXT_AREA_HEIGHT = int(VIDEO_HEIGHT * 0.3)
FONT_PATH = "arial.ttf" # Default, consider bundling a font for CI/CD
# FONT_PATH = "path/to/your/font.ttf" # Example for a bundled font
FALLBACK_FONT = "DejaVu-Sans-Bold" # A common font in Linux environments

# --- Helper Functions ---

def get_latest_json_file(bucket_name, prefix):
    """Lists files in GCS and returns the name of the latest JSON file based on filename timestamp."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            print(f"No files found with prefix '{prefix}' in bucket '{bucket_name}'.")
            return None

        # Filter for .json files and extract timestamps
        json_files = []
        # Regex to match 'songs_YYYYMMDD_HHMMSS.json'
        file_pattern = re.compile(rf"{prefix}(\d{{8}}_\d{{6}})\.json$")

        for blob in blobs:
            match = file_pattern.match(blob.name)
            if match:
                timestamp_str = match.group(1)
                try:
                    # Convert YYYYMMDD_HHMMSS to a datetime object
                    dt_obj = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    json_files.append({"name": blob.name, "datetime": dt_obj, "blob": blob})
                except ValueError:
                    print(f"Warning: Could not parse timestamp from filename: {blob.name}")
                    continue # Skip files with malformed timestamps

        if not json_files:
            print(f"No valid JSON files found matching the pattern '{prefix}YYYYMMDD_HHMMSS.json'.")
            return None

        # Sort by datetime in descending order to get the latest
        latest_file_info = sorted(json_files, key=lambda x: x["datetime"], reverse=True)[0]
        print(f"Latest JSON file found: {latest_file_info['name']}")
        return latest_file_info["blob"]

    except Exception as e:
        print(f"Error listing files in GCS: {e}")
        return None

def download_json_from_gcs(blob):
    """Downloads a JSON file from GCS and parses it."""
    try:
        json_data_string = blob.download_as_text()
        data = json.loads(json_data_string)
        return data
    except Exception as e:
        print(f"Error downloading or parsing JSON from GCS ({blob.name}): {e}")
        return None

def download_file(url, local_filename, is_image=False):
    """Downloads a file from a URL."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {local_filename}")

        if is_image: # Verify image integrity
            try:
                img = PILImage.open(local_filename)
                img.verify() # Verify it's an image
                img.close()
                 # Reopen for use if needed, verify() can make it unusable directly
                img = PILImage.open(local_filename)
                img.load() # Ensure image data is loaded
                img.close()

            except (IOError, SyntaxError) as e:
                print(f"Error: Downloaded file {local_filename} is not a valid image or is corrupted: {e}")
                os.remove(local_filename) # Clean up corrupted file
                return None
        return local_filename
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while downloading {url}: {e}")
        return None


def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to GCS."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        print(f"File {source_file_name} uploaded to {destination_blob_name}.")
        return True
    except Exception as e:
        print(f"Error uploading {source_file_name} to GCS: {e}")
        return False

def create_song_video(song_info, artwork_path, audio_path, output_video_path):
    """Creates a video for a song."""
    try:
        # 1. Load Artwork and Resize
        artwork_clip = ImageClip(artwork_path)

        # Calculate new dimensions maintaining aspect ratio
        img_width, img_height = artwork_clip.size
        ratio = min(ARTWORK_MAX_WIDTH / img_width, ARTWORK_MAX_HEIGHT / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        artwork_clip_resized = artwork_clip.resize(height=new_height, width=new_width).set_duration(VIDEO_DURATION)
        artwork_pos_x = (VIDEO_WIDTH - new_width) / 2
        artwork_pos_y = (VIDEO_HEIGHT - TEXT_AREA_HEIGHT - new_height) / 2 # Position above text area

        artwork_clip_final = artwork_clip_resized.set_position((artwork_pos_x, artwork_pos_y))

        # 2. Create Background Clip (can be based on artwork_bg_color or a default)
        try:
            bg_color_hex = song_info.get("artwork_bg_color", "#000000").lstrip('#')
            bg_color_rgb = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            print(f"Warning: Invalid artwork_bg_color '{song_info.get('artwork_bg_color')}'. Using black.")
            bg_color_rgb = (0,0,0) # Black background

        background_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                                    color=bg_color_rgb,
                                    ismask=False, duration=VIDEO_DURATION)


        # 3. Create Text Clips
        text_clips = []
        text_y_start = artwork_pos_y + new_height + 30 # Start text below artwork
        line_height = 60 # Approximate line height, adjust as needed
        font_size = 45   # Adjust as needed

        def create_text(txt, y_pos, f_size=font_size, color='white', stroke_color='black', stroke_width=1.5):
            try:
                # Try primary font
                return TextClip(txt, fontsize=f_size, color=color, font=FONT_PATH,
                                stroke_color=stroke_color, stroke_width=stroke_width).set_position(('center', y_pos)).set_duration(VIDEO_DURATION)
            except Exception:
                try:
                    # Try fallback font
                    print(f"Warning: Font '{FONT_PATH}' not found or error. Trying fallback '{FALLBACK_FONT}'.")
                    return TextClip(txt, fontsize=f_size, color=color, font=FALLBACK_FONT,
                                    stroke_color=stroke_color, stroke_width=stroke_width).set_position(('center', y_pos)).set_duration(VIDEO_DURATION)
                except Exception as e_fallback:
                    print(f"Error: Fallback font '{FALLBACK_FONT}' also failed: {e_fallback}. Text will be missing for: {txt}")
                    return None # Cannot create text

        song_name_clip = create_text(f"Song: {song_info['song_name']}", text_y_start)
        if song_name_clip: text_clips.append(song_name_clip)

        artist_name_clip = create_text(f"Artist: {song_info['artist']}", text_y_start + line_height)
        if artist_name_clip: text_clips.append(artist_name_clip)

        album_name_clip = create_text(f"Album: {song_info['album']}", text_y_start + (2 * line_height))
        if album_name_clip: text_clips.append(album_name_clip)

        # 4. Load Audio
        if not audio_path or not os.path.exists(audio_path):
            print(f"Warning: Audio file not found at {audio_path}. Video will have no audio.")
            audio_clip_final = None
        else:
            audio_clip = AudioFileClip(audio_path)
            if audio_clip.duration > VIDEO_DURATION:
                audio_clip_final = audio_clip.subclip(0, VIDEO_DURATION)
            else:
                # If audio is shorter, it will play for its duration and then stop.
                # To loop it or extend silence, more complex logic is needed.
                # For now, we just use it as is.
                audio_clip_final = audio_clip.set_duration(min(audio_clip.duration, VIDEO_DURATION))


        # 5. Composite Video
        final_clips_for_composite = [background_clip, artwork_clip_final] + [tc for tc in text_clips if tc is not None]
        video = CompositeVideoClip(final_clips_for_composite, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        if audio_clip_final:
            video = video.set_audio(audio_clip_final)
        else: # Ensure video has silent audio if no audio file
            pass # Moviepy handles videos without audio fine, but if explicit silence is needed:
                 # from moviepy.editor import AudioClip
                 # silent_audio = AudioClip(lambda t: [0,0], duration=VIDEO_DURATION, fps=44100)
                 # video = video.set_audio(silent_audio)


        video.write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac") # common codecs
        print(f"Successfully created video: {output_video_path}")
        return output_video_path

    except Exception as e:
        print(f"Error creating video for '{song_info['song_name']}': {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Clean up individual clips if they exist to free memory
        if 'artwork_clip' in locals() and artwork_clip: artwork_clip.close()
        if 'artwork_clip_resized' in locals() and artwork_clip_resized: artwork_clip_resized.close()
        if 'background_clip' in locals() and background_clip: background_clip.close()
        for tc in text_clips:
            if tc: tc.close()
        if 'audio_clip' in locals() and audio_clip: audio_clip.close()
        if 'audio_clip_final' in locals() and audio_clip_final: audio_clip_final.close()
        if 'video' in locals() and video: video.close()


# --- Main Script Logic ---
def main():
    print(f"Script started at {datetime.now()}")

    # 1. Get the latest JSON file from GCS
    latest_json_blob = get_latest_json_file(BUCKET_NAME, JSON_FILE_PREFIX)
    if not latest_json_blob:
        print("Could not find the latest JSON file. Exiting.")
        return

    # 2. Download and parse JSON
    songs_data = download_json_from_gcs(latest_json_blob)
    if not songs_data:
        print("Could not download or parse JSON data. Exiting.")
        return

    if not isinstance(songs_data, list) or not songs_data:
        print("JSON data is not a list or is empty. Exiting.")
        return

    # 3. Sort songs by views (descending) and take top 3
    #    Handle cases where 'views' might be missing or not a number
    def get_views(song):
        try:
            return int(song.get("views", 0))
        except (ValueError, TypeError):
            return 0 # Default to 0 if 'views' is not a valid number

    sorted_songs = sorted(songs_data, key=get_views, reverse=True)
    top_songs = sorted_songs[:3]

    if not top_songs:
        print("No songs found in the JSON data after sorting. Exiting.")
        return

    print(f"Top {len(top_songs)} songs selected:")
    for i, song in enumerate(top_songs):
        print(f"  {i+1}. {song['song_name']} by {song['artist']} (Views: {get_views(song)})")


    # --- Temporary local directory for downloads ---
    temp_dir = "temp_song_assets"
    os.makedirs(temp_dir, exist_ok=True)

    processed_videos_count = 0
    for i, song in enumerate(top_songs):
        print(f"\nProcessing song {i+1}/{len(top_songs)}: {song['song_name']} by {song['artist']}")

        artwork_url = song.get("artwork_url")
        audio_url = song.get("preview_url") # Using preview_url as per description

        if not artwork_url:
            print(f"Skipping song '{song['song_name']}' due to missing 'artwork_url'.")
            continue
        if not audio_url:
            print(f"Skipping song '{song['song_name']}' due to missing 'preview_url' (audio_url).")
            continue

        # Sanitize song name for filenames
        safe_song_name = re.sub(r'[^\w\s-]', '', song['song_name'].lower()).replace(' ', '_')
        safe_artist_name = re.sub(r'[^\w\s-]', '', song['artist'].lower()).replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Define local paths for downloaded files
        artwork_filename = f"{safe_song_name}_artwork.jpg" # Assuming jpg, png, webp
        artwork_local_path = os.path.join(temp_dir, artwork_filename)

        audio_filename = f"{safe_song_name}_audio.m4a" # Based on example URL
        audio_local_path = os.path.join(temp_dir, audio_filename)

        video_output_filename = f"{safe_song_name}_{safe_artist_name}_{timestamp}.mp4"
        video_local_path = os.path.join(temp_dir, video_output_filename)

        # 4. Download artwork and audio
        downloaded_artwork = download_file(artwork_url, artwork_local_path, is_image=True)
        downloaded_audio = download_file(audio_url, audio_local_path)

        if not downloaded_artwork:
            print(f"Failed to download or validate artwork for '{song['song_name']}'. Skipping video creation for this song.")
            continue
        # Note: Video creation will proceed even if audio download fails, resulting in a silent video.
        # You can add 'if not downloaded_audio: continue' here if audio is mandatory.

        # 5. Create video
        created_video_path = create_song_video(song, downloaded_artwork, downloaded_audio, video_local_path)

        # 6. Upload video to GCS
        if created_video_path and os.path.exists(created_video_path):
            gcs_video_path = os.path.join(VIDEOS_OUTPUT_FOLDER, video_output_filename).replace("\\", "/") # Ensure forward slashes
            if upload_to_gcs(BUCKET_NAME, created_video_path, gcs_video_path):
                processed_videos_count +=1
        else:
            print(f"Skipping upload for '{song['song_name']}' as video creation failed or file not found.")


        # Clean up local files for this song (optional, but good practice)
        if os.path.exists(artwork_local_path):
            os.remove(artwork_local_path)
        if os.path.exists(audio_local_path):
            os.remove(audio_local_path)
        if os.path.exists(video_local_path):
            os.remove(video_local_path)

    # Clean up temporary directory
    if os.path.exists(temp_dir) and not os.listdir(temp_dir) : # only remove if empty
        os.rmdir(temp_dir)
    elif os.path.exists(temp_dir):
        print(f"Warning: Temporary directory {temp_dir} is not empty. Manual cleanup might be needed.")


    print(f"\nScript finished at {datetime.now()}. Processed {processed_videos_count} videos.")

if __name__ == "__main__":
    # --- Environment Variable for GCP Authentication ---
    # In GitHub Actions, you'd set GOOGLE_APPLICATION_CREDENTIALS
    # For local testing, you can set it here or in your shell:
    # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your-service-account-key.json"

    if not os.getenv("GCP_SA_KEY") and BUCKET_NAME != "bebop_data":
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("         The script might not be able to authenticate with GCP.")
    if BUCKET_NAME == "your-gcp-bucket-name":
        print("ERROR: Please update BUCKET_NAME in the script before running.")
    else:
        main()

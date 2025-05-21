from moviepy.editor import *
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import os
import numpy as np
import colorsys
import tempfile
import datetime
import shutil
import json
from google.cloud import storage
import io
import gspread
from google.oauth2 import service_account

# Set environment for headless execution
os.environ["IMAGEIO_FFMPEG_EXE"] = "ffmpeg"

def init_gcp():
    """Initialize GCP credentials"""
    service_account_json = os.environ.get('GCP_SA_KEY')
    with open('gcp_credentials.json', 'w') as f:
        f.write(service_account_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def upload_video_to_gcs(local_path, bucket_name, destination_blob_name):
    """Upload video to GCS bucket"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_path)
    print(f"File {local_path} uploaded to gs://{bucket_name}/{destination_blob_name}.")

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_vignette(size, intensity=0.25):
    """Create a very subtle vignette mask"""
    width, height = size
    mask = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(mask)
    
    # Calculate gradient parameters
    min_dim = min(width, height)
    center_x, center_y = width/2, height/2
    radius = min_dim * 0.9  # Very large radius for subtle effect
    
    # Draw radial gradient
    for y in range(height):
        for x in range(width):
            # Distance from center
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            # Calculate gradient factor
            factor = min(1.0, distance / radius)
            # Apply intensity (very low intensity)
            factor = factor ** intensity
            # Set pixel value (only slightly darker at edges)
            value = int(255 * (1 - factor * 0.4))  # Only darken by 40% max
            mask.putpixel((x, y), value)
    
    return mask

def create_highlight_gradient(size, base_color):
    """Create a gradient with subtle highlight effect"""
    width, height = size
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Convert base color to HSV
    r, g, b = base_color
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    
    # Create lighter and darker versions
    top_h = h
    top_s = max(0.0, s * 0.9)  # Less saturated
    top_v = min(1.0, v * 1.15)  # Brighter
    
    mid_h = h
    mid_s = s
    mid_v = v
    
    bottom_h = h
    bottom_s = min(1.0, s * 1.05)
    bottom_v = max(0.2, v * 0.9)
    
    # Convert back to RGB
    top_r, top_g, top_b = colorsys.hsv_to_rgb(top_h, top_s, top_v)
    mid_r, mid_g, mid_b = colorsys.hsv_to_rgb(mid_h, mid_s, mid_v)
    bottom_r, bottom_g, bottom_b = colorsys.hsv_to_rgb(bottom_h, bottom_s, bottom_v)
    
    top_color = (int(top_r*255), int(top_g*255), int(top_b*255))
    mid_color = (int(mid_r*255), int(mid_g*255), int(mid_b*255))
    bottom_color = (int(bottom_r*255), int(bottom_g*255), int(bottom_b*255))
    
    # Draw gradient with highlight in upper third
    for y in range(height):
        # Position ratio
        ratio = y / height
        
        if ratio < 0.33:  # Top third - transition from bright to base
            sub_ratio = ratio / 0.33
            r = int(top_color[0] * (1 - sub_ratio) + mid_color[0] * sub_ratio)
            g = int(top_color[1] * (1 - sub_ratio) + mid_color[1] * sub_ratio)
            b = int(top_color[2] * (1 - sub_ratio) + mid_color[2] * sub_ratio)
        else:  # Bottom two-thirds - transition from base to darker
            sub_ratio = (ratio - 0.33) / 0.67
            r = int(mid_color[0] * (1 - sub_ratio) + bottom_color[0] * sub_ratio)
            g = int(mid_color[1] * (1 - sub_ratio) + bottom_color[1] * sub_ratio)
            b = int(mid_color[2] * (1 - sub_ratio) + bottom_color[2] * sub_ratio)
            
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return img

def create_scrolling_text_clip(text, font, fontsize, color, duration, max_width, stroke_color=None, stroke_width=0):
    """Create a text clip that scrolls horizontally if too long for max_width"""
    # First create a static text clip to get its dimensions
    static_clip = TextClip(
        txt=text,
        fontsize=fontsize,
        color=color,
        font=font,
        method='label',
        stroke_color=stroke_color,
        stroke_width=stroke_width
    ).set_duration(duration)
    
    # If text fits within max_width, return the static clip
    if static_clip.size[0] <= max_width:
        return static_clip
    
    # Text is too long, need to create scrolling effect
    def make_frame(t):
        # Add padding between repeated text
        scroll_text = text + "   " + text
        
        # Create the frame with the full text
        txt_frame = TextClip(
            txt=scroll_text,
            fontsize=fontsize,
            color=color,
            font=font,
            method='label',
            stroke_color=stroke_color,
            stroke_width=stroke_width
        ).get_frame(0)
        
        # Calculate total scroll distance
        total_text_width = static_clip.size[0] + 100  # Add a little extra space
        
        # Calculate scroll speed - complete one full cycle in duration seconds
        # For a smoother feel, we'll use 3 seconds delay before starting scroll
        delay = 3
        if t < delay:
            offset = 0
        else:
            # Scroll one text width over the remaining duration
            scroll_duration = duration - delay
            scroll_speed = total_text_width / scroll_duration
            offset = ((t - delay) * scroll_speed) % total_text_width
        
        # Create a frame showing just the visible portion
        h, w = static_clip.size[1], max_width
        x1, x2 = int(offset), int(offset) + w
        
        # Make sure we don't go out of bounds
        if x2 > txt_frame.shape[1]:
            return txt_frame[:, 0:w]
        
        return txt_frame[:, x1:x2]
    
    # Create and return the scrolling clip
    scrolling_clip = VideoClip(make_frame=make_frame, duration=duration)
    return scrolling_clip


def generate_music_preview_video(song_data, index=0):
    """Generate a music preview video for a single song"""
    # Create a temp directory for our working files
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Video dimensions
        width, height = 1080, 1920
        clip_duration = 15
        
        # Download and prepare audio
        audio_url = song_data['preview_url']
        audio_response = requests.get(audio_url)
        audio_path = os.path.join(temp_dir, 'preview_audio.m4a')
        with open(audio_path, 'wb') as f:
            f.write(audio_response.content)
        
        # Load audio and trim to 15 seconds
        audio_clip = AudioFileClip(audio_path).subclip(0, clip_duration)
        
        # Add fade in/out for smooth transitions
        audio_clip = audio_clip.audio_fadein(1.0).audio_fadeout(1.0)
        
        # Create gradient with highlight effect
        base_color = hex_to_rgb(song_data['artwork_bg_color'])
        gradient_img = create_highlight_gradient((width, height), base_color)
        
        # Add subtle vignette effect to background
        vignette_mask = create_vignette((width, height), 0.2)
        vignette_mask = vignette_mask.filter(ImageFilter.GaussianBlur(radius=150))
        gradient_img = Image.composite(
            gradient_img, 
            Image.new('RGB', (width, height), (0, 0, 0)), 
            vignette_mask
        )
        
        # Save and create clip from background
        bg_path = os.path.join(temp_dir, 'bg.png')
        gradient_img.save(bg_path)
        background = ImageClip(bg_path).set_duration(clip_duration)
        
        # Download artwork
        artwork_url = song_data['artwork_url']
        artwork_response = requests.get(artwork_url)
        artwork_path = os.path.join(temp_dir, 'artwork.jpg')
        with open(artwork_path, 'wb') as f:
            f.write(artwork_response.content)
        
        # Load artwork with Pillow and enhance
        with Image.open(artwork_path) as img:
            # Resize artwork
            img = img.resize((800, 800), Image.Resampling.LANCZOS)
            
            # Create mask for rounded corners
            mask = Image.new('L', img.size, 0)
            radius = 25  # Corner radius
            
            # Draw the rounded rectangle on the mask
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([(0, 0), (799, 799)], radius=radius, fill=255)
            
            # Create a new RGBA image
            artwork_rounded = Image.new('RGBA', img.size, (0, 0, 0, 0))
            artwork_rounded.paste(img, (0, 0), mask)
            
            # Create a subtle drop shadow
            shadow = Image.new('RGBA', (img.width + 60, img.height + 60), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            
            # Draw bottom shadow with reduced opacity
            shadow_draw.rounded_rectangle([
                (30, 30 + img.height - 20),
                (img.width + 30, img.height + 40)
            ], radius=radius, fill=(0, 0, 0, 40))
            
            # Add blur for softer shadow
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
            
            # Save shadow and artwork
            shadow_path = os.path.join(temp_dir, 'shadow.png')
            artwork_path = os.path.join(temp_dir, 'artwork.png')
            shadow.save(shadow_path)
            artwork_rounded.save(artwork_path)
        
        # Set font paths - for GitHub Actions, use fonts in the repository
        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
        outfit_bold = f"{font_dir}/Outfit-Bold.ttf"
        outfit_semibold = f"{font_dir}/Outfit-SemiBold.ttf"
        outfit_medium = f"{font_dir}/Outfit-Medium.ttf"
        outfit_regular = f"{font_dir}/Outfit-Regular.ttf"
        
        # Calculate positions starting with artwork
        artwork_x = (width - 800) / 2
        artwork_y = height * 0.25  # Position artwork at 25% from top
        
        # Create "WEEKLY ROTATION" text (left-aligned) - made bolder with semibold font
        weekly_rotation_text = TextClip(
            txt="NEW MUSIC TODAY",
            fontsize=42,
            color='white',
            font=outfit_semibold,  # Changed to semibold for more emphasis
            method='label',
            stroke_color='rgba(0,0,0,0.3)',
            stroke_width=1
        ).set_duration(clip_duration)
        
        # Create date text (right-aligned) - made lighter
        date_str = song_data.get('selected_date', datetime.datetime.now().strftime("%Y-%m-%d"))
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%b %d, %Y")
        except:
            formatted_date = date_str
            
        date_title = TextClip(
            txt=formatted_date,
            fontsize=42,
            color='rgba(255,255,255,0.7)',  # Made more transparent for lighter appearance
            font=outfit_regular,
            method='label'
        ).set_duration(clip_duration)
        
        # Position for text - right above artwork with small margin
        text_margin = 20
        header_y = artwork_y - weekly_rotation_text.size[1] - text_margin
        artwork_right = artwork_x + 800
        
        # Position shadow
        shadow_y = artwork_y - 20
        shadow_x = (width - 840) / 2
        
        # Load shadow and artwork clips
        shadow_clip = ImageClip(shadow_path).set_position((shadow_x, shadow_y))
        artwork_clip = ImageClip(artwork_path).set_position((artwork_x, artwork_y))
        
        # Maximum width for text
        max_text_width = 780
        
        # Song title with scrolling if needed
        song_title_clip = create_scrolling_text_clip(
            text=song_data['song_name'],
            fontsize=80,
            color='white',
            font=outfit_bold,
            duration=clip_duration,
            max_width=max_text_width,
            stroke_color='rgba(0,0,0,0.3)',
            stroke_width=1
        )
        
        # Artist name with scrolling if needed
        artist_name_clip = create_scrolling_text_clip(
            text=song_data['artist'],
            fontsize=48,
            color='rgba(255,255,255,0.85)',
            font=outfit_regular,
            duration=clip_duration,
            max_width=max_text_width
        )
        
        # Preview text
        preview_text = TextClip(
            txt="SONG PREVIEW",
            fontsize=24,
            color='rgba(255,255,255,0.6)',
            font=outfit_regular,
            method='label'
        ).set_duration(clip_duration)
        
        # Positioning
        artwork_bottom = artwork_y + 800
        spacing_after_artwork = 100
        spacing_between_text = 12
        
        # Center the clips horizontally
        song_title_pos = ((width - max_text_width) / 2, artwork_bottom + spacing_after_artwork)
        artist_name_pos = ((width - max_text_width) / 2, song_title_pos[1] + song_title_clip.size[1] + spacing_between_text)
        
        # Position the text clips
        song_title_clip = song_title_clip.set_position(('center', song_title_pos[1]))
        artist_name_clip = artist_name_clip.set_position(('center', artist_name_pos[1]))
        
        # Progress bar dimensions
        progress_bar_width = 800
        progress_bar_height = 6
        progress_bar_y = artist_name_pos[1] + artist_name_clip.size[1] + 60
        
        # Create progress bar background
        progress_bg = ColorClip(
            size=(progress_bar_width, progress_bar_height),
            color=(50, 50, 50)
        ).set_duration(clip_duration)
        
        progress_bg_pos = ((width - progress_bar_width) / 2, progress_bar_y)
        
        # Create animated progress bar
        def make_progress_bar_frame(t):
            progress_width = int(progress_bar_width * (t / clip_duration))
            progress_img = np.zeros((progress_bar_height, progress_bar_width, 3), dtype=np.uint8)
            
            # Create gradient colors for progress bar
            r, g, b = base_color
            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
            
            # Ensure high brightness for better contrast
            bright_h = h
            bright_s = max(0.4, min(0.9, s))
            bright_v = max(0.85, min(1.0, v * 1.5))
            
            # Convert to RGB
            bright_r, bright_g, bright_b = colorsys.hsv_to_rgb(bright_h, bright_s, bright_v)
            bright_color = (int(min(255, bright_r*255)), int(min(255, bright_g*255)), int(min(255, bright_b*255)))
            
            # Fill progress portion
            progress_img[:, :progress_width, 0] = bright_color[0]
            progress_img[:, :progress_width, 1] = bright_color[1]
            progress_img[:, :progress_width, 2] = bright_color[2]
            
            return progress_img
        
        progress_bar = VideoClip(make_frame=make_progress_bar_frame, duration=clip_duration)
        progress_bar = progress_bar.set_position(progress_bg_pos)
        
        # Position preview text under progress bar
        preview_text_pos = ((width - preview_text.size[0]) / 2, progress_bar_y + progress_bar_height + 12)
        
        # Compose final video
        final_clip = CompositeVideoClip([
            background,
            weekly_rotation_text.set_position((artwork_x, header_y)),
            date_title.set_position((artwork_right - date_title.size[0], header_y)),
            shadow_clip,
            artwork_clip,
            song_title_clip,
            artist_name_clip,
            progress_bg.set_position(progress_bg_pos),
            progress_bar,
            preview_text.set_position(preview_text_pos)
        ]).set_duration(clip_duration)
        
        # Set audio to the final clip
        final_clip = final_clip.set_audio(audio_clip)
        
        # Create output directory if it doesn't exist
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        output_dir = os.path.join("video_output", today)
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize song name and artist for filename
        safe_song_name = song_data['song_name'].replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_artist = song_data['artist'].replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Add numbered prefix (01, 02, etc.)
        filename = f"{index+1:02d}_{safe_song_name}_{safe_artist}_{today}.mp4"
        
        # Write video file with audio
        output_path = os.path.join(output_dir, filename)
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac'
        )
        
        print(f"Video saved to: {output_path}")
        
        # Upload to GCS
        bucket_name = os.environ.get('GCS_BUCKET_NAME')
        gcs_path = f"videos/{today}/individual/{filename}"
        upload_video_to_gcs(output_path, bucket_name, gcs_path)
        
        return output_path
        
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)

def fetch_songs_from_spreadsheet(spreadsheet_id):
    """Fetch songs data from Google Spreadsheet"""
    try:
        # Use the same credentials file for both GCS and Sheets
        credentials = service_account.Credentials.from_service_account_file(
            'gcp_credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly', 
                    'https://www.googleapis.com/auth/drive.readonly']
        )
        gc = gspread.authorize(credentials)
        
        # Open the spreadsheet and get the first sheet
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.sheet1
        
        # Get all values including headers
        all_values = worksheet.get_all_values()
        
        if not all_values:
            print("Spreadsheet is empty")
            return []
        
        # Extract headers and data
        headers = all_values[0]
        data = all_values[1:]
        
        # Convert to list of dictionaries
        songs_data = []
        for row in data:
            song = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    # Convert TRUE/FALSE strings to boolean
                    if header == 'create_video':
                        song[header] = row[i].upper() == 'TRUE'
                    else:
                        song[header] = row[i]
            songs_data.append(song)
        
        print(f"Fetched {len(songs_data)} songs from spreadsheet")
        return songs_data
        
    except Exception as e:
        print(f"Error fetching songs from spreadsheet: {e}")
        raise

def fetch_songs_from_gcs(bucket_name, blob_name, service_account_path=None):
    """Fetch songs data from Google Cloud Storage"""
    # Initialize GCS client
    if service_account_path:
        storage_client = storage.Client.from_service_account_json(service_account_path)
    else:
        storage_client = storage.Client()
    
    # Get bucket and blob
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Download blob as string
    content = blob.download_as_string()
    
    # Parse JSON
    songs_data = json.loads(content)
    
    return songs_data

def process_latest_songs(spreadsheet_id=None):
    """Process songs marked for video creation with today's date"""
    try:
        if spreadsheet_id is None:
            # Get spreadsheet ID from environment or use default
            spreadsheet_id = os.environ.get('SPREADSHEET_ID')
        
        # Fetch songs data from spreadsheet
        print(f"Fetching songs data from spreadsheet ID: {spreadsheet_id}")
        songs_data = fetch_songs_from_spreadsheet(spreadsheet_id)
        
        # Get today's date
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"Today's date: {today}")
        
        # Filter songs with today's date and create_video = True
        selected_songs = [
            song for song in songs_data 
            if song.get('selected_date') == today and song.get('create_video') == True
        ]
        
        print(f"Found {len(selected_songs)} songs with today's date and marked for video creation")
        
        # Generate videos for each song
        output_paths = []
        for i, song in enumerate(selected_songs):
            print(f"Generating video {i+1}/{len(selected_songs)} for '{song['song_name']}' by {song['artist']}")
            output_path = generate_music_preview_video(song, index=i)
            output_paths.append(output_path)
        
        return output_paths
        
    except Exception as e:
        print(f"Error processing songs: {e}")
        raise

if __name__ == "__main__":
    # Initialize GCP credentials
    init_gcp()
    
    # Configuration - use environment variable for spreadsheet ID
    spreadsheet_id = os.environ.get('SPREADSHEET_ID')
    
    # Process songs
    output_paths = process_latest_songs(spreadsheet_id=spreadsheet_id)
    
    if output_paths:
        print(f"\nSuccessfully generated {len(output_paths)} videos:")
        for path in output_paths:
            print(f"- {path}")
    else:
        print("No videos were generated")

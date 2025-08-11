import os
import datetime
import time
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Configuration
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
COMMENT_TEMPLATE = os.environ.get('YOUTUBE_COMMENT_TEMPLATE', "{artist_name} deserved a spot in the Weekly Rotation with this one ❤️")

def init_gcp():
    """Initialize GCP credentials"""
    service_account_json = os.environ.get('GCP_SA_KEY')
    with open('gcp_credentials.json', 'w') as f:
        f.write(service_account_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_credentials.json'

def authenticate_youtube():
    """Authenticate and return YouTube API service using refresh token"""
    try:
        # Get refresh token from environment (using Weekly Rotation account credentials)
        refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN_WR')
        client_id = os.environ.get('YOUTUBE_CLIENT_ID_WR') 
        client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET_WR')
        
        if not all([refresh_token, client_id, client_secret]):
            raise ValueError("Weekly Rotation YouTube credentials missing. Please check YOUTUBE_REFRESH_TOKEN_WR, YOUTUBE_CLIENT_ID_WR, and YOUTUBE_CLIENT_SECRET_WR environment variables.")
        
        print("🔑 Authenticating with YouTube API...")
        
        # Create credentials from refresh token
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        
        # Refresh the token
        creds.refresh(Request())
        
        # Build YouTube service
        youtube = build('youtube', 'v3', credentials=creds)
        print("✅ YouTube authentication successful")
        return youtube
        
    except Exception as e:
        print(f"❌ YouTube authentication failed: {e}")
        raise

def fetch_songs_from_spreadsheet():
    """Fetch songs from Google Spreadsheet"""
    try:
        init_gcp()
        credentials = service_account.Credentials.from_service_account_file(
            'gcp_credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly']
        )
        gc = gspread.authorize(credentials)
        
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1
        
        all_values = worksheet.get_all_values()
        
        if not all_values:
            return []
        
        headers = all_values[0]
        data = all_values[1:]
        
        songs_data = []
        for row in data:
            song = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    if header == 'create_video':
                        song[header] = row[i].upper() == 'TRUE'
                    else:
                        song[header] = row[i]
            songs_data.append(song)
        
        return songs_data
        
    except Exception as e:
        print(f"Error fetching songs: {e}")
        return []

def get_today_songs():
    """Get today's songs with create_video = TRUE"""
    songs = fetch_songs_from_spreadsheet()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    today_songs = [
        song for song in songs 
        if song.get('selected_date') == today and song.get('create_video') == True
    ]
    
    print(f"Found {len(today_songs)} songs for today with create_video=TRUE")
    return today_songs

def create_comment_text(song_data):
    """Create personalized comment text using the template"""
    artist_name = song_data.get('artist', 'This artist')
    comment_text = COMMENT_TEMPLATE.format(artist_name=artist_name)
    return comment_text

def post_comment_on_video(youtube, video_id, comment_text, song_info):
    """Attempt to post a comment on a YouTube video"""
    try:
        print(f"💬 Posting comment on video {video_id}...")
        print(f"🎵 Song: '{song_info.get('song_name', '')}' by {song_info.get('artist', '')}")
        print(f"📝 Comment: '{comment_text}'")
        
        # Create comment thread
        comment_thread = {
            'snippet': {
                'videoId': video_id,
                'topLevelComment': {
                    'snippet': {
                        'textOriginal': comment_text
                    }
                }
            }
        }
        
        response = youtube.commentThreads().insert(
            part='snippet',
            body=comment_thread
        ).execute()
        
        comment_id = response['id']
        print(f"✅ Comment posted successfully!")
        print(f"🆔 Comment ID: {comment_id}")
        print(f"🔗 Comment URL: https://www.youtube.com/watch?v={video_id}&lc={comment_id}")
        
        return True, comment_id
        
    except Exception as e:
        error_reason = str(e)
        song_name = song_info.get('song_name', 'Unknown')
        
        # Handle specific YouTube API errors gracefully
        if ("commentsDisabled" in error_reason or 
            "disabled" in error_reason.lower() or 
            "This action is not available for the item" in error_reason or
            "mfkWrite" in error_reason):
            print(f"⏭️  Comments are disabled on video {video_id} for '{song_name}' - skipping gracefully")
            return False, "comments_disabled"
        elif "forbidden" in error_reason.lower():
            if "comment" in error_reason.lower():
                print(f"🚫 Comments are restricted on video {video_id} for '{song_name}' - skipping")
                return False, "comments_restricted"
            else:
                print(f"🔒 Insufficient permissions to comment on video {video_id} for '{song_name}'")
                return False, "insufficient_permissions"
        elif "videoNotFound" in error_reason or "not found" in error_reason.lower():
            print(f"❌ Video {video_id} not found for '{song_name}'")
            return False, "video_not_found"
        elif "quotaExceeded" in error_reason or "quota" in error_reason.lower():
            print(f"⏰ YouTube API quota exceeded - try again later")
            return False, "quota_exceeded"
        else:
            print(f"❌ Unexpected error posting comment on {video_id} for '{song_name}': {error_reason}")
            return False, "unknown_error"

def main():
    """Main function to post comments on today's selected songs"""
    print("🚀 Starting YouTube Comment Posting Pipeline")
    print("=" * 60)
    
    try:
        # Get today's songs
        songs = get_today_songs()
        if not songs:
            print("No songs found for today with create_video=TRUE")
            return
        
        # Authenticate with YouTube
        youtube = authenticate_youtube()
        
        # Track statistics
        total_songs = len(songs)
        successful_comments = 0
        skipped_comments = 0
        failed_comments = 0
        
        print(f"\n🎯 Processing {total_songs} songs for commenting...")
        print("=" * 40)
        
        for i, song in enumerate(songs, 1):
            print(f"\n[{i}/{total_songs}] Processing song:")
            
            # Get video ID
            video_id = song.get('youtube_video_id', '').strip()
            
            if not video_id:
                print(f"⏭️  No YouTube video ID found for '{song.get('song_name', '')}' - skipping")
                skipped_comments += 1
                continue
            
            # Create comment text
            comment_text = create_comment_text(song)
            
            # Post comment with rate limiting
            success, result = post_comment_on_video(youtube, video_id, comment_text, song)
            
            if success:
                successful_comments += 1
            elif result in ["comments_disabled", "comments_restricted", "video_not_found"]:
                skipped_comments += 1
            else:
                failed_comments += 1
            
            # Rate limiting - wait between comments to avoid hitting YouTube limits
            if i < total_songs:  # Don't wait after the last song
                print("⏱️  Waiting 30 seconds before next comment...")
                time.sleep(30)
        
        # Final summary
        print("\n" + "=" * 60)
        print("🎉 YouTube Commenting Pipeline Complete!")
        print(f"📊 Summary:")
        print(f"   ✅ Successful comments: {successful_comments}")
        print(f"   ⏭️  Skipped (disabled/restricted): {skipped_comments}")
        print(f"   ❌ Failed comments: {failed_comments}")
        print(f"   📈 Success rate: {(successful_comments / total_songs * 100):.1f}%")
        
        if successful_comments > 0:
            print(f"\n🔥 Posted {successful_comments} promotional comments for Weekly Rotation playlist!")
        
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {e}")
        print("🔧 Check your environment variables and API credentials")

if __name__ == "__main__":
    main()
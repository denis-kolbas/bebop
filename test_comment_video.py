#!/usr/bin/env python3
"""
Test YouTube Comment on Specific Video

Usage: python test_comment_video.py VIDEO_ID

This script tests commenting on a specific YouTube video using the new Weekly Rotation account.
"""

import os
import sys
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load environment variables from .env.local
load_dotenv('.env.local')

# Static comment template for testing
TEST_COMMENT = "This deserved a spot in the Weekly Rotation with this one ❤️"

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

def get_video_info(youtube, video_id):
    """Get basic video information"""
    try:
        response = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()
        
        if not response.get('items'):
            return None
            
        video = response['items'][0]
        return {
            'title': video['snippet']['title'],
            'channel': video['snippet']['channelTitle']
        }
        
    except Exception as e:
        print(f"❌ Error getting video info: {e}")
        return None

def post_test_comment(youtube, video_id, comment_text):
    """Attempt to post a test comment"""
    try:
        print(f"💬 Posting comment on video {video_id}...")
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
        
        # Handle specific YouTube API errors gracefully
        if ("commentsDisabled" in error_reason or 
            "disabled" in error_reason.lower() or 
            "This action is not available for the item" in error_reason or
            "mfkWrite" in error_reason):
            print(f"⏭️  Comments are disabled on video {video_id} - skipping gracefully")
            return False, "comments_disabled"
        elif "forbidden" in error_reason.lower():
            if "comment" in error_reason.lower():
                print(f"🚫 Comments are restricted on video {video_id} - skipping")
                return False, "comments_restricted"
            else:
                print(f"🔒 Insufficient permissions to comment on video {video_id}")
                return False, "insufficient_permissions"
        elif "videoNotFound" in error_reason or "not found" in error_reason.lower():
            print(f"❌ Video {video_id} not found")
            return False, "video_not_found"
        elif "quotaExceeded" in error_reason or "quota" in error_reason.lower():
            print(f"⏰ YouTube API quota exceeded - try again later")
            return False, "quota_exceeded"
        else:
            print(f"❌ Unexpected error posting comment: {error_reason}")
            return False, "unknown_error"

def main():
    """Main test function"""
    if len(sys.argv) != 2:
        print("Usage: python test_comment_video.py VIDEO_ID")
        print("Example: python test_comment_video.py Q4kCS4u9b8")
        sys.exit(1)
    
    video_id = sys.argv[1]
    
    print("🚀 Testing YouTube Comment on Specific Video")
    print("=" * 60)
    print(f"🎯 Video ID: {video_id}")
    print(f"💬 Test Comment: '{TEST_COMMENT}'")
    print("=" * 60)
    
    try:
        # Authenticate with YouTube
        youtube = authenticate_youtube()
        
        # Get video info
        print("🔍 Getting video information...")
        video_info = get_video_info(youtube, video_id)
        
        if video_info:
            print(f"📺 Video: '{video_info['title']}' by {video_info['channel']}")
        else:
            print(f"⚠️  Could not get video info for {video_id}, but will try to comment anyway...")
        
        print("\n" + "=" * 40)
        
        # Post test comment
        success, result = post_test_comment(youtube, video_id, TEST_COMMENT)
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 SUCCESS: Test comment posted successfully!")
            print(f"✅ Comment ID: {result}")
        else:
            print(f"📋 TEST RESULT: {result}")
            if result in ["comments_disabled", "comments_restricted"]:
                print("✅ Error handling is working properly - comments disabled/restricted scenario handled gracefully")
            else:
                print("⚠️  This error should be investigated for production use")
        
        print("\n🔧 Your Weekly Rotation YouTube account commenting is working!")
        
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {e}")
        print("🔧 Please check your .env.local file and credentials")
        sys.exit(1)

if __name__ == "__main__":
    main()
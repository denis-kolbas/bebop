#!/usr/bin/env python3
"""
Test get_song_views function directly
"""

import os
from ytmusicapi import YTMusic, OAuthCredentials

# OAuth credentials
CLIENT_ID = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"

def test_get_song_views(song_name, artist_name):
    try:
        ytmusic = YTMusic('client_secret_YOUR_CLIENT_ID_HERE.json', oauth_credentials=OAuthCredentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        ))
        search_query = f"{song_name} {artist_name} official"
        print(f"🔍 YouTube search for: '{search_query}'")
        results = ytmusic.search(search_query, filter='videos', limit=1)
        
        if results and len(results) > 0:
            video_data = results[0]
            print(f"📋 Found video data keys: {list(video_data.keys())}")
            
            # Get view count
            view_count = '0'
            for field in ['views', 'videoCountText', 'viewCount']:
                if field in video_data:
                    view_count = video_data[field]
                    print(f"📊 Found views in field '{field}': {view_count}")
                    break
            
            # Get video ID for commenting - try multiple possible field names
            video_id = ''
            for field in ['videoId', 'id', 'video_id']:
                if field in video_data and video_data[field]:
                    video_id = video_data[field]
                    print(f"🎥 Found video ID in field '{field}': {video_id}")
                    break
            
            if not video_id:
                print(f"⚠️  No video ID found in video_data: {video_data}")
            
            result = {
                'views': view_count,
                'youtube_video_id': video_id
            }
            print(f"✅ Returning: {result}")
            return result
        else:
            print(f"❌ No YouTube results found for: {search_query}")
            return {'views': '0', 'youtube_video_id': ''}
    except Exception as e:
        print(f"YouTube search error for '{song_name}' by '{artist_name}': {e}")
        return {'views': '0', 'youtube_video_id': ''}

if __name__ == "__main__":
    # Test with a specific song
    result = test_get_song_views("enjoy the ride", "almost monday")
    print(f"\nFinal result: {result}")
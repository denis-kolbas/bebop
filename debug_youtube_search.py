#!/usr/bin/env python3
"""
Debug YouTube Search for Video IDs

This script helps debug what ytmusicapi is returning for video searches.
"""

import os
from ytmusicapi import YTMusic, OAuthCredentials

# OAuth credentials (from the old account)
CLIENT_ID = "YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"

def debug_youtube_search(song_name, artist_name):
    """Debug YouTube search to see what fields are available"""
    try:
        # Try without authentication first (public search should work)
        ytmusic = YTMusic()
        search_query = f"{song_name} {artist_name} official"
        print(f"🔍 Searching for: '{search_query}'")
        
        results = ytmusic.search(search_query, filter='videos', limit=3)
        
        if results and len(results) > 0:
            print(f"📊 Found {len(results)} results")
            
            for i, video_data in enumerate(results):
                print(f"\n--- Result {i+1} ---")
                print(f"Available fields: {list(video_data.keys())}")
                
                # Print all fields and their values
                for key, value in video_data.items():
                    if isinstance(value, (str, int, float)):
                        print(f"  {key}: {value}")
                    elif isinstance(value, dict):
                        print(f"  {key}: {dict}")
                    elif isinstance(value, list):
                        print(f"  {key}: [list with {len(value)} items]")
                    else:
                        print(f"  {key}: {type(value)}")
                
                # Look for video ID specifically
                potential_id_fields = ['videoId', 'id', 'video_id', 'youtubeId', 'browseId']
                print(f"\n🎥 Checking for video ID fields:")
                for field in potential_id_fields:
                    if field in video_data:
                        print(f"  ✅ {field}: {video_data[field]}")
                    else:
                        print(f"  ❌ {field}: not found")
        else:
            print("❌ No results found")
            
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Test with a few songs"""
    test_songs = [
        ("enjoy the ride", "almost monday"),
        ("Bowery", "Zach Bryan"),
        ("Anti-Hero", "Taylor Swift")
    ]
    
    for song, artist in test_songs:
        print("=" * 60)
        debug_youtube_search(song, artist)
        print("\n")

if __name__ == "__main__":
    main()
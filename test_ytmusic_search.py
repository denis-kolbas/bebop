#!/usr/bin/env python3
"""
Test ytmusicapi search with authentication using .env.local
Usage: python test_ytmusic_search.py "song name artist name"
"""

import os
import sys
import json
from dotenv import load_dotenv
from ytmusicapi import YTMusic
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load environment variables from .env.local
load_dotenv('.env.local')

def test_ytmusic_search(search_query):
    """Test ytmusicapi search with proper authentication"""
    try:
        # Get credentials from environment (Weekly Rotation account)
        refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN_WR')
        client_id = os.environ.get('YOUTUBE_CLIENT_ID_WR')
        client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET_WR')
        
        print(f"🔍 Search query: '{search_query}'")
        print(f"🔑 Using refresh token: {'✅ Found' if refresh_token else '❌ Missing'}")
        print(f"🔑 Using client ID: {'✅ Found' if client_id else '❌ Missing'}")
        print(f"🔑 Using client secret: {'✅ Found' if client_secret else '❌ Missing'}")
        print("=" * 60)
        
        if refresh_token and client_id and client_secret:
            # Create credentials with refresh token
            print("🔐 Creating authenticated YTMusic instance...")
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token"
            )
            creds.refresh(Request())
            ytmusic = YTMusic()
            ytmusic._auth = creds
            print("✅ Authentication successful")
        else:
            # Fallback to no authentication
            print("⚠️  Missing credentials, using public search...")
            ytmusic = YTMusic()
        
        print(f"\n🔍 Searching for: '{search_query}'")
        results = ytmusic.search(search_query, filter='videos', limit=3)
        
        print(f"\n📊 Found {len(results)} results")
        print("=" * 60)
        
        # Output full response
        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_ytmusic_search.py \"search query\"")
        print("Example: python test_ytmusic_search.py \"enjoy the ride almost monday\"")
        sys.exit(1)
    
    search_query = sys.argv[1]
    results = test_ytmusic_search(search_query)
    
    print(f"\n🎯 Search completed. Found {len(results)} results.")

if __name__ == "__main__":
    main()
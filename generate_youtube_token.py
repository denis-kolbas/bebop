#!/usr/bin/env python3
"""
YouTube OAuth Token Generator

This script helps you generate a refresh token for your YouTube account.
Place your client_secret JSON file in this directory and run the script.
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Required scopes for YouTube operations
SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',  # For commenting
    'https://www.googleapis.com/auth/youtube'  # For playlist management and uploads
]

def find_client_secret_file():
    """Find the client secret JSON file in the current directory"""
    current_dir = os.getcwd()
    
    # Look for JSON files that look like client secrets
    for filename in os.listdir(current_dir):
        if filename.startswith('client_secret_') and filename.endswith('.json'):
            return filename
        elif filename == 'client_secret.json':
            return filename
        elif filename == 'credentials.json':
            return filename
    
    return None

def load_client_config(filename):
    """Load and return client configuration from JSON file"""
    try:
        with open(filename, 'r') as f:
            config = json.load(f)
        
        # Handle both formats (installed vs web)
        if 'installed' in config:
            return config['installed']
        elif 'web' in config:
            return config['web']
        else:
            return config
            
    except Exception as e:
        print(f"❌ Error reading {filename}: {e}")
        return None

def generate_refresh_token(client_config):
    """Generate refresh token using OAuth flow"""
    try:
        print("🔑 Starting OAuth flow...")
        
        # Create flow using client config
        flow = InstalledAppFlow.from_client_config(
            {'installed': client_config}, 
            SCOPES
        )
        
        print("🌐 Opening browser for authentication...")
        print("📋 Please:")
        print("   1. Log in with your NEW account (the one with the Weekly Rotation playlist)")
        print("   2. Grant all requested permissions")
        print("   3. Complete the authorization process")
        print()
        
        # Run local server flow
        creds = flow.run_local_server(port=0)
        
        print("✅ Authentication successful!")
        
        # Test the credentials by getting channel info
        youtube = build('youtube', 'v3', credentials=creds)
        response = youtube.channels().list(part='snippet', mine=True).execute()
        
        if response.get('items'):
            channel_info = response['items'][0]['snippet']
            channel_title = channel_info.get('title', 'Unknown')
            print(f"🎬 Authenticated as: {channel_title}")
        
        return creds.refresh_token
        
    except Exception as e:
        print(f"❌ OAuth flow failed: {e}")
        return None

def main():
    """Main function"""
    print("🚀 YouTube OAuth Token Generator")
    print("=" * 50)
    
    # Find client secret file
    client_secret_file = find_client_secret_file()
    
    if not client_secret_file:
        print("❌ No client secret file found!")
        print("💡 Please:")
        print("   1. Download your OAuth client credentials from Google Cloud Console")
        print("   2. Save it as 'client_secret.json' in this directory")
        print("   3. Run this script again")
        return
    
    print(f"📁 Found client secret file: {client_secret_file}")
    
    # Load client configuration
    client_config = load_client_config(client_secret_file)
    
    if not client_config:
        print("❌ Failed to load client configuration")
        return
    
    # Extract client info
    client_id = client_config.get('client_id', 'Unknown')
    print(f"🔑 Client ID: {client_id[:20]}...")
    
    print("\n" + "=" * 30)
    
    # Generate refresh token
    refresh_token = generate_refresh_token(client_config)
    
    if refresh_token:
        print("\n" + "=" * 50)
        print("🎉 SUCCESS! Your refresh token has been generated:")
        print("-" * 50)
        print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
        print("-" * 50)
        print()
        print("📋 Next steps:")
        print("1. Copy the refresh token above")
        print("2. Go to your GitHub repository settings")
        print("3. Update the YOUTUBE_REFRESH_TOKEN secret with this value")
        print("4. Also update these secrets with your new credentials:")
        print(f"   YOUTUBE_CLIENT_ID={client_config.get('client_id', '')}")
        print(f"   YOUTUBE_CLIENT_SECRET={client_config.get('client_secret', '')}")
        print()
        print("✅ After updating GitHub secrets, your pipeline will use the new account!")
        
    else:
        print("\n❌ Failed to generate refresh token")
        print("🔧 Please check your client credentials and try again")

if __name__ == "__main__":
    main()
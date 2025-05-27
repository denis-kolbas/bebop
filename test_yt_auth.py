import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# YouTube API scope - broader scope needed
SCOPES = ['https://www.googleapis.com/auth/youtube']

# Path to your downloaded credentials file
CLIENT_SECRETS_FILE = "path/to/your/client_secret.json"

def authenticate_youtube():
    """Authenticate and return YouTube API service"""
    creds = None
    
    # Check if token.json exists (saved credentials)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    # Build YouTube service
    youtube = build('youtube', 'v3', credentials=creds)
    return youtube

def test_channel_access(youtube):
    """Test if we can access channel info"""
    try:
        request = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        response = request.execute()
        
        if response['items']:
            channel = response['items'][0]
            print(f"✅ Successfully authenticated!")
            print(f"Channel: {channel['snippet']['title']}")
            print(f"Subscribers: {channel['statistics']['subscriberCount']}")
            return True
        else:
            print("❌ No channel found")
            return False
            
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

def main():
    print("Testing YouTube API authentication...")
    
    # Update this path to your downloaded credentials file
    global CLIENT_SECRETS_FILE
    CLIENT_SECRETS_FILE = input("Enter path to your client_secret.json file: ")
    
    try:
        youtube = authenticate_youtube()
        test_channel_access(youtube)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
# Replace direct credential paths with environment variables
import os
import base64
import json

# Spotify API credentials from environment variables
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"  # Still needed for setup
SPOTIFY_PLAYLIST_ID = "23jlRqLpPrVUPhMuGGtfX9"

# For non-interactive auth, use refresh token
SPOTIFY_REFRESH_TOKEN = os.environ.get("SPOTIFY_REFRESH_TOKEN")

# GCP configuration
GCS_BUCKET_NAME = "bebop_data"
GCS_BLOB_NAME = "selected_songs.json"

def initialize_gcp():
    """Initialize GCP credentials from environment variable"""
    # Create a temporary file with the service account JSON
    gcp_sa_content = os.environ.get("GCP_SA_KEY")
    temp_sa_file = "/tmp/gcp_sa.json"
    with open(temp_sa_file, "w") as f:
        f.write(gcp_sa_content)
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_sa_file
    logging.info("GCP credentials initialized")

def get_spotify_client():
    """Create an authenticated Spotify client using refresh token"""
    try:
        scope = "playlist-modify-public playlist-read-private playlist-modify-private"
        
        # Use refresh token instead of OAuth flow for non-interactive auth
        auth_manager = spotipy.oauth2.SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=scope,
            cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path="/tmp/spotify_cache")
        )
        
        # Set the refresh token explicitly
        token_info = auth_manager.refresh_access_token(SPOTIFY_REFRESH_TOKEN)
        auth_manager.cache_handler.save_token_to_cache(token_info)
        
        sp = spotipy.Spotify(auth_manager=auth_manager)
        logging.info("Spotify client authenticated successfully")
        return sp
    except Exception as e:
        logging.error(f"Failed to authenticate with Spotify: {str(e)}")
        raise

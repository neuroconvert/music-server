import os
import time
import shutil
import fcntl
import logging
import requests
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC, error

# --- CONFIGURATION ---
SPOTIFY_CLIENT_ID = '6d8134abeb0f4a3a9124bebbf9590480'
SPOTIFY_CLIENT_SECRET = '9272483688b54c28a0949b19ca5fabd9'

INBOX = "/inbox"
MUSIC = "/music"
ASIS_DIR = os.path.join(MUSIC, "Recommended_AsIs")
LOG_DIR = "/logs"
COPY_DELAY = 300  # 5 minutes without modification before processing
AUDIO_EXT = {'.mp3', '.flac', '.m4a', '.ogg', '.wav'}

# --- LOGGING SETUP ---
def setup_logger(name, log_file):
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file))
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

sys_log = setup_logger('system', 'system.log')
process_log = setup_logger('processor', 'processing.log')

sp_auth = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=sp_auth)

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_audio_files(directory):
    return [os.path.join(root, f) for root, _, files in os.walk(directory) 
            for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXT]

def cleanup_empty_folders(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        if root == directory: continue
        if not get_audio_files(root):
            try:
                shutil.rmtree(root)
            except Exception:
                pass

def extract_original_artist(file_path):
    """Attempts to read the original Artist tag from the MP3 before overwriting it."""
    try:
        audio = MP3(file_path, ID3=ID3)
        if 'TPE1' in audio.tags:
            return str(audio.tags['TPE1'])
    except Exception:
        pass
    return ""

def process_inbox():
    for file_path in get_audio_files(INBOX):
        if time.time() - os.path.getmtime(file_path) < COPY_DELAY:
            continue
            
        filename = os.path.basename(file_path)
        name_without_ext, ext = os.path.splitext(filename)
        
        # 1. Try to guess artist from the folder name
        path_parts = file_path.split(os.sep)
        guessed_artist = path_parts[-2] if len(path_parts) >= 3 and path_parts[-2] != 'inbox' else ""
        
        # 2. If no folder name exists, try reading the MP3's internal Artist tag
        if not guessed_artist and ext.lower() == '.mp3':
            guessed_artist = extract_original_artist(file_path)

        search_query = f"{name_without_ext} {guessed_artist}".strip()
        process_log.info(f"Processing '{filename}'. Searching Spotify for: '{search_query}'")
        
        try:
            results = sp.search(q=search_query, type='track', limit=1)
            tracks = results.get('tracks', {}).get('items', [])
            
            if not tracks:
                process_log.warning(f"No Spotify match for '{filename}'. Moving to As-Is.")
                rel_path = os.path.relpath(file_path, INBOX)
                dest_path = os.path.join(ASIS_DIR, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(file_path, dest_path)
                continue
            
            track = tracks[0]
            sp_title = track['name']
            sp_artist = track['artists'][0]['name']
            sp_album = track['album']['name']
            sp_year = track['album']['release_date'][:4]
            sp_cover_url = track['album']['images'][0]['url'] if track['album']['images'] else None

            process_log.info(f"Match found! Tagging as: {sp_artist} - {sp_title} ({sp_year})")

            if ext.lower() == '.mp3':
                try:
                    audio = MP3(file_path, ID3=ID3)
                except error:
                    audio = MP3(file_path)
                    audio.add_tags()
                
                audio.tags.clear()
                audio.tags.add(TIT2(encoding=3, text=sp_title))
                audio.tags.add(TPE1(encoding=3, text=sp_artist))
                audio.tags.add(TALB(encoding=3, text=sp_album))
                audio.tags.add(TDRC(encoding=3, text=sp_year))
                
                if sp_cover_url:
                    img_data = requests.get(sp_cover_url).content
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data))
                
                audio.save()

            final_dir = os.path.join(MUSIC, clean_filename(sp_artist), clean_filename(sp_album))
            os.makedirs(final_dir, exist_ok=True)
            
            final_filename = f"{clean_filename(sp_title)}{ext}"
            final_path = os.path.join(final_dir, final_filename)
            
            if os.path.exists(final_path):
                final_path = os.path.join(final_dir, f"{clean_filename(sp_title)}_{int(time.time())}{ext}")
                
            shutil.move(file_path, final_path)
            process_log.info(f"Successfully organized: {final_path}")

        except Exception as e:
            process_log.error(f"Failed to process {filename}: {e}")

def main():
    lock_file = open("/tmp/music_organizer.lock", "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    sys_log.info("Custom Spotify Auto-Tagger Started.")
    
    while True:
        try:
            if get_audio_files(INBOX):
                process_inbox()
            cleanup_empty_folders(INBOX)
                
        except Exception as e:
            sys_log.error(f"Error in main loop: {e}")
            
        time.sleep(300)

if __name__ == "__main__":
    main()
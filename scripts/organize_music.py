import os
import time
import shutil
import fcntl
import logging
import requests
import re
import asyncio
import mutagen
from shazamio import Shazam
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, APIC, error

# --- CONFIGURATION ---
INBOX = "/inbox"
STAGING = "/staging"
MUSIC = "/music"
ASIS_DIR = os.path.join(MUSIC, "Recommended_AsIs")
LOG_DIR = "/logs"
COPY_DELAY = 60  # 1 minute network copy delay
AUDIO_EXT = {'.mp3', '.flac', '.m4a', '.ogg', '.wav'}

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

def clean_filename(name):
    # Fixed escape characters for Windows/Linux safe filenames
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

def get_audio_files(directory):
    return [os.path.join(root, f) for root, _, files in os.walk(directory) 
            for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXT]

def cleanup_empty_folders(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        if root == directory: 
            continue
        if not os.listdir(root):
            try: shutil.rmtree(root)
            except Exception: pass

async def process_pipeline():
    shazam = Shazam()
    
    # STEP 1: INBOX -> STAGING (Shazam Recognition & Tagging)
    for file_path in get_audio_files(INBOX):
        if time.time() - os.path.getmtime(file_path) < COPY_DELAY:
            continue
            
        filename = os.path.basename(file_path)
        _, ext = os.path.splitext(filename)
        
        process_log.info(f"Phase 1: Listening to '{filename}' from Inbox...")
        
        try:
            out = await shazam.recognize(file_path)
            track = out.get('track')
            
            if not track:
                process_log.warning(f"Shazam failed for '{filename}'. Extracting existing ID3 tags to organize in As-Is.")
                
                asis_artist = "Unknown Artist"
                asis_album = "Unknown Album"
                asis_title = ""
                
                # Extract tags (including Title) using both MP3 and mutagen fallback for other formats
                if ext.lower() == '.mp3':
                    try:
                        audio = MP3(file_path, ID3=ID3)
                        if 'TPE1' in audio.tags: asis_artist = str(audio.tags['TPE1'])
                        if 'TALB' in audio.tags: asis_album = str(audio.tags['TALB'])
                        if 'TIT2' in audio.tags: asis_title = str(audio.tags['TIT2'])
                    except Exception: pass
                else:
                    try:
                        audio = mutagen.File(file_path, easy=True)
                        if audio:
                            if 'artist' in audio: asis_artist = str(audio['artist'][0])
                            if 'album' in audio: asis_album = str(audio['album'][0])
                            if 'title' in audio: asis_title = str(audio['title'][0])
                    except Exception: pass
                
                asis_target_dir = os.path.join(ASIS_DIR, clean_filename(asis_artist), clean_filename(asis_album))
                os.makedirs(asis_target_dir, exist_ok=True)
                
                # 1. Determine the new filename (Title or Timestamp)
                if asis_title.strip():
                    new_filename = f"{clean_filename(asis_title)}{ext}"
                else:
                    new_filename = f"{int(time.time())}{ext}"
                    
                dest_path = os.path.join(asis_target_dir, new_filename)
                
                # 2. Smart Size-Based Duplicate Check
                if os.path.exists(dest_path):
                    src_size = os.path.getsize(file_path)
                    dest_size = os.path.getsize(dest_path)
                    
                    if src_size == dest_size:
                        # Sizes match exactly -> It's the same song -> Delete duplicate
                        process_log.info(f"Exact duplicate found in As-Is (Same Name & Size): '{new_filename}'. Deleting duplicate.")
                        os.remove(file_path)
                        continue
                    else:
                        # Different sizes -> Different songs sharing the same name -> Append timestamp
                        name_no_ext, extension = os.path.splitext(new_filename)
                        new_filename = f"{name_no_ext}_{int(time.time())}{extension}"
                        dest_path = os.path.join(asis_target_dir, new_filename)
                        process_log.info(f"Name collision in As-Is (Different Size). Saving as '{new_filename}'.")
                    
                shutil.move(file_path, dest_path)
                process_log.info(f"Moved to As-Is: {dest_path}")
                continue

            shazam_title = track.get('title', 'Unknown Title')
            shazam_artist = track.get('subtitle', 'Unknown Artist')
            shazam_cover = track.get('images', {}).get('coverarthq')
            shazam_genre = track.get('genres', {}).get('primary', '')
            
            shazam_album = "Unknown Album"
            shazam_year = "2024"
            for section in track.get('sections', []):
                if section.get('type') == 'SONG':
                    for meta in section.get('metadata', []):
                        if meta.get('title') == 'Album': shazam_album = meta.get('text')
                        elif meta.get('title') == 'Released': shazam_year = meta.get('text')

            process_log.info(f"Match found! Tagging as: {shazam_artist} - {shazam_title}")

            if ext.lower() == '.mp3':
                try: audio = MP3(file_path, ID3=ID3)
                except error:
                    audio = MP3(file_path)
                    audio.add_tags()
                
                audio.tags.clear()
                audio.tags.add(TIT2(encoding=3, text=shazam_title))
                audio.tags.add(TPE1(encoding=3, text=shazam_artist))
                audio.tags.add(TALB(encoding=3, text=shazam_album))
                audio.tags.add(TDRC(encoding=3, text=shazam_year))
                if shazam_genre: audio.tags.add(TCON(encoding=3, text=shazam_genre))
                
                if shazam_cover:
                    try:
                        img_data = await asyncio.to_thread(requests.get, shazam_cover)
                        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data.content))
                    except Exception:
                        pass
                
                audio.save()

            staging_dir = os.path.join(STAGING, clean_filename(shazam_artist), clean_filename(shazam_album))
            os.makedirs(staging_dir, exist_ok=True)
            
            staging_filename = f"{clean_filename(shazam_title)}{ext}"
            staging_path = os.path.join(staging_dir, staging_filename)
            live_music_path = os.path.join(MUSIC, clean_filename(shazam_artist), clean_filename(shazam_album), staging_filename)
            
            # --- STRICT DUPLICATE DELETION FOR STAGING ---
            if os.path.exists(live_music_path) or os.path.exists(staging_path):
                process_log.info(f"Duplicate Match! '{shazam_artist} - {shazam_title}' already exists in library. Deleting new copy.")
                os.remove(file_path)
                continue
            
            shutil.move(file_path, staging_path)
            process_log.info(f"Moved to Staging: {staging_path}")

        except Exception as e:
            process_log.error(f"Failed to process {filename}: {e}")
            
        await asyncio.sleep(2) 

    # STEP 2: STAGING -> LIVE MUSIC FOLDER
    for file_path in get_audio_files(STAGING):
        rel_path = os.path.relpath(file_path, STAGING)
        final_path = os.path.join(MUSIC, rel_path)
        final_dir = os.path.dirname(final_path)
        
        os.makedirs(final_dir, exist_ok=True)
        
        # --- STRICT DUPLICATE DELETION FOR STEP 2 (NO TIMESTAMPS!) ---
        if os.path.exists(final_path):
            process_log.info(f"Duplicate caught during publish: {os.path.basename(final_path)}. Deleting new copy.")
            os.remove(file_path)
            continue
            
        shutil.move(file_path, final_path)
        process_log.info(f"Phase 2: Published to Live Music Library: {final_path}")

async def main_loop():
    sys_log.info("Advanced Shazam Pipeline (Inbox -> Staging -> Live) Started.")
    while True:
        try:
            await process_pipeline()
            cleanup_empty_folders(INBOX)
            cleanup_empty_folders(STAGING)
        except Exception as e:
            sys_log.error(f"Error in main loop: {e}")
        
        await asyncio.sleep(300)

def main():
    lock_file = open("/tmp/music_organizer.lock", "w")
    try: fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: return

    asyncio.run(main_loop())

if __name__ == "__main__":
    main()
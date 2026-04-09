# 🎵 NeuroConvert Music Server

A fully automated, self-hosted music streaming platform powered by **Navidrome** and an intelligent **Shazamio** ingestion pipeline. 

This system acts as a smart music ingestion engine. You simply upload raw, untagged audio files via a sleek Web Dashboard or drop them into an `inbox` folder. A custom Python microservice automatically identifies the song using Shazam's acoustic fingerprinting, downloads the correct album art, tags the ID3 metadata, securely handles duplicates, organizes the files into clean directories, and instantly publishes them to a live streaming server accessible anywhere.

Live instance: [https://music.neuroconvert.com](https://music.neuroconvert.com)

---

## ✨ Features

* **Interactive Web Dashboard:** A beautiful Drag-and-Drop UI that lets you upload, preview Shazam matches, and manually correct metadata before submitting files to the server.
* **Automated Acoustic Fingerprinting:** Identifies music purely by its audio signature using Shazam's engine—no existing tags required.
* **Strict Duplicate Deletion:** Completely eliminates library clutter. If a song already exists in your live library (whether fully tagged by Shazam or stored in the fallback folder), new incoming duplicates are instantly and safely deleted.
* **Auto-Tagging & Cover Art:** Automatically writes perfect ID3 tags (`Artist`, `Title`, `Album`, `Release Year`, `Genre`) and embeds high-quality downloaded album covers directly into the `.mp3` files.
* **Cyrillic & Unicode Support:** Flawlessly handles Ukrainian, Russian, and other international characters in filenames and metadata.
* **Intelligent Fallback:** If Shazam fails to identify a track, the system extracts whatever existing ID3 tags the file has and safely moves it to an organized `Recommended_AsIs` folder.
* **High-Performance Streaming:** Powered by Navidrome, offering instantaneous playback and compatibility with any Subsonic client (Symfonium, DSub, ultrasonic, etc.).

---

## 🏗️ Architecture

The system is deployed via Docker Compose and consists of three primary components:

1. **`navidrome`**: The frontend and streaming backend. It scans the live `/music` library and serves it over the web.
2. **`uploader.py`**: The "Smart Gatekeeper" Web UI. It handles file uploads, real-time background Shazam scanning, duplicate upload prevention, and manual tag overrides.
3. **`organize.py`**: The robust background daemon running a continuous async loop. It monitors the `/inbox`, injects final ID3 tags, downloads cover art, performs strict duplicate checks, and securely moves files to the Live Library.

---

## 🚀 Installation & Deployment

### Prerequisites
* Docker & Docker Compose
* Nginx (or preferred reverse proxy) for SSL and domain routing.

### 1. Clone & Setup Directories
Create the required absolute directory structure:
```bash
mkdir -p data upload_drafts inbox staging music/Recommended_AsIs scripts logs test
```

### 2. Add the Scripts
Place both the `uploader.py` and `organize.py` scripts inside the `./scripts/` directory.

### 3. Deploy
Start the stack in detached mode:
```bash
docker compose up -d --build
```
*(The Web UI uses Basic Authentication. You can secure it using `UPLOAD_USER` and `UPLOAD_PASS` environment variables).*

### 4. Reverse Proxy Setup (Nginx)
To route traffic from `https://music.neuroconvert.com` to the streaming container and the upload dashboard:

```nginx
server {
    listen 443 ssl;
    server_name music.neuroconvert.com;

    # SSL Certs (Let's Encrypt / Certbot)
    ssl_certificate /etc/letsencrypt/live/music.neuroconvert.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/music.neuroconvert.com/privkey.pem;

    # Navidrome Streaming Server
    location / {
        proxy_pass http://127.0.0.1:4533;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Music Ingestion Dashboard
    location /add-music {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🎧 Usage Workflow

### Step 1: Upload & Review (Web UI)
1. Navigate to `https://music.neuroconvert.com/add-music` and drag-and-drop your audio files.
2. The background Shazam engine will automatically scan them. If recognized, it will show a **🎵 Shazam Match** badge. If unrecognized, you can manually type the Artist, Title, and Album.
3. Click **✅ Submit** to apply your metadata and move the file to the Live Processing Queue (Inbox).

### Step 2: The 5-Minute Grace Period
Once submitted, files wait in the **Live Processing Queue** for 5 minutes. This prevents partial file corruption and gives you time to click **🗑️ Cancel** if you made a mistake.

### Step 3: Background Organization & Streaming
1. Once the timer hits zero, `organize.py` takes over. It completely scrubs old ID3 tags, writes clean metadata, and fetches the Cover Art.
2. It checks your live library. **If the exact song already exists, the incoming duplicate is instantly deleted.**
3. Unique files are published to the beautifully structured Live Library (`Artist / Album / Song.mp3`).
4. Navidrome automatically scans the library, and your new tracks are instantly ready for streaming!

---

## 🛠️ Logs & Troubleshooting

You can monitor the real-time background processing directly from the Web Dashboard under **Step 3: Processing History**. 

For deeper debugging via the terminal:
```bash
# View Docker logs
docker logs -f music-processor
docker logs -f music-uploader

# View detailed Python application logs
tail -f ./logs/processing.log
tail -f ./logs/system.log
```

---

## 📝 Technologies Used
* [Navidrome](https://www.navidrome.org/) - Modern Music Server
* [Flask](https://flask.palletsprojects.com/) & [Dropzone.js](https://www.dropzone.dev/) - Web UI Dashboard
* [Shazamio](https://github.com/dotX12/shazamio) - Asynchronous Shazam API Wrapper
* [Mutagen](https://mutagen.readthedocs.io/) - Python Multimedia Tagging Library
* Python 3.11 & Asyncio
* Docker & Alpine/Slim Linux
# 🎵 NeuroConvert Music Server

A fully automated, self-hosted music streaming platform powered by **Navidrome** and **Shazamio**. 

This system acts as an intelligent music ingestion pipeline. You simply drop raw, untagged audio files into an `inbox` folder. A custom Python microservice automatically identifies the song using Shazam's acoustic fingerprinting, downloads the correct album art, tags the ID3 metadata, organizes the files into clean directories, and instantly publishes them to a live streaming server accessible anywhere.

Live instance: [https://music.neuroconvert.com](https://music.neuroconvert.com)

---

## ✨ Features

* **Automated Acoustic Fingerprinting:** Identifies music purely by its audio signature using Shazam's engine—no existing tags required.
* **Auto-Tagging & Metadata:** Automatically writes perfect ID3 tags (`Artist`, `Title`, `Album`, `Release Year`, `Genre`) directly to the `.mp3` files.
* **Cover Art Fetching:** Downloads high-quality album covers and embeds them directly into the audio files.
* **Smart Organization Pipeline:**
  * **Inbox:** Drop raw files here.
  * **Staging:** Processing zone.
  * **Live Music:** Beautifully structured `Artist / Album / Song.mp3` folders.
* **Intelligent Fallback:** If Shazam fails to identify a track, the system extracts whatever existing ID3 tags the file has and safely moves it to an organized `Recommended_AsIs` folder.
* **High-Performance Streaming:** Powered by Navidrome, offering instantaneous playback and compatibility with any Subsonic client (Symfonium, DSub, ultrasonic, etc.).

---

## 🏗️ Architecture

The system is deployed via Docker Compose and consists of two primary services:

1. `navidrome`: The frontend and streaming backend. It scans the live `/music` library and serves it over the web.
2. `music-processor`: A custom Python container running a continuous async loop. It monitors the `/inbox`, utilizes `ffmpeg` and `shazamio` to identify tracks, handles `mutagen` for ID3 tagging, and moves processed files to the live library.

---

## 🚀 Installation & Deployment

### Prerequisites
* Docker & Docker Compose
* Nginx (or preferred reverse proxy) for SSL and domain routing.

### 1. Clone & Setup Directories
Create the required directory structure:
```bash
mkdir -p data inbox staging music/Recommended_AsIs scripts logs test
```

### 2. Add the Script
Place the `organize_music.py` script inside the `./scripts/` directory.

### 3. Deploy
Start the stack in detached mode:
```bash
docker compose up -d --build
```

### 4. Reverse Proxy Setup (Nginx)
The application is exposed on port `4533`. To route traffic from `https://music.neuroconvert.com` to the container, set up Nginx:

```nginx
server {
    listen 443 ssl;
    server_name music.neuroconvert.com;

    # SSL Certs (Let's Encrypt / Certbot)
    ssl_certificate /etc/letsencrypt/live/music.neuroconvert.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/music.neuroconvert.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:4533;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🎧 Usage Workflow

1. **Upload Music:** Drop your untagged `.mp3`, `.flac`, or `.m4a` files into the `./inbox` directory. You can do this via SFTP, SMB, or a web file manager.
2. **Wait 5 Minutes:** To prevent partial file corruption, the `music-processor` waits 5 minutes after a file's last modification before touching it.
3. **Processing:** The script reads the file, identifies it via Shazam, injects tags and cover art, and moves it to the Live Library.
4. **Streaming:** Open [https://music.neuroconvert.com](https://music.neuroconvert.com). Navidrome automatically scans the library every hour, but you can trigger a quick scan in the UI to see your new tracks instantly.

### Unrecognized Music 
If you upload an obscure track or a personal recording that Shazam cannot identify, the processor will not delete it. Instead, it moves it to:
`./music/Recommended_AsIs/Artist/Album/Song.mp3`
(It will attempt to use any existing ID3 tags to build this folder structure).

---

## 🛠️ Logs & Troubleshooting

If a song isn't showing up, you can monitor the real-time processing logs:

```bash
# View Docker logs
docker logs -f music-processor

# View detailed Python application logs
tail -f ./logs/processing.log
tail -f ./logs/system.log
```

---

## 📝 Technologies Used
* [Navidrome](https://www.navidrome.org/) - Modern Music Server
* [Shazamio](https://github.com/dotX12/shazamio) - Asynchronous Shazam API Wrapper
* [Mutagen](https://mutagen.readthedocs.io/) - Python Multimedia Tagging Library
* Python 3.11 & Asyncio
* Docker & Alpine/Slim Linux
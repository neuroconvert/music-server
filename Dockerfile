FROM python:3.11-slim

# Install ffmpeg which is required by shazamio to analyze audio
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Install python requirements
RUN pip install --no-cache-dir mutagen requests shazamio

ENV PYTHONUNBUFFERED=1

USER 1000:1000

CMD ["python", "/scripts/organize_music.py"]
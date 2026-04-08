FROM python:3.11-slim

# Install the exact libraries we need for the custom Spotify tagger
RUN pip install --no-cache-dir spotipy mutagen requests

ENV PYTHONUNBUFFERED=1

USER 1000:1000

CMD ["python", "/scripts/organize_music.py"]
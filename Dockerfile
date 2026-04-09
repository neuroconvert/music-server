FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Added flask and werkzeug here
RUN pip install --no-cache-dir mutagen requests shazamio flask werkzeug

ENV PYTHONUNBUFFERED=1

USER 1000:1000

CMD ["python", "/scripts/organize_music.py"]
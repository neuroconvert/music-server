1) Link for config beet (to check if is peeking correct one use 'beet config -c' command)
ln -s /home/musicserver/music-server/config/beets_config.yaml /home/musicserver/.config/beets/config.yaml                               

rm /home/musicserver/navidrome/data/beets.db 
exiftool -r -json . > ../songs_metadata.json
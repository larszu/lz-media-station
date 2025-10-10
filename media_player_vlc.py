# Wrapper für Kompatibilität mit gui_vlc.py
from media_player import MediaPlayer

class VLCMediaPlayer(MediaPlayer):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

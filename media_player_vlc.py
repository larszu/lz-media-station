# Wrapper für Kompatibilität mit gui_vlc.py
from media_player import MediaPlayer

class VLCMediaPlayer(MediaPlayer):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
	
	def play_single_media(self, file_path):
		"""Spielt eine einzelne Mediendatei ab (Wrapper für play_media_list mit einem Element)"""
		print(f"[VLCMediaPlayer] play_single_media() aufgerufen für: {file_path}")
		return self.play_media_list([file_path], shuffle=False)

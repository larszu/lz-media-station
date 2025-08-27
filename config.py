"""
Standardwerte und Pfade
"""
DEFAULT_MIN_DIST = 30  # cm
DEFAULT_MAX_DIST = 80  # cm
DEFAULT_INTERVAL = 0.2 # Sekunden
VIDEO_FOLDER = "videos"
IMAGE_FOLDER = "images"
AUDIO_FOLDER = "audio"

# Media-Wechsel-Konfiguration
IMAGE_DISPLAY_TIME = 5.0  # Sekunden pro Bild
VIDEO_LOOP_CHECK_TIME = 30.0  # Sekunden bis Video-Wechsel geprüft wird
AUDIO_FADE_TIME = 2.0  # Sekunden für Audio-Übergang (Fade)

# Mindestlaufzeiten (Stabilität bei schwankenden Sensorwerten)
MIN_VIDEO_RUNTIME = 3.0  # Sekunden - Video muss mindestens so lange laufen
MIN_IMAGE_DISPLAY_TIME = 2.0  # Sekunden - Bild muss mindestens so lange angezeigt werden
MIN_AUDIO_RUNTIME = 5.0  # Sekunden - Audio-Track muss mindestens so lange spielen

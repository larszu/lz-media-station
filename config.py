"""
Standardwerte und Pfade
"""
DEFAULT_MIN_DIST = 5  # cm (Standardwert: 5cm Mindestabstand)
DEFAULT_MAX_DIST = 80  # cm (Standardwert: 80cm Maximalabstand)
DEFAULT_INTERVAL = 0.4 # Sekunden (Standardwert: 400ms Messintervall)
VIDEO_FOLDER = "videos"
IMAGE_FOLDER = "images"
AUDIO_FOLDER = "audio"

# Media-Wechsel-Konfiguration
IMAGE_DISPLAY_TIME = 30.0  # Sekunden pro Bild (Standardwert: 30 Sekunden Bildwechsel)
VIDEO_LOOP_CHECK_TIME = 30.0  # Sekunden bis Video-Wechsel geprüft wird
AUDIO_FADE_TIME = 0.04  # Sekunden für Audio-Übergang (Standardwert: 40ms Audiofade)

# Mindestlaufzeiten (Stabilität bei schwankenden Sensorwerten)
MIN_VIDEO_RUNTIME = 3.0  # Sekunden (Standardwert: 3s Min-Video-Zeit)
MIN_IMAGE_DISPLAY_TIME = 3.0  # Sekunden (Standardwert: 3s Min-Bild-Zeit)
MIN_AUDIO_RUNTIME = 3.0  # Sekunden (Standardwert: 3s Min-Audio-Zeit)

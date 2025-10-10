#!/bin/bash
# FACES Start-Script mit VLC-Konfiguration

cd /home/pi/pi_media_station

# Display und X11 Settings
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority

# VLC Settings für Raspberry Pi
export VLC_PLUGIN_PATH=/usr/lib/arm-linux-gnueabihf/vlc/plugins
export LIBVA_DRIVER_NAME=v4l2
export XDG_RUNTIME_DIR=/run/user/1000

# Audio Settings
export SDL_AUDIODRIVER=alsa
export AUDIODEV=hw:0,0

# Video-Treiber für pygame/SDL
export SDL_VIDEODRIVER=x11

echo "=== FACES Media Station Start ==="
echo "Display: $DISPLAY"
echo "VLC Plugin Path: $VLC_PLUGIN_PATH"
echo "Audio Driver: $SDL_AUDIODRIVER"
echo "=================================="

# Programm über main.py starten (nicht direkt gui_vlc.py!)
python3 -u main.py 2>&1 | tee /tmp/faces_debug.log

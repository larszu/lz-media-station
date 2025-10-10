#!/bin/bash
cd /home/pi/pi_media_station
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority
python3 main.py 2>&1 | tee /tmp/gui_debug.log

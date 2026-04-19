#!/bin/bash
# FACES Media Station - Startskript für Raspberry Pi
cd "$(dirname "$0")"

echo "FACES Media Station wird gestartet..."

# Server starten (Hintergrund)
python3 main.py &
SERVER_PID=$!

# Warten bis Server bereit ist
sleep 3

# Chromium im Kiosk-Modus öffnen
if command -v chromium-browser &> /dev/null; then
    chromium-browser \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --check-for-update-interval=31536000 \
        --autoplay-policy=no-user-gesture-required \
        --incognito \
        http://localhost:5000/ &
    echo "Chromium gestartet"
elif command -v chromium &> /dev/null; then
    chromium \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --autoplay-policy=no-user-gesture-required \
        --incognito \
        http://localhost:5000/ &
    echo "Chromium gestartet"
else
    echo "Chromium nicht gefunden."
    echo "Web-UI erreichbar unter: http://$(hostname -I | awk '{print $1}'):5000"
fi

# Auf Beendigung des Servers warten
wait $SERVER_PID

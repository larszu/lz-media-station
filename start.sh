#!/bin/bash
# FACES Media Station - Startskript für Raspberry Pi
cd "$(dirname "$0")"

echo "FACES Media Station wird gestartet..."

# Wayland-Umgebung sicherstellen (falls Skript ohne DE-Session-Vars läuft)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "$WAYLAND_DISPLAY" ] && [ -S "$XDG_RUNTIME_DIR/wayland-0" ]; then
    export WAYLAND_DISPLAY=wayland-0
fi

# Server starten (Hintergrund)
python3 main.py >/tmp/faces_main.log 2>&1 &
SERVER_PID=$!

# Warten bis Server bereit ist
sleep 3

# Chromium im Kiosk-Modus öffnen
CHROME_BIN=""
if command -v chromium-browser &> /dev/null; then CHROME_BIN=chromium-browser
elif command -v chromium &> /dev/null; then CHROME_BIN=chromium
fi
if [ -n "$CHROME_BIN" ]; then
    OZONE_ARG=""
    if [ -n "$WAYLAND_DISPLAY" ]; then OZONE_ARG="--ozone-platform=wayland"; fi
    "$CHROME_BIN" \
        $OZONE_ARG \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=Translate,TranslateUI \
        --disable-translate \
        --lang=de-DE \
        --check-for-update-interval=31536000 \
        --autoplay-policy=no-user-gesture-required \
        --incognito \
        http://localhost:5000/ &
    echo "Chromium gestartet ($CHROME_BIN)"
else
    echo "Chromium nicht gefunden."
    echo "Web-UI erreichbar unter: http://$(hostname -I | awk '{print $1}'):5000"
fi

# Auf Beendigung des Servers warten
wait $SERVER_PID

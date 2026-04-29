#!/bin/bash
# FACES Media Station - Robustes Startskript für Raspberry Pi Kiosk

cd "$(dirname "$0")"
echo "[FACES] Starte Media Station..."

# Diese Umgebung hat sich im SSH-Test als stabil erwiesen.
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY="wayland-0"

# Beim Login kann Autostart vor dem Wayland-Socket laufen.
for i in $(seq 1 30); do
    [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] && break
    sleep 1
done
if [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    echo "[FACES] Wayland-Socket nicht verfügbar, Chromium-Start übersprungen."
    exit 0
fi

# Flask-Server nur starten, wenn er noch nicht läuft
if ! curl -fsS http://127.0.0.1:5000/api/status >/dev/null 2>&1; then
    setsid nohup python3 main.py >/tmp/faces_main.log 2>&1 < /dev/null &
fi

# Warten bis API erreichbar ist (max. 30s)
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:5000/api/status >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Vorherigen Kiosk-Browser schließen
pkill -f 'chromium.*--kiosk' >/dev/null 2>&1 || true
sleep 1

# Chromium wie im funktionierenden manuellen Start starten
if command -v chromium-browser >/dev/null 2>&1; then
    CHROME_BIN="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
    CHROME_BIN="chromium"
else
    CHROME_BIN=""
fi

if [ -n "$CHROME_BIN" ]; then
    setsid "$CHROME_BIN" \
        --ozone-platform=wayland \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=Translate,TranslateUI,MediaRouter,DialMediaRouteProvider \
        --disable-translate \
        --lang=de-DE \
        --password-store=basic \
        --use-mock-keychain \
        --no-first-run \
        --no-default-browser-check \
        --disable-component-update \
        --disable-background-networking \
        --autoplay-policy=no-user-gesture-required \
        --incognito \
        http://localhost:5000/admin \
        </dev/null >/tmp/chromium.log 2>&1 &
    echo "[FACES] Chromium gestartet ($CHROME_BIN)"
else
    echo "[FACES] Chromium nicht gefunden."
fi

exit 0

#!/bin/bash
# LZ Media Station - Robustes Startskript für Raspberry Pi Kiosk

cd "$(dirname "$0")"
echo "[LZ] Starte Media Station..."

# Diese Umgebung hat sich im SSH-Test als stabil erwiesen.
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WAYLAND_DISPLAY="wayland-0"

# Beim Login kann Autostart vor dem Wayland-Socket laufen.
for i in $(seq 1 30); do
    [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] && break
    sleep 1
done
if [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    echo "[LZ] Wayland-Socket nicht verfügbar, Chromium-Start übersprungen."
    # Boot-Race: Session ist oft noch nicht komplett oben. Einmal verzögert neu versuchen.
    nohup /bin/bash -lc "sleep 25; $(cd "$(dirname "$0")" && pwd)/start.sh" >/tmp/lz_retry.log 2>&1 &
    exit 0
fi

# Labwc/pcmanfm Desktop-Session braucht nach dem Wayland-Socket noch ein paar
# Sekunden, bis sie bereit ist und keine Pi-Standarddialoge mehr aufpoppen.
sleep 5

# Pi-Standard-Dialoge entsorgen, damit sie nicht über dem Kiosk landen:
# - pprompt.sh: SSH/Default-Passwort-Warnung
# - piwiz: Welcome-Wizard
# - zenity/yad: generische Modaldialoge der Session
pkill -f 'pprompt'   2>/dev/null || true
pkill -f 'piwiz'     2>/dev/null || true
pkill -f 'zenity'    2>/dev/null || true
pkill -f 'yad'       2>/dev/null || true

# Flask-Server nur starten, wenn er noch nicht läuft
if ! curl -fsS http://127.0.0.1:5000/api/status >/dev/null 2>&1; then
    setsid nohup python3 main.py >/tmp/lz_main.log 2>&1 < /dev/null &
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

# Chromium direkt aus /usr/lib/chromium starten, um den chromium-browser
# Wrapper und dessen /etc/chromium.d/* Flags zu umgehen, die auf Pi/Wayland
# zu grauem Renderer-Bild führen (--enable-gpu-rasterization, --use-angle=gles,
# --force-renderer-accessibility, --enable-remote-extensions). Wir setzen
# nur die Flags, die wir wirklich wollen.
if [ -x /usr/lib/chromium/chromium ]; then
    CHROME_BIN="/usr/lib/chromium/chromium"
elif command -v chromium >/dev/null 2>&1; then
    CHROME_BIN="$(command -v chromium)"
elif command -v chromium-browser >/dev/null 2>&1; then
    CHROME_BIN="$(command -v chromium-browser)"
else
    CHROME_BIN=""
fi

if [ -n "$CHROME_BIN" ]; then
    # Sauberer Start: Wrapper-Variablen entfernen, eigenes Profil nutzen.
    unset CHROMIUM_FLAGS
    PROFILE_DIR="${HOME}/.lz-chromium-profile"
    mkdir -p "$PROFILE_DIR"

    setsid "$CHROME_BIN" \
        --ozone-platform=wayland \
        --enable-features=UseOzonePlatform \
        --kiosk \
        --start-fullscreen \
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
        --user-data-dir="$PROFILE_DIR" \
        --disable-gpu-driver-bug-workarounds \
        http://localhost:5000/ \
        </dev/null >/tmp/chromium.log 2>&1 &
    echo "[LZ] Chromium gestartet ($CHROME_BIN)"
else
    echo "[LZ] Chromium nicht gefunden."
fi

exit 0

#!/bin/bash
# LZ Media Station - One-Shot Installer für Raspberry Pi
# Verwendung:  curl -sSL https://raw.githubusercontent.com/larszu/lz-media-station/main/install_pi.sh | bash
# oder lokal:  bash install_pi.sh

set -e

REPO_URL="https://github.com/larszu/lz-media-station.git"
APP_NAME="lz-media-station"
APP_DIR="$HOME/$APP_NAME"
# Frueherer Installationsort; wird beim naechsten Lauf samt Medien und
# config.json hierher umgezogen.
ALT_DIR="$HOME/pi_media_station"
BRANCH="${BRANCH:-main}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[*]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[X]${NC} $1"; }

cat <<'BANNER'
========================================================
   LZ Media Station - Installer
   github.com/larszu/lz-media-station
========================================================
BANNER

# 1) Pakete
log "Installiere Systempakete (Python, Chromium, git)..."
sudo apt update -qq
sudo apt install -y --no-install-recommends \
    python3 python3-pip python3-flask python3-gpiozero \
    chromium-browser git curl avahi-daemon

# 2) Quellcode
if [ -d "$ALT_DIR/.git" ] && [ ! -e "$APP_DIR" ]; then
    log "Ziehe $ALT_DIR nach $APP_DIR um ..."
    mv "$ALT_DIR" "$APP_DIR"
    git -C "$APP_DIR" remote set-url origin "$REPO_URL"
fi
if [ -d "$APP_DIR/.git" ]; then
    log "Update vorhandenes Repo in $APP_DIR ..."
    git -C "$APP_DIR" fetch --all
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
    if [ -d "$APP_DIR" ]; then
        warn "Verschiebe alte $APP_DIR -> ${APP_DIR}_backup_$(date +%s)"
        mv "$APP_DIR" "${APP_DIR}_backup_$(date +%s)"
    fi
    log "Clone $REPO_URL nach $APP_DIR ..."
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
chmod +x "$APP_DIR/start.sh" 2>/dev/null || true

# 3) Medien-Ordner sicherstellen
mkdir -p "$APP_DIR/videos" "$APP_DIR/images" "$APP_DIR/audio" "$APP_DIR/subtitles"

# 4) Autostart-Eintrag
log "Schreibe Autostart-Datei ..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/LZ_Media_Station.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=LZ Media Station
Comment=Startet die LZ Media Station
Exec=/bin/bash -lc '$APP_DIR/start.sh'
Icon=$APP_DIR/static/brand/icon-512.png
Terminal=false
Categories=AudioVideo;
StartupNotify=true
Path=$APP_DIR/
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF

# 4b) Desktop-Startskript (manueller Neustart vom Pi-Desktop)
log "Schreibe Desktop-Startskript ..."
mkdir -p "$HOME/Desktop"
cat > "$HOME/Desktop/LZ_Starten.sh" <<EOF
#!/bin/bash
cd "$APP_DIR"
/bin/bash -lc "$APP_DIR/start.sh"
EOF
chmod +x "$HOME/Desktop/LZ_Starten.sh"

cat > "$HOME/Desktop/LZ_Media_Station.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=LZ Media Station starten
Comment=Startet/öffnet LZ Media Station im Kiosk erneut
Exec=/bin/bash -lc '$HOME/Desktop/LZ_Starten.sh'
Icon=$APP_DIR/static/brand/icon-512.png
Terminal=false
Categories=AudioVideo;
Path=$APP_DIR/
StartupNotify=true
EOF
chmod +x "$HOME/Desktop/LZ_Media_Station.desktop"

# 5) Chromium-Policy: kein Übersetzungs-Hinweis
log "Chromium-Policy: Translate aus ..."
sudo mkdir -p /etc/chromium/policies/managed
sudo tee /etc/chromium/policies/managed/no-translate.json >/dev/null <<'POL'
{ "TranslateEnabled": false }
POL

# 6) Stör-Dialoge unterdrücken (gnome-keyring etc.)
log "Deaktiviere störende Autostart-Dialoge ..."
for f in /etc/xdg/autostart/gnome-keyring-pkcs11.desktop \
         /etc/xdg/autostart/gnome-keyring-secrets.desktop \
         /etc/xdg/autostart/gnome-keyring-ssh.desktop \
         /etc/xdg/autostart/pprompt.desktop \
         /etc/xdg/autostart/piwiz.desktop; do
    [ -f "$f" ] || continue
    n=$(basename "$f")
    cat > "$HOME/.config/autostart/$n" <<EOF
[Desktop Entry]
Type=Application
Name=disabled
Hidden=true
X-GNOME-Autostart-enabled=false
EOF
done

# 7) Alten V1-Autostart wegräumen, falls vorhanden
if [ -f "$HOME/.config/autostart/Start_Simple_Faces.desktop" ]; then
    mv "$HOME/.config/autostart/Start_Simple_Faces.desktop" \
       "$HOME/.config/autostart/Start_Simple_Faces.desktop.disabled"
fi

# 8) Sudoers: nmcli + reboot ohne Passwort (für Netzwerk-Konfiguration aus Web-UI)
log "Konfiguriere passwortloses sudo für nmcli/reboot ..."
SUDO_USER_NAME="$(id -un)"
sudo tee /etc/sudoers.d/lz-media-station >/dev/null <<EOF
$SUDO_USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/nmcli, /sbin/reboot, /usr/sbin/reboot
EOF
sudo chmod 0440 /etc/sudoers.d/lz-media-station

# 9) mDNS / Avahi: Station als _lzstation._tcp ankündigen
log "Registriere Avahi-Service _lzstation._tcp ..."
if [ -f "$APP_DIR/lzstation.service" ]; then
    sudo cp "$APP_DIR/lzstation.service" /etc/avahi/services/lzstation.service
    sudo systemctl enable avahi-daemon >/dev/null 2>&1 || true
    sudo systemctl restart avahi-daemon || true
fi

cat <<EOF

${GREEN}========================================================${NC}
  Installation fertig.

  - App-Verzeichnis: $APP_DIR
  - Web-UI:          http://$(hostname -I | awk '{print $1}'):5000
  - Start jetzt:     $APP_DIR/start.sh
  - Auto-Start:      beim nächsten Login (oder: sudo reboot)
========================================================
EOF

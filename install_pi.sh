#!/bin/bash
# FACES Media Station - One-Shot Installer für Raspberry Pi
# Verwendung:  curl -sSL https://raw.githubusercontent.com/larszu/pi-media-station/main/install_pi.sh | bash
# oder lokal:  bash install_pi.sh

set -e

REPO_URL="https://github.com/larszu/pi-media-station.git"
APP_NAME="pi_media_station"
APP_DIR="$HOME/$APP_NAME"
BRANCH="${BRANCH:-main}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[*]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[X]${NC} $1"; }

cat <<'BANNER'
========================================================
   FACES Media Station - Installer
   github.com/larszu/pi-media-station
========================================================
BANNER

# 1) Pakete
log "Installiere Systempakete (Python, Chromium, git)..."
sudo apt update -qq
sudo apt install -y --no-install-recommends \
    python3 python3-pip python3-flask python3-gpiozero \
    chromium-browser git curl

# 2) Quellcode
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
mkdir -p "$APP_DIR/videos" "$APP_DIR/images" "$APP_DIR/audio"

# 4) Autostart-Eintrag
log "Schreibe Autostart-Datei ..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/FACES_Media_Station.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=FACES Media Station
Comment=Startet die FACES Media Station
Exec=$APP_DIR/start.sh
Icon=/usr/share/pixmaps/python.xpm
Terminal=false
Categories=AudioVideo;
StartupNotify=true
Path=$APP_DIR/
X-GNOME-Autostart-enabled=true
EOF

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
         /etc/xdg/autostart/gnome-keyring-ssh.desktop; do
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

cat <<EOF

${GREEN}========================================================${NC}
  Installation fertig.

  - App-Verzeichnis: $APP_DIR
  - Web-UI:          http://$(hostname -I | awk '{print $1}'):5000
  - Start jetzt:     $APP_DIR/start.sh
  - Auto-Start:      beim nächsten Login (oder: sudo reboot)
========================================================
EOF

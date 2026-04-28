# FACES Media Station

> Sensor-gesteuerte Medien-Station mit Web-Admin, Display-Modus und Multi-Station Manager.
> Läuft auf **Raspberry Pi** (HC-SR04 Ultraschallsensor) und für Tests auf **Windows** (Dummy-Sensor).

[![Release](https://img.shields.io/badge/release-v2.1.0-blue)](https://github.com/larszu/pi-media-station/releases)

---

## Inhalt

- [Features](#features)
- [Schnellstart Raspberry Pi](#schnellstart-raspberry-pi)
- [Manuelles Deploy / Update](#manuelles-deploy--update)
- [Bedienung](#bedienung)
- [Multi-Station Manager (Desktop-App)](#multi-station-manager-desktop-app)
- [Architektur](#architektur)
- [API-Übersicht](#api-übersicht)
- [Troubleshooting](#troubleshooting)
- [Tailscale (Remote-Verwaltung)](#tailscale-remote-verwaltung)

---

## Features

### Sensor-/Medien-Kern
- **HC-SR04 Ultraschallsensor** an GPIO 23 (Trigger) und GPIO 24 (Echo) — frei konfigurierbar
- **Zwei Zonen**: NAH (≤ Schwelle) / FERN (> Schwelle), mit konfigurierbarer Verzögerung gegen Flackern
- **Pro Zone** beliebige Auswahl an Videos, Bildern und Audio
- **Bildslideshow** mit einstellbarem Intervall
- **Lautstärke** getrennt für Master / Video / Audio (0–100 %)
- **Video-Resume**: Optional Wiedergabe an gleicher Stelle fortsetzen, statt von vorne
- **Dummy-Sensor** auf Windows für UI-Tests ohne Hardware

### Web-Admin (`/admin`)
- Zonen-Übersicht mit Drag-Zuordnung
- Medien-Bibliothek mit Tabs (Videos / Bilder / Audio)
- **Drag-and-Drop-Upload** mit Fortschrittsanzeige
- Datei-Löschung **nicht-destruktiv**: entfernt nur aus Zonen, die Datei bleibt auf dem Pi
- Live-Status: Distanz, aktive Zone, Sensor-Modus
- Einstellungen: Stationsname, Schwelle, Verzögerung, Bildwechsel, Lautstärken, Video-Resume

### Systemeinstellungen (eigener Bereich in `/admin`)
- **GPIO-Konfiguration**: Trigger-/Echo-Pin änderbar
- **Anzeige-IP** für Fernsteuerung (leer = Auto-Erkennung)
- **Netzwerk** via `nmcli`:
  - DHCP / statische IP wählbar
  - IP/CIDR, Gateway, DNS direkt konfigurierbar
- **WLAN-Steuerung**:
  - WLAN ein/aus per Toggle
  - Netzwerk-Scan mit Signal-Stärke und Verschlüsselung
  - SSID per Klick übernehmen, Passwort eingeben → verbinden
- **Pi-Reboot** direkt aus der UI

### Display-Modus (`/`)
- Vollbild-Player für Kiosk-Betrieb (Chromium `--kiosk`)
- ESC öffnet `/admin`
- Auto-Verstecken des Cursors

### Manager Desktop-App (`faces-manager/`)
- Verwaltet **mehrere Pi-Stationen** zentral
- **Auto-Discovery** via mDNS (`_faces._tcp` über Avahi)
- **Manuelles Hinzufügen** per IP/Hostname
- Live-Polling: Online-Status, Distanz, Zone
- **Bulk-Aktionen**: Start / Stop / Reboot
- **Bulk-Upload**: dieselbe Datei an N Stationen gleichzeitig
- **Config-Push**: Stationsname, Schwelle, Verzögerung
- Direktsprung in die Web-Admin-UI jeder Station
- Builds für **Windows (NSIS + Portable)**, **macOS (Intel + Apple Silicon)**, **Linux (AppImage)**

---

## Schnellstart Raspberry Pi

Frischer Pi (Raspberry Pi OS Bookworm, Wayland/labwc-Session, User `pi`):

```bash
curl -sSL https://raw.githubusercontent.com/larszu/pi-media-station/main/install_pi.sh | bash
```

Der Installer erledigt automatisch:

1. Systempakete (`python3-flask`, `python3-gpiozero`, `chromium-browser`, `avahi-daemon`, `git`)
2. Klont das Repo nach `~/pi_media_station`
3. Erstellt Medien-Ordner (`videos/`, `images/`, `audio/`)
4. Schreibt `~/.config/autostart/FACES_Media_Station.desktop`
5. Chromium-Policy: deaktiviert Translate-Banner
6. Unterdrückt störende Login-Dialoge (`gnome-keyring*`)
7. **Sudoers-Regel** für `nmcli` und `reboot` (passwortlos für `pi`)
8. **Avahi-Service** `_faces._tcp` für mDNS-Discovery durch den Manager

Nach Installation:

```bash
~/pi_media_station/start.sh    # sofort starten
# ODER
sudo reboot                    # nutzt Autostart
```

Web-UI dann unter `http://<pi-ip>:5000/admin`.

---

## Manuelles Deploy / Update

### Erstmaliges Klonen

```bash
git clone https://github.com/larszu/pi-media-station.git ~/pi_media_station
cd ~/pi_media_station
chmod +x start.sh install_pi.sh
bash install_pi.sh   # idempotent, erkennt vorhandenes Repo
```

### Update auf neueste Version

```bash
cd ~/pi_media_station
git pull
pkill -f 'python3 main.py' || true
nohup python3 main.py >/tmp/main.log 2>&1 &
```

oder einfacher:

```bash
sudo reboot
```

### Einzeldateien per SCP (vom Entwickler-PC)

```powershell
# Windows PowerShell
cd "c:\Users\<user>\Documents\FACES Raspberry\pi_media_station"
scp web_ui.py templates/admin.html static/app.js pi@<pi-ip>:/tmp/
ssh pi@<pi-ip> "cp /tmp/web_ui.py ~/pi_media_station/web_ui.py && \
                cp /tmp/admin.html ~/pi_media_station/templates/ && \
                cp /tmp/app.js ~/pi_media_station/static/ && \
                pkill -f 'python3 main.py' || true; \
                sleep 2; cd ~/pi_media_station; \
                setsid nohup python3 main.py >/tmp/main.log 2>&1 < /dev/null &"
```

### Auf Windows lokal entwickeln

```cmd
run_windows.bat
```

Startet Flask mit Dummy-Sensor auf `http://localhost:5000`.

---

## Bedienung

### Web-Admin (`/admin`)

| Bereich | Funktion |
|---|---|
| **Status** | Distanz, Zone, Start/Stop, Display-Link |
| **Zonen** | Drag-Zuordnung Medien → NAH / FERN |
| **Bibliothek** | Upload, Löschen (nur aus Zonen, Datei bleibt) |
| **Einstellungen** | Name, Schwelle, Verzögerung, Bildintervall, Lautstärken, Video-Resume |
| **Systemeinstellungen** | GPIO, Anzeige-IP, Netzwerk, WLAN, Reboot |

### Display-Modus (`/`)

- ESC → `/admin`
- Wird beim Pi-Boot automatisch im Chromium-Kiosk geladen (siehe `start.sh`)

### Netzwerk konfigurieren

In `/admin` → **Systemeinstellungen** → **Netzwerk**:

1. Aktive Verbindung wählen
2. **DHCP** oder **Statisch**
3. Bei statisch: IP/CIDR (z. B. `192.168.1.50/24`), Gateway, DNS
4. **Netzwerk übernehmen**

> Verbindung wird kurz getrennt — danach neue IP im Browser eingeben.

### WLAN konfigurieren

In `/admin` → **Systemeinstellungen** → **WLAN**:

1. WLAN-Toggle aktivieren
2. **Netzwerke scannen**
3. SSID anklicken → Passwort eingeben
4. **Mit WLAN verbinden**

> Bei aktiver Ethernet-Verbindung bleibt diese bestehen — du kannst Pi parallel per WLAN ins Netz bringen.

---

## Multi-Station Manager (Desktop-App)

Im Ordner `faces-manager/` liegt eine Electron-App für Win/Mac/Linux.

### Entwicklung

```bash
cd faces-manager
npm install
npm start
```

### Build (Distributables)

```bash
npm run dist:win    # Windows: NSIS Installer + Portable .exe
npm run dist:mac    # macOS: DMG für Intel + Apple Silicon
npm run dist        # plus Linux AppImage
```

Artefakte in `faces-manager/dist/`.

### Workflow

1. **Discovery**: alle Pis im LAN mit Avahi-Service erscheinen automatisch
2. **Manuell adden**: per IP wenn mDNS nicht durchkommt (z. B. via Tailscale)
3. **Auswahl**: Karten anklicken → Bulk-Aktionen aktiv
4. **Bulk**: Start / Stop / Reboot, Media-Upload, Config-Push
5. **Admin öffnen**: pro Karte öffnet `/admin` im System-Browser

Persistente Daten der App: `%APPDATA%\faces-manager\stations.json` (Win) bzw. `~/Library/Application Support/faces-manager/` (Mac).

---

## Architektur

```
                ┌─────────────────────────────┐
                │   FACES Manager (Electron)  │
                │   Win / macOS / Linux       │
                └──────────────┬──────────────┘
                               │ HTTP/JSON (LAN oder Tailscale)
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐            ┌────▼────┐            ┌────▼────┐
   │ Pi #1   │            │ Pi #2   │            │ Pi #N   │
   │ Flask   │            │ Flask   │            │ Flask   │
   │ + Avahi │            │ + Avahi │            │ + Avahi │
   │ HC-SR04 │            │ HC-SR04 │            │ HC-SR04 │
   └─────────┘            └─────────┘            └─────────┘
```

**Pi-Stack:**
- `main.py` – Controller (Sensor-Loop, State-Machine, Player)
- `web_ui.py` – Flask-Routes (`/`, `/admin`, `/api/*`)
- `sensor.py` – `gpiozero.DistanceSensor` mit Dummy-Fallback
- `media_player.py` – Player
- `static/`, `templates/` – Frontend
- `faces.service` – Avahi mDNS

**Manager-Stack:**
- `main.js` – Electron-Hauptprozess, mDNS (`bonjour-service`), HTTP-Multipart-Upload
- `preload.js` – contextIsolation IPC-Bridge
- `renderer/` – UI

---

## API-Übersicht

Alle Endpoints unter `http://<pi-ip>:5000`.

| Method | Path | Beschreibung |
|---|---|---|
| GET | `/api/status` | Distanz, Zone, Active, IP, Config |
| GET | `/api/scene` | Aktuelle Medien-Zuweisungen |
| GET | `/api/identity` | Station-ID + Version (Manager-Discovery) |
| POST | `/api/start` | Sensor-Loop starten |
| POST | `/api/stop` | Stop |
| GET/POST | `/api/config` | Konfiguration lesen/schreiben |
| POST | `/api/zone` | Datei einer Zone zuweisen |
| POST | `/api/upload/<type>` | Multipart-Upload (videos/images/audio) |
| DELETE | `/api/media/<type>/<name>` | Aus allen Zonen entfernen (Datei bleibt) |
| GET/POST | `/api/system/network` | nmcli IP-Konfiguration |
| GET/POST | `/api/system/wifi` | WLAN ein/aus, Scan, Connect |
| POST | `/api/system/reboot` | `sudo reboot` |
| GET | `/media/<type>/<name>` | Datei-Download |

---

## Troubleshooting

### Server läuft nicht nach Reboot

```bash
ssh pi@<pi-ip>
cat /tmp/main.log              # letzte Fehler
ps -ef | grep main.py          # läuft Prozess?
~/pi_media_station/start.sh    # manuell starten
```

### Manager findet Pi nicht

- Avahi prüfen: `systemctl status avahi-daemon`
- Service registriert? `ls /etc/avahi/services/faces.service`
- Fallback: manuell mit IP adden
- Firewall: Port 5000 freigegeben?

### nmcli verlangt Passwort

Sudoers-Regel fehlt:
```bash
cat /etc/sudoers.d/faces-media-station
# Sollte enthalten:
# pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli, /sbin/reboot, /usr/sbin/reboot
```
Mit `bash install_pi.sh` neu erstellen.

### Display zeigt schwarzen Bildschirm

- Wayland-Env? `echo $WAYLAND_DISPLAY`
- `start.sh` setzt `XDG_RUNTIME_DIR=/run/user/1000` und `WAYLAND_DISPLAY=wayland-0`
- Chromium-Log: `tail /tmp/chromium.log`

### Status zeigt 127.0.0.1 statt LAN-IP

- Anzeige-IP in Systemeinstellungen manuell setzen, ODER
- Default-Route fehlt → mit `ip route` prüfen, ggf. Gateway setzen

### SSH-Hintergrundstart killt Server beim Logout

Statt `nohup ... &` immer `setsid` verwenden:
```bash
setsid nohup python3 main.py >/tmp/main.log 2>&1 < /dev/null &
```

---

## Tailscale (Remote-Verwaltung)

Für Multi-Standort oder Verwaltung von zuhause:

```bash
# Auf jedem Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Auf dem Manager-Rechner ebenfalls Tailscale installieren und im selben Tailnet anmelden. Pis erreichen sich dann unter `100.x.y.z` oder `<pi-name>.<tailnet>.ts.net` (MagicDNS).

> mDNS funktioniert **nicht** über Tailscale → Stationen einmalig manuell im Manager mit ihrer Tailscale-Adresse hinzufügen.

---

## Lizenz

MIT

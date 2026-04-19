# FACES Media Station

Interaktive Medienstation für Raspberry Pi mit HC-SR04 Ultraschallsensor. Wechselt automatisch zwischen zwei Videos basierend auf der Entfernung einer Person. Komplett konfigurierbar über eine moderne Web-Oberfläche.

## Funktionsweise

- **Person nah** (Distanz ≤ Schwelle) → Video 1 wird abgespielt
- **Person fern** (Distanz > Schwelle) → Video 2 wird abgespielt
- **Hysterese**: Konfigurierbare Verzögerung verhindert hektisches Umschalten
- **Headless**: Pi zeigt nur Vollbild-Video, Konfiguration läuft über Web-UI

## Schnellstart

```bash
# 1. Repo klonen
git clone https://github.com/larszu/pi-media-station.git
cd pi-media-station

# 2. Abhängigkeiten installieren
pip3 install -r requirements.txt
sudo apt install vlc

# 3. Videos in videos/ Ordner legen

# 4. Starten
python3 main.py          # Auf dem Pi (echter Sensor)
python3 main.py --dummy  # Zum Testen (Dummy-Sensor)

# 5. Browser öffnen
# http://<pi-ip>:5000
```

## Web-UI

Erreichbar unter `http://<pi-ip>:5000` von jedem Gerät im Netzwerk.

- Live-Distanzanzeige mit animiertem Balken
- Video-Auswahl für "nah" und "fern" per Dropdown
- Schwellenwert und Verzögerung per Slider
- Video-Upload direkt über den Browser
- GPIO-Pin Konfiguration
- Stationsname (für mehrere Stationen im Netzwerk)

## Hardware

### HC-SR04 Sensor (Standard-Pins)
| Pin | GPIO | Raspberry Pi |
|-----|------|-------------|
| VCC | - | 5V (Pin 2) |
| GND | - | GND (Pin 6) |
| Trig | 23 | Pin 16 |
| Echo | 24 | Pin 18 |

GPIO-Pins sind über die Web-UI änderbar.

## Projektstruktur

```
pi_media_station/
├── main.py          # Einstiegspunkt + Controller-Logik
├── sensor.py        # HC-SR04 via gpiozero
├── player.py        # VLC mit RC-Interface
├── web_ui.py        # Flask Web-API
├── templates/
│   └── index.html   # Web-Oberfläche
├── static/
│   ├── style.css    # Dark Theme
│   └── app.js       # Frontend-Logik
├── config.json      # Konfiguration (wird automatisch erstellt)
├── videos/          # Video-Dateien hierhin
├── requirements.txt
├── start.sh
└── README.md
```

## Autostart (systemd)

```bash
sudo cp pi-media-station.service /etc/systemd/system/
sudo systemctl enable pi-media-station
sudo systemctl start pi-media-station
```

## Mehrere Stationen

Jede Station bekommt über die Web-UI einen eigenen Namen. Alle Stationen sind unter ihrer jeweiligen IP erreichbar. Port ist konfigurierbar (Standard: 5000).


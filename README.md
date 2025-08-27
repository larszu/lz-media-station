# Raspberry Pi 5 Medienstation

Eine interaktive Medienstation für den Raspberry Pi 5 mit HC-SR04 Ultraschallsensor, die basierend auf der Entfernung Videos oder Bilder im Vollbildmodus anzeigt.

## Features

- **Abstandsmessung** mit HC-SR04 Ultraschallsensor (Dummy-Sensor für Testing enthalten)
- **Responsive GUI** mit tkinter im Kiosk-Modus
- **Automatische Media-Steuerung**: Video bei bestimmter Entfernung, sonst Bild
- **Live-Dateierkennung** in Watchfoldern mit `watchdog`
- **Mittelwertfilter** für stabile Sensordaten
- **Vollbild-Darstellung** ohne sichtbares Umschalten

## Hardware Setup

### HC-SR04 Sensor Verkabelung
- **VCC** → 5V (Pin 2)
- **GND** → GND (Pin 6) 
- **Trig** → GPIO 18 (Pin 12)
- **Echo** → GPIO 24 (Pin 18)

## Installation

### 1. Raspberry Pi OS Setup
Empfohlen: **Raspberry Pi OS Lite (64-bit)**

```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Abhängigkeiten installieren
sudo apt install python3 python3-pip python3-venv git xserver-xorg xinit vlc python3-vlc -y
```

### 2. Projekt installieren
```bash
# Repository klonen
git clone https://github.com/DEIN-USERNAME/pi-media-station.git /home/pi/pi_media_station
cd /home/pi/pi_media_station

# Python-Pakete installieren
pip3 install -r requirements.txt
```

### 3. Auto-Start beim Boot (optional)
```bash
# Service installieren
sudo cp pi-media-station.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-media-station.service
sudo systemctl start pi-media-station.service
```

## Verwendung

### Manueller Start
```bash
cd /home/pi/pi_media_station
python3 main.py
```

### GUI-Bedienung
- **ESC**: Programm beenden (Test-Modus)
- **Min/Max Abstand**: Schwellwerte für Video-Aktivierung
- **Messintervall**: Sensor-Abfragezeit in ms
- **Dateiauswahl**: Videos/Bilder aus Watchfoldern oder manuell

## Projektstruktur

```
pi_media_station/
├── main.py              # Einstiegspunkt, startet GUI + Sensor-Thread
├── gui.py               # GUI-Logik (tkinter)
├── sensor.py            # HC-SR04-Abstandsmessung + Glättung
├── media_player.py      # Media-Player (VLC-Vorbereitung)
├── config.py            # Standardwerte und Konfiguration
├── requirements.txt     # Python-Abhängigkeiten
├── pi-media-station.service  # Systemd-Service für Auto-Start
├── videos/              # Watchfolder für Videos
├── images/              # Watchfolder für Bilder
└── README.md           # Diese Datei
```

## Konfiguration

### Sensor-Einstellungen
In `main.py` kannst du zwischen Dummy-Sensor und echtem HC-SR04 wechseln:
```python
# Für echten Sensor:
sensor_thread = SensorThread(interval=DEFAULT_INTERVAL, use_dummy=False)

# Für Testing ohne Hardware:
sensor_thread = SensorThread(interval=DEFAULT_INTERVAL, use_dummy=True)
```

### Standard-Werte
In `config.py`:
- `DEFAULT_MIN_DIST = 30`  # Minimum-Abstand für Video (cm)
- `DEFAULT_MAX_DIST = 80`  # Maximum-Abstand für Video (cm)  
- `DEFAULT_INTERVAL = 0.2` # Sensor-Abfrageintervall (s)

## Media-Logik

1. **Abstand zwischen Min/Max**: Video wird im Loop abgespielt
2. **Abstand außerhalb**: Bild wird angezeigt
3. **Keine Datei gewählt**: Schwarzer Bildschirm

## Entwicklung

### TODO: VLC-Integration
Der `media_player.py` enthält Platzhalter für VLC. Aktiviere die kommentierten Bereiche für echte Video/Bild-Wiedergabe.

### TODO: Optimierungen
- Performance-Tuning für Pi 5
- Erweiterte Media-Formate
- Web-Interface für Remote-Konfiguration

## Lizenz

MIT License - siehe LICENSE-Datei für Details.

## Problembehebung

### GPIO-Berechtigungen
```bash
sudo usermod -a -G gpio pi
```

### Service-Logs anzeigen
```bash
sudo journalctl -u pi-media-station.service -f
```

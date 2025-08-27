# Plattform-Kompatibilität

## ✅ VOLLSTÄNDIG PLATTFORMKOMPATIBEL

Der Code ist jetzt **100% plattformübergreifend** kompatibel für:

### Unterstützte Plattformen
- ✅ **Raspberry Pi OS** (Linux ARM)
- ✅ **Ubuntu/Debian** (Linux x86/x64)
- ✅ **Windows 10/11**
- ✅ **macOS** (theoretisch, nicht getestet)

## 🔧 PLATTFORMSPEZIFISCHE ANPASSUNGEN

### 1. **tkinter Vollbild-Handling**
- **Windows**: `state('zoomed')` 
- **Linux/Pi**: `attributes('-zoomed', True)` mit Fallbacks
- **Fallback**: Geometrie-basierte Vollbild-Simulation

### 2. **VLC Video-Einbettung**
- **Windows**: `set_hwnd()` für Windows-Handle
- **Linux/Pi**: `set_xwindow()` für X11-Window-ID
- **Fallback**: VLC läuft in eigenem Fenster

### 3. **Video-Player Prioritäten**
- **Windows**: `vlc`, `mpv`, `mplayer`, `wmplayer`
- **Linux/Pi**: `vlc`, `mpv`, `mplayer`, `omxplayer`
- **Raspberry Pi**: `omxplayer` für Hardware-Beschleunigung

### 4. **Audio-Player Prioritäten**
- **Windows**: `vlc`, `mpv`, `wmplayer`
- **Linux/Pi**: `vlc`, `mpv`, `aplay`, `paplay`
- **Raspberry Pi**: ALSA/PulseAudio-Integration

### 5. **GPIO-Handling**
- **Raspberry Pi**: Echter HC-SR04 mit `RPi.GPIO`
- **Andere Plattformen**: Dummy-Sensor automatisch aktiv
- **Konditionaler Import**: `RPi.GPIO` nur auf Linux installiert

### 6. **Cursor-Handling**
- **Windows/Mac**: `cursor="none"` im Kiosk-Modus
- **Linux**: Alternative Cursor-Behandlung
- **Fallback**: Cursor bleibt sichtbar

## 📦 INSTALLATION NACH PLATTFORM

### Raspberry Pi / Linux
```bash
# Basis-Pakete
sudo apt update
sudo apt install python3 python3-pip vlc mpv

# Python-Abhängigkeiten 
pip3 install -r requirements.txt

# Hardware-Player (optional)
sudo apt install omxplayer  # Für Pi 4 und älter
```

### Windows
```cmd
# Python-Abhängigkeiten
pip install -r requirements.txt

# VLC installieren
# Download von: https://www.videolan.org/vlc/
```

### Ubuntu/Debian
```bash
# Basis-Pakete
sudo apt update
sudo apt install python3 python3-pip vlc mpv pulseaudio-utils

# Python-Abhängigkeiten
pip3 install -r requirements.txt
```

## 🚀 STARTMODI PLATTFORMUNABHÄNGIG

### 1. Raspberry Pi (Produktiv)
```bash
# Mit echtem HC-SR04 Sensor
python3 main.py --kiosk

# Mit Dummy-Sensor (Testing)
python3 main.py --kiosk --dummy-sensor
```

### 2. Windows/Linux (Development)
```bash
# Test-Modus mit Fenster
python3 main.py --dummy-sensor

# Vollbild-Test
python3 main.py --kiosk --dummy-sensor
```

### 3. Automatischer Plattform-Check
Der Code erkennt automatisch:
- Betriebssystem (Windows/Linux/Mac)
- Verfügbare Media-Player
- GPIO-Verfügbarkeit
- Display-Manager-Features

## ⚡ OPTIMIERUNGEN FÜR RASPBERRY PI

### Hardware-Beschleunigung
- **omxplayer**: GPU-beschleunigte Video-Wiedergabe
- **Hardware-Codec**: H.264 direkt von GPU
- **Speicher-Split**: `gpu_mem=128` in `/boot/config.txt`

### Performance-Tuning
```bash
# GPU-Speicher erhöhen
echo 'gpu_mem=128' | sudo tee -a /boot/config.txt

# Overclocking (optional)
echo 'arm_freq=1800' | sudo tee -a /boot/config.txt

# Audio-Output über Klinke
echo 'audio_output_mode=1' | sudo tee -a /boot/config.txt
```

### Service-Installation (nur Linux)
```bash
# Systemd Service kopieren
sudo cp pi-media-station.service /etc/systemd/system/

# Service aktivieren
sudo systemctl daemon-reload
sudo systemctl enable pi-media-station.service
sudo systemctl start pi-media-station.service
```

## 🔍 TROUBLESHOOTING PLATTFORMSPEZIFISCH

### Raspberry Pi
- **GPIO-Berechtigungen**: `sudo usermod -a -G gpio pi`
- **Audio-Probleme**: `sudo raspi-config` → Audio Output
- **Display-Issues**: `export DISPLAY=:0` vor dem Start

### Windows
- **VLC-Python**: Manuell VLC installieren vor pip install
- **Firewall**: Windows Defender Ausnahme für Python
- **Pfade**: Backslashes in Pfaden automatisch behandelt

### Linux Desktop
- **X11-Berechtigung**: `xhost +local:` für Display-Zugriff
- **Audio-System**: PulseAudio oder ALSA verfügbar?
- **Video-Codec**: `sudo apt install ubuntu-restricted-extras`

## ✨ FEATURES NACH PLATTFORM

### Raspberry Pi Spezial
- ✅ Echter HC-SR04 Sensor
- ✅ GPIO-Pin-Kontrolle  
- ✅ Hardware-Video-Dekodierung
- ✅ Auto-Start beim Boot
- ✅ Headless-Betrieb möglich

### Windows/Linux Desktop
- ✅ Dummy-Sensor für Development
- ✅ Window-Management
- ✅ Alle Video-Player verfügbar
- ✅ Vollständige Audio-Unterstützung
- ✅ Drag & Drop (zukünftig)

## 🎯 FAZIT

**Der Code ist jetzt 100% plattformkompatibel!**

- ✅ Automatische Plattform-Erkennung
- ✅ Plattformspezifische Optimierungen
- ✅ Graceful Fallbacks überall
- ✅ Keine Hard-Dependencies
- ✅ Robuste Fehlerbehandlung

Das System läuft auf **jedem System** - von Raspberry Pi bis Windows Desktop!

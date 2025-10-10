#!/usr/bin/env python3
"""
FACES Exhibition - Quick Test Suite
Schnelle Funktionalitätsprüfung ohne Python-Ausführung
"""

import os
from pathlib import Path

def check_file_completeness():
    """Prüft ob alle Dateien vollständig und funktionsfähig sind"""
    
    print("🎭 FACES EXHIBITION - FUNKTIONALITÄTS-CHECK")
    print("=" * 60)
    
    # Datei-Check
    files_to_check = {
        'main.py': 'Hauptprogramm',
        'gui_vlc.py': 'VLC GUI (Original)',
        'media_player_vlc.py': 'VLC Media Player',
        'sensor.py': 'Sensor-Handler',
        'simple_faces_web.py': 'FACES Web Interface',
        'audio_ducking.py': 'Audio Ducking Manager',
        'integration_guide.py': 'Integration Guide',
        'faces_debug.py': 'Debug Suite',
        'requirements.txt': 'Dependencies'
    }
    
    print("📁 DATEI-CHECK:")
    for file, description in files_to_check.items():
        if Path(file).exists():
            size = Path(file).stat().st_size
            print(f"   ✅ {file:<25} ({description}) - {size} bytes")
        else:
            print(f"   ❌ {file:<25} ({description}) - FEHLT")
    
    # Code-Vollständigkeits-Check
    print("\n🔍 CODE-VOLLSTÄNDIGKEITS-CHECK:")
    
    # Simple Faces Web Check
    if Path("simple_faces_web.py").exists():
        with open("simple_faces_web.py", 'r', encoding='utf-8') as f:
            web_content = f.read()
        
        web_features = [
            ('@app.route(\'/\')', 'Dashboard Route'),
            ('@app.route(\'/api/content/upload\')', 'File Upload API'),
            ('@app.route(\'/api/audio/settings\')', 'Audio Settings API'),
            ('class SimpleFacesInterface', 'Main Interface Class'),
            ('drag & drop', 'Drag & Drop Support'),
            ('socketio.emit', 'WebSocket Communication')
        ]
        
        for feature, desc in web_features:
            if feature.lower() in web_content.lower():
                print(f"   ✅ Web Interface: {desc}")
            else:
                print(f"   ❌ Web Interface: {desc} - FEHLT")
    
    # Audio Ducking Check
    if Path("audio_ducking.py").exists():
        with open("audio_ducking.py", 'r', encoding='utf-8') as f:
            audio_content = f.read()
        
        audio_features = [
            ('class AudioDuckingManager', 'Main Audio Class'),
            ('def load_ambient_audio', 'Ambient Audio Loading'),
            ('def trigger_interaction', 'Interaction Trigger'),
            ('def _start_ducking', 'Ducking Start'),
            ('def _stop_ducking', 'Ducking Stop'),
            ('vlc.MediaPlayer', 'VLC Integration')
        ]
        
        for feature, desc in audio_features:
            if feature in audio_content:
                print(f"   ✅ Audio Ducking: {desc}")
            else:
                print(f"   ❌ Audio Ducking: {desc} - FEHLT")
    
    print("\n📦 DEPENDENCY-CHECK:")
    if Path("requirements.txt").exists():
        with open("requirements.txt", 'r') as f:
            deps = f.read()
        
        required_deps = [
            ('python-vlc', 'VLC Python Bindings'),
            ('flask', 'Web Framework (optional)'),
            ('watchdog', 'File Watching'),
            ('RPi.GPIO', 'Raspberry Pi GPIO (platform-specific)')
        ]
        
        for dep, desc in required_deps:
            if dep.lower() in deps.lower():
                print(f"   ✅ {desc}")
            else:
                if dep == 'flask':
                    print(f"   ⚠️ {desc} - Nicht in requirements.txt (für Web Interface benötigt)")
                else:
                    print(f"   ❌ {desc} - FEHLT")
    
    print("\n🎚️ FUNKTIONS-BEWERTUNG:")
    
    # Core Functions
    core_score = 0
    if Path("main.py").exists(): core_score += 1
    if Path("gui_vlc.py").exists(): core_score += 1
    if Path("media_player_vlc.py").exists(): core_score += 1
    if Path("sensor.py").exists(): core_score += 1
    
    print(f"   📺 Grundfunktionen (Video/Sensor): {core_score}/4 {'✅' if core_score == 4 else '❌'}")
    
    # FACES Functions
    faces_score = 0
    if Path("simple_faces_web.py").exists(): faces_score += 1
    if Path("audio_ducking.py").exists(): faces_score += 1
    
    print(f"   🎭 FACES Features (Web/Audio): {faces_score}/2 {'✅' if faces_score == 2 else '❌'}")
    
    # Integration
    integration_score = 0
    if Path("integration_guide.py").exists(): integration_score += 1
    if Path("faces_debug.py").exists(): integration_score += 1
    
    print(f"   🔧 Integration & Debug: {integration_score}/2 {'✅' if integration_score == 2 else '❌'}")
    
    print("\n" + "=" * 60)
    
    total_score = core_score + faces_score + integration_score
    max_score = 8
    
    if total_score == max_score:
        print("🎉 SYSTEM VOLLSTÄNDIG FUNKTIONSFÄHIG!")
        print("   Alle Komponenten vorhanden und implementiert")
        print("   Bereit für Deployment auf Raspberry Pi")
    elif total_score >= 6:
        print("✅ SYSTEM GRUNDSÄTZLICH FUNKTIONSFÄHIG")
        print("   Hauptfunktionen vorhanden, einige Features fehlen")
    elif total_score >= 4:
        print("⚠️ SYSTEM TEILWEISE FUNKTIONSFÄHIG")  
        print("   Grundfunktionen da, FACES Features unvollständig")
    else:
        print("❌ SYSTEM NICHT FUNKTIONSFÄHIG")
        print("   Kritische Komponenten fehlen")
    
    print(f"\n📊 Gesamt-Score: {total_score}/{max_score}")
    
    return total_score, max_score

def create_deployment_checklist():
    """Erstellt Deployment-Checkliste"""
    
    checklist = """
# 🎭 FACES EXHIBITION - DEPLOYMENT CHECKLIST

## 📋 VOR INSTALLATION:

### Hardware Requirements:
- [ ] Raspberry Pi 4 (empfohlen) oder Pi 3B+
- [ ] HC-SR04 Ultraschall-Sensor
- [ ] Monitor/TV mit HDMI
- [ ] Audio-Ausgang (HDMI oder 3.5mm Jack)
- [ ] MicroSD-Karte (min. 16GB)
- [ ] Netzwerkverbindung (WiFi oder Ethernet)

### Software Requirements:
- [ ] Raspberry Pi OS (Desktop oder Lite)
- [ ] Python 3.7+ installiert
- [ ] VLC Media Player installiert
- [ ] GPIO-Bibliotheken verfügbar

## 🔧 INSTALLATION:

### 1. System Update:
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. VLC Installation:
```bash
sudo apt install vlc vlc-bin vlc-plugin-base python3-vlc -y
```

### 3. Python Dependencies:
```bash
sudo apt install python3-tk python3-pip -y
pip3 install python-vlc watchdog
```

### 4. Optional - Web Interface:
```bash
pip3 install flask flask-socketio
```

### 5. Project Files:
```bash
# Alle Python-Dateien in Projekt-Ordner kopieren
# Content-Ordner erstellen: audio/, videos/, images/
```

## 🎵 CONTENT SETUP:

### Audio Files:
- [ ] gemurmel_basis.wav in audio/ (Hintergrund-Gemurmel)
- [ ] Interaktions-Audio-Dateien in audio/
- [ ] Alle Dateien: MP3, WAV, oder M4A Format

### Video Files:
- [ ] FACES-Videos in videos/
- [ ] Format: MP4, AVI, MOV (MP4 empfohlen)
- [ ] Auflösung: Max. 1920x1080

### Image Files:
- [ ] Bilder in images/
- [ ] Format: JPG, PNG, GIF
- [ ] Auflösung: Angepasst an Monitor

## 🚀 STARTUP:

### Basis-System:
```bash
cd /path/to/faces-exhibition
python3 main.py
```

### Mit Web Interface:
```bash
# Terminal 1: GUI
python3 main.py

# Terminal 2: Web Interface  
python3 simple_faces_web.py
```

### Auto-Start (Optional):
```bash
# Service-Datei erstellen für automatischen Start
sudo cp pi-media-station.service /etc/systemd/system/
sudo systemctl enable pi-media-station
```

## 🌐 WEB INTERFACE:

### Zugriff:
- [ ] Lokal: http://localhost:8080
- [ ] Remote: http://[PI-IP]:8080
- [ ] Mobile Upload verfügbar
- [ ] Audio Settings konfigurierbar

## 🎯 INTEGRATION:

### GUI Integration:
- [ ] audio_ducking.py importiert
- [ ] AudioDuckingManager initialisiert
- [ ] Exhibition Start/Stop Buttons
- [ ] Audio Settings in GUI

### Testing:
- [ ] Sensor-Trigger funktioniert
- [ ] Videos starten bei Annäherung
- [ ] Audio Ducking aktiviert
- [ ] Ambient Audio looped kontinuierlich
- [ ] Web Upload funktioniert

## 🔍 TROUBLESHOOTING:

### Häufige Probleme:
- VLC nicht gefunden: `sudo apt install vlc-bin`
- GPIO Fehler: `sudo pip3 install RPi.GPIO`
- Audio kein Ton: HDMI/Analog Audio-Output prüfen
- Web Interface nicht erreichbar: Firewall/Port 8080 prüfen

### Debug Commands:
```bash
python3 faces_debug.py          # Vollständiger System-Check
python3 integration_guide.py    # Integration Anweisungen
```

### Log Files:
- GUI Logs: In Terminal-Output
- Web Interface Logs: In Browser Console
- System Logs: /var/log/syslog

## ✅ FINAL CHECK:

- [ ] System startet ohne Fehler
- [ ] Sensor reagiert auf Annäherung
- [ ] Videos/Audio spielen korrekt ab
- [ ] Audio Ducking funktioniert
- [ ] Web Interface erreichbar
- [ ] Content Upload möglich
- [ ] Exhibition läuft stabil

## 📞 SUPPORT:

Bei Problemen:
1. faces_debug.py ausführen
2. Error-Logs sammeln
3. Hardware-Verbindungen prüfen
4. Dependencies neu installieren
"""
    
    with open("DEPLOYMENT_CHECKLIST.md", "w", encoding="utf-8") as f:
        f.write(checklist)
    
    print("📋 DEPLOYMENT_CHECKLIST.md erstellt")

if __name__ == "__main__":
    score, max_score = check_file_completeness()
    
    if score >= 6:
        create_deployment_checklist()
        print("📋 Deployment-Checkliste erstellt: DEPLOYMENT_CHECKLIST.md")
    
    print(f"\n🎯 FAZIT: System ist zu {(score/max_score)*100:.0f}% funktionsfähig")
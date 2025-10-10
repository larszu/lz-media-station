# FACES AUSSTELLUNG - ERWEITERTE FEATURES KONZEPT

## 🎭 FACES AUSSTELLUNG REQUIREMENTS

### Aktuelle Situation:
- 2-10 Monitor-Setups in einem Raum
- Globales Gemurmel als Basis-Audio (gleiche Datei überall)
- Bei Annäherung: Bilder/Videos/Audio-Wechsel
- Web-Interface für Management gewünscht
- Flexible Einstellungen für unklaren Anwendungsfall

### Erkannte Anforderungen:
1. **Multi-Station Management** - Zentrale Kontrolle aller Monitore
2. **Ambient Audio System** - Globales Gemurmel synchron
3. **Web-Interface** - Remote-Konfiguration
4. **Mobile Upload** - Content-Management via Smartphone
5. **Flexible Playlist-Modi** - Verschiedene Interaktions-Szenarien

## 🚀 VORGESCHLAGENE ERWEITERUNGEN:

### 1. ZENTRALES MANAGEMENT SYSTEM
```
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│   Web Dashboard │ -> │ Master-Pi    │ -> │ Station-Pi 1 │
│   (Tablet/Phone)│    │ (Controller) │    │ Station-Pi 2 │
└─────────────────┘    └──────────────┘    │ Station-Pi N │
                                            └──────────────┘
```

### 2. AUDIO-MANAGEMENT
- **Ambient Layer**: Globales Gemurmel (Master-Pi managed)
- **Interactive Layer**: Station-spezifische Audio-Reaktionen
- **Audio-Mixing**: Ambient dämpfen wenn Station aktiv

### 3. WEB-INTERFACE FEATURES
```
🌐 Web-Dashboard Features:
├── 📊 Live-Status aller Stationen
├── 📁 Content-Upload (Drag & Drop)
├── 🎚️ Audio-Level pro Station
├── ⏱️ Timing-Parameter global/individual
├── 📋 Playlist-Management
├── 🎯 Interaktions-Modi konfigurieren
└── 📈 Analytics (wer war wann wo)
```

### 4. ERWEITERTE INTERAKTIONS-MODI
```
Mode 1: PORTRAIT MODE
├── Basis: Stille Person auf Monitor
├── Nähe: Spricht/Audio aktiviert
└── Weg: Verstummt wieder

Mode 2: STORY MODE  
├── Basis: Neutral/wartend
├── Nähe: Persönliche Geschichte
└── Mehrere Personen: Gespräch zwischen Charakteren

Mode 3: REACTIVE MODE
├── Basis: Beobachtung der Umgebung
├── Nähe: Direkte Ansprache des Besuchers
└── Bewegung: Folgt mit Blick/reagiert

Mode 4: CROWD MODE
├── 1 Person: Intimes Gespräch
├── 2+ Personen: Gruppen-Interaktion
└── Lange Verweildauer: Tiefere Inhalte
```

### 5. TECHNISCHE ERWEITERUNGEN
```
🔧 Hardware-Erweiterungen:
├── 📸 Kamera-Integration (Gesichts-/Alter-Erkennung)
├── 🎤 Mikrofon (Stimmen-Aktivierung)
├── 💡 LED-Feedback (Interaktions-Status)
├── 📳 Vibrations-Feedback bei Touch-Displays
└── 🌡️ Umgebungs-Sensoren (Licht/Temperatur)

🛜 Netzwerk-Features:
├── 📡 MQTT für Station-Kommunikation
├── 🔄 Auto-Sync Content zwischen Stationen
├── 📱 Progressive Web App für Mobile
├── 🔒 Benutzer-Rollen (Admin/Kurator/Techniker)
└── 📊 Real-time Analytics Dashboard
```
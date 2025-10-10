python3 main.py
#!/usr/bin/env python3
"""
FACES Exhibition - Integration Guide
Zeigt wie Audio Ducking in bestehende GUI integriert wird
"""
import os

# SCHRITT 1: gui_vlc.py erweitern
integration_guide = """
# ========================================
# INTEGRATION VON AUDIO DUCKING IN GUI_VLC.PY
# ========================================

# 1. Import hinzufügen (am Anfang der Datei)
from audio_ducking import AudioDuckingManager

# 2. In der __init__ Methode der VLCMediaPlayerGUI Klasse:
def __init__(self):
    # ... bestehender Code ...
    
    # Audio Ducking Manager hinzufügen
    self.audio_manager = AudioDuckingManager()
    self.exhibition_started = False

# 3. Methode für Exhibition Start:
def start_exhibition(self):
    '''Exhibition mit Ambient Audio starten'''
    if not self.exhibition_started:
        # Ambient Audio Datei laden
        ambient_file = os.path.join("audio", "gemurmel_basis.wav")
        
        if self.audio_manager.load_ambient_audio(ambient_file):
            self.audio_manager.start_ambient()
            self.exhibition_started = True
            print("🎭 FACES Exhibition gestartet - Ambient Audio läuft")
            self.media_status_label.config(text="Exhibition läuft - Ambient Audio aktiv", fg='green')
        else:
            print("❌ Konnte Ambient Audio nicht laden")
            self.media_status_label.config(text="Warnung: Ambient Audio nicht verfügbar", fg='orange')

# 4. Methode für Exhibition Stop:
def stop_exhibition(self):
    '''Exhibition stoppen'''
    if self.exhibition_started:
        self.audio_manager.stop_ambient()
        self.exhibition_started = False
        print("🎭 FACES Exhibition gestoppt")
        self.media_status_label.config(text="Exhibition gestoppt", fg='red')

# 5. handle_sensor_trigger erweitern (bestehende Methode ändern):
def handle_sensor_trigger(self):
    '''Sensor ausgelöst - mit Audio Ducking'''
    try:
        if self.sensor_mode == "video":
            selected_videos = self.get_selected_videos()
            print(f"[VLC-GUI] Sensor ausgelöst - Video-Modus: {len(selected_videos)} Videos gefunden")
            
            if selected_videos:
                video_file = random.choice(selected_videos)
                
                # AUDIO DUCKING AKTIVIEREN
                if self.exhibition_started:
                    self.audio_manager.trigger_interaction(video_file)
                
                # Bestehende VLC-Player Logik
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                success = self.media_player.play_media_list([video_file])
                if success:
                    self.media_status_label.config(
                        text=f"Sensor → Video + Audio Ducking: {os.path.basename(video_file)}", fg='lime'
                    )
                else:
                    self.media_status_label.config(text="Video-Start fehlgeschlagen!", fg='red')
            
        elif self.sensor_mode == "audio":
            # Ähnlich für Audio-Modus...
            selected_audios = self.get_selected_audios()
            if selected_audios:
                audio_file = random.choice(selected_audios)
                
                # AUDIO DUCKING AKTIVIEREN  
                if self.exhibition_started:
                    self.audio_manager.trigger_interaction(audio_file)
                
                # Normale Audio-Wiedergabe...
                
    except Exception as e:
        print(f"[VLC-GUI] FEHLER in handle_sensor_trigger: {e}")

# 6. GUI-Buttons hinzufügen (in create_ui_elements):
def create_ui_elements(self):
    # ... bestehender Code ...
    
    # Exhibition Control Frame
    exhibition_frame = tk.Frame(control_frame)
    exhibition_frame.pack(fill='x', pady=5)
    
    tk.Label(exhibition_frame, text="🎭 FACES Exhibition:", font=('Arial', 10, 'bold')).pack(side='left')
    
    self.start_exhibition_btn = tk.Button(
        exhibition_frame, 
        text="▶️ Exhibition Starten",
        command=self.start_exhibition,
        bg='green', fg='white'
    )
    self.start_exhibition_btn.pack(side='left', padx=5)
    
    self.stop_exhibition_btn = tk.Button(
        exhibition_frame,
        text="⏹️ Exhibition Stoppen", 
        command=self.stop_exhibition,
        bg='red', fg='white'
    )
    self.stop_exhibition_btn.pack(side='left', padx=5)
    
    # Audio Settings Frame
    audio_frame = tk.Frame(control_frame)
    audio_frame.pack(fill='x', pady=5)
    
    tk.Label(audio_frame, text="🎚️ Audio Settings:", font=('Arial', 10, 'bold')).pack(anchor='w')
    
    # Ambient Volume
    ambient_frame = tk.Frame(audio_frame)
    ambient_frame.pack(fill='x', pady=2)
    tk.Label(ambient_frame, text="Ambient Volume:").pack(side='left')
    self.ambient_scale = tk.Scale(ambient_frame, from_=0, to=100, orient='horizontal')
    self.ambient_scale.set(30)  # 30%
    self.ambient_scale.pack(side='right', fill='x', expand=True)
    
    # Ducking Level
    ducking_frame = tk.Frame(audio_frame)
    ducking_frame.pack(fill='x', pady=2)
    tk.Label(ducking_frame, text="Audio Ducking:").pack(side='left')
    self.ducking_scale = tk.Scale(ducking_frame, from_=0, to=50, orient='horizontal')
    self.ducking_scale.set(10)  # 10%
    self.ducking_scale.pack(side='right', fill='x', expand=True)
    
    # Update Button
    tk.Button(
        audio_frame,
        text="💾 Audio Settings Speichern",
        command=self.update_audio_settings
    ).pack(pady=5)

# 7. Audio Settings Update Methode:
def update_audio_settings(self):
    '''Audio Settings von GUI übernehmen'''
    ambient_vol = self.ambient_scale.get() / 100.0
    ducking_vol = self.ducking_scale.get() / 100.0
    
    self.audio_manager.update_settings(
        ambient_vol=ambient_vol,
        ducking_vol=ducking_vol
    )
    
    print(f"🎚️ Audio Settings aktualisiert: Ambient={ambient_vol}, Ducking={ducking_vol}")
    self.media_status_label.config(text="Audio Settings gespeichert", fg='blue')

# 8. Cleanup beim Beenden (in destructor/cleanup):
def cleanup(self):
    '''Beim Beenden aufrufen'''
    try:
        if hasattr(self, 'audio_manager'):
            self.audio_manager.stop_ambient()
        # ... bestehender cleanup code ...
    except:
        pass
"""

print("🎭 FACES INTEGRATION GUIDE")
print("=" * 50)
print(integration_guide)

# Erstelle auch Template-Dateien
def create_example_files():
    """Erstellt Beispiel-Dateien für FACES"""
    
    # Beispiel Audio-Datei Info
    audio_info = """
# AUDIO-DATEIEN FÜR FACES EXHIBITION

📁 Ordnerstruktur:
audio/
├── gemurmel_basis.wav          # Hintergrund-Gemurmel (looped)
├── person_1_geschichte.mp3     # Interaktions-Audio
├── person_2_gespräch.wav       # Weitere Interaktionen
└── README.md                   # Diese Datei

🎵 Ambient Audio (gemurmel_basis.wav):
- Sollte nahtlos loopbar sein
- Empfohlene Länge: 2-10 Minuten
- Format: WAV oder MP3
- Lautstärke: Gleichmäßig, nicht zu laut

🎯 Interaktions-Audio:
- Verschiedene Personen/Charaktere  
- Geschichten, Gespräche, Reaktionen
- Format: MP3, WAV, M4A
- Länge: 30 Sekunden bis 5 Minuten

⚠️ WICHTIG:
- Dateinamen ohne Leerzeichen verwenden
- Unterstützte Formate: .mp3, .wav, .ogg, .m4a, .aac
- Für beste Kompatibilität: MP3 oder WAV verwenden
"""
    
    # Ordner erstellen
    os.makedirs("audio", exist_ok=True)
    os.makedirs("videos", exist_ok=True) 
    os.makedirs("images", exist_ok=True)
    
    # README erstellen
    with open("audio/README.md", "w", encoding="utf-8") as f:
        f.write(audio_info)
    
    print("📁 Beispiel-Ordnerstruktur erstellt")
    print("📄 audio/README.md mit Anweisungen erstellt")

if __name__ == "__main__":
    create_example_files()
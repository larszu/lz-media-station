"""
Vereinfachte VLC-basierte GUI für Pi Media Station
"""
import tkinter as tk
from tkinter import ttk
import os
import time
from config import DEFAULT_MIN_DIST, DEFAULT_MAX_DIST, DEFAULT_INTERVAL, VIDEO_FOLDER, IMAGE_FOLDER, AUDIO_FOLDER, IMAGE_DISPLAY_TIME
from media_player_vlc import VLCMediaPlayer

class VLCMediaStationGUI:
    def __init__(self, sensor_thread, kiosk_mode=False):
        self.sensor_thread = sensor_thread
        self.media_player = VLCMediaPlayer()
        self.kiosk_mode = kiosk_mode
        self.sensor_mode = "video"  # "video" oder "audio"
        
        # Dateien
        self.all_video_files = []
        self.all_image_files = []
        self.all_audio_files = []
        self.video_checkboxes = {}
        self.image_checkboxes = {}
        self.audio_checkboxes = {}
        
        # GUI erstellen
        self.root = tk.Tk()
        self.root.title("Pi Media Station - VLC Edition")
        self.root.configure(bg='black')
        
        if self.kiosk_mode:
            self.root.attributes('-fullscreen', True)
        else:
            self.root.geometry("1000x700")
        
        self.setup_gui()
        self.scan_media_files()
        self.update_status()
    
    def setup_gui(self):
        """GUI-Layout erstellen"""
        # Hauptframe
        main_frame = tk.Frame(self.root, bg='black')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Titel
        tk.Label(main_frame, text="🎬 Pi Media Station - VLC Edition", 
                font=('Arial', 24, 'bold'), fg='cyan', bg='black').pack(pady=10)
        
        # Status
        self.status_label = tk.Label(main_frame, text="Sensor: Initialisierung...", 
                                   font=('Arial', 16), fg='yellow', bg='black')
        self.status_label.pack(pady=5)
        
        # Sensor-Einstellungen
        settings_frame = tk.LabelFrame(main_frame, text="🔧 Einstellungen", 
                                     font=('Arial', 14, 'bold'), fg='white', bg='black')
        settings_frame.pack(pady=10, padx=10, fill='x')
        
        # Min/Max Abstand
        tk.Label(settings_frame, text="Min. Abstand (cm):", fg='white', bg='black').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.min_dist_var = tk.StringVar(value=str(DEFAULT_MIN_DIST))
        tk.Entry(settings_frame, textvariable=self.min_dist_var, width=10).grid(row=0, column=1, padx=10)
        
        tk.Label(settings_frame, text="Max. Abstand (cm):", fg='white', bg='black').grid(row=0, column=2, sticky='w', padx=10)
        self.max_dist_var = tk.StringVar(value=str(DEFAULT_MAX_DIST))
        tk.Entry(settings_frame, textvariable=self.max_dist_var, width=10).grid(row=0, column=3, padx=10)
        
        # Sensor-Modus
        tk.Label(settings_frame, text="Sensor-Modus:", fg='orange', bg='black').grid(row=1, column=0, sticky='w', padx=10, pady=10)
        self.sensor_mode_var = tk.StringVar(value="video")
        tk.Radiobutton(settings_frame, text="Video-Modus", variable=self.sensor_mode_var, value="video", 
                      bg='black', fg='white', command=self.update_sensor_mode).grid(row=1, column=1, sticky='w')
        tk.Radiobutton(settings_frame, text="Audio+Bild-Modus", variable=self.sensor_mode_var, value="audio", 
                      bg='black', fg='white', command=self.update_sensor_mode).grid(row=1, column=2, sticky='w')
        
        # VLC-Steuerung
        control_frame = tk.Frame(settings_frame, bg='black')
        control_frame.grid(row=2, column=0, columnspan=4, pady=10)
        
        tk.Button(control_frame, text="⏸️ Pause", command=self.vlc_pause, bg='yellow').pack(side='left', padx=5)
        tk.Button(control_frame, text="⏹️ Stop", command=self.vlc_stop, bg='red', fg='white').pack(side='left', padx=5)
        tk.Button(control_frame, text="⏭️ Nächstes", command=self.vlc_next, bg='lightblue').pack(side='left', padx=5)
        tk.Button(control_frame, text="⏮️ Vorheriges", command=self.vlc_previous, bg='lightblue').pack(side='left', padx=5)
        
        # Kiosk-Modus Toggle
        if self.kiosk_mode:
            tk.Button(control_frame, text="→ Fenstermodus", command=self.toggle_kiosk, 
                     bg='orange', fg='black').pack(side='right', padx=5)
        else:
            tk.Button(control_frame, text="→ Vollbild", command=self.toggle_kiosk, 
                     bg='lime', fg='black').pack(side='right', padx=5)
        
        # Dateiauswahl
        files_frame = tk.LabelFrame(main_frame, text="📁 Datei-Auswahl", 
                                  font=('Arial', 14, 'bold'), fg='lime', bg='black')
        files_frame.pack(pady=10, fill='both', expand=True)
        
        # Drei Spalten für Video/Bild/Audio
        video_frame = tk.Frame(files_frame, bg='black')
        video_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        image_frame = tk.Frame(files_frame, bg='black')
        image_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        audio_frame = tk.Frame(files_frame, bg='black')
        audio_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        # Labels
        tk.Label(video_frame, text="🎬 Videos", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=5)
        tk.Label(image_frame, text="🖼️ Bilder", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=5)
        tk.Label(audio_frame, text="🎵 Audio", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=5)
        
        # Scrollable Checkboxen
        self.video_scroll_frame = tk.Frame(video_frame, bg='black')
        self.video_scroll_frame.pack(fill='both', expand=True)
        
        self.image_scroll_frame = tk.Frame(image_frame, bg='black')
        self.image_scroll_frame.pack(fill='both', expand=True)
        
        self.audio_scroll_frame = tk.Frame(audio_frame, bg='black')
        self.audio_scroll_frame.pack(fill='both', expand=True)
        
        # Media-Status
        self.media_status_label = tk.Label(main_frame, text="Status: VLC bereit", 
                                         font=('Arial', 14), fg='lime', bg='black')
        self.media_status_label.pack(pady=10)
        
        # ESC-Taste für Vollbild-Toggle
        self.root.bind('<Escape>', lambda e: self.toggle_kiosk())
    
    def scan_media_files(self):
        """Mediendateien scannen und Checkboxen erstellen"""
        # Video-Dateien
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv']
        if os.path.exists(VIDEO_FOLDER):
            self.all_video_files = [
                os.path.join(VIDEO_FOLDER, f) 
                for f in os.listdir(VIDEO_FOLDER) 
                if any(f.lower().endswith(ext) for ext in video_extensions)
            ]
        
        # Bild-Dateien
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        if os.path.exists(IMAGE_FOLDER):
            self.all_image_files = [
                os.path.join(IMAGE_FOLDER, f) 
                for f in os.listdir(IMAGE_FOLDER) 
                if any(f.lower().endswith(ext) for ext in image_extensions)
            ]
        
        # Audio-Dateien
        audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a']
        if os.path.exists(AUDIO_FOLDER):
            self.all_audio_files = [
                os.path.join(AUDIO_FOLDER, f) 
                for f in os.listdir(AUDIO_FOLDER) 
                if any(f.lower().endswith(ext) for ext in audio_extensions)
            ]
        
        # Checkboxen erstellen
        self.create_checkboxes()
    
    def create_checkboxes(self):
        """Checkboxen für alle Medientypen erstellen"""
        # Videos
        for widget in self.video_scroll_frame.winfo_children():
            widget.destroy()
        self.video_checkboxes.clear()
        
        for video_file in self.all_video_files:
            var = tk.BooleanVar(value=True)  # Standardmäßig alle ausgewählt
            self.video_checkboxes[video_file] = var
            cb = tk.Checkbutton(self.video_scroll_frame, text=os.path.basename(video_file), 
                               variable=var, bg='black', fg='white', selectcolor='darkgray')
            cb.pack(anchor='w', padx=5, pady=1)
        
        # Bilder
        for widget in self.image_scroll_frame.winfo_children():
            widget.destroy()
        self.image_checkboxes.clear()
        
        for image_file in self.all_image_files:
            var = tk.BooleanVar(value=True)
            self.image_checkboxes[image_file] = var
            cb = tk.Checkbutton(self.image_scroll_frame, text=os.path.basename(image_file), 
                               variable=var, bg='black', fg='white', selectcolor='darkgray')
            cb.pack(anchor='w', padx=5, pady=1)
        
        # Audio
        for widget in self.audio_scroll_frame.winfo_children():
            widget.destroy()
        self.audio_checkboxes.clear()
        
        for audio_file in self.all_audio_files:
            var = tk.BooleanVar(value=True)
            self.audio_checkboxes[audio_file] = var
            cb = tk.Checkbutton(self.audio_scroll_frame, text=os.path.basename(audio_file), 
                               variable=var, bg='black', fg='white', selectcolor='darkgray')
            cb.pack(anchor='w', padx=5, pady=1)
        
        print(f"[VLC-GUI] Gefunden: {len(self.all_video_files)} Videos, {len(self.all_image_files)} Bilder, {len(self.all_audio_files)} Audio")
    
    def get_selected_videos(self):
        """Ausgewählte Videos zurückgeben"""
        return [path for path, var in self.video_checkboxes.items() if var.get()]
    
    def get_selected_images(self):
        """Ausgewählte Bilder zurückgeben"""
        return [path for path, var in self.image_checkboxes.items() if var.get()]
    
    def get_selected_audios(self):
        """Ausgewählte Audio-Dateien zurückgeben"""
        return [path for path, var in self.audio_checkboxes.items() if var.get()]
    
    def update_sensor_mode(self):
        """Sensor-Modus aktualisieren"""
        self.sensor_mode = self.sensor_mode_var.get()
        print(f"[VLC-GUI] Sensor-Modus: {self.sensor_mode}")
    
    def vlc_pause(self):
        """VLC Pause/Play"""
        self.media_player.pause()
    
    def vlc_stop(self):
        """VLC Stop"""
        self.media_player.stop()
    
    def vlc_next(self):
        """VLC Nächstes"""
        self.media_player.next_media()
    
    def vlc_previous(self):
        """VLC Vorheriges"""
        self.media_player.previous_media()
    
    def toggle_kiosk(self):
        """Vollbild-Modus umschalten"""
        try:
            self.kiosk_mode = not self.kiosk_mode
            self.root.attributes('-fullscreen', self.kiosk_mode)
            print(f"[VLC-GUI] Kiosk-Modus: {self.kiosk_mode}")
        except Exception as e:
            print(f"[VLC-GUI] Kiosk-Fehler: {e}")
    
    def update_status(self):
        """Status-Update-Schleife"""
        distance = self.sensor_thread.distance
        
        if distance == 0.0:
            self.status_label.config(text="Sensor: Nicht verbunden", fg='red')
            self.media_player.show_black()
            self.media_status_label.config(text="Status: Kein Sensor", fg='red')
        else:
            self.status_label.config(text=f"Abstand: {distance:.1f} cm", fg='lime')
            
            # Sensor-Bereich prüfen
            try:
                min_dist = float(self.min_dist_var.get())
                max_dist = float(self.max_dist_var.get())
                
                if min_dist <= distance <= max_dist:
                    # Sensor ausgelöst
                    self.handle_sensor_trigger()
                else:
                    # Außerhalb Bereich - weiter laufen lassen
                    if self.media_player.is_playing:
                        media_info = self.media_player.get_current_media_info()
                        if media_info:
                            self.media_status_label.config(
                                text=f"Läuft: {media_info['name']} ({media_info['index']}/{media_info['total']})",
                                fg='cyan'
                            )
                        
                        # Auto-weiter bei Ende
                        if self.media_player.is_media_finished():
                            self.media_player.next_media()
                    else:
                        self.media_status_label.config(text="Bereit - außerhalb Sensor-Bereich", fg='yellow')
                        
            except ValueError:
                self.media_status_label.config(text="Ungültige Sensor-Werte", fg='red')
        
        # Nächstes Update
        self.root.after(200, self.update_status)
    
    def handle_sensor_trigger(self):
        """Sensor ausgelöst - VLC-Playlist starten"""
        if self.sensor_mode == "video":
            # Nur Videos
            selected_videos = self.get_selected_videos()
            if selected_videos and not self.media_player.is_playing:
                self.media_player.play_media_list(selected_videos, shuffle=True)
                self.media_status_label.config(
                    text=f"Video-Playlist: {len(selected_videos)} Videos", fg='lime'
                )
        
        elif self.sensor_mode == "audio":
            # Audio + Bilder gemischt
            selected_audios = self.get_selected_audios()
            selected_images = self.get_selected_images()
            mixed_playlist = selected_audios + selected_images
            
            if mixed_playlist and not self.media_player.is_playing:
                self.media_player.play_media_list(mixed_playlist, shuffle=True)
                self.media_status_label.config(
                    text=f"Audio+Bild: {len(selected_audios)}A + {len(selected_images)}B", fg='lime'
                )
    
    def run(self):
        """GUI starten"""
        try:
            self.root.mainloop()
        finally:
            self.sensor_thread.stop()
            self.media_player.cleanup()

# Kompatibilitäts-Alias
MediaStationGUI = VLCMediaStationGUI

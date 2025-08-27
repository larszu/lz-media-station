"""
Vollständige VLC-basierte GUI für Pi Media Station mit allen Features
"""
import tkinter as tk
from tkinter import ttk, simpledialog
import os
import time
import json
import datetime
import subprocess
import platform
from config import DEFAULT_MIN_DIST, DEFAULT_MAX_DIST, DEFAULT_INTERVAL, VIDEO_FOLDER, IMAGE_FOLDER, AUDIO_FOLDER, IMAGE_DISPLAY_TIME, AUDIO_FADE_TIME, MIN_VIDEO_RUNTIME, MIN_IMAGE_DISPLAY_TIME, MIN_AUDIO_RUNTIME
from media_player_vlc import VLCMediaPlayer

class VLCMediaStationGUI:
    def __init__(self, sensor_thread, kiosk_mode=False):
        self.sensor_thread = sensor_thread
        self.media_player = VLCMediaPlayer()
        self.kiosk_mode = kiosk_mode  # Nur für GUI-Fenster, nicht für Media-Vorschau
        self.sensor_mode = "video"  # "video" oder "audio"
        
        # Dateien
        self.all_video_files = []
        self.all_image_files = []
        self.all_audio_files = []
        self.video_checkboxes = {}
        self.image_checkboxes = {}
        self.audio_checkboxes = {}
        
        # Konfigurable Werte (wie in der alten GUI)
        self.current_image_display_time = IMAGE_DISPLAY_TIME
        self.current_audio_fade_time = AUDIO_FADE_TIME
        self.current_min_video_time = MIN_VIDEO_RUNTIME
        self.current_min_image_time = MIN_IMAGE_DISPLAY_TIME
        self.current_min_audio_time = MIN_AUDIO_RUNTIME
        
        # GUI erstellen
        self.root = tk.Tk()
        self.root.title("Pi Media Station - VLC Edition")
        self.root.configure(bg='black')
        
        # GUI ist immer im Fenstermodus - Media-Player hat eigenes Vollbild
        if self.kiosk_mode:
            self.root.state('zoomed')  # GUI maximiert, aber nicht fullscreen
        else:
            self.root.geometry("1200x800")
        
        self.setup_gui()
        self.scan_media_files()
        
        # Sensor-Modus initial setzen
        self.update_sensor_mode()
        
        self.update_status()
    
    def setup_gui(self):
        """Vollständige GUI-Layout mit allen Features"""
        # Hauptframe mit Scrolling
        canvas = tk.Canvas(self.root, bg='black')
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = scrollable_frame
        
        # Titel
        tk.Label(main_frame, text="Pi Media Station - VLC Edition", 
                font=('Arial', 24, 'bold'), fg='cyan', bg='black').pack(pady=10)
        
        # Status
        self.status_label = tk.Label(main_frame, text="Sensor: Initialisierung...", 
                                   font=('Arial', 16), fg='yellow', bg='black')
        self.status_label.pack(pady=5)
        
        # Sensor-Einstellungen
        settings_frame = tk.LabelFrame(main_frame, text="Sensor-Einstellungen", 
                                     font=('Arial', 14, 'bold'), fg='white', bg='black', bd=2)
        settings_frame.pack(pady=10, padx=10, fill='x')
        
        # Min/Max Abstand mit Speichern-Buttons
        tk.Label(settings_frame, text="Min. Abstand (cm):", fg='white', bg='black').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.min_dist_var = tk.StringVar(value=str(DEFAULT_MIN_DIST))
        tk.Entry(settings_frame, textvariable=self.min_dist_var, width=10, 
                bg='gray20', fg='white', insertbackground='white').grid(row=0, column=1, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_min_dist, font=('Arial', 10)).grid(row=0, column=2, padx=5)
        
        tk.Label(settings_frame, text="Max. Abstand (cm):", fg='white', bg='black').grid(row=0, column=3, sticky='w', padx=10)
        self.max_dist_var = tk.StringVar(value=str(DEFAULT_MAX_DIST))
        tk.Entry(settings_frame, textvariable=self.max_dist_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=0, column=4, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_max_dist, font=('Arial', 10)).grid(row=0, column=5, padx=5)
        
        # Messintervall
        tk.Label(settings_frame, text="Messintervall (ms):", fg='white', bg='black').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.interval_var = tk.StringVar(value=str(int(DEFAULT_INTERVAL * 1000)))
        tk.Entry(settings_frame, textvariable=self.interval_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=1, column=1, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_interval, font=('Arial', 10)).grid(row=1, column=2, padx=5)
        
        # Bildwechselzeit
        tk.Label(settings_frame, text="Bildwechsel (s):", fg='white', bg='black').grid(row=1, column=3, sticky='w', padx=10)
        self.image_interval_var = tk.StringVar(value=str(IMAGE_DISPLAY_TIME))
        tk.Entry(settings_frame, textvariable=self.image_interval_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=1, column=4, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_image_interval, font=('Arial', 10)).grid(row=1, column=5, padx=5)
        
        # Audio-Fade
        tk.Label(settings_frame, text="Audio-Fade (ms):", fg='white', bg='black').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.audio_fade_var = tk.StringVar(value=str(int(AUDIO_FADE_TIME * 1000)))
        tk.Entry(settings_frame, textvariable=self.audio_fade_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=2, column=1, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_audio_fade, font=('Arial', 10)).grid(row=2, column=2, padx=5)
        
        # Mindestzeiten
        tk.Label(settings_frame, text="Min. Video-Zeit (s):", fg='white', bg='black').grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.min_video_var = tk.StringVar(value=str(MIN_VIDEO_RUNTIME))
        tk.Entry(settings_frame, textvariable=self.min_video_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=3, column=1, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_min_video_time, font=('Arial', 10)).grid(row=3, column=2, padx=5)
        
        tk.Label(settings_frame, text="Min. Bild-Zeit (s):", fg='white', bg='black').grid(row=3, column=3, sticky='w', padx=10)
        self.min_image_var = tk.StringVar(value=str(MIN_IMAGE_DISPLAY_TIME))
        tk.Entry(settings_frame, textvariable=self.min_image_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=3, column=4, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_min_image_time, font=('Arial', 10)).grid(row=3, column=5, padx=5)
        
        tk.Label(settings_frame, text="Min. Audio-Zeit (s):", fg='white', bg='black').grid(row=4, column=0, sticky='w', padx=10, pady=5)
        self.min_audio_var = tk.StringVar(value=str(MIN_AUDIO_RUNTIME))
        tk.Entry(settings_frame, textvariable=self.min_audio_var, width=10,
                bg='gray20', fg='white', insertbackground='white').grid(row=4, column=1, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                 command=self.save_min_audio_time, font=('Arial', 10)).grid(row=4, column=2, padx=5)
        
        # Sensor-Modus
        sensor_mode_frame = tk.LabelFrame(main_frame, text="Sensor-Modus", 
                                        font=('Arial', 14, 'bold'), fg='orange', bg='black', bd=2)
        sensor_mode_frame.pack(pady=10, padx=10, fill='x')
        
        self.sensor_mode_var = tk.StringVar(value="video")
        tk.Radiobutton(sensor_mode_frame, text="Video abspielen bei Sensor-Auslösung", 
                      variable=self.sensor_mode_var, value="video", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 12),
                      command=self.update_sensor_mode).pack(anchor='w', padx=10, pady=5)
        
        tk.Radiobutton(sensor_mode_frame, text="Audio abspielen bei Sensor-Auslösung (+ Bilder)", 
                      variable=self.sensor_mode_var, value="audio", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 12),
                      command=self.update_sensor_mode).pack(anchor='w', padx=10, pady=5)
        
        # VLC-Steuerung + Media-Vollbild
        control_frame = tk.LabelFrame(main_frame, text="VLC-Steuerung", 
                                    font=('Arial', 14, 'bold'), fg='magenta', bg='black', bd=2)
        control_frame.pack(pady=10, padx=10, fill='x')
        
        controls_row1 = tk.Frame(control_frame, bg='black')
        controls_row1.pack(pady=5)
        
        tk.Button(controls_row1, text="Pause/Play", command=self.vlc_pause, 
                 bg='yellow', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Stop", command=self.vlc_stop, 
                 bg='red', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Nächstes", command=self.vlc_next, 
                 bg='lightblue', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Vorheriges", command=self.vlc_previous, 
                 bg='lightblue', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        
        # Media-Vollbild Toggle (nicht GUI-Vollbild!)
        controls_row2 = tk.Frame(control_frame, bg='black')
        controls_row2.pack(pady=5)
        
        tk.Label(controls_row2, text="Media-Anzeige:", font=('Arial', 12, 'bold'), 
                fg='cyan', bg='black').pack(side='left', padx=10)
        
        tk.Button(controls_row2, text="Media-Vollbild EIN", command=self.toggle_media_fullscreen, 
                 bg='lime', fg='black', font=('Arial', 11, 'bold')).pack(side='left', padx=5)
        
        tk.Button(controls_row2, text="Media-Fenster", command=self.set_media_windowed, 
                 bg='orange', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        
        # GUI-Kontrollen
        tk.Label(controls_row2, text=" | GUI:", font=('Arial', 12, 'bold'), 
                fg='white', bg='black').pack(side='left', padx=10)
        
        tk.Button(controls_row2, text="GUI verstecken", command=self.hide_gui, 
                 bg='purple', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Button(controls_row2, text="GUI-Vollbild (F11)", command=self.toggle_gui_fullscreen, 
                 bg='darkgreen', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        
        # Playlist Editor
        playlist_frame = tk.LabelFrame(main_frame, text="Playlist Editor", 
                                      font=('Arial', 14, 'bold'), fg='magenta', bg='black', bd=2)
        playlist_frame.pack(pady=10, padx=10, fill='x')
        
        playlist_controls = tk.Frame(playlist_frame, bg='black')
        playlist_controls.pack(pady=5, fill='x')
        
        tk.Button(playlist_controls, text="↻ Playlists laden", bg='lightblue', fg='black',
                 command=self.refresh_playlists, font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Button(playlist_controls, text="Aktuelle speichern", bg='lightgreen', fg='black',
                 command=self.save_current_playlist, font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Button(playlist_controls, text="Playlist laden", bg='orange', fg='black',
                 command=self.load_playlist, font=('Arial', 11)).pack(side='left', padx=5)
        
        # Playlist-Liste
        playlist_info = tk.Frame(playlist_frame, bg='black')
        playlist_info.pack(pady=5, fill='x')
        
        tk.Label(playlist_info, text="Gespeicherte Playlists:", 
                font=('Arial', 11, 'bold'), fg='white', bg='black').pack(anchor='w')
        
        self.playlist_listbox = tk.Listbox(playlist_info, height=3, font=('Arial', 9), 
                                          bg='gray20', fg='white', selectbackground='blue')
        self.playlist_listbox.pack(fill='x', pady=5)
        
        self.playlist_status_label = tk.Label(playlist_info, text="Playlist-Status: Keine Playlist geladen", 
                                            font=('Arial', 10), fg='gray', bg='black')
        self.playlist_status_label.pack(pady=2)
        
        # Dateiauswahl
        files_frame = tk.LabelFrame(main_frame, text="Datei-Auswahl", 
                                  font=('Arial', 14, 'bold'), fg='lime', bg='black', bd=2)
        files_frame.pack(pady=10, padx=10, fill='both', expand=True)
        
        # Drei Spalten für Video/Bild/Audio
        columns_frame = tk.Frame(files_frame, bg='black')
        columns_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Video-Spalte
        video_frame = tk.Frame(columns_frame, bg='black')
        video_frame.pack(side='left', fill='both', expand=True, padx=2)
        
        tk.Label(video_frame, text="Videos", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=2)
        tk.Button(video_frame, text="Ordner öffnen", bg='lightblue', fg='black', 
                 font=('Arial', 9), command=self.open_video_folder).pack(pady=2)
        
        video_scroll_container = tk.Frame(video_frame, bg='black', relief='sunken', bd=1)
        video_scroll_container.pack(fill='both', expand=True, pady=2)
        
        video_canvas = tk.Canvas(video_scroll_container, bg='gray10', height=200)
        video_scrollbar = tk.Scrollbar(video_scroll_container, orient="vertical", command=video_canvas.yview)
        self.video_scroll_frame = tk.Frame(video_canvas, bg='gray10')
        
        self.video_scroll_frame.bind("<Configure>", lambda e: video_canvas.configure(scrollregion=video_canvas.bbox("all")))
        video_canvas.create_window((0, 0), window=self.video_scroll_frame, anchor="nw")
        video_canvas.configure(yscrollcommand=video_scrollbar.set)
        
        video_canvas.pack(side="left", fill="both", expand=True)
        video_scrollbar.pack(side="right", fill="y")
        
        # Bild-Spalte
        image_frame = tk.Frame(columns_frame, bg='black')
        image_frame.pack(side='left', fill='both', expand=True, padx=2)
        
        tk.Label(image_frame, text="Bilder", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=2)
        tk.Button(image_frame, text="Ordner öffnen", bg='lightblue', fg='black', 
                 font=('Arial', 9), command=self.open_image_folder).pack(pady=2)
        
        image_scroll_container = tk.Frame(image_frame, bg='black', relief='sunken', bd=1)
        image_scroll_container.pack(fill='both', expand=True, pady=2)
        
        image_canvas = tk.Canvas(image_scroll_container, bg='gray10', height=200)
        image_scrollbar = tk.Scrollbar(image_scroll_container, orient="vertical", command=image_canvas.yview)
        self.image_scroll_frame = tk.Frame(image_canvas, bg='gray10')
        
        self.image_scroll_frame.bind("<Configure>", lambda e: image_canvas.configure(scrollregion=image_canvas.bbox("all")))
        image_canvas.create_window((0, 0), window=self.image_scroll_frame, anchor="nw")
        image_canvas.configure(yscrollcommand=image_scrollbar.set)
        
        image_canvas.pack(side="left", fill="both", expand=True)
        image_scrollbar.pack(side="right", fill="y")
        
        # Audio-Spalte
        audio_frame = tk.Frame(columns_frame, bg='black')
        audio_frame.pack(side='left', fill='both', expand=True, padx=2)
        
        tk.Label(audio_frame, text="Audio", font=('Arial', 12, 'bold'), fg='cyan', bg='black').pack(pady=2)
        tk.Button(audio_frame, text="Ordner öffnen", bg='lightblue', fg='black', 
                 font=('Arial', 9), command=self.open_audio_folder).pack(pady=2)
        
        audio_scroll_container = tk.Frame(audio_frame, bg='black', relief='sunken', bd=1)
        audio_scroll_container.pack(fill='both', expand=True, pady=2)
        
        audio_canvas = tk.Canvas(audio_scroll_container, bg='gray10', height=200)
        audio_scrollbar = tk.Scrollbar(audio_scroll_container, orient="vertical", command=audio_canvas.yview)
        self.audio_scroll_frame = tk.Frame(audio_canvas, bg='gray10')
        
        self.audio_scroll_frame.bind("<Configure>", lambda e: audio_canvas.configure(scrollregion=audio_canvas.bbox("all")))
        audio_canvas.create_window((0, 0), window=self.audio_scroll_frame, anchor="nw")
        audio_canvas.configure(yscrollcommand=audio_scrollbar.set)
        
        audio_canvas.pack(side="left", fill="both", expand=True)
        audio_scrollbar.pack(side="right", fill="y")
        
        # Status-Labels für Dateien
        status_frame = tk.Frame(files_frame, bg='black')
        status_frame.pack(fill='x', pady=5)
        
        self.video_status_label = tk.Label(status_frame, text="Videos: Wird geladen...", 
                                          font=('Arial', 10), fg='gray', bg='black')
        self.video_status_label.pack(side='left', padx=20)
        
        self.image_status_label = tk.Label(status_frame, text="Bilder: Wird geladen...", 
                                          font=('Arial', 10), fg='gray', bg='black')
        self.image_status_label.pack(side='left', padx=20)
        
        self.audio_status_label = tk.Label(status_frame, text="Audio: Wird geladen...", 
                                          font=('Arial', 10), fg='gray', bg='black')
        self.audio_status_label.pack(side='left', padx=20)
        
        # Media-Status
        self.media_status_label = tk.Label(main_frame, text="Status: VLC bereit", 
                                         font=('Arial', 14, 'bold'), fg='lime', bg='black')
        self.media_status_label.pack(pady=10)
        
        # Tastenkombinationen für GUI
        self.root.bind('<F11>', lambda e: self.toggle_gui_fullscreen())
        self.root.bind('<Escape>', lambda e: self.root.quit())
    
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
                               variable=var, bg='gray10', fg='white', selectcolor='darkgray',
                               font=('Arial', 9))
            cb.pack(anchor='w', padx=3, pady=1)
        
        # Bilder
        for widget in self.image_scroll_frame.winfo_children():
            widget.destroy()
        self.image_checkboxes.clear()
        
        for image_file in self.all_image_files:
            var = tk.BooleanVar(value=True)
            self.image_checkboxes[image_file] = var
            cb = tk.Checkbutton(self.image_scroll_frame, text=os.path.basename(image_file), 
                               variable=var, bg='gray10', fg='white', selectcolor='darkgray',
                               font=('Arial', 9))
            cb.pack(anchor='w', padx=3, pady=1)
        
        # Audio
        for widget in self.audio_scroll_frame.winfo_children():
            widget.destroy()
        self.audio_checkboxes.clear()
        
        for audio_file in self.all_audio_files:
            var = tk.BooleanVar(value=True)
            self.audio_checkboxes[audio_file] = var
            cb = tk.Checkbutton(self.audio_scroll_frame, text=os.path.basename(audio_file), 
                               variable=var, bg='gray10', fg='white', selectcolor='darkgray',
                               font=('Arial', 9))
            cb.pack(anchor='w', padx=3, pady=1)
        
        # Status-Labels aktualisieren
        self.video_status_label.config(text=f"Videos: {len(self.all_video_files)} gefunden", fg='lime')
        self.image_status_label.config(text=f"Bilder: {len(self.all_image_files)} gefunden", fg='lime')
        self.audio_status_label.config(text=f"Audio: {len(self.all_audio_files)} gefunden", fg='lime')
        
        print(f"[VLC-GUI] Gefunden: {len(self.all_video_files)} Videos, {len(self.all_image_files)} Bilder, {len(self.all_audio_files)} Audio")
    
    # Speichern-Methoden für alle Parameter
    def save_min_dist(self):
        """Min-Abstand speichern"""
        try:
            new_min = float(self.min_dist_var.get())
            if new_min >= 1:
                print(f"[VLC-GUI] Min-Abstand gespeichert: {new_min} cm")
            else:
                print("[VLC-GUI] Min-Abstand zu klein (mindestens 1cm)")
        except ValueError:
            print("[VLC-GUI] Ungültiger Min-Abstand")
    
    def save_max_dist(self):
        """Max-Abstand speichern"""
        try:
            new_max = float(self.max_dist_var.get())
            if new_max >= 10:
                print(f"[VLC-GUI] Max-Abstand gespeichert: {new_max} cm")
            else:
                print("[VLC-GUI] Max-Abstand zu klein (mindestens 10cm)")
        except ValueError:
            print("[VLC-GUI] Ungültiger Max-Abstand")
    
    def save_interval(self):
        """Messintervall speichern"""
        try:
            new_interval_ms = float(self.interval_var.get())
            new_interval_s = new_interval_ms / 1000.0
            self.sensor_thread.interval = max(0.1, new_interval_s)
            print(f"[VLC-GUI] Messintervall gespeichert: {new_interval_ms}ms ({new_interval_s}s)")
        except ValueError:
            print("[VLC-GUI] Ungültiges Messintervall")
    
    def save_image_interval(self):
        """Bildwechselzeit speichern"""
        try:
            new_interval = float(self.image_interval_var.get())
            self.current_image_display_time = max(1.0, new_interval)
            self.media_player.set_min_display_time(self.current_image_display_time)
            print(f"[VLC-GUI] Bildwechselzeit gespeichert: {self.current_image_display_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Bildwechselzeit")
    
    def save_audio_fade(self):
        """Audio-Fade-Zeit speichern"""
        try:
            new_fade_ms = float(self.audio_fade_var.get())
            self.current_audio_fade_time = max(10, new_fade_ms) / 1000.0
            print(f"[VLC-GUI] Audio-Fade-Zeit gespeichert: {new_fade_ms}ms ({self.current_audio_fade_time}s)")
        except ValueError:
            print("[VLC-GUI] Ungültige Audio-Fade-Zeit")
    
    def save_min_video_time(self):
        """Min-Video-Zeit speichern"""
        try:
            new_min_video = float(self.min_video_var.get())
            self.current_min_video_time = max(0.5, new_min_video)
            print(f"[VLC-GUI] Min-Video-Zeit gespeichert: {self.current_min_video_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Video-Zeit")
    
    def save_min_image_time(self):
        """Min-Bild-Zeit speichern"""
        try:
            new_min_image = float(self.min_image_var.get())
            self.current_min_image_time = max(0.5, new_min_image)
            print(f"[VLC-GUI] Min-Bild-Zeit gespeichert: {self.current_min_image_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Bild-Zeit")
    
    def save_min_audio_time(self):
        """Min-Audio-Zeit speichern"""
        try:
            new_min_audio = float(self.min_audio_var.get())
            self.current_min_audio_time = max(1.0, new_min_audio)
            print(f"[VLC-GUI] Min-Audio-Zeit gespeichert: {self.current_min_audio_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Audio-Zeit")
    
    # Playlist-Methoden
    def refresh_playlists(self):
        """Verfügbare Playlists laden"""
        try:
            playlist_dir = "playlists"
            if not os.path.exists(playlist_dir):
                os.makedirs(playlist_dir)
            
            self.playlist_listbox.delete(0, tk.END)
            playlist_files = [f for f in os.listdir(playlist_dir) if f.endswith('.json')]
            
            if playlist_files:
                for playlist_file in sorted(playlist_files):
                    display_name = playlist_file[:-5]
                    self.playlist_listbox.insert(tk.END, display_name)
                
                self.playlist_status_label.config(text=f"Verfügbare Playlists: {len(playlist_files)}", fg='lime')
            else:
                self.playlist_listbox.insert(tk.END, "Keine Playlists vorhanden")
                self.playlist_status_label.config(text="Keine Playlists gefunden", fg='orange')
                
        except Exception as e:
            self.playlist_status_label.config(text=f"Fehler beim Laden: {e}", fg='red')
    
    def save_current_playlist(self):
        """Aktuelle Auswahl als Playlist speichern"""
        try:
            playlist_name = simpledialog.askstring("Playlist speichern", "Name für die Playlist:")
            if not playlist_name:
                return
            
            safe_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:
                safe_name = "neue_playlist"
            
            selected_videos = self.get_selected_videos()
            selected_images = self.get_selected_images()
            selected_audios = self.get_selected_audios()
            
            if not (selected_videos or selected_images or selected_audios):
                self.playlist_status_label.config(text="Keine Dateien ausgewählt!", fg='red')
                return
            
            playlist_data = {
                "name": safe_name,
                "created": str(datetime.datetime.now()),
                "videos": [os.path.basename(v) for v in selected_videos],
                "images": [os.path.basename(i) for i in selected_images],  
                "audios": [os.path.basename(a) for a in selected_audios],
                "video_count": len(selected_videos),
                "image_count": len(selected_images),
                "audio_count": len(selected_audios)
            }
            
            playlist_dir = "playlists"
            if not os.path.exists(playlist_dir):
                os.makedirs(playlist_dir)
            
            file_path = os.path.join(playlist_dir, f"{safe_name}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=2, ensure_ascii=False)
            
            self.playlist_status_label.config(
                text=f"Playlist '{safe_name}' gespeichert! ({playlist_data['video_count']}V, {playlist_data['image_count']}B, {playlist_data['audio_count']}A)", 
                fg='lime')
            
            self.refresh_playlists()
            
        except Exception as e:
            self.playlist_status_label.config(text=f"Speichern fehlgeschlagen: {e}", fg='red')
    
    def load_playlist(self):
        """Ausgewählte Playlist laden"""
        try:
            selection = self.playlist_listbox.curselection()
            if not selection:
                self.playlist_status_label.config(text="Bitte eine Playlist auswählen!", fg='orange')
                return
            
            playlist_name = self.playlist_listbox.get(selection[0])
            if playlist_name == "Keine Playlists vorhanden":
                return
            
            file_path = os.path.join("playlists", f"{playlist_name}.json")
            if not os.path.exists(file_path):
                self.playlist_status_label.config(text=f"Playlist-Datei nicht gefunden: {playlist_name}", fg='red')
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                playlist_data = json.load(f)
            
            # Alle Checkboxen zurücksetzen
            for checkbox in self.video_checkboxes.values():
                checkbox.set(False)
            for checkbox in self.image_checkboxes.values():
                checkbox.set(False)
            for checkbox in self.audio_checkboxes.values():
                checkbox.set(False)
            
            # Playlist-Dateien aktivieren
            loaded_videos = loaded_images = loaded_audios = 0
            
            for video_filename in playlist_data.get('videos', []):
                for file_path, checkbox in self.video_checkboxes.items():
                    if os.path.basename(file_path) == video_filename:
                        checkbox.set(True)
                        loaded_videos += 1
                        break
            
            for image_filename in playlist_data.get('images', []):
                for file_path, checkbox in self.image_checkboxes.items():
                    if os.path.basename(file_path) == image_filename:
                        checkbox.set(True)
                        loaded_images += 1
                        break
            
            for audio_filename in playlist_data.get('audios', []):
                for file_path, checkbox in self.audio_checkboxes.items():
                    if os.path.basename(file_path) == audio_filename:
                        checkbox.set(True)
                        loaded_audios += 1
                        break
            
            total_files = loaded_videos + loaded_images + loaded_audios
            self.playlist_status_label.config(
                text=f"Playlist '{playlist_name}' geladen: {loaded_videos}V, {loaded_images}B, {loaded_audios}A ({total_files} Dateien)", 
                fg='lime')
            
        except Exception as e:
            self.playlist_status_label.config(text=f"Laden fehlgeschlagen: {e}", fg='red')
    
    # Media-Vollbild-Methoden (nicht GUI-Vollbild!)
    def toggle_media_fullscreen(self):
        """Media-Player Vollbild umschalten"""
        try:
            self.media_player._toggle_fullscreen()
            print("[VLC-GUI] Media-Vollbild umgeschaltet")
        except Exception as e:
            print(f"[VLC-GUI] Media-Vollbild-Fehler: {e}")
    
    def set_media_windowed(self):
        """Media-Player im Fenstermodus"""
        try:
            if self.media_player.media_window:
                self.media_player.media_window.attributes('-fullscreen', False)
            print("[VLC-GUI] Media-Player im Fenstermodus")
        except Exception as e:
            print(f"[VLC-GUI] Media-Fenster-Fehler: {e}")
    
    def toggle_gui_fullscreen(self):
        """GUI-Vollbild umschalten (F11)"""
        try:
            self.kiosk_mode = not self.kiosk_mode
            if self.kiosk_mode:
                self.root.attributes('-fullscreen', True)
            else:
                self.root.attributes('-fullscreen', False)
            print(f"[VLC-GUI] GUI-Vollbild: {self.kiosk_mode}")
        except Exception as e:
            print(f"[VLC-GUI] GUI-Vollbild-Fehler: {e}")
    
    def hide_gui(self):
        """GUI verstecken (nur Media-Fenster sichtbar)"""
        try:
            self.root.withdraw()  # GUI-Fenster verstecken
            print("[VLC-GUI] GUI versteckt - nur Media-Fenster sichtbar")
            print("[VLC-GUI] TIPP: Alt+Tab zum GUI zurückkehren oder GUI-Fenster in Taskleiste klicken")
        except Exception as e:
            print(f"[VLC-GUI] GUI-Hide-Fehler: {e}")
    
    def show_gui(self):
        """GUI wieder anzeigen"""
        try:
            self.root.deiconify()  # GUI-Fenster wieder anzeigen
            self.root.lift()       # GUI in Vordergrund
            print("[VLC-GUI] GUI wieder sichtbar")
        except Exception as e:
            print(f"[VLC-GUI] GUI-Show-Fehler: {e}")
    
    def update_sensor_mode(self):
        """Sensor-Modus aktualisieren"""
        new_mode = self.sensor_mode_var.get()
        self.sensor_mode = new_mode
        print(f"[VLC-GUI] Sensor-Modus geändert zu: {self.sensor_mode}")
        
        # Zusätzlicher Status für Benutzer
        if self.sensor_mode == "video":
            print("[VLC-GUI] → Bei Sensor-Auslösung werden Videos abgespielt")
        elif self.sensor_mode == "audio":
            print("[VLC-GUI] → Bei Sensor-Auslösung werden Audio + Bilder abgespielt")
        else:
            print(f"[VLC-GUI] → Unbekannter Modus: {self.sensor_mode}")
    
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
    
    def get_selected_videos(self):
        """Ausgewählte Videos zurückgeben"""
        return [path for path, var in self.video_checkboxes.items() if var.get()]
    
    def get_selected_images(self):
        """Ausgewählte Bilder zurückgeben"""
        return [path for path, var in self.image_checkboxes.items() if var.get()]
    
    def get_selected_audios(self):
        """Ausgewählte Audio-Dateien zurückgeben"""
        return [path for path, var in self.audio_checkboxes.items() if var.get()]
    
    def scan_files(self):
        """Alle Mediendateien erneut scannen"""
        print("[VLC-GUI] Scanne Mediendateien...")
        self.all_video_files = []
        self.all_image_files = []
        self.all_audio_files = []
        
        # Videos scannen
        video_dir = os.path.join(os.path.dirname(__file__), 'videos')
        if os.path.exists(video_dir):
            for file in os.listdir(video_dir):
                if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.m4v')):
                    self.all_video_files.append(os.path.join(video_dir, file))
        
        # Bilder scannen
        image_dir = os.path.join(os.path.dirname(__file__), 'images')
        if os.path.exists(image_dir):
            for file in os.listdir(image_dir):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')):
                    self.all_image_files.append(os.path.join(image_dir, file))
        
        # Audio scannen
        audio_dir = os.path.join(os.path.dirname(__file__), 'audio')
        if os.path.exists(audio_dir):
            for file in os.listdir(audio_dir):
                if file.lower().endswith(('.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma')):
                    self.all_audio_files.append(os.path.join(audio_dir, file))
        
        print(f"[VLC-GUI] Scan abgeschlossen: {len(self.all_video_files)} Videos, {len(self.all_image_files)} Bilder, {len(self.all_audio_files)} Audio")
        self.create_checkboxes()
    
    def start_playback(self):
        """Wiedergabe starten"""
        try:
            selected_videos = self.get_selected_videos()
            selected_images = self.get_selected_images()
            selected_audios = self.get_selected_audios()
            
            all_selected = selected_videos + selected_images + selected_audios
            
            if not all_selected:
                self.video_status_label.config(text="Keine Dateien ausgewählt!", fg='red')
                return
            
            # Shuffle wenn gewünscht
            import random
            random.shuffle(all_selected)
            
            # Media-Player mit Liste starten
            self.media_player.play_media_list(all_selected)
            
            self.video_status_label.config(text=f"Wiedergabe gestartet: {len(all_selected)} Dateien", fg='lime')
            print(f"[VLC-GUI] Wiedergabe gestartet mit {len(all_selected)} Dateien")
            
        except Exception as e:
            self.video_status_label.config(text=f"Start-Fehler: {e}", fg='red')
            print(f"[VLC-GUI] Start-Fehler: {e}")
    
    def close(self):
        """GUI schließen"""
        try:
            if hasattr(self, 'sensor_thread') and self.sensor_thread:
                self.sensor_thread.stop()
                self.sensor_thread = None
            
            if hasattr(self, 'media_player') and self.media_player:
                self.media_player.stop()
                self.media_player = None
            
            self.root.quit()
            self.root.destroy()
            print("[VLC-GUI] GUI erfolgreich geschlossen")
            
        except Exception as e:
            print(f"[VLC-GUI] Schließ-Fehler: {e}")
    
    def on_closing(self):
        """Window-Close-Event"""
        self.close()
    
    # Ordner-öffnen-Funktionen
    def open_video_folder(self):
        """Video-Ordner im Datei-Explorer öffnen"""
        try:
            video_path = os.path.abspath(VIDEO_FOLDER)
            if not os.path.exists(video_path):
                os.makedirs(video_path)
                print(f"[VLC-GUI] Video-Ordner erstellt: {video_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', video_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', video_path])
            else:  # Linux
                subprocess.run(['xdg-open', video_path])
            
            print(f"[VLC-GUI] Video-Ordner geöffnet: {video_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Video-Ordners: {e}")
    
    def open_image_folder(self):
        """Bild-Ordner im Datei-Explorer öffnen"""
        try:
            image_path = os.path.abspath(IMAGE_FOLDER)
            if not os.path.exists(image_path):
                os.makedirs(image_path)
                print(f"[VLC-GUI] Bild-Ordner erstellt: {image_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', image_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', image_path])
            else:  # Linux
                subprocess.run(['xdg-open', image_path])
            
            print(f"[VLC-GUI] Bild-Ordner geöffnet: {image_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Bild-Ordners: {e}")
    
    def open_audio_folder(self):
        """Audio-Ordner im Datei-Explorer öffnen"""
        try:
            audio_path = os.path.abspath(AUDIO_FOLDER)
            if not os.path.exists(audio_path):
                os.makedirs(audio_path)
                print(f"[VLC-GUI] Audio-Ordner erstellt: {audio_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', audio_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', audio_path])
            else:  # Linux
                subprocess.run(['xdg-open', audio_path])
            
            print(f"[VLC-GUI] Audio-Ordner geöffnet: {audio_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Audio-Ordners: {e}")
    
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

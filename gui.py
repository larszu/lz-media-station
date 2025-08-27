"""
GUI-Logik mit tkinter
"""
import tkinter as tk
from tkinter import filedialog, ttk
import os
import time
from config import DEFAULT_MIN_DIST, DEFAULT_MAX_DIST, DEFAULT_INTERVAL, VIDEO_FOLDER, IMAGE_FOLDER, AUDIO_FOLDER, IMAGE_DISPLAY_TIME, VIDEO_LOOP_CHECK_TIME, AUDIO_FADE_TIME, MIN_VIDEO_RUNTIME, MIN_IMAGE_DISPLAY_TIME, MIN_AUDIO_RUNTIME
from media_player import MediaPlayer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileWatcher(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
    
    def on_created(self, event):
        if not event.is_directory:
            self.callback()

class MediaStationGUI:
    def __init__(self, sensor_thread, kiosk_mode=False):
        self.sensor_thread = sensor_thread
        self.media_player = MediaPlayer()
        self.kiosk_mode = kiosk_mode
        
        # Dateipfade (Listen für alle Dateien und Auswahl)
        self.all_video_files = []  # Alle gefundenen Videos
        self.all_image_files = []  # Alle gefundenen Bilder
        self.all_audio_files = []  # Alle gefundenen Audio-Dateien
        self.selected_videos = []  # Ausgewählte Videos (Checkboxen)
        self.selected_images = []  # Ausgewählte Bilder (Checkboxen)
        self.selected_audios = []  # Ausgewählte Audio-Dateien (Checkboxen)
        self.current_video_index = 0
        self.current_image_index = 0
        
        # Checkbox-Variablen
        self.video_checkboxes = {}  # {filepath: BooleanVar}
        self.image_checkboxes = {}  # {filepath: BooleanVar}
        self.audio_checkboxes = {}  # {filepath: BooleanVar}
        
        # Timer für Media-Wechsel
        self.last_media_change = 0
        self.last_mode = None
        self.video_finished = False  # Flag für Video-Ende
        self.current_image_display_time = IMAGE_DISPLAY_TIME  # Einstellbare Bildwechselzeit
        self.current_audio_fade_time = AUDIO_FADE_TIME  # Einstellbare Audio-Fade-Zeit
        
        # Einstellbare Mindestlaufzeiten
        self.current_min_video_time = MIN_VIDEO_RUNTIME
        self.current_min_image_time = MIN_IMAGE_DISPLAY_TIME  
        self.current_min_audio_time = MIN_AUDIO_RUNTIME
        
        # GUI erstellen
        self.root = tk.Tk()
        
        if self.kiosk_mode:
            self.root.attributes('-fullscreen', True)
            self.root.config(cursor="none")  # Mauszeiger im Kiosk-Modus ausblenden
        else:
            # Test-Modus: Fenster mit Mauszeiger
            self.root.geometry("1024x768")
            self.root.title("Pi Media Station - Test Modus")
        
        self.root.configure(bg='black')
        
        # ESC zum Beenden (für Testing) - Robuste Behandlung
        self.root.bind('<Escape>', self._handle_escape_key)
        self.root.bind('<Control-c>', lambda e: self._emergency_quit())
        self.root.bind('<Control-q>', lambda e: self._emergency_quit())
        self.root.bind('<Alt-F4>', lambda e: self._emergency_quit())
        
        self.setup_gui()
        self.setup_file_watchers()
        self.update_status()
        
    def setup_gui(self):
        # Hauptframe
        main_frame = tk.Frame(self.root, bg='black')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Titel
        title_label = tk.Label(main_frame, text="Raspberry Pi Media Station", 
                              font=('Arial', 24, 'bold'), fg='white', bg='black')
        title_label.pack(pady=(0, 30))
        
        # Sensor-Status
        self.status_label = tk.Label(main_frame, text="Abstand: -- cm", 
                                   font=('Arial', 18), fg='lime', bg='black')
        self.status_label.pack(pady=10)
        
        # Einstellungen Frame
        settings_frame = tk.Frame(main_frame, bg='black')
        settings_frame.pack(pady=20)
        
        # Abstand-Schwellwerte
        tk.Label(settings_frame, text="Min. Abstand (cm):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=0, column=0, sticky='w', padx=10)
        self.min_dist_var = tk.StringVar(value=str(DEFAULT_MIN_DIST))
        tk.Entry(settings_frame, textvariable=self.min_dist_var, 
                font=('Arial', 14), width=10).grid(row=0, column=1, padx=10)
        
        tk.Label(settings_frame, text="Max. Abstand (cm):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=1, column=0, sticky='w', padx=10)
        self.max_dist_var = tk.StringVar(value=str(DEFAULT_MAX_DIST))
        tk.Entry(settings_frame, textvariable=self.max_dist_var, 
                font=('Arial', 14), width=10).grid(row=1, column=1, padx=10)
        
        # Messintervall
        tk.Label(settings_frame, text="Messintervall (ms):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=2, column=0, sticky='w', padx=10)
        self.interval_var = tk.StringVar(value=str(int(DEFAULT_INTERVAL * 1000)))
        tk.Entry(settings_frame, textvariable=self.interval_var, 
                font=('Arial', 14), width=10).grid(row=2, column=1, padx=10)
        
        # Update Button für Intervall
        tk.Button(settings_frame, text="Intervall aktualisieren", 
                 command=self.update_interval, font=('Arial', 12)).grid(row=2, column=2, padx=10)
        
        # Bildwechsel-Zeit
        tk.Label(settings_frame, text="Bildwechsel (Sekunden):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=3, column=0, sticky='w', padx=10)
        self.image_interval_var = tk.StringVar(value=str(IMAGE_DISPLAY_TIME))
        tk.Entry(settings_frame, textvariable=self.image_interval_var, 
                font=('Arial', 14), width=10).grid(row=3, column=1, padx=10)
        
        # Update Button für Bildwechsel-Zeit
        tk.Button(settings_frame, text="Bildzeit aktualisieren", 
                 command=self.update_image_interval, font=('Arial', 12)).grid(row=3, column=2, padx=10)
        
        # Audio-Fade-Zeit
        tk.Label(settings_frame, text="Audio-Fade (Sekunden):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=4, column=0, sticky='w', padx=10)
        self.audio_fade_var = tk.StringVar(value=str(AUDIO_FADE_TIME))
        tk.Entry(settings_frame, textvariable=self.audio_fade_var, 
                font=('Arial', 14), width=10).grid(row=4, column=1, padx=10)
        
        # Update Button für Audio-Fade-Zeit
        tk.Button(settings_frame, text="Fade-Zeit aktualisieren", 
                 command=self.update_audio_fade, font=('Arial', 12)).grid(row=4, column=2, padx=10)
        
        # Mindestlaufzeiten (Stabilität)
        tk.Label(settings_frame, text="Min. Video-Zeit (s):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=5, column=0, sticky='w', padx=10)
        self.min_video_var = tk.StringVar(value=str(MIN_VIDEO_RUNTIME))
        tk.Entry(settings_frame, textvariable=self.min_video_var, 
                font=('Arial', 14), width=10).grid(row=5, column=1, padx=10)
        
        tk.Label(settings_frame, text="Min. Bild-Zeit (s):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=6, column=0, sticky='w', padx=10)
        self.min_image_var = tk.StringVar(value=str(MIN_IMAGE_DISPLAY_TIME))
        tk.Entry(settings_frame, textvariable=self.min_image_var, 
                font=('Arial', 14), width=10).grid(row=6, column=1, padx=10)
        
        tk.Label(settings_frame, text="Min. Audio-Zeit (s):", 
                font=('Arial', 14), fg='white', bg='black').grid(row=7, column=0, sticky='w', padx=10)
        self.min_audio_var = tk.StringVar(value=str(MIN_AUDIO_RUNTIME))
        tk.Entry(settings_frame, textvariable=self.min_audio_var, 
                font=('Arial', 14), width=10).grid(row=7, column=1, padx=10)
        
        # Update Button für Mindestlaufzeiten
        tk.Button(settings_frame, text="Mindestzeiten aktualisieren", 
                 command=self.update_min_times, font=('Arial', 12)).grid(row=8, column=0, columnspan=3, pady=10)
        
        # Dateiauswahl Frame (Checkboxen für Video/Bild-Auswahl)
        file_frame = tk.Frame(main_frame, bg='black')
        file_frame.pack(pady=30)
        
        # Automatische Dateierkennung anzeigen
        tk.Label(file_frame, text="Datei-Auswahl:", font=('Arial', 16, 'bold'), fg='lime', bg='black').pack(pady=10)
        
        # Video-Auswahl
        video_frame = tk.Frame(file_frame, bg='black')
        video_frame.pack(pady=10, fill='x')
        
        tk.Label(video_frame, text="Videos:", font=('Arial', 14, 'bold'), fg='cyan', bg='black').pack(anchor='w')
        
        # Scrollable Frame für Video-Checkboxen
        self.video_scroll_frame = tk.Frame(video_frame, bg='black')
        self.video_scroll_frame.pack(fill='both', expand=True, pady=5)
        
        # Bild-Auswahl
        image_frame = tk.Frame(file_frame, bg='black') 
        image_frame.pack(pady=10, fill='x')
        
        tk.Label(image_frame, text="Bilder:", font=('Arial', 14, 'bold'), fg='cyan', bg='black').pack(anchor='w')
        
        # Scrollable Frame für Bild-Checkboxen
        self.image_scroll_frame = tk.Frame(image_frame, bg='black')
        self.image_scroll_frame.pack(fill='both', expand=True, pady=5)
        
        # Audio-Auswahl
        audio_frame = tk.Frame(file_frame, bg='black')
        audio_frame.pack(pady=10, fill='x')
        
        tk.Label(audio_frame, text="Audio:", font=('Arial', 14, 'bold'), fg='cyan', bg='black').pack(anchor='w')
        
        # Scrollable Frame für Audio-Checkboxen
        self.audio_scroll_frame = tk.Frame(audio_frame, bg='black')
        self.audio_scroll_frame.pack(fill='both', expand=True, pady=5)
        
        # Status-Labels
        self.video_status_label = tk.Label(file_frame, text="Videos: Wird geladen...", 
                                          font=('Arial', 12), fg='gray', bg='black')
        self.video_status_label.pack(pady=5)
        
        self.image_status_label = tk.Label(file_frame, text="Bilder: Wird geladen...", 
                                          font=('Arial', 12), fg='gray', bg='black')
        self.image_status_label.pack(pady=5)
        
        self.audio_status_label = tk.Label(file_frame, text="Audio: Wird geladen...", 
                                          font=('Arial', 12), fg='gray', bg='black')
        self.audio_status_label.pack(pady=5)
        
        # Media-Status
        self.media_status_label = tk.Label(main_frame, text="Status: Schwarzes Bild", 
                                         font=('Arial', 16), fg='yellow', bg='black')
        self.media_status_label.pack(pady=20)
        
        self.refresh_file_lists()
    
    def setup_file_watchers(self):
        """File Watcher für automatische Dateierkennung"""
        self.observer = Observer()
        
        # Video-Ordner überwachen
        if os.path.exists(VIDEO_FOLDER):
            video_handler = FileWatcher(self.refresh_file_lists)
            self.observer.schedule(video_handler, VIDEO_FOLDER, recursive=False)
        
        # Bild-Ordner überwachen  
        if os.path.exists(IMAGE_FOLDER):
            image_handler = FileWatcher(self.refresh_file_lists)
            self.observer.schedule(image_handler, IMAGE_FOLDER, recursive=False)
        
        # Audio-Ordner überwachen
        if os.path.exists(AUDIO_FOLDER):
            audio_handler = FileWatcher(self.refresh_file_lists)
            self.observer.schedule(audio_handler, AUDIO_FOLDER, recursive=False)
            
        self.observer.start()
    
    def refresh_file_lists(self):
        """Aktualisiert die Dateilisten und erstellt Checkboxen"""
        # Videos laden
        old_video_count = len(self.all_video_files)
        self.all_video_files = []
        if os.path.exists(VIDEO_FOLDER):
            for file in os.listdir(VIDEO_FOLDER):
                if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv')):
                    full_path = os.path.join(VIDEO_FOLDER, file)
                    self.all_video_files.append(full_path)
        
        # Bilder laden
        old_image_count = len(self.all_image_files)
        self.all_image_files = []
        if os.path.exists(IMAGE_FOLDER):
            for file in os.listdir(IMAGE_FOLDER):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')):
                    full_path = os.path.join(IMAGE_FOLDER, file)
                    self.all_image_files.append(full_path)
        
        # Audio-Dateien laden
        old_audio_count = len(self.all_audio_files)
        self.all_audio_files = []
        if os.path.exists(AUDIO_FOLDER):
            for file in os.listdir(AUDIO_FOLDER):
                if file.lower().endswith(('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma')):
                    full_path = os.path.join(AUDIO_FOLDER, file)
                    self.all_audio_files.append(full_path)
        
        # Video-Checkboxen erstellen
        self._create_video_checkboxes()
        
        # Bild-Checkboxen erstellen
        self._create_image_checkboxes()
        
        # Audio-Checkboxen erstellen
        self._create_audio_checkboxes()
        
        # Status-Labels aktualisieren
        if hasattr(self, 'video_status_label'):
            selected_count = len(self.get_selected_videos())
            video_text = f"Videos: {len(self.all_video_files)} gefunden, {selected_count} ausgewählt"
            self.video_status_label.config(text=video_text, fg='lime' if selected_count > 0 else 'orange')
        
        if hasattr(self, 'image_status_label'):
            selected_count = len(self.get_selected_images())
            image_text = f"Bilder: {len(self.all_image_files)} gefunden, {selected_count} ausgewählt"
            self.image_status_label.config(text=image_text, fg='lime' if selected_count > 0 else 'orange')
        
        if hasattr(self, 'audio_status_label'):
            selected_count = len(self.get_selected_audios())
            audio_text = f"Audio: {len(self.all_audio_files)} gefunden, {selected_count} ausgewählt"
            self.audio_status_label.config(text=audio_text, fg='lime' if selected_count > 0 else 'orange')
        
        # Index zurücksetzen wenn neue Dateien
        if len(self.all_video_files) != old_video_count:
            self.current_video_index = 0
        if len(self.all_image_files) != old_image_count:
            self.current_image_index = 0
        
        print(f"[GUI] Dateien aktualisiert: {len(self.all_video_files)} Videos, {len(self.all_image_files)} Bilder, {len(self.all_audio_files)} Audio")
    
    def _create_video_checkboxes(self):
        """Erstellt Checkboxen für Video-Auswahl"""
        # Alte Checkboxen löschen
        for widget in self.video_scroll_frame.winfo_children():
            widget.destroy()
        self.video_checkboxes.clear()
        
        # Neue Checkboxen erstellen
        for video_path in self.all_video_files:
            filename = os.path.basename(video_path)
            var = tk.BooleanVar(value=True)  # Standardmäßig alle ausgewählt
            self.video_checkboxes[video_path] = var
            
            checkbox = tk.Checkbutton(
                self.video_scroll_frame,
                text=filename,
                variable=var,
                bg='black',
                fg='white',
                selectcolor='black',
                activebackground='gray',
                command=self._update_video_selection,
                font=('Arial', 10)
            )
            checkbox.pack(anchor='w', padx=20)
    
    def _create_image_checkboxes(self):
        """Erstellt Checkboxen für Bild-Auswahl"""
        # Alte Checkboxen löschen
        for widget in self.image_scroll_frame.winfo_children():
            widget.destroy()
        self.image_checkboxes.clear()
        
        # Neue Checkboxen erstellen
        for image_path in self.all_image_files:
            filename = os.path.basename(image_path)
            var = tk.BooleanVar(value=True)  # Standardmäßig alle ausgewählt
            self.image_checkboxes[image_path] = var
            
            checkbox = tk.Checkbutton(
                self.image_scroll_frame,
                text=filename,
                variable=var,
                bg='black',
                fg='white',
                selectcolor='black',
                activebackground='gray',
                command=self._update_image_selection,
                font=('Arial', 10)
            )
            checkbox.pack(anchor='w', padx=20)
    
    def _create_audio_checkboxes(self):
        """Erstellt Checkboxen für Audio-Auswahl"""
        # Alte Checkboxen löschen
        for widget in self.audio_scroll_frame.winfo_children():
            widget.destroy()
        self.audio_checkboxes.clear()
        
        # Neue Checkboxen erstellen
        for audio_path in self.all_audio_files:
            filename = os.path.basename(audio_path)
            var = tk.BooleanVar(value=True)  # Standardmäßig alle ausgewählt
            self.audio_checkboxes[audio_path] = var
            
            checkbox = tk.Checkbutton(
                self.audio_scroll_frame,
                text=filename,
                variable=var,
                bg='black',
                fg='white',
                selectcolor='black',
                activebackground='gray',
                command=self._update_audio_selection,
                font=('Arial', 10)
            )
            checkbox.pack(anchor='w', padx=20)
    
    def _update_video_selection(self):
        """Callback für Video-Checkbox-Änderungen"""
        selected_count = len(self.get_selected_videos())
        video_text = f"Videos: {len(self.all_video_files)} gefunden, {selected_count} ausgewählt"
        self.video_status_label.config(text=video_text, fg='lime' if selected_count > 0 else 'orange')
        self.current_video_index = 0  # Index zurücksetzen
    
    def _update_image_selection(self):
        """Callback für Bild-Checkbox-Änderungen"""
        selected_count = len(self.get_selected_images())
        image_text = f"Bilder: {len(self.all_image_files)} gefunden, {selected_count} ausgewählt"
        self.image_status_label.config(text=image_text, fg='lime' if selected_count > 0 else 'orange')
        self.current_image_index = 0  # Index zurücksetzen
    
    def _update_audio_selection(self):
        """Callback für Audio-Checkbox-Änderungen"""
        selected_audios = self.get_selected_audios()
        selected_count = len(selected_audios)
        audio_text = f"Audio: {len(self.all_audio_files)} gefunden, {selected_count} ausgewählt"
        self.audio_status_label.config(text=audio_text, fg='lime' if selected_count > 0 else 'orange')
        
        # Audio-Playlist sofort aktualisieren
        if selected_audios:
            self.media_player.start_audio_playlist(selected_audios)
        else:
            self.media_player.stop_audio()
    
    def get_selected_videos(self):
        """Gibt Liste der ausgewählten Videos zurück"""
        selected = []
        for video_path, var in self.video_checkboxes.items():
            if var.get():
                selected.append(video_path)
        return selected
    
    def get_selected_images(self):
        """Gibt Liste der ausgewählten Bilder zurück"""
        selected = []
        for image_path, var in self.image_checkboxes.items():
            if var.get():
                selected.append(image_path)
        return selected
    
    def get_selected_audios(self):
        """Gibt Liste der ausgewählten Audio-Dateien zurück"""
        selected = []
        for audio_path, var in self.audio_checkboxes.items():
            if var.get():
                selected.append(audio_path)
        return selected
    
    def get_current_video(self):
        """Gibt das aktuelle ausgewählte Video zurück und wechselt zum nächsten"""
        selected_videos = self.get_selected_videos()
        if not selected_videos:
            return None
        
        current_video = selected_videos[self.current_video_index]
        self.current_video_index = (self.current_video_index + 1) % len(selected_videos)
        return current_video
    
    def get_current_image(self):
        """Gibt das aktuelle ausgewählte Bild zurück und wechselt zum nächsten"""
        selected_images = self.get_selected_images()
        if not selected_images:
            return None
            
        current_image = selected_images[self.current_image_index]
        self.current_image_index = (self.current_image_index + 1) % len(selected_images)
        return current_image
    
    def update_interval(self):
        """Messintervall des Sensors aktualisieren"""
        try:
            new_interval = float(self.interval_var.get()) / 1000.0  # ms -> s
            self.sensor_thread.interval = new_interval
        except ValueError:
            pass  # Ungültige Eingabe ignorieren
    
    def update_image_interval(self):
        """Bildwechsel-Zeit aktualisieren"""
        try:
            new_time = float(self.image_interval_var.get())
            self.current_image_display_time = max(0.5, new_time)  # Minimum 0.5 Sekunden
            print(f"[GUI] Bildwechsel-Zeit geändert auf: {self.current_image_display_time} Sekunden")
        except ValueError:
            print("[GUI] Ungültige Bildwechsel-Zeit eingegeben")
            pass
    
    def update_audio_fade(self):
        """Audio-Fade-Zeit aktualisieren"""
        try:
            new_fade = float(self.audio_fade_var.get())
            self.current_audio_fade_time = max(0.1, new_fade)  # Minimum 0.1 Sekunden
            self.media_player.set_audio_fade_time(self.current_audio_fade_time)
            print(f"[GUI] Audio-Fade-Zeit geändert auf: {self.current_audio_fade_time} Sekunden")
        except ValueError:
            print("[GUI] Ungültige Audio-Fade-Zeit eingegeben")
            pass
    
    def update_min_times(self):
        """Mindestlaufzeiten aktualisieren"""
        try:
            # Video-Mindestzeit
            new_min_video = float(self.min_video_var.get())
            self.current_min_video_time = max(0.5, new_min_video)
            print(f"[GUI] Mindest-Video-Zeit: {self.current_min_video_time}s")
            
            # Bild-Mindestzeit  
            new_min_image = float(self.min_image_var.get())
            self.current_min_image_time = max(0.5, new_min_image)
            print(f"[GUI] Mindest-Bild-Zeit: {self.current_min_image_time}s")
            
            # Audio-Mindestzeit
            new_min_audio = float(self.min_audio_var.get())
            self.current_min_audio_time = max(1.0, new_min_audio)
            print(f"[GUI] Mindest-Audio-Zeit: {self.current_min_audio_time}s")
            
        except ValueError:
            print("[GUI] Ungültige Mindestlaufzeit eingegeben")
            pass
    
    def update_status(self):
        """Status-Update (wird zyklisch aufgerufen)"""
        # Abstand anzeigen
        distance = self.sensor_thread.distance
        print(f"[DEBUG] Sensor-Abstand: {distance:.1f} cm")  # Debug-Output
        
        if distance == 0.0:
            self.status_label.config(text="Sensor: Nicht verbunden", fg='red')
            # Ohne Sensor immer schwarzes Bild
            self.media_player.show_black()
            self.media_status_label.config(text="Status: Kein Sensor - Schwarzes Bild", fg='red')
        else:
            self.status_label.config(text=f"Abstand: {distance:.1f} cm", fg='lime')
            
            # Media-Steuerung basierend auf Abstand
            try:
                min_dist = float(self.min_dist_var.get())
                max_dist = float(self.max_dist_var.get())
                
                current_time = time.time()
                
                if min_dist <= distance <= max_dist:
                    # Video-Modus
                    selected_videos = self.get_selected_videos()
                    if selected_videos:
                        # Video wechseln nur bei Modus-Wechsel oder wenn Video beendet
                        # ABER nur wenn Mindestlaufzeit erfüllt ist
                        can_switch_from_current = True
                        if self.last_mode == "image":
                            can_switch_from_current = self.media_player.can_switch_from_image(self.current_min_image_time)
                        elif self.last_mode == "video":
                            can_switch_from_current = self.media_player.can_switch_from_video(self.current_min_video_time)
                        
                        if (can_switch_from_current and 
                            (self.last_mode != "video" or self.media_player.is_video_finished())):
                            
                            current_video = self.get_current_video()
                            if current_video:
                                self.media_player.play_video(current_video)
                                self.last_media_change = current_time
                                self.last_mode = "video"
                        
                        # Status anzeigen
                        current_index = (self.current_video_index - 1) % len(selected_videos)
                        if selected_videos:
                            video_name = os.path.basename(selected_videos[current_index])
                            audio_info = self.media_player.get_current_audio_info()
                            status_text = f"Status: Video läuft - {video_name} ({current_index + 1}/{len(selected_videos)})"
                            if audio_info:
                                status_text += f" | Audio: {audio_info}"
                            self.media_status_label.config(text=status_text, fg='lime')
                    else:
                        self.media_player.show_black()
                        self.media_status_label.config(text="Status: Keine Videos ausgewählt", fg='orange')
                        self.last_mode = "black"
                else:
                    # Bild-Modus
                    selected_images = self.get_selected_images()
                    if selected_images:
                        # Bild wechseln nach bestimmter Zeit oder bei Modus-Wechsel
                        # ABER nur wenn Mindestlaufzeit erfüllt ist
                        can_switch_from_current = True
                        if self.last_mode == "video":
                            can_switch_from_current = self.media_player.can_switch_from_video(self.current_min_video_time)
                        elif self.last_mode == "image":
                            can_switch_from_current = self.media_player.can_switch_from_image(self.current_min_image_time)
                        
                        should_switch_image = (
                            can_switch_from_current and
                            (self.last_mode != "image" or 
                             current_time - self.last_media_change > self.current_image_display_time)
                        )
                        
                        if should_switch_image:
                            current_image = self.get_current_image()
                            if current_image:
                                self.media_player.show_image(current_image)
                                self.last_media_change = current_time
                                self.last_mode = "image"
                        
                        # Status anzeigen
                        current_index = (self.current_image_index - 1) % len(selected_images)
                        if selected_images:
                            image_name = os.path.basename(selected_images[current_index])
                            audio_info = self.media_player.get_current_audio_info()
                            status_text = f"Status: Bild angezeigt - {image_name} ({current_index + 1}/{len(selected_images)})"
                            if audio_info:
                                status_text += f" | Audio: {audio_info}"
                            self.media_status_label.config(text=status_text, fg='cyan')
                    else:
                        self.media_player.show_black()
                        self.media_status_label.config(text="Status: Keine Bilder ausgewählt", fg='orange')
                        self.last_mode = "black"
            except ValueError:
                # Ungültige Schwellwerte
                pass
        
        # Nächstes Update in 100ms
        self.root.after(100, self.update_status)

    def run(self):
        """GUI starten"""
        try:
            self.root.mainloop()
        finally:
            # Cleanup
            self.observer.stop()
            self.observer.join()
            self.sensor_thread.stop()
            self.media_player.cleanup()  # VLC-Ressourcen freigeben

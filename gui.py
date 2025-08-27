"""
GUI-Logik mit tkinter
"""
import tkinter as tk
from tkinter import filedialog, ttk
import os
from config import DEFAULT_MIN_DIST, DEFAULT_MAX_DIST, DEFAULT_INTERVAL, VIDEO_FOLDER, IMAGE_FOLDER
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
        
        # Dateipfade
        self.selected_video = None
        self.selected_image = None
        self.video_files = []
        self.image_files = []
        
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
        
        # ESC zum Beenden (für Testing)
        self.root.bind('<Escape>', lambda e: self.root.quit())
        
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
        
        # Dateiauswahl Frame
        file_frame = tk.Frame(main_frame, bg='black')
        file_frame.pack(pady=30)
        
        # Video-Auswahl
        tk.Label(file_frame, text="Video:", font=('Arial', 14), fg='white', bg='black').grid(row=0, column=0, sticky='w')
        self.video_var = tk.StringVar(value="Keine Datei gewählt")
        self.video_combo = ttk.Combobox(file_frame, textvariable=self.video_var, 
                                       font=('Arial', 12), width=30, state='readonly')
        self.video_combo.grid(row=0, column=1, padx=10)
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)
        
        tk.Button(file_frame, text="Video durchsuchen", command=self.browse_video,
                 font=('Arial', 12)).grid(row=0, column=2, padx=10)
        
        # Bild-Auswahl  
        tk.Label(file_frame, text="Bild:", font=('Arial', 14), fg='white', bg='black').grid(row=1, column=0, sticky='w')
        self.image_var = tk.StringVar(value="Keine Datei gewählt")
        self.image_combo = ttk.Combobox(file_frame, textvariable=self.image_var,
                                       font=('Arial', 12), width=30, state='readonly')
        self.image_combo.grid(row=1, column=1, padx=10)
        self.image_combo.bind('<<ComboboxSelected>>', self.on_image_selected)
        
        tk.Button(file_frame, text="Bild durchsuchen", command=self.browse_image,
                 font=('Arial', 12)).grid(row=1, column=2, padx=10)
        
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
            
        self.observer.start()
    
    def refresh_file_lists(self):
        """Aktualisiert die Dateilisten aus den Watchfoldern"""
        # Videos laden
        self.video_files = []
        if os.path.exists(VIDEO_FOLDER):
            for file in os.listdir(VIDEO_FOLDER):
                if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
                    self.video_files.append(file)
        
        # Bilder laden
        self.image_files = []
        if os.path.exists(IMAGE_FOLDER):
            for file in os.listdir(IMAGE_FOLDER):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    self.image_files.append(file)
        
        # Comboboxen aktualisieren
        self.video_combo['values'] = self.video_files
        self.image_combo['values'] = self.image_files
    
    def browse_video(self):
        """Video-Datei auswählen"""
        file_path = filedialog.askopenfilename(
            title="Video auswählen",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_video = file_path
            self.video_var.set(os.path.basename(file_path))
    
    def browse_image(self):
        """Bild-Datei auswählen"""
        file_path = filedialog.askopenfilename(
            title="Bild auswählen", 
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_image = file_path
            self.image_var.set(os.path.basename(file_path))
    
    def on_video_selected(self, event):
        """Video aus Watchfolder gewählt"""
        selected = self.video_combo.get()
        if selected and selected in self.video_files:
            self.selected_video = os.path.join(VIDEO_FOLDER, selected)
    
    def on_image_selected(self, event):
        """Bild aus Watchfolder gewählt"""
        selected = self.image_combo.get()
        if selected and selected in self.image_files:
            self.selected_image = os.path.join(IMAGE_FOLDER, selected)
    
    def update_interval(self):
        """Messintervall des Sensors aktualisieren"""
        try:
            new_interval = float(self.interval_var.get()) / 1000.0  # ms -> s
            self.sensor_thread.interval = new_interval
        except ValueError:
            pass  # Ungültige Eingabe ignorieren
    
    def update_status(self):
        """Status-Update (wird zyklisch aufgerufen)"""
        # Abstand anzeigen
        distance = self.sensor_thread.distance
        self.status_label.config(text=f"Abstand: {distance:.1f} cm")
        
        # Media-Steuerung basierend auf Abstand
        try:
            min_dist = float(self.min_dist_var.get())
            max_dist = float(self.max_dist_var.get())
            
            if min_dist <= distance <= max_dist:
                # Video abspielen
                if self.selected_video:
                    self.media_player.play_video(self.selected_video)
                    self.media_status_label.config(text="Status: Video läuft", fg='lime')
                else:
                    self.media_player.show_black()
                    self.media_status_label.config(text="Status: Kein Video gewählt - Schwarzes Bild", fg='orange')
            else:
                # Bild anzeigen
                if self.selected_image:
                    self.media_player.show_image(self.selected_image)
                    self.media_status_label.config(text="Status: Bild angezeigt", fg='cyan')
                else:
                    self.media_player.show_black()
                    self.media_status_label.config(text="Status: Kein Bild gewählt - Schwarzes Bild", fg='orange')
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

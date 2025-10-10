"""
VLC-basierte GUI mit Live-Bildvorschau und Sensor-Integration
Erweiterte Version mit allen Features der ursprünglichen GUI
"""
import tkinter as tk
from tkinter import ttk, simpledialog
import os
import time
import json
import datetime
import subprocess
import platform
import threading
from config import (DEFAULT_MIN_DIST, DEFAULT_MAX_DIST, DEFAULT_INTERVAL, 
                   VIDEO_FOLDER, IMAGE_FOLDER, AUDIO_FOLDER, 
                   IMAGE_DISPLAY_TIME, AUDIO_FADE_TIME,
                   MIN_VIDEO_RUNTIME, MIN_IMAGE_DISPLAY_TIME, MIN_AUDIO_RUNTIME)
from media_player_vlc import VLCMediaPlayer

class VLCMediaStationGUI:
    def __init__(self, sensor_thread, kiosk_mode=False):
        self.sensor_thread = sensor_thread
        self.kiosk_mode = kiosk_mode
        self._sensor_in_range = False  # Entprellung für Sensor-Trigger
        # Erweiterte Entprellung/Hysterese & Cooldown
        self._in_range_count = 0
        self._out_of_range_count = 0
        self._stability_cycles_enter = 3  # Anzahl aufeinanderfolgender Messungen für stabilen Eintritt
        self._stability_cycles_exit = 2   # Schnelleres Reagieren beim Verlassen (nur 2 Messungen = 400ms)
        self._last_trigger_ts = 0.0
        self._play_started_ts = 0.0
        self._cooldown_until_ts = 0.0
        self._restore_after_id = None  # für verzögertes Wiederherstellen der Bildvorschau
        
        # Dateien
        self.all_video_files = []
        self.all_image_files = []
        self.all_audio_files = []
        self.video_checkboxes = {}
        self.selected_image_var = None  # Radio-Button für Bildauswahl (nur EINS)
        self.audio_checkboxes = {}
        
        # Konfigurable Werte
        self.current_image_display_time = IMAGE_DISPLAY_TIME
        self.current_audio_fade_time = AUDIO_FADE_TIME
        self.current_min_video_time = MIN_VIDEO_RUNTIME
        self.current_min_image_time = MIN_IMAGE_DISPLAY_TIME
        self.current_min_audio_time = MIN_AUDIO_RUNTIME
        
        # GUI erstellen (ERST Root-Fenster, dann MediaPlayer!)
        self.root = tk.Tk()
        self.root.title("FACES Player V1.0")
        self.root.configure(bg='black')
        
        # Fullscreen für Raspberry Pi (robuster Ansatz)
        try:
            # Versuch 1: attributes -zoomed (funktioniert auf Linux)
            self.root.attributes('-zoomed', True)
        except:
            try:
                # Versuch 2: Fullscreen-Attribut
                self.root.attributes('-fullscreen', True)
            except:
                # Versuch 3: Manuelles Setzen der Größe
                width = self.root.winfo_screenwidth()
                height = self.root.winfo_screenheight()
                self.root.geometry(f"{width}x{height}+0+0")
        
        # ESC-Taste zum Beenden im Fullscreen
        self.root.bind('<Escape>', lambda e: self.cleanup() if not self.kiosk_mode else None)
        
        # JETZT MediaPlayer erstellen (nachdem Root existiert)
        self.media_player = VLCMediaPlayer()
        
        self.setup_gui()
        self.scan_media_files()
        self.sync_entry_fields()
        self.update_trigger_labels()  # Trigger-Labels mit aktuellen Werten initialisieren
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
        tk.Label(main_frame, text="FACES Player V1.0", 
                 font=('Arial', 24, 'bold'), fg='cyan', bg='black').pack(pady=10)

        # Status
        self.status_label = tk.Label(main_frame, text="Sensor: Initialisierung...", 
                                     font=('Arial', 16), fg='yellow', bg='black')
        self.status_label.pack(pady=5)

        # Sensor Aktivierung Button
        self.sensor_enabled = False  # Sensor standardmäßig deaktiviert
        self.sensor_button = tk.Button(main_frame, text="▶ Sensor AKTIVIEREN", 
                                       command=self.toggle_sensor,
                                       font=('Arial', 14, 'bold'), 
                                       bg='green', fg='white',
                                       width=25, height=2)
        self.sensor_button.pack(pady=10)

        # Sensor-Einstellungen
        settings_frame = tk.LabelFrame(main_frame, text="Sensor-Einstellungen",
                                       font=('Arial', 14, 'bold'), fg='white', bg='black', bd=2)
        settings_frame.pack(pady=10, padx=10, fill='x')

        # Min/Max Abstand mit Speichern-Buttons
        tk.Label(settings_frame, text="Min. Abstand (cm):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.min_dist_var = tk.StringVar()
        self.min_dist_var.set(str(DEFAULT_MIN_DIST))
        self.min_dist_entry = tk.Entry(settings_frame, textvariable=self.min_dist_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.min_dist_entry.grid(row=0, column=1, padx=5)
        self.min_dist_entry.delete(0, tk.END)
        self.min_dist_entry.insert(0, str(DEFAULT_MIN_DIST))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_min_dist, font=('Arial', 10)).grid(row=0, column=2, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_min_dist, font=('Arial', 10)).grid(row=0, column=3, padx=5)

        tk.Label(settings_frame, text="Max. Abstand (cm):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=0, column=4, sticky='w', padx=10)
        self.max_dist_var = tk.StringVar()
        self.max_dist_var.set(str(DEFAULT_MAX_DIST))
        self.max_dist_entry = tk.Entry(settings_frame, textvariable=self.max_dist_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.max_dist_entry.grid(row=0, column=5, padx=5)
        self.max_dist_entry.delete(0, tk.END)
        self.max_dist_entry.insert(0, str(DEFAULT_MAX_DIST))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_max_dist, font=('Arial', 10)).grid(row=0, column=6, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_max_dist, font=('Arial', 10)).grid(row=0, column=7, padx=5)

        # Messintervall
        tk.Label(settings_frame, text="Messintervall (ms):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.interval_var = tk.StringVar()
        self.interval_var.set(str(int(DEFAULT_INTERVAL * 1000)))
        self.interval_entry = tk.Entry(settings_frame, textvariable=self.interval_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.interval_entry.grid(row=1, column=1, padx=5)
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(int(DEFAULT_INTERVAL * 1000)))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_interval, font=('Arial', 10)).grid(row=1, column=2, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_interval, font=('Arial', 10)).grid(row=1, column=3, padx=5)

        # Bildwechselzeit
        tk.Label(settings_frame, text="Bildwechsel (s):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=1, column=4, sticky='w', padx=10)
        self.image_interval_var = tk.StringVar()
        self.image_interval_var.set(str(IMAGE_DISPLAY_TIME))
        self.image_interval_entry = tk.Entry(settings_frame, textvariable=self.image_interval_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.image_interval_entry.grid(row=1, column=5, padx=5)
        self.image_interval_entry.delete(0, tk.END)
        self.image_interval_entry.insert(0, str(IMAGE_DISPLAY_TIME))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_image_interval, font=('Arial', 10)).grid(row=1, column=6, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_image_interval, font=('Arial', 10)).grid(row=1, column=7, padx=5)

        # Audio-Fade
        tk.Label(settings_frame, text="Audio-Fade (ms):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.audio_fade_var = tk.StringVar()
        self.audio_fade_var.set(str(int(AUDIO_FADE_TIME * 1000)))
        self.audio_fade_entry = tk.Entry(settings_frame, textvariable=self.audio_fade_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.audio_fade_entry.grid(row=2, column=1, padx=5)
        self.audio_fade_entry.delete(0, tk.END)
        self.audio_fade_entry.insert(0, str(int(AUDIO_FADE_TIME * 1000)))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_audio_fade, font=('Arial', 10)).grid(row=2, column=2, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_audio_fade, font=('Arial', 10)).grid(row=2, column=3, padx=5)

        # Mindestzeiten
        tk.Label(settings_frame, text="Min. Video-Zeit (s):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.min_video_var = tk.StringVar()
        self.min_video_var.set(str(MIN_VIDEO_RUNTIME))
        self.min_video_entry = tk.Entry(settings_frame, textvariable=self.min_video_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.min_video_entry.grid(row=3, column=1, padx=5)
        self.min_video_entry.delete(0, tk.END)
        self.min_video_entry.insert(0, str(MIN_VIDEO_RUNTIME))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_min_video_time, font=('Arial', 10)).grid(row=3, column=2, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_min_video_time, font=('Arial', 10)).grid(row=3, column=3, padx=5)

        tk.Label(settings_frame, text="Min. Bild-Zeit (s):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=3, column=4, sticky='w', padx=10)
        self.min_image_var = tk.StringVar()
        self.min_image_var.set(str(MIN_IMAGE_DISPLAY_TIME))
        self.min_image_entry = tk.Entry(settings_frame, textvariable=self.min_image_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.min_image_entry.grid(row=3, column=5, padx=5)
        self.min_image_entry.delete(0, tk.END)
        self.min_image_entry.insert(0, str(MIN_IMAGE_DISPLAY_TIME))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_min_image_time, font=('Arial', 10)).grid(row=3, column=6, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_min_image_time, font=('Arial', 10)).grid(row=3, column=7, padx=5)

        tk.Label(settings_frame, text="Min. Audio-Zeit (s):", fg='white', bg='black', font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', padx=10, pady=5)
        self.min_audio_var = tk.StringVar()
        self.min_audio_var.set(str(MIN_AUDIO_RUNTIME))
        self.min_audio_entry = tk.Entry(settings_frame, textvariable=self.min_audio_var, width=10,
                 bg='gray20', fg='lime', insertbackground='white', font=('Arial', 12, 'bold'))
        self.min_audio_entry.grid(row=4, column=1, padx=5)
        self.min_audio_entry.delete(0, tk.END)
        self.min_audio_entry.insert(0, str(MIN_AUDIO_RUNTIME))
        tk.Button(settings_frame, text="Standard", bg='gray30', fg='white',
                  command=self.reset_min_audio_time, font=('Arial', 10)).grid(row=4, column=2, padx=5)
        tk.Button(settings_frame, text="Speichern", bg='lightgreen', fg='black',
                  command=self.save_min_audio_time, font=('Arial', 10)).grid(row=4, column=3, padx=5)
        
        # Sensor-Trigger-Konfiguration (4 separate Bereiche für Video/Audio1/Audio2/Bild)
        sensor_config_frame = tk.LabelFrame(main_frame, text="Sensor-Trigger Konfiguration", 
                                        font=('Arial', 14, 'bold'), fg='orange', bg='black', bd=2)
        sensor_config_frame.pack(pady=10, padx=10, fill='x')
        
        # === VIDEO TRIGGER ===
        video_trigger_frame = tk.LabelFrame(sensor_config_frame, text="🎬 VIDEO", 
                                           font=('Arial', 12, 'bold'), fg='cyan', bg='black', bd=2)
        video_trigger_frame.pack(pady=5, padx=10, fill='x')
        
        self.video_trigger_var = tk.StringVar(value="inside")
        # Dynamische Labels - werden später mit update_trigger_labels() aktualisiert
        self.video_inside_label = tk.StringVar(value=f"Innerhalb ({DEFAULT_MIN_DIST}-{DEFAULT_MAX_DIST}cm)")
        self.video_outside_label = tk.StringVar(value=f"Außerhalb (<{DEFAULT_MIN_DIST}cm oder >{DEFAULT_MAX_DIST}cm)")
        
        tk.Radiobutton(video_trigger_frame, textvariable=self.video_inside_label, 
                      variable=self.video_trigger_var, value="inside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(video_trigger_frame, textvariable=self.video_outside_label, 
                      variable=self.video_trigger_var, value="outside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(video_trigger_frame, text="Deaktiviert", 
                      variable=self.video_trigger_var, value="disabled", bg='black', fg='gray',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        # === AUDIO 1 TRIGGER ===
        audio_trigger_frame = tk.LabelFrame(sensor_config_frame, text="🎵 AUDIO 1", 
                                           font=('Arial', 12, 'bold'), fg='magenta', bg='black', bd=2)
        audio_trigger_frame.pack(pady=5, padx=10, fill='x')
        
        self.audio_trigger_var = tk.StringVar(value="disabled")
        self.audio_inside_label = tk.StringVar(value=f"Innerhalb ({DEFAULT_MIN_DIST}-{DEFAULT_MAX_DIST}cm)")
        self.audio_outside_label = tk.StringVar(value=f"Außerhalb (<{DEFAULT_MIN_DIST}cm oder >{DEFAULT_MAX_DIST}cm)")
        
        tk.Radiobutton(audio_trigger_frame, textvariable=self.audio_inside_label, 
                      variable=self.audio_trigger_var, value="inside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(audio_trigger_frame, textvariable=self.audio_outside_label, 
                      variable=self.audio_trigger_var, value="outside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(audio_trigger_frame, text="Deaktiviert", 
                      variable=self.audio_trigger_var, value="disabled", bg='black', fg='gray',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        # === AUDIO 2 TRIGGER ===
        audio2_trigger_frame = tk.LabelFrame(sensor_config_frame, text="🎵 AUDIO 2", 
                                           font=('Arial', 12, 'bold'), fg='violet', bg='black', bd=2)
        audio2_trigger_frame.pack(pady=5, padx=10, fill='x')
        
        self.audio2_trigger_var = tk.StringVar(value="disabled")
        self.audio2_inside_label = tk.StringVar(value=f"Innerhalb ({DEFAULT_MIN_DIST}-{DEFAULT_MAX_DIST}cm)")
        self.audio2_outside_label = tk.StringVar(value=f"Außerhalb (<{DEFAULT_MIN_DIST}cm oder >{DEFAULT_MAX_DIST}cm)")
        
        tk.Radiobutton(audio2_trigger_frame, textvariable=self.audio2_inside_label, 
                      variable=self.audio2_trigger_var, value="inside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(audio2_trigger_frame, textvariable=self.audio2_outside_label, 
                      variable=self.audio2_trigger_var, value="outside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(audio2_trigger_frame, text="Deaktiviert", 
                      variable=self.audio2_trigger_var, value="disabled", bg='black', fg='gray',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        # === BILD TRIGGER ===
        image_trigger_frame = tk.LabelFrame(sensor_config_frame, text="🖼️ BILD", 
                                           font=('Arial', 12, 'bold'), fg='yellow', bg='black', bd=2)
        image_trigger_frame.pack(pady=5, padx=10, fill='x')
        
        self.image_trigger_var = tk.StringVar(value="outside")  # Bild standardmäßig außerhalb
        self.image_inside_label = tk.StringVar(value=f"Innerhalb ({DEFAULT_MIN_DIST}-{DEFAULT_MAX_DIST}cm)")
        self.image_outside_label = tk.StringVar(value=f"Außerhalb (<{DEFAULT_MIN_DIST}cm oder >{DEFAULT_MAX_DIST}cm)")
        
        tk.Radiobutton(image_trigger_frame, textvariable=self.image_inside_label, 
                      variable=self.image_trigger_var, value="inside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(image_trigger_frame, textvariable=self.image_outside_label, 
                      variable=self.image_trigger_var, value="outside", bg='black', fg='white',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        tk.Radiobutton(image_trigger_frame, text="Deaktiviert", 
                      variable=self.image_trigger_var, value="disabled", bg='black', fg='gray',
                      selectcolor='darkgray', font=('Arial', 11)).pack(side='left', padx=15, pady=5)
        
        # VLC-Steuerung
        control_frame = tk.LabelFrame(main_frame, text="VLC-Steuerung", 
                                    font=('Arial', 14, 'bold'), fg='magenta', bg='black', bd=2)
        control_frame.pack(pady=10, padx=10, fill='x')
        
        controls_row1 = tk.Frame(control_frame, bg='black')
        controls_row1.pack(pady=5)
        
        tk.Button(controls_row1, text="▶ START", command=self.start_playback, 
                 bg='lime', fg='black', font=('Arial', 11, 'bold')).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Pause/Play", command=self.vlc_pause, 
                 bg='yellow', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Stop", command=self.vlc_stop, 
                 bg='red', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Nächstes", command=self.vlc_next, 
                 bg='lightblue', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        tk.Button(controls_row1, text="Vorheriges", command=self.vlc_previous, 
                 bg='lightblue', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        
        # Media-Vollbild Controls
        controls_row2 = tk.Frame(control_frame, bg='black')
        controls_row2.pack(pady=5)
        
        tk.Label(controls_row2, text="Media-Anzeige:", font=('Arial', 12, 'bold'), 
                fg='cyan', bg='black').pack(side='left', padx=10)
        
        tk.Button(controls_row2, text="Media-Vollbild EIN", command=self.toggle_media_fullscreen, 
                 bg='lime', fg='black', font=('Arial', 11, 'bold')).pack(side='left', padx=5)
        
        tk.Button(controls_row2, text="Media-Fenster", command=self.set_media_windowed, 
                 bg='orange', fg='black', font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Label(controls_row2, text=" | GUI:", font=('Arial', 12, 'bold'), 
                fg='white', bg='black').pack(side='left', padx=10)
        
        tk.Button(controls_row2, text="GUI verstecken", command=self.hide_gui, 
                 bg='purple', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Button(controls_row2, text="GUI-Vollbild (F11)", command=self.toggle_gui_fullscreen, 
                 bg='darkgreen', fg='white', font=('Arial', 11)).pack(side='left', padx=5)
        
        tk.Button(controls_row2, text="TEST BILD", command=self.test_show_image, 
                 bg='orange', fg='black', font=('Arial', 11, 'bold')).pack(side='left', padx=5)
        
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

        # Bestätigen-Button für Bildauswahl
        tk.Button(image_frame, text="Bestätigen", bg='lightgreen', fg='black',
                 font=('Arial', 10, 'bold'), command=self.confirm_image_selection).pack(pady=4)

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
        
        # Tastenkombinationen
        self.root.bind('<F11>', lambda e: self.toggle_gui_fullscreen())
        self.root.bind('<Escape>', lambda e: self.root.quit())

    def confirm_image_selection(self):
        """Handler für Bestätigen-Button: wendet aktuelle Bildauswahl an und gibt Feedback."""
        selected_images = self.get_selected_images()
        if selected_images:
            print(f"[VLC-GUI] Bildauswahl bestätigt: {[os.path.basename(f) for f in selected_images]}")
            self.media_status_label.config(text=f"Bildauswahl bestätigt ({len(selected_images)} Bilder)", fg='lightgreen')
            # Hier ggf. weitere Logik zum Speichern/Anwenden der Auswahl einfügen
        else:
            print("[VLC-GUI] Keine Bilder ausgewählt bei Bestätigung.")
            self.media_status_label.config(text="Keine Bilder ausgewählt!", fg='orange')
    
    def toggle_sensor(self):
        """Aktiviert oder deaktiviert die Sensor-Reaktion"""
        self.sensor_enabled = not self.sensor_enabled
        
        if self.sensor_enabled:
            # Sensor aktiviert
            self.sensor_button.config(
                text="⏸ Sensor DEAKTIVIEREN",
                bg='red',
                fg='white'
            )
            print("[VLC-GUI] Sensor wurde AKTIVIERT - reagiert auf Bewegung")
            self.media_status_label.config(text="Sensor aktiviert - warte auf Auslösung", fg='lime')
            # Bildvorschau anzeigen wenn Bilder vorhanden
            self.restore_image_preview()
        else:
            # Sensor deaktiviert
            self.sensor_button.config(
                text="▶ Sensor AKTIVIEREN",
                bg='green',
                fg='white'
            )
            print("[VLC-GUI] Sensor wurde DEAKTIVIERT")
            self.media_status_label.config(text="Sensor deaktiviert - bereit zur Konfiguration", fg='yellow')
            # Stoppe laufende Wiedergabe
            if self.media_player.is_playing:
                self.media_player.stop()
            # Zeige schwarzen Bildschirm
            self.media_player.show_black()
    
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
            var = tk.BooleanVar(value=True)
            self.video_checkboxes[video_file] = var
            cb = tk.Checkbutton(self.video_scroll_frame, text=os.path.basename(video_file), 
                               variable=var, bg='gray10', fg='white', selectcolor='darkgray',
                               font=('Arial', 9))
            cb.pack(anchor='w', padx=3, pady=1)
        
        # Bilder - NUR EINS AUSWÄHLBAR (Radio statt Checkbox)
        for widget in self.image_scroll_frame.winfo_children():
            widget.destroy()
        
        # Initialisiere Variable beim ersten Mal - erstes Bild automatisch wählen
        if not self.selected_image_var:
            default_image = self.all_image_files[0] if self.all_image_files else ""
            self.selected_image_var = tk.StringVar(value=default_image)
            if default_image:
                print(f"[FACES] Erstes Bild automatisch ausgewählt: {os.path.basename(default_image)}")
        
        for image_file in self.all_image_files:
            rb = tk.Radiobutton(self.image_scroll_frame, text=os.path.basename(image_file), 
                               variable=self.selected_image_var, value=image_file,
                               bg='gray10', fg='white', selectcolor='darkgray',
                               font=('Arial', 9))
            rb.pack(anchor='w', padx=3, pady=1)
        
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
        
        # KEIN Auto-Start der Bildvorschau mehr - Nutzer wählt manuell
    
    # ====== LIVE IMAGE PREVIEW FUNKTIONALITÄT (ENTFERNT) ======
    
    def restore_image_preview(self):
        """Stellt die Bildvorschau wieder her wenn Sensor-Wiedergabe beendet ist"""
        try:
            selected_images = self.get_selected_images()
            print(f"[FACES] restore_image_preview() - Ausgewählte Bilder: {len(selected_images)}")
            if selected_images:
                first_image = selected_images[0]
                print(f"[FACES] Zeige Bild: {os.path.basename(first_image)}")
                success = self.media_player.play_single_media(first_image)
                if success:
                    self.media_status_label.config(
                        text=f"Bild-Vorschau: {os.path.basename(first_image)}", 
                        fg='cyan'
                    )
                    print(f"[FACES] Bild erfolgreich angezeigt")
                else:
                    print(f"[FACES] FEHLER: Bild konnte nicht angezeigt werden")
            else:
                print("[FACES] WARNUNG: Keine Bilder ausgewählt - zeige schwarzes Bild")
                self.media_player.show_black()
                self.media_status_label.config(text="Kein Bild ausgewählt", fg='yellow')
        except Exception as e:
            print(f"[FACES] FEHLER bei Bildvorschau: {e}")
            import traceback
            traceback.print_exc()
            self.media_player.show_black()
    
    def test_show_image(self):
        """TEST-BUTTON: Zeigt das ausgewählte Bild direkt an"""
        print("\n" + "="*50)
        print("[FACES TEST] TEST BILD Button gedrückt!")
        print("="*50)
        
        # Hole ausgewählte Bilder
        selected_images = self.get_selected_images()
        print(f"[FACES TEST] get_selected_images() liefert: {selected_images}")
        
        if selected_images:
            first_image = selected_images[0]
            print(f"[FACES TEST] Versuche Bild anzuzeigen: {first_image}")
            print(f"[FACES TEST] Datei existiert: {os.path.exists(first_image)}")
            
            # Direkt Media Player aufrufen
            success = self.media_player.play_single_media(first_image)
            print(f"[FACES TEST] play_single_media() Ergebnis: {success}")
            
            if success:
                self.media_status_label.config(text=f"TEST: Bild angezeigt - {os.path.basename(first_image)}", fg='lime')
                print("[FACES TEST] ✓ Bild erfolgreich angezeigt!")
            else:
                self.media_status_label.config(text="TEST: Bild-Anzeige FEHLGESCHLAGEN!", fg='red')
                print("[FACES TEST] ✗ Bild konnte NICHT angezeigt werden!")
        else:
            print("[FACES TEST] ✗ KEINE Bilder ausgewählt!")
            self.media_status_label.config(text="TEST: Kein Bild ausgewählt!", fg='orange')
        
        print("="*50 + "\n")
    
    # ====== PARAMETER SPEICHERN METHODEN ======
    def save_min_dist(self):
        try:
            new_min = float(self.min_dist_var.get())
            if new_min >= 1:
                print(f"[FACES] Min-Abstand gespeichert: {new_min} cm")
                self.update_trigger_labels()  # Labels aktualisieren
            else:
                print("[FACES] Min-Abstand zu klein (mindestens 1cm)")
        except ValueError:
            print("[FACES] Ungültiger Min-Abstand")
    
    def save_max_dist(self):
        try:
            new_max = float(self.max_dist_var.get())
            if new_max >= 10:
                print(f"[FACES] Max-Abstand gespeichert: {new_max} cm")
                self.update_trigger_labels()  # Labels aktualisieren
            else:
                print("[FACES] Max-Abstand zu klein (mindestens 10cm)")
        except ValueError:
            print("[FACES] Ungültiger Max-Abstand")
    
    def update_trigger_labels(self):
        """Aktualisiert die Trigger-Label-Texte mit aktuellen Min/Max-Werten"""
        try:
            min_val = self.min_dist_var.get()
            max_val = self.max_dist_var.get()
            
            # Video-Trigger Labels
            self.video_inside_label.set(f"Innerhalb ({min_val}-{max_val}cm)")
            self.video_outside_label.set(f"Außerhalb (<{min_val}cm oder >{max_val}cm)")
            
            # Audio 1-Trigger Labels
            self.audio_inside_label.set(f"Innerhalb ({min_val}-{max_val}cm)")
            self.audio_outside_label.set(f"Außerhalb (<{min_val}cm oder >{max_val}cm)")
            
            # Audio 2-Trigger Labels
            self.audio2_inside_label.set(f"Innerhalb ({min_val}-{max_val}cm)")
            self.audio2_outside_label.set(f"Außerhalb (<{min_val}cm oder >{max_val}cm)")
            
            # Bild-Trigger Labels
            self.image_inside_label.set(f"Innerhalb ({min_val}-{max_val}cm)")
            self.image_outside_label.set(f"Außerhalb (<{min_val}cm oder >{max_val}cm)")
            
            print(f"[FACES] Trigger-Labels aktualisiert: {min_val}-{max_val}cm")
        except Exception as e:
            print(f"[FACES] Fehler beim Aktualisieren der Trigger-Labels: {e}")
    
    def save_interval(self):
        try:
            new_interval_ms = float(self.interval_var.get())
            new_interval_s = new_interval_ms / 1000.0
            self.sensor_thread.interval = max(0.1, new_interval_s)
            print(f"[VLC-GUI] Messintervall gespeichert: {new_interval_ms}ms ({new_interval_s}s)")
        except ValueError:
            print("[VLC-GUI] Ungültiges Messintervall")
    
    def save_image_interval(self):
        try:
            new_interval = float(self.image_interval_var.get())
            self.current_image_display_time = max(1.0, new_interval)
            self.media_player.set_min_display_time(self.current_image_display_time)
            print(f"[VLC-GUI] Bildwechselzeit gespeichert: {self.current_image_display_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Bildwechselzeit")
    
    def save_audio_fade(self):
        try:
            new_fade_ms = float(self.audio_fade_var.get())
            self.current_audio_fade_time = max(10, new_fade_ms) / 1000.0
            print(f"[VLC-GUI] Audio-Fade-Zeit gespeichert: {new_fade_ms}ms ({self.current_audio_fade_time}s)")
        except ValueError:
            print("[VLC-GUI] Ungültige Audio-Fade-Zeit")
    
    def save_min_video_time(self):
        try:
            new_min_video = float(self.min_video_var.get())
            self.current_min_video_time = max(0.5, new_min_video)
            print(f"[VLC-GUI] Min-Video-Zeit gespeichert: {self.current_min_video_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Video-Zeit")
    
    def save_min_image_time(self):
        try:
            new_min_image = float(self.min_image_var.get())
            self.current_min_image_time = max(0.5, new_min_image)
            print(f"[VLC-GUI] Min-Bild-Zeit gespeichert: {self.current_min_image_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Bild-Zeit")
    
    def save_min_audio_time(self):
        try:
            new_min_audio = float(self.min_audio_var.get())
            self.current_min_audio_time = max(1.0, new_min_audio)
            print(f"[VLC-GUI] Min-Audio-Zeit gespeichert: {self.current_min_audio_time}s")
        except ValueError:
            print("[VLC-GUI] Ungültige Min-Audio-Zeit")
    
    # ====== RESET-METHODEN FÜR STANDARD-BUTTONS ======
    def reset_min_dist(self):
        """Setzt Min-Abstand auf Standard zurück"""
        self.min_dist_var.set(str(DEFAULT_MIN_DIST))
        self.min_dist_entry.delete(0, tk.END)
        self.min_dist_entry.insert(0, str(DEFAULT_MIN_DIST))
        self.update_trigger_labels()  # Labels aktualisieren
        print(f"[FACES] Min-Abstand auf Standard zurückgesetzt: {DEFAULT_MIN_DIST} cm")
    
    def reset_max_dist(self):
        """Setzt Max-Abstand auf Standard zurück"""
        self.max_dist_var.set(str(DEFAULT_MAX_DIST))
        self.max_dist_entry.delete(0, tk.END)
        self.max_dist_entry.insert(0, str(DEFAULT_MAX_DIST))
        self.update_trigger_labels()  # Labels aktualisieren
        print(f"[FACES] Max-Abstand auf Standard zurückgesetzt: {DEFAULT_MAX_DIST} cm")
    
    def reset_interval(self):
        """Setzt Messintervall auf Standard zurück"""
        self.interval_var.set(str(int(DEFAULT_INTERVAL * 1000)))
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, str(int(DEFAULT_INTERVAL * 1000)))
        print(f"[VLC-GUI] Messintervall auf Standard zurückgesetzt: {int(DEFAULT_INTERVAL * 1000)} ms")
    
    def reset_image_interval(self):
        """Setzt Bildwechselzeit auf Standard zurück"""
        self.image_interval_var.set(str(IMAGE_DISPLAY_TIME))
        self.image_interval_entry.delete(0, tk.END)
        self.image_interval_entry.insert(0, str(IMAGE_DISPLAY_TIME))
        print(f"[VLC-GUI] Bildwechselzeit auf Standard zurückgesetzt: {IMAGE_DISPLAY_TIME} s")
    
    def reset_audio_fade(self):
        """Setzt Audio-Fade auf Standard zurück"""
        self.audio_fade_var.set(str(int(AUDIO_FADE_TIME * 1000)))
        self.audio_fade_entry.delete(0, tk.END)
        self.audio_fade_entry.insert(0, str(int(AUDIO_FADE_TIME * 1000)))
        print(f"[VLC-GUI] Audio-Fade auf Standard zurückgesetzt: {int(AUDIO_FADE_TIME * 1000)} ms")
    
    def reset_min_video_time(self):
        """Setzt Min-Video-Zeit auf Standard zurück"""
        self.min_video_var.set(str(MIN_VIDEO_RUNTIME))
        self.min_video_entry.delete(0, tk.END)
        self.min_video_entry.insert(0, str(MIN_VIDEO_RUNTIME))
        print(f"[VLC-GUI] Min-Video-Zeit auf Standard zurückgesetzt: {MIN_VIDEO_RUNTIME} s")
    
    def reset_min_image_time(self):
        """Setzt Min-Bild-Zeit auf Standard zurück"""
        self.min_image_var.set(str(MIN_IMAGE_DISPLAY_TIME))
        self.min_image_entry.delete(0, tk.END)
        self.min_image_entry.insert(0, str(MIN_IMAGE_DISPLAY_TIME))
        print(f"[VLC-GUI] Min-Bild-Zeit auf Standard zurückgesetzt: {MIN_IMAGE_DISPLAY_TIME} s")
    
    def reset_min_audio_time(self):
        """Setzt Min-Audio-Zeit auf Standard zurück"""
        self.min_audio_var.set(str(MIN_AUDIO_RUNTIME))
        self.min_audio_entry.delete(0, tk.END)
        self.min_audio_entry.insert(0, str(MIN_AUDIO_RUNTIME))
        print(f"[VLC-GUI] Min-Audio-Zeit auf Standard zurückgesetzt: {MIN_AUDIO_RUNTIME} s")
    
    # ====== PLAYLIST METHODEN ======
    def refresh_playlists(self):
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
            
            # Bildvorschau aktualisieren falls Bilder geladen wurden
            if loaded_images > 0:
                self.on_image_selection_changed()
            
        except Exception as e:
            self.playlist_status_label.config(text=f"Laden fehlgeschlagen: {e}", fg='red')
    
    # ====== VLC STEUERUNG ======
    def vlc_pause(self):
        self.media_player.pause()
    
    def vlc_stop(self):
        self.media_player.stop()
    
    def vlc_next(self):
        self.media_player.next_media()
    
    def vlc_previous(self):
        self.media_player.previous_media()
    
    def start_playback(self):
        """Wiedergabe manuell starten"""
        try:
            if self.sensor_mode == "video":
                selected_videos = self.get_selected_videos()
                
                if not selected_videos:
                    self.media_status_label.config(text="Keine Videos ausgewählt!", fg='red')
                    print("[VLC-GUI] Manueller Start: Keine Videos ausgewählt")
                    return
                
                print(f"[VLC-GUI] Manueller Video-Start mit {len(selected_videos)} Videos")
                
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                success = self.media_player.play_media_list(selected_videos, shuffle=True)
                
                if success:
                    self.media_status_label.config(text=f"Video-Wiedergabe: {len(selected_videos)} Videos", fg='lime')
                    print("[VLC-GUI] Video-Wiedergabe erfolgreich gestartet")
                else:
                    self.media_status_label.config(text="Video-Start fehlgeschlagen!", fg='red')
                    print("[VLC-GUI] FEHLER: Video-Wiedergabe fehlgeschlagen")
                    
            elif self.sensor_mode == "audio":
                selected_audios = self.get_selected_audios()
                selected_images = self.get_selected_images()
                mixed_playlist = selected_audios + selected_images
                
                if not mixed_playlist:
                    self.media_status_label.config(text="Keine Audio/Bild-Dateien ausgewählt!", fg='red')
                    print("[VLC-GUI] Manueller Start: Keine Audio/Bild-Dateien ausgewählt")
                    return
                
                print(f"[VLC-GUI] Manueller Audio+Bild-Start: {len(selected_audios)} Audio + {len(selected_images)} Bilder")
                
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                success = self.media_player.play_media_list(mixed_playlist, shuffle=True)
                
                if success:
                    self.media_status_label.config(
                        text=f"Audio+Bild-Wiedergabe: {len(selected_audios)}A + {len(selected_images)}B", fg='lime')
                    print("[VLC-GUI] Audio+Bild-Wiedergabe erfolgreich gestartet")
                else:
                    self.media_status_label.config(text="Audio+Bild-Start fehlgeschlagen!", fg='red')
                    print("[VLC-GUI] FEHLER: Audio+Bild-Wiedergabe fehlgeschlagen")
            
        except Exception as e:
            self.media_status_label.config(text=f"Start-Fehler: {e}", fg='red')
            print(f"[VLC-GUI] FEHLER in start_playback: {e}")
    
    # ====== VOLLBILD & GUI CONTROLS ======
    def toggle_media_fullscreen(self):
        try:
            self.media_player._toggle_fullscreen()
            print("[VLC-GUI] Media-Vollbild umgeschaltet")
        except Exception as e:
            print(f"[VLC-GUI] Media-Vollbild-Fehler: {e}")
    
    def set_media_windowed(self):
        try:
            if self.media_player.media_window:
                self.media_player.media_window.attributes('-fullscreen', False)
            print("[VLC-GUI] Media-Player im Fenstermodus")
        except Exception as e:
            print(f"[VLC-GUI] Media-Fenster-Fehler: {e}")
    
    def toggle_gui_fullscreen(self):
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
        try:
            self.root.withdraw()
            print("[VLC-GUI] GUI versteckt - nur Media-Fenster sichtbar")
            print("[VLC-GUI] TIPP: Alt+Tab zum GUI zurückkehren oder GUI-Fenster in Taskleiste klicken")
        except Exception as e:
            print(f"[VLC-GUI] GUI-Hide-Fehler: {e}")
    
    def show_gui(self):
        try:
            self.root.deiconify()
            self.root.lift()
            print("[VLC-GUI] GUI wieder sichtbar")
        except Exception as e:
            print(f"[VLC-GUI] GUI-Show-Fehler: {e}")
    
    # ====== ORDNER ÖFFNEN ======
    def open_video_folder(self):
        try:
            video_path = os.path.abspath(VIDEO_FOLDER)
            if not os.path.exists(video_path):
                os.makedirs(video_path)
                print(f"[VLC-GUI] Video-Ordner erstellt: {video_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', video_path])
            elif platform.system() == "Darwin":
                subprocess.run(['open', video_path])
            else:
                subprocess.run(['xdg-open', video_path])
            
            print(f"[VLC-GUI] Video-Ordner geöffnet: {video_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Video-Ordners: {e}")
    
    def open_image_folder(self):
        try:
            image_path = os.path.abspath(IMAGE_FOLDER)
            if not os.path.exists(image_path):
                os.makedirs(image_path)
                print(f"[VLC-GUI] Bild-Ordner erstellt: {image_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', image_path])
            elif platform.system() == "Darwin":
                subprocess.run(['open', image_path])
            else:
                subprocess.run(['xdg-open', image_path])
            
            print(f"[VLC-GUI] Bild-Ordner geöffnet: {image_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Bild-Ordners: {e}")
    
    def open_audio_folder(self):
        try:
            audio_path = os.path.abspath(AUDIO_FOLDER)
            if not os.path.exists(audio_path):
                os.makedirs(audio_path)
                print(f"[VLC-GUI] Audio-Ordner erstellt: {audio_path}")
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', audio_path])
            elif platform.system() == "Darwin":
                subprocess.run(['open', audio_path])
            else:
                subprocess.run(['xdg-open', audio_path])
            
            print(f"[VLC-GUI] Audio-Ordner geöffnet: {audio_path}")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Öffnen des Audio-Ordners: {e}")
    
    # ====== HILFSMETHODEN ======
    def get_selected_videos(self):
        return [path for path, var in self.video_checkboxes.items() if var.get()]
    
    def get_selected_images(self):
        """Gibt das eine ausgewählte Bild zurück (oder leere Liste)"""
        if self.selected_image_var and self.selected_image_var.get():
            selected = self.selected_image_var.get()
            print(f"[FACES] get_selected_images() - Bild ausgewählt: {os.path.basename(selected)}")
            return [selected]
        else:
            print(f"[FACES] get_selected_images() - KEIN Bild ausgewählt (var exists: {bool(self.selected_image_var)}, value: '{self.selected_image_var.get() if self.selected_image_var else 'None'}')")
            return []
    
    def get_selected_audios(self):
        return [path for path, var in self.audio_checkboxes.items() if var.get()]
    
    def sync_entry_fields(self):
        """Synchronisiert die GUI-Entry-Felder mit den aktuellen Sensor- und Config-Werten"""
        try:
            # Min/Max Abstand
            if hasattr(self.sensor_thread, 'min_distance'):
                self.min_dist_var.set(str(self.sensor_thread.min_distance))
            else:
                self.min_dist_var.set(str(DEFAULT_MIN_DIST))
            
            if hasattr(self.sensor_thread, 'max_distance'):
                self.max_dist_var.set(str(self.sensor_thread.max_distance))
            else:
                self.max_dist_var.set(str(DEFAULT_MAX_DIST))
            
            # Messintervall
            if hasattr(self.sensor_thread, 'interval'):
                self.interval_var.set(str(int(self.sensor_thread.interval * 1000)))
            else:
                self.interval_var.set(str(int(DEFAULT_INTERVAL * 1000)))
            
            # Bildwechsel, Audio-Fade und Mindestzeiten
            self.image_interval_var.set(str(self.current_image_display_time))
            self.audio_fade_var.set(str(int(self.current_audio_fade_time * 1000)))
            self.min_video_var.set(str(self.current_min_video_time))
            self.min_image_var.set(str(self.current_min_image_time))
            self.min_audio_var.set(str(self.current_min_audio_time))
            
            # Force update - stelle sicher dass die Entry-Widgets die Werte auch wirklich anzeigen
            self.root.update_idletasks()
            
            print(f"[VLC-GUI] Entry-Felder synchronisiert: Min={self.min_dist_var.get()}, Max={self.max_dist_var.get()}, Intervall={self.interval_var.get()}ms")
            
        except Exception as e:
            print(f"[VLC-GUI] Fehler beim Synchronisieren der Entry-Felder: {e}")
    
    # ====== SENSOR INTEGRATION & STATUS UPDATE ======
    def update_status(self):
        """Status-Update-Schleife mit Sensor-Integration"""
        distance = self.sensor_thread.distance
        
        # Prüfe ob Sensor aktiviert ist
        if not self.sensor_enabled:
            # Sensor ist deaktiviert - zeige nur Status, aber keine Reaktion
            if distance == 0.0:
                self.status_label.config(text="Sensor: Nicht verbunden (deaktiviert)", fg='orange')
            else:
                self.status_label.config(text=f"Abstand: {distance:.1f} cm (deaktiviert)", fg='gray')
            # Nächstes Update
            self.root.after(200, self.update_status)
            return
        
        # Sensor ist aktiviert - normale Logik
        if distance == 0.0:
            self.status_label.config(text="Sensor: Nicht verbunden", fg='red')
            # Bildvorschau anzeigen wenn Sensor nicht verbunden
            if not self._sensor_in_range:
                self.restore_image_preview()
            self.media_status_label.config(text="Status: Kein Sensor", fg='red')
        else:
            self.status_label.config(text=f"Abstand: {distance:.1f} cm", fg='lime')
            
            try:
                min_dist = float(self.min_dist_var.get())
                max_dist = float(self.max_dist_var.get())
                
                # Prüfe ob innerhalb oder außerhalb des Bereichs
                in_range = (min_dist <= distance <= max_dist)
                
                # DEBUG: Sensor-Werte ausgeben
                print(f"[SENSOR] Abstand={distance:.1f}cm, Min={min_dist:.1f}cm, Max={max_dist:.1f}cm, in_range={in_range}")
                
                # Hole ALLE Trigger-Einstellungen
                video_trigger_mode = self.video_trigger_var.get()
                audio_trigger_mode = self.audio_trigger_var.get()
                audio2_trigger_mode = self.audio2_trigger_var.get()
                image_trigger_mode = self.image_trigger_var.get()
                
                # Bestimme ob Video getriggert werden soll (nur wenn nicht "disabled")
                should_trigger_video = (video_trigger_mode != "disabled") and (
                    (video_trigger_mode == "inside" and in_range) or 
                    (video_trigger_mode == "outside" and not in_range)
                )
                
                # Bestimme ob Audio 1 getriggert werden soll (nur wenn nicht "disabled")
                should_trigger_audio = (audio_trigger_mode != "disabled") and (
                    (audio_trigger_mode == "inside" and in_range) or 
                    (audio_trigger_mode == "outside" and not in_range)
                )
                
                # Bestimme ob Audio 2 getriggert werden soll (nur wenn nicht "disabled")
                should_trigger_audio2 = (audio2_trigger_mode != "disabled") and (
                    (audio2_trigger_mode == "inside" and in_range) or 
                    (audio2_trigger_mode == "outside" and not in_range)
                )
                
                # Bestimme ob Bild gezeigt werden soll (nur wenn nicht "disabled")
                should_show_image = (image_trigger_mode != "disabled") and (
                    (image_trigger_mode == "inside" and in_range) or 
                    (image_trigger_mode == "outside" and not in_range)
                )
                
                # DEBUG: Trigger-Entscheidungen ausgeben
                print(f"[TRIGGER] Video={video_trigger_mode}→{should_trigger_video}, Audio1={audio_trigger_mode}→{should_trigger_audio}, Audio2={audio2_trigger_mode}→{should_trigger_audio2}, Bild={image_trigger_mode}→{should_show_image}")
                
                now = time.time()
                
                # EINFACHE LOGIK: Jeder Trigger ist völlig unabhängig!
                # Jeder Trigger hat eigenen Cooldown um Race Conditions zu vermeiden
                
                # Initialisiere Cooldowns beim ersten Mal
                if not hasattr(self, '_video_cooldown_ts'):
                    self._video_cooldown_ts = 0
                    self._audio_cooldown_ts = 0
                    self._audio2_cooldown_ts = 0
                    self._image_cooldown_ts = 0
                
                # VIDEO-TRIGGER: Unabhängig, nur eigenen Cooldown beachten
                if should_trigger_video:
                    if not hasattr(self, '_video_is_triggered') or not self._video_is_triggered:
                        # Nur Cooldown prüfen wenn Video bereits läuft/lief (verhindert schnelles Neustart)
                        # Beim ersten Trigger (nach Stop) KEIN Cooldown
                        print("[FACES] Video-Trigger AKTIVIERT")
                        self._video_is_triggered = True
                        try:
                            self.handle_video_trigger()
                            self._video_cooldown_ts = now + max(0.5, float(self.current_min_video_time))
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Video-Start: {e}")
                            self._video_is_triggered = False
                else:
                    if hasattr(self, '_video_is_triggered') and self._video_is_triggered:
                        print(f"[FACES] Video-Trigger DEAKTIVIERT - should_trigger_video={should_trigger_video}, in_range={in_range}, distance={distance:.1f}cm")
                        self._video_is_triggered = False
                        try:
                            if self.media_player.is_playing:
                                print("[FACES] Stoppe Video-Wiedergabe...")
                                self.media_player.stop()
                                print("[FACES] Video gestoppt")
                            else:
                                print("[FACES] Kein Video am Laufen (is_playing=False)")
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Video-Stop: {e}")
                
                # AUDIO 1-TRIGGER: Unabhängig
                if should_trigger_audio:
                    if not hasattr(self, '_audio_is_triggered') or not self._audio_is_triggered:
                        print("[FACES] Audio 1-Trigger AKTIVIERT")
                        self._audio_is_triggered = True
                        try:
                            self.handle_audio_trigger()
                            self._audio_cooldown_ts = now + max(0.5, float(self.current_min_audio_time))
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Audio-Start: {e}")
                            self._audio_is_triggered = False
                else:
                    if hasattr(self, '_audio_is_triggered') and self._audio_is_triggered:
                        print("[FACES] Audio 1-Trigger DEAKTIVIERT")
                        self._audio_is_triggered = False
                        try:
                            if self.media_player.is_playing:
                                self.media_player.stop()
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Audio-Stop: {e}")
                
                # AUDIO 2-TRIGGER: Unabhängig
                if should_trigger_audio2:
                    if not hasattr(self, '_audio2_is_triggered') or not self._audio2_is_triggered:
                        print("[FACES] Audio 2-Trigger AKTIVIERT")
                        self._audio2_is_triggered = True
                        try:
                            self.handle_audio2_trigger()
                            self._audio2_cooldown_ts = now + max(0.5, float(self.current_min_audio_time))
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Audio2-Start: {e}")
                            self._audio2_is_triggered = False
                else:
                    if hasattr(self, '_audio2_is_triggered') and self._audio2_is_triggered:
                        print("[FACES] Audio 2-Trigger DEAKTIVIERT")
                        self._audio2_is_triggered = False
                        try:
                            if self.media_player.is_playing:
                                self.media_player.stop()
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Audio2-Stop: {e}")
                
                # BILD-TRIGGER: Unabhängig
                if should_show_image:
                    if not hasattr(self, '_image_is_triggered') or not self._image_is_triggered:
                        print("[FACES] Bild-Trigger AKTIVIERT")
                        self._image_is_triggered = True
                        try:
                            self.restore_image_preview()
                            self._image_cooldown_ts = now + 0.5
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Bild-Anzeigen: {e}")
                            self._image_is_triggered = False
                else:
                    if hasattr(self, '_image_is_triggered') and self._image_is_triggered:
                        print("[FACES] Bild-Trigger DEAKTIVIERT")
                        self._image_is_triggered = False
                        # Nur schwarzes Bild zeigen wenn KEIN Video/Audio läuft
                        try:
                            video_laeuft = hasattr(self, '_video_is_triggered') and self._video_is_triggered
                            audio_laeuft = hasattr(self, '_audio_is_triggered') and self._audio_is_triggered
                            audio2_laeuft = hasattr(self, '_audio2_is_triggered') and self._audio2_is_triggered
                            
                            if not (video_laeuft or audio_laeuft or audio2_laeuft):
                                if self.media_player.current_file:
                                    print("[FACES] Kein anderer Trigger aktiv - zeige schwarzes Bild")
                                    self.media_player.show_black()
                            else:
                                print("[FACES] Video/Audio läuft noch - Bild nicht ausblenden")
                        except Exception as e:
                            print(f"[FACES] FEHLER beim Bild-Ausblenden: {e}")
                        
            except ValueError:
                self.media_status_label.config(text="Ungültige Sensor-Werte", fg='red')
        
        # Nächstes Update
        self.root.after(200, self.update_status)
    
    def handle_video_trigger(self):
        """Video-Trigger ausgelöst - Videos starten"""
        try:
            selected_videos = self.get_selected_videos()
            print(f"[FACES] Video-Trigger ausgelöst: {len(selected_videos)} Videos gefunden")
            
            if selected_videos:
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                print(f"[FACES] Starte Video-Wiedergabe: {[os.path.basename(v) for v in selected_videos]}")
                success = self.media_player.play_media_list(selected_videos, shuffle=True)
                if success:
                    self.media_status_label.config(
                        text=f"Video-Trigger → {len(selected_videos)} Videos", fg='lime'
                    )
                    print("[FACES] Video-Wiedergabe erfolgreich gestartet")
                else:
                    self.media_status_label.config(text="Video-Start fehlgeschlagen!", fg='red')
                    print("[FACES] FEHLER: Video-Wiedergabe konnte nicht gestartet werden")
            else:
                print("[FACES] WARNUNG: Keine Videos ausgewählt für Video-Trigger")
                self.media_status_label.config(text="Keine Videos ausgewählt!", fg='orange')
                
        except Exception as e:
            print(f"[FACES] FEHLER in handle_video_trigger: {e}")
            self.media_status_label.config(text=f"Video-Trigger-Fehler: {e}", fg='red')
    
    def handle_audio_trigger(self):
        """Audio-Trigger ausgelöst - Audio + Bilder starten"""
        try:
            selected_audios = self.get_selected_audios()
            selected_images = self.get_selected_images()
            mixed_playlist = selected_audios + selected_images
            
            print(f"[FACES] Audio-Trigger ausgelöst: {len(selected_audios)} Audio + {len(selected_images)} Bilder")
            
            if mixed_playlist:
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                print(f"[FACES] Starte Audio+Bild-Wiedergabe: {[os.path.basename(f) for f in mixed_playlist]}")
                success = self.media_player.play_media_list(mixed_playlist, shuffle=True)
                if success:
                    self.media_status_label.config(
                        text=f"Audio-Trigger → {len(selected_audios)}A + {len(selected_images)}B", fg='lime'
                    )
                    print("[FACES] Audio+Bild-Wiedergabe erfolgreich gestartet")
                else:
                    self.media_status_label.config(text="Audio+Bild-Start fehlgeschlagen!", fg='red')
            else:
                print("[FACES] WARNUNG: Keine Audio/Bild-Dateien ausgewählt für Audio-Trigger")
                self.media_status_label.config(text="Keine Audio/Bild-Dateien ausgewählt!", fg='orange')
                
        except Exception as e:
            print(f"[FACES] FEHLER in handle_audio_trigger: {e}")
            self.media_status_label.config(text=f"Audio-Trigger-Fehler: {e}", fg='red')
    
    def handle_audio2_trigger(self):
        """Audio 2-Trigger ausgelöst - Audio + Bilder starten"""
        try:
            selected_audios = self.get_selected_audios()
            selected_images = self.get_selected_images()
            mixed_playlist = selected_audios + selected_images
            
            print(f"[FACES] Audio2-Trigger ausgelöst: {len(selected_audios)} Audio + {len(selected_images)} Bilder")
            
            if mixed_playlist:
                if self.media_player.is_playing:
                    self.media_player.stop()
                
                print(f"[FACES] Starte Audio2+Bild-Wiedergabe: {[os.path.basename(f) for f in mixed_playlist]}")
                success = self.media_player.play_media_list(mixed_playlist, shuffle=True)
                if success:
                    self.media_status_label.config(
                        text=f"Audio2-Trigger → {len(selected_audios)}A + {len(selected_images)}B", fg='lime'
                    )
                    print("[FACES] Audio2+Bild-Wiedergabe erfolgreich gestartet")
                else:
                    self.media_status_label.config(text="Audio2+Bild-Start fehlgeschlagen!", fg='red')
            else:
                print("[FACES] WARNUNG: Keine Audio/Bild-Dateien ausgewählt für Audio2-Trigger")
                self.media_status_label.config(text="Keine Audio/Bild-Dateien ausgewählt!", fg='orange')
                
        except Exception as e:
            print(f"[FACES] FEHLER in handle_audio2_trigger: {e}")
            self.media_status_label.config(text=f"Audio2-Trigger-Fehler: {e}", fg='red')
    
    # ====== HAUPTMETHODEN ======
    def run(self):
        """GUI starten"""
        try:
            # Window close handler
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except Exception as e:
            print(f"[VLC-GUI] Fehler in run(): {e}")
        finally:
            self.cleanup()
    
    def on_closing(self):
        """Cleanup beim Schließen"""
        self.cleanup()
    
    def cleanup(self):
        """Aufräumen"""
        try:
            print("[VLC-GUI] Cleanup wird durchgeführt...")
            
            if hasattr(self, 'sensor_thread') and self.sensor_thread:
                self.sensor_thread.stop()
                self.sensor_thread = None
            
            if hasattr(self, 'media_player') and self.media_player:
                self.media_player.cleanup()
                self.media_player = None
            
            if hasattr(self, 'root'):
                self.root.quit()
                try:
                    self.root.destroy()
                except:
                    pass  # Bereits zerstört
            
            print("[VLC-GUI] Cleanup abgeschlossen")
            
        except Exception as e:
            print(f"[VLC-GUI] Cleanup-Fehler: {e}")

# Kompatibilitäts-Alias
MediaStationGUI = VLCMediaStationGUI

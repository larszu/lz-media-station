"""
Media-Player mit separatem Vollbild-Fenster für Video/Bild-Anzeige
Unterstützt VLC, externe Player und tkinter Fallback
"""
import os
import threading
import time
import tkinter as tk
from tkinter import Label
import subprocess
import platform
import sys

# VLC-Integration versuchen
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("[MediaPlayer] VLC nicht verfügbar - Verwende tkinter Fallback")

# PIL für Bildanzeige
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[MediaPlayer] PIL nicht verfügbar - Bildanzeige limitiert")

# pygame für Audio
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[MediaPlayer] pygame nicht verfügbar - Audio-Funktionen limitiert")

class MediaPlayer:
    def __init__(self):
        global VLC_AVAILABLE
        
        self.current_mode = "black"  # "black", "video", "image"
        self.current_file = None
        self.vlc_instance = None
        self.vlc_player = None
        self.is_playing = False
        
        # Separates Media-Fenster
        self.media_window = None
        self.media_label = None
        self.video_process = None
        self.video_start_time = 0
        self.video_duration = 0
        
        # Audio-System
        self.current_audio = None
        self.audio_thread = None
        self.audio_playing = False
        self.audio_fade_time = 2.0  # Standard Fade-Zeit
        self.selected_audio_files = []
        self.current_audio_index = 0
        self.audio_stop_event = threading.Event()
        self.audio_start_time = 0  # Start-Zeit für Mindestlaufzeit
        
        # Mindestlaufzeiten für Stabilität
        self.image_start_time = 0
        self.video_forced_start_time = 0  # Für Mindest-Video-Laufzeit
        
        # Immer tkinter-Fenster erstellen
        print("[MediaPlayer] Initialisiere separates Media-Fenster...")
        self._init_fallback_window()
        
        # VLC-Instanz für echte Implementierung (optional)
        if VLC_AVAILABLE:
            try:
                self.vlc_instance = vlc.Instance(
                    '--no-video-title-show',
                    '--no-osd',
                    '--quiet'
                )
                self.vlc_player = self.vlc_instance.media_player_new()
                print("[MediaPlayer] VLC erfolgreich initialisiert (als zusätzliche Option)")
            except Exception as e:
                print(f"[MediaPlayer] VLC-Initialisierung fehlgeschlagen: {e}")
                VLC_AVAILABLE = False
        
        print(f"[MediaPlayer] Bereit - VLC verfügbar: {VLC_AVAILABLE}")
        
    def _init_fallback_window(self):
        """Initialisiert separates tkinter-Fenster für Medien"""
        try:
            self.media_window = tk.Toplevel()
            self.media_window.title("Pi Media Station - Anzeige")
            self.media_window.configure(bg='black')
            
            # Fenster konfigurieren - plattformabhängig
            self.media_window.geometry("800x600")  # Startgröße
            
            # Plattformspezifische Vollbild-Logik
            if platform.system() == "Windows":
                self.media_window.state('zoomed')  # Windows: Maximiert
            else:
                # Linux/Raspberry Pi: Andere Ansätze
                try:
                    self.media_window.attributes('-zoomed', True)  # Linux-Variante
                except:
                    try:
                        self.media_window.state('zoomed')  # Falls unterstützt
                    except:
                        # Fallback: Vollbild über Geometrie
                        self.media_window.geometry(f"{self.media_window.winfo_screenwidth()}x{self.media_window.winfo_screenheight()}+0+0")
            
            # Label für Bilder/Text
            self.media_label = Label(
                self.media_window, 
                bg='black', 
                fg='white',
                text="Pi Media Station\n\nBereit für Medien-Anzeige\n\nF11 = Vollbild\nESC = Fenster",
                font=('Arial', 20),
                justify='center'
            )
            self.media_label.pack(fill=tk.BOTH, expand=True)
            
            # Tastenkombinationen
            self.media_window.bind('<Escape>', self._handle_escape)
            self.media_window.bind('<F11>', self._toggle_fullscreen)
            self.media_window.bind('<Alt-F4>', lambda e: self._emergency_quit())
            self.media_window.bind('<Control-c>', lambda e: self._emergency_quit())
            self.media_window.bind('<Control-q>', lambda e: self._emergency_quit())
            
            # Fenster in den Vordergrund
            self.media_window.lift()
            self.media_window.focus_force()
            
            print("[MediaPlayer] Separates Media-Fenster erstellt")
            
        except Exception as e:
            print(f"[MediaPlayer] Fehler beim Erstellen des Media-Fensters: {e}")
            self.media_window = None
            self.media_label = None
        
    def _handle_escape(self, event=None):
        """Intelligente ESC-Behandlung: Vollbild-Toggle oder Notfall-Beenden"""
        try:
            # Prüfen ob wir im Vollbild sind
            if self.media_window:
                try:
                    is_fullscreen = self.media_window.attributes('-fullscreen')
                    if is_fullscreen:
                        # Aus Vollbild heraus
                        self._toggle_fullscreen()
                        print("[MediaPlayer] ESC: Vollbild deaktiviert")
                    else:
                        # Nicht im Vollbild - Notfall-Beenden
                        print("[MediaPlayer] ESC: Notfall-Beenden aktiviert")
                        self._emergency_quit()
                except:
                    # Fallback bei Fehlern
                    self._emergency_quit()
        except Exception as e:
            print(f"[MediaPlayer] ESC-Handler Fehler: {e}")
            self._emergency_quit()
    
    def _emergency_quit(self):
        """Notfall-Beenden der Anwendung"""
        print("[MediaPlayer] NOTFALL-BEENDEN: Stoppe alle Medien und beende Anwendung")
        try:
            # Alle Medien sofort stoppen
            self.stop_audio()
            self._stop_video()
            
            # VLC stoppen
            if VLC_AVAILABLE and self.vlc_player:
                try:
                    self.vlc_player.stop()
                except:
                    pass
            
            # Media-Fenster schließen
            if self.media_window:
                try:
                    self.media_window.quit()
                    self.media_window.destroy()
                except:
                    pass
            
            # Hauptanwendung beenden (über tkinter root)
            import tkinter
            for widget in tkinter._default_root.winfo_children():
                if hasattr(widget, 'quit'):
                    widget.quit()
            
            # Als letzter Ausweg: Prozess beenden
            import sys
            import os
            print("[MediaPlayer] Erzwinge Prozess-Beendigung...")
            os._exit(0)
            
        except Exception as e:
            print(f"[MediaPlayer] Notfall-Beenden Fehler: {e}")
            # Harte Beendigung als allerletzte Option
            import os
            os._exit(1)
    
    def _toggle_fullscreen(self, event=None):
        """Vollbild ein/aus für tkinter Fallback - plattformkompatibel"""
        if self.media_window:
            try:
                current = self.media_window.attributes('-fullscreen')
                self.media_window.attributes('-fullscreen', not current)
                if not current:
                    print("[MediaPlayer] Vollbild aktiviert")
                else:
                    print("[MediaPlayer] Vollbild deaktiviert")
            except Exception as e:
                print(f"[MediaPlayer] Vollbild-Toggle Fehler: {e}")
                # Plattformspezifische Fallbacks
                try:
                    if platform.system() == "Windows":
                        # Windows-spezifischer Fallback
                        if self.media_window.state() == 'zoomed':
                            self.media_window.state('normal')
                            self.media_window.geometry("800x600")
                        else:
                            self.media_window.state('zoomed')
                    else:
                        # Linux/Pi Fallback: Geometrie-basiert
                        current_geometry = self.media_window.geometry()
                        if "800x600" in current_geometry:
                            # Zu Vollbild wechseln
                            screen_w = self.media_window.winfo_screenwidth()
                            screen_h = self.media_window.winfo_screenheight()
                            self.media_window.geometry(f"{screen_w}x{screen_h}+0+0")
                        else:
                            # Zu Fenster wechseln
                            self.media_window.geometry("800x600+100+100")
                except Exception as fallback_error:
                    print(f"[MediaPlayer] Fallback-Toggle Fehler: {fallback_error}")
                    pass
            
    def is_video_finished(self):
        """Prüft ob das aktuelle Video beendet ist"""
        if self.current_mode != "video":
            return False
        
        # VLC-Prüfung
        if VLC_AVAILABLE and self.vlc_player:
            try:
                state = self.vlc_player.get_state()
                # Video ist beendet wenn es gestoppt oder am Ende ist
                if state in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
                    return True
            except:
                pass
        
        # Externe Player-Prüfung
        if self.video_process:
            # Prüfen ob Prozess noch läuft
            if self.video_process.poll() is not None:
                return True  # Prozess beendet
        
        # Fallback: Zeit-basierte Schätzung (sehr grob)
        if self.video_start_time > 0:
            elapsed = time.time() - self.video_start_time
            # Annahme: Video ist nach 5 Minuten "wahrscheinlich" beendet
            if elapsed > 300:  # 5 Minuten
                return True
        
        return False
            
    def play_video(self, path):
        """Video im Vollbild abspielen - nur ein System aktiv"""
        if not os.path.exists(path):
            print(f"[MediaPlayer] Video nicht gefunden: {path}")
            self.show_black()
            return
            
        if self.current_mode == "video" and self.current_file == path:
            return  # Bereits das richtige Video am Laufen
            
        self.current_mode = "video"
        self.current_file = path
        self.video_start_time = time.time()  # Startzeit speichern
        self.video_forced_start_time = time.time()  # Mindestlaufzeit-Timer
        
        print(f"[MediaPlayer] Starte Video: {os.path.basename(path)}")
        
        # Priorität: VLC eingebettet > Externes VLC > tkinter Fallback
        # Aber NUR EIN System verwenden!
        if VLC_AVAILABLE and self.vlc_player:
            # Versuche VLC eingebettet
            if self._vlc_play_video(path):
                return  # Erfolgreich mit VLC eingebettet
        
        # Fallback: Externes VLC (aber tkinter-Fenster ausblenden)
        if self._fallback_video(path):
            # Externes Video läuft - tkinter-Fenster minimieren
            if self.media_window:
                try:
                    self.media_window.withdraw()  # Fenster ausblenden
                except:
                    pass
            return
        
        # Letzter Fallback: tkinter mit Fehlermeldung
        if self.media_window and self.media_label:
            try:
                self.media_window.deiconify()  # Fenster wieder einblenden
            except:
                pass
            self.media_label.config(
                text=f"🎬 VIDEO\n\n{os.path.basename(path)}\n\n(Kein Video-Player verfügbar)\n\nBitte VLC installieren",
                font=('Arial', 16),
                fg='yellow'
            )
    
    def _vlc_play_video(self, path):
        """VLC Video-Wiedergabe - plattformkompatibel"""
        try:
            media = self.vlc_instance.media_new(path)
            # Kein Loop - Video soll normal enden
            self.vlc_player.set_media(media)
            
            # VLC in separatem Fenster einbetten (plattformspezifisch)
            if self.media_window:
                try:
                    if platform.system() == "Windows":
                        # Windows Handle für VLC
                        hwnd = self.media_window.winfo_id()
                        self.vlc_player.set_hwnd(hwnd)
                    else:
                        # Linux/X11 Handle für VLC
                        xid = self.media_window.winfo_id()
                        self.vlc_player.set_xwindow(xid)
                except Exception as embed_error:
                    print(f"[MediaPlayer] VLC-Einbettung Fehler: {embed_error}")
                    # VLC läuft in eigenem Fenster falls Einbettung fehlschlägt
                    pass
            
            self.vlc_player.play()
            self.is_playing = True
            print(f"[MediaPlayer] VLC spielt Video: {os.path.basename(path)}")
            
            # Status im tkinter-Fenster anzeigen
            if self.media_window and self.media_label:
                self.media_label.config(
                    text=f"🎬 VLC VIDEO\n\n{os.path.basename(path)}\n\nWird wiedergegeben...",
                    font=('Arial', 18),
                    fg='lime'
                )
            
        except Exception as e:
            print(f"[MediaPlayer] VLC Video-Fehler: {e}")
            return False
        return True
    
    def _fallback_video(self, path):
        """Fallback Video-Wiedergabe mit externem Player - plattformkompatibel"""
        # Aktuellen Video-Prozess stoppen
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process.wait(timeout=2)
            except:
                pass
        
        try:
            # Plattformspezifische Player-Liste
            if platform.system() == "Windows":
                players = ['vlc', 'mpv', 'mplayer', 'wmplayer']
            else:
                # Linux/Raspberry Pi - kein wmplayer
                players = ['vlc', 'mpv', 'mplayer', 'omxplayer']  # omxplayer für Raspberry Pi
            
            for player in players:
                try:
                    if player == 'vlc':
                        self.video_process = subprocess.Popen([
                            player, path, 
                            '--fullscreen', 
                            '--no-video-title-show',
                            '--quiet',
                            '--intf', 'dummy',  # Verhindert VLC-GUI
                            '--no-embedded-video'  # Kein eingebettetes Video
                        ])
                    elif player == 'mpv':
                        self.video_process = subprocess.Popen([
                            player, path,
                            '--fullscreen'
                        ])
                    elif player == 'omxplayer':
                        # Raspberry Pi Hardware-Player
                        self.video_process = subprocess.Popen([
                            player, path,
                            '--win', '0,0,1920,1080',  # Vollbild
                            '--no-osd'
                        ])
                    elif player == 'wmplayer':
                        # Windows Media Player (nur Windows)
                        self.video_process = subprocess.Popen([
                            player, path,
                            '/fullscreen'
                        ])
                    else:  # mplayer
                        self.video_process = subprocess.Popen([
                            player, path,
                            '-fs'  # Vollbild
                        ])
                    
                    print(f"[MediaPlayer] {player} spielt Video: {os.path.basename(path)}")
                    
                    # Status im tkinter-Fenster anzeigen
                    if self.media_window and self.media_label:
                        self.media_label.config(
                            text=f"🎬 EXTERNAL VIDEO\n\n{os.path.basename(path)}\n\nPlayer: {player.upper()}",
                            font=('Arial', 18),
                            fg='cyan'
                        )
                    return True
                    
                except FileNotFoundError:
                    continue
            
            # Kein externer Player gefunden
            print("[MediaPlayer] Kein Video-Player gefunden")
            return False
                    
        except Exception as e:
            print(f"[MediaPlayer] Fallback Video-Fehler: {e}")
            return False

    def show_image(self, path):
        """Bild anzeigen - nur ein System aktiv"""
        if not os.path.exists(path):
            print(f"[MediaPlayer] Bild nicht gefunden: {path}")
            self.show_black()
            return
            
        if self.current_mode == "image" and self.current_file == path:
            return  # Bereits das richtige Bild angezeigt
            
        self.current_mode = "image"
        self.current_file = path
        self.image_start_time = time.time()  # Mindestlaufzeit-Timer
        
        # Video stoppen falls läuft
        self._stop_video()
        
        # tkinter-Fenster wieder einblenden für Bilder
        if self.media_window:
            try:
                self.media_window.deiconify()
            except:
                pass
        
        if VLC_AVAILABLE and self.vlc_player:
            # VLC für Bild-Anzeige
            try:
                media = self.vlc_instance.media_new(path)
                self.vlc_player.set_media(media)
                self.vlc_player.set_fullscreen(True)
                self.vlc_player.play()
                print(f"[MediaPlayer] VLC zeigt Bild: {os.path.basename(path)}")
                return  # VLC erfolgreich
            except Exception as e:
                print(f"[MediaPlayer] VLC Bild-Fehler: {e}")
        
        # Fallback: tkinter für Bilder
        self._fallback_image(path)
    
    def _fallback_image(self, path):
        """Fallback Bild-Anzeige mit tkinter"""
        if not self.media_window or not self.media_label:
            return
            
        try:
            if PIL_AVAILABLE:
                # Bild laden und skalieren mit PIL
                image = Image.open(path)
                
                # Bildschirmgröße ermitteln
                screen_width = self.media_window.winfo_screenwidth()
                screen_height = self.media_window.winfo_screenheight()
                
                # Bild proportional skalieren
                image.thumbnail((screen_width, screen_height), Image.Resampling.LANCZOS)
                
                # Zu tkinter PhotoImage konvertieren
                photo = ImageTk.PhotoImage(image)
                
                # Bild anzeigen
                self.media_label.config(image=photo, text="")
                self.media_label.image = photo  # Referenz behalten
                
                print(f"[MediaPlayer] tkinter zeigt Bild: {os.path.basename(path)}")
            else:
                # Ohne PIL nur Dateinamen anzeigen
                self.media_label.config(
                    image="",
                    text=f"BILD: {os.path.basename(path)}\n\n(PIL nicht verfügbar)",
                    font=('Arial', 20)
                )
            
        except Exception as e:
            print(f"[MediaPlayer] Fallback Bild-Fehler: {e}")
            self.media_label.config(
                image="",
                text=f"BILD: {os.path.basename(path)}\n\n(Anzeige-Fehler)",
                font=('Arial', 20)
            )

    def show_black(self):
        """Schwarzes Bild anzeigen"""
        if self.current_mode == "black":
            return
            
        self.current_mode = "black"
        self.current_file = None
        
        print("[MediaPlayer] Zeige schwarzes Bild")
        
        # Video stoppen
        self._stop_video()
        
        # tkinter-Fenster wieder einblenden
        if self.media_window:
            try:
                self.media_window.deiconify()
            except:
                pass
        
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
            except:
                pass
        
        # tkinter: Schwarzes Bild mit Status
        if self.media_window and self.media_label:
            self.media_label.config(
                image="",
                text="⚫ STANDBY\n\nKein Objekt erkannt\n\nWarte auf Sensor-Signal...", 
                fg='gray',
                font=('Arial', 20),
                justify='center'
            )
            self.media_label.image = None

    def _stop_video(self):
        """Video-Wiedergabe stoppen"""
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process.wait(timeout=2)
            except:
                try:
                    self.video_process.kill()
                except:
                    pass
            finally:
                self.video_process = None
        
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
            except:
                pass
        
        self.is_playing = False

    def cleanup(self):
        """Ressourcen freigeben"""
        print("[MediaPlayer] Cleanup...")
        
        # Audio stoppen
        self.stop_audio()
        
        # Video stoppen
        self._stop_video()
        
        # VLC cleanup
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
                self.vlc_player.release()
            except:
                pass
        
        if VLC_AVAILABLE and self.vlc_instance:
            try:
                self.vlc_instance.release()
            except:
                pass
        
        # pygame cleanup
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.quit()
            except:
                pass
        
        # tkinter Fenster schließen
        if self.media_window:
            try:
                self.media_window.destroy()
            except:
                pass
    
    def set_audio_fade_time(self, fade_time):
        """Setzt die Fade-Zeit für Audio-Übergänge"""
        self.audio_fade_time = max(0.1, float(fade_time))
        print(f"[MediaPlayer] Audio Fade-Zeit: {self.audio_fade_time}s")
    
    def start_audio_playlist(self, audio_files):
        """Startet Audio-Playlist im Hintergrund"""
        if not audio_files:
            self.stop_audio()
            return
        
        # Aktuelle Audio stoppen
        self.stop_audio()
        
        self.selected_audio_files = audio_files.copy()
        self.current_audio_index = 0
        self.audio_stop_event.clear()
        
        # Audio-Thread starten
        self.audio_thread = threading.Thread(
            target=self._audio_playlist_worker, 
            daemon=True
        )
        self.audio_thread.start()
        print(f"[MediaPlayer] Audio-Playlist gestartet: {len(audio_files)} Dateien")
    
    def _audio_playlist_worker(self):
        """Audio-Playlist Worker Thread"""
        while not self.audio_stop_event.is_set() and self.selected_audio_files:
            try:
                # Aktuelle Audio-Datei
                current_file = self.selected_audio_files[self.current_audio_index]
                
                if not os.path.exists(current_file):
                    print(f"[MediaPlayer] Audio-Datei nicht gefunden: {current_file}")
                    self._next_audio()
                    continue
                
                print(f"[MediaPlayer] Spiele Audio: {os.path.basename(current_file)}")
                self.current_audio = current_file
                self.audio_playing = True
                self.audio_start_time = time.time()  # Mindestlaufzeit-Timer
                
                # Audio mit pygame abspielen
                if PYGAME_AVAILABLE:
                    self._play_audio_pygame(current_file)
                else:
                    # Fallback mit externem Player
                    self._play_audio_external(current_file)
                
                # Zum nächsten Track
                if not self.audio_stop_event.is_set():
                    self._next_audio()
                    
            except Exception as e:
                print(f"[MediaPlayer] Audio-Playlist Fehler: {e}")
                time.sleep(1)
        
        self.audio_playing = False
        print("[MediaPlayer] Audio-Playlist beendet")
    
    def _play_audio_pygame(self, file_path):
        """Audio mit pygame abspielen"""
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Warten bis Audio beendet
            while pygame.mixer.music.get_busy() and not self.audio_stop_event.is_set():
                time.sleep(0.1)
            
            # Fade-out wenn gestoppt
            if not self.audio_stop_event.is_set():
                # Fade zwischen Tracks
                fade_ms = int(self.audio_fade_time * 1000)
                pygame.mixer.music.fadeout(fade_ms)
                time.sleep(self.audio_fade_time)
            
        except Exception as e:
            print(f"[MediaPlayer] pygame Audio-Fehler: {e}")
            # Fallback: kurz warten
            time.sleep(2)
    
    def _play_audio_external(self, file_path):
        """Audio mit externem Player abspielen - plattformkompatibel"""
        try:
            # Plattformspezifische Audio-Player
            if platform.system() == "Windows":
                players = ['vlc', 'mpv', 'wmplayer']
            else:
                # Linux/Raspberry Pi
                players = ['vlc', 'mpv', 'aplay', 'paplay']  # aplay/paplay für Pi
            
            for player in players:
                try:
                    if player == 'vlc':
                        process = subprocess.Popen([
                            player, file_path,
                            '--intf', 'dummy',
                            '--play-and-exit',
                            '--quiet'
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif player == 'mpv':
                        process = subprocess.Popen([
                            player, file_path,
                            '--no-video'
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif player == 'aplay':
                        # ALSA player für Linux/Pi (nur WAV)
                        if file_path.lower().endswith('.wav'):
                            process = subprocess.Popen([
                                player, file_path
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            continue  # Überspringen für nicht-WAV
                    elif player == 'paplay':
                        # PulseAudio player für Linux/Pi
                        process = subprocess.Popen([
                            player, file_path
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:  # wmplayer (Windows)
                        process = subprocess.Popen([
                            player, file_path
                        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Warten bis Prozess beendet
                    while process.poll() is None and not self.audio_stop_event.is_set():
                        time.sleep(0.1)
                    
                    if not self.audio_stop_event.is_set():
                        # Kurze Pause zwischen Tracks
                        time.sleep(self.audio_fade_time)
                    
                    if process.poll() is None:
                        process.terminate()
                    
                    return  # Erfolgreich abgespielt
                    
                except FileNotFoundError:
                    continue
            
            # Kein Player gefunden
            print("[MediaPlayer] Kein Audio-Player gefunden")
            time.sleep(2)  # Kurze Pause
            
        except Exception as e:
            print(f"[MediaPlayer] Externer Audio-Player Fehler: {e}")
            time.sleep(2)
    
    def _next_audio(self):
        """Zum nächsten Audio-Track wechseln"""
        if self.selected_audio_files:
            self.current_audio_index = (self.current_audio_index + 1) % len(self.selected_audio_files)
    
    def stop_audio(self):
        """Audio-Wiedergabe stoppen"""
        print("[MediaPlayer] Stoppe Audio")
        
        # Stop-Event setzen
        self.audio_stop_event.set()
        
        # pygame stoppen
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.stop()
            except:
                pass
        
        # Thread beenden
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        
        self.audio_playing = False
        self.current_audio = None
        self.audio_thread = None
    
    def get_current_audio_info(self):
        """Gibt Informationen über aktuell laufende Audio zurück"""
        if self.audio_playing and self.current_audio:
            total_files = len(self.selected_audio_files)
            current_index = self.current_audio_index + 1
            filename = os.path.basename(self.current_audio)
            return f"{filename} ({current_index}/{total_files})"
        return None
    
    def can_switch_from_video(self, min_runtime=3.0):
        """Prüft ob genug Zeit vergangen ist um vom Video zu wechseln"""
        if self.current_mode != "video":
            return True
        
        if self.video_forced_start_time == 0:
            return True  # Kein erzwungener Start
        
        elapsed = time.time() - self.video_forced_start_time
        return elapsed >= min_runtime
    
    def can_switch_from_image(self, min_runtime=2.0):
        """Prüft ob genug Zeit vergangen ist um vom Bild zu wechseln"""
        if self.current_mode != "image":
            return True
        
        if self.image_start_time == 0:
            return True  # Kein Start-Zeit gesetzt
        
        elapsed = time.time() - self.image_start_time
        return elapsed >= min_runtime
    
    def can_switch_audio(self, min_runtime=5.0):
        """Prüft ob Audio-Track genug Zeit hatte zum Abspielen"""
        if not self.audio_playing:
            return True
        
        if self.audio_start_time == 0:
            return True  # Kein Start-Zeit gesetzt
        
        elapsed = time.time() - self.audio_start_time
        return elapsed >= min_runtime

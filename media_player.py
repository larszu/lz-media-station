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
import random

# Konfiguration (für Standardzeiten)
try:
    from config import IMAGE_DISPLAY_TIME, MIN_IMAGE_DISPLAY_TIME
except Exception:
    # Fallback-Defaults, falls config nicht verfügbar ist
    IMAGE_DISPLAY_TIME = 5
    MIN_IMAGE_DISPLAY_TIME = 2

# VLC-Integration versuchen
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("[MediaPlayer] VLC nicht verfügbar - Verwende tkinter Fallback")

# PIL für Bildanzeige (Image optional, ImageTk optional)
PIL_AVAILABLE = False
IMAGETK_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
    try:
        from PIL import ImageTk
        IMAGETK_AVAILABLE = True
    except Exception:
        IMAGETK_AVAILABLE = False
        print("[MediaPlayer] PIL installiert, aber ImageTk fehlt - Bildanzeige limitiert")
except ImportError:
    PIL_AVAILABLE = False
    IMAGETK_AVAILABLE = False
    print("[MediaPlayer] PIL nicht verfügbar - Bildanzeige limitiert")

# pygame für Audio (Mixer bei Bedarf initialisieren)
try:
    import pygame
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

        # Playlist-/Slideshow-Status
        self.current_playlist = []
        self.playlist_index = 0
        self.playlist_shuffle = False
        self.is_paused = False
        self.slideshow_thread = None
        self.slideshow_stop_event = threading.Event()
        
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
    
    def _init_vlc(self):
        """Initialisiert oder re-initialisiert VLC"""
        global VLC_AVAILABLE
        if not VLC_AVAILABLE:
            return False
            
        try:
            self.vlc_instance = vlc.Instance(
                '--no-video-title-show',
                '--no-osd',
                '--quiet',
                '--no-xlib'  # Verhindert X11-Threading-Probleme
            )
            self.vlc_player = self.vlc_instance.media_player_new()
            print("[MediaPlayer] VLC (re-)initialisiert")
            return True
        except Exception as e:
            print(f"[MediaPlayer] VLC-Initialisierung fehlgeschlagen: {e}")
            VLC_AVAILABLE = False
            return False
        
    def _init_fallback_window(self):
        """Initialisiert separates tkinter-Fenster für Medien"""
        try:
            self.media_window = tk.Toplevel()
            self.media_window.title("Pi Media Station - Anzeige")
            self.media_window.configure(bg='black')
            
            # Fenster initial verstecken (wird nur bei Fallback-Anzeige gebraucht)
            self.media_window.withdraw()
            
            # Fenster konfigurieren
            self.media_window.geometry("800x600")  # Startgröße
            # Maximieren plattformabhängig, aber nie Fehler werfen
            try:
                # Auf Windows meist verfügbar
                self.media_window.state('zoomed')
            except Exception:
                try:
                    # Manche Window-Manager unterstützen dies
                    self.media_window.attributes('-zoomed', True)
                except Exception:
                    # Als Fallback einfach normal anzeigen
                    pass
            
            # Label für Bilder/Text
            self.media_label = Label(
                self.media_window, 
                bg='black', 
                fg='white',
                text="",  # Kein Text - nur schwarzes Fenster
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
            if self.media_window and str(self.media_window) != '':
                try:
                    self.media_window.lift()
                    self.media_window.focus_force()
                except Exception:
                    pass
            
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
        """Vollbild ein/aus für tkinter Fallback"""
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
                # Fallback für Windows
                try:
                    if self.media_window.state() == 'zoomed':
                        self.media_window.state('normal')
                        self.media_window.geometry("800x600")
                    else:
                        self.media_window.state('zoomed')
                except:
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
        """Video im Loop und Vollbild abspielen"""
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
        
        # PRIORITÄT 1: Externer VLC-Prozess (stabiler auf Raspberry Pi!)
        if self._fallback_video(path):
            self.is_playing = True
            return
            
        # PRIORITÄT 2: Python-VLC (nur wenn externer VLC fehlschlägt)
        if VLC_AVAILABLE and self.vlc_player:
            if self._vlc_play_video(path):
                self.is_playing = True
                return
        
        # PRIORITÄT 3: tkinter Fallback
        if self.media_window and self.media_label:
            self.media_label.config(
                text=f"🎬 VIDEO\n\n{os.path.basename(path)}\n\n(Kein Video-Player verfügbar)\n\nExterner Player erforderlich",
                font=('Arial', 16),
                fg='yellow'
            )
    
    def _vlc_play_video(self, path):
        """VLC Video-Wiedergabe mit Crash-Recovery"""
        try:
            # Fenster verstecken - VLC öffnet eigenes Fenster
            if self.media_window:
                self.media_window.withdraw()
            
            # Prüfe ob VLC Player noch funktioniert
            if not self.vlc_player or not self.vlc_instance:
                print("[MediaPlayer] VLC nicht verfügbar - reinitalisiere...")
                if not self._init_vlc():
                    print("[MediaPlayer] VLC Reinitalisierung fehlgeschlagen")
                    return False
            
            # Setze Timeouts um Hänger zu vermeiden
            try:
                media = self.vlc_instance.media_new(path)
                if not media:
                    print(f"[MediaPlayer] Konnte VLC Media nicht erstellen für: {path}")
                    return False
                    
                # Kein Loop - Video soll normal enden
                self.vlc_player.set_media(media)
                
                # VLC in separatem Fenster einbetten (falls möglich)
                if self.media_window:
                    try:
                        # Windows Handle für VLC
                        hwnd = self.media_window.winfo_id()
                        self.vlc_player.set_hwnd(hwnd)
                    except:
                        pass
                
                # Versuche Video zu starten
                ret = self.vlc_player.play()
                if ret == -1:
                    print(f"[MediaPlayer] VLC play() fehlgeschlagen für: {path}")
                    # Versuche VLC neu zu initialisieren
                    self._recover_vlc()
                    return False
                    
                self.is_playing = True
                print(f"[MediaPlayer] VLC spielt Video: {os.path.basename(path)}")
                
                # Status im tkinter-Fenster anzeigen
                if self.media_window and self.media_label and str(self.media_label) != '':
                    self.media_label.config(
                        text=f"🎬 VLC VIDEO\n\n{os.path.basename(path)}\n\nWird wiedergegeben...",
                        font=('Arial', 18),
                        fg='lime'
                    )
                    
            except Exception as e:
                print(f"[MediaPlayer] Fehler beim VLC-Start: {e}")
                self._recover_vlc()
                return False
            
        except Exception as e:
            print(f"[MediaPlayer] VLC Video-Fehler: {e}")
            self._recover_vlc()
            return False
        return True
    
    def _recover_vlc(self):
        """Versuche VLC nach Crash wiederherzustellen"""
        print("[MediaPlayer] Versuche VLC-Recovery...")
        try:
            if self.vlc_player:
                try:
                    self.vlc_player.stop()
                except:
                    pass
                try:
                    self.vlc_player.release()
                except:
                    pass
            self.vlc_player = None
            self.vlc_instance = None
            
            # Warte kurz
            time.sleep(0.5)
            
            # Neu initialisieren
            if self._init_vlc():
                print("[MediaPlayer] VLC erfolgreich wiederhergestellt")
            else:
                print("[MediaPlayer] VLC Recovery fehlgeschlagen")
        except Exception as e:
            print(f"[MediaPlayer] Fehler bei VLC-Recovery: {e}")
    
    def _fallback_video(self, path):
        """Fallback Video-Wiedergabe mit externem Player (HAUPTMETHODE für Raspberry Pi!)"""
        # Aktuellen Video-Prozess stoppen
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process.wait(timeout=2)
            except:
                try:
                    self.video_process.kill()
                except:
                    pass
        
        try:
            # Versuche verschiedene Video-Player
            # Priorität: VLC (extern) > mpv > mplayer
            players_config = [
                ('cvlc', [  # Command-line VLC (stabiler auf Pi!)
                    path, 
                    '--fullscreen', 
                    '--no-video-title-show',
                    '--no-osd',
                    '--quiet',
                    '--play-and-exit'  # Schließt nach Ende
                ]),
                ('vlc', [  # GUI VLC als Fallback
                    path, 
                    '--fullscreen', 
                    '--no-video-title-show',
                    '--no-osd',
                    '--quiet',
                    '--play-and-exit'
                ]),
                ('mpv', [path, '--fullscreen']),
                ('mplayer', [path, '-fs']),
                ('wmplayer', [path, '/fullscreen'])  # Windows
            ]
            
            for player, args in players_config:
                try:
                    self.video_process = subprocess.Popen(
                        [player] + args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
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
                except Exception as e:
                    print(f"[MediaPlayer] {player} Fehler: {e}")
                    continue
            
            # Kein externer Player gefunden
            print("[MediaPlayer] Kein Video-Player gefunden")
            return False
                    
        except Exception as e:
            print(f"[MediaPlayer] Fallback Video-Fehler: {e}")
            return False

    def show_image(self, path):
        """Bild anzeigen"""
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
        
        if VLC_AVAILABLE and self.vlc_player:
            # VLC für Bild-Anzeige
            try:
                # Fenster verstecken - VLC öffnet eigenes Fenster
                if self.media_window:
                    self.media_window.withdraw()
                
                media = self.vlc_instance.media_new(path)
                self.vlc_player.set_media(media)
                self.vlc_player.set_fullscreen(True)
                self.vlc_player.play()
                print(f"[MediaPlayer] VLC zeigt Bild: {os.path.basename(path)}")
            except Exception as e:
                print(f"[MediaPlayer] VLC Bild-Fehler: {e}")
                self._fallback_image(path)
        else:
            # tkinter Fallback für Bilder
            self._fallback_image(path)
    
    def _fallback_image(self, path):
        """Fallback Bild-Anzeige mit tkinter"""
        if not self.media_window or not self.media_label or str(self.media_label) == '':
            return
        
        # Fenster sichtbar machen für Fallback-Anzeige
        self.media_window.deiconify()
        self.media_window.lift()
            
        try:
            if PIL_AVAILABLE and IMAGETK_AVAILABLE:
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
                if self.media_label and str(self.media_label) != '':
                    self.media_label.config(image=photo, text="")
                    self.media_label.image = photo  # Referenz behalten
                
                print(f"[MediaPlayer] tkinter zeigt Bild: {os.path.basename(path)}")
            else:
                # Ohne PIL nur Dateinamen anzeigen
                msg = "ImageTk fehlt" if PIL_AVAILABLE and not IMAGETK_AVAILABLE else "PIL nicht verfügbar"
                if self.media_label and str(self.media_label) != '':
                    self.media_label.config(
                        image="",
                        text=f"BILD: {os.path.basename(path)}\n\n({msg})",
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
        
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
            except:
                pass
        
        # tkinter: Schwarzes Bild mit Status
        if self.media_window and self.media_label:
            if str(self.media_label) != '':
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
        print("[MediaPlayer] _stop_video() aufgerufen")
        
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
                print("[MediaPlayer] Stoppe VLC Player...")
                self.vlc_player.stop()
                print("[MediaPlayer] VLC Player gestoppt")
            except Exception as e:
                print(f"[MediaPlayer] Fehler beim VLC-Stop: {e}")
        
        self.is_playing = False
        self.current_mode = None
        self.current_file = None
        print("[MediaPlayer] Video-Stop abgeschlossen, is_playing=False")

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
                if hasattr(pygame, 'mixer') and pygame.mixer.get_init():
                    pygame.mixer.quit()
            except:
                pass
        
        # tkinter Fenster schließen
        if self.media_window:
            try:
                self.media_window.destroy()
            except:
                pass

    # ===== Playlist / Steuerung API (für gui_vlc.py) =====
    def _classify_media(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in {'.mp4', '.mov', '.avi', '.mkv', '.webm'}:
            return 'video'
        if ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}:
            return 'image'
        if ext in {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}:
            return 'audio'
        return 'unknown'

    def _stop_slideshow(self):
        if self.slideshow_thread and self.slideshow_thread.is_alive():
            self.slideshow_stop_event.set()
            try:
                self.slideshow_thread.join(timeout=2)
            except:
                pass
        self.slideshow_thread = None
        self.slideshow_stop_event.clear()

    def _start_slideshow(self, images, interval_s=None):
        if not images:
            return False
        self._stop_slideshow()
        self.current_playlist = images
        self.playlist_index = 0
        self.is_playing = True
        display_time = max(MIN_IMAGE_DISPLAY_TIME, (interval_s or IMAGE_DISPLAY_TIME))

        def _worker():
            print(f"[MediaPlayer] Slideshow gestartet ({len(images)} Bilder)")
            while not self.slideshow_stop_event.is_set() and self.current_playlist:
                path = self.current_playlist[self.playlist_index % len(self.current_playlist)]
                self.show_image(path)
                # Wartezeit in kleinen Schritten, damit Stop schnell reagiert
                waited = 0.0
                step = 0.1
                while waited < display_time and not self.slideshow_stop_event.is_set():
                    time.sleep(step)
                    waited += step
                self.playlist_index = (self.playlist_index + 1) % len(self.current_playlist)
            print("[MediaPlayer] Slideshow beendet")
            self.is_playing = False

        self.slideshow_thread = threading.Thread(target=_worker, daemon=True)
        self.slideshow_thread.start()
        return True

    def play_media_list(self, files, shuffle=False):
        """Startet die Wiedergabe einer Medienliste.
        - Nur Videos: spielt das erste/nächste Video (kein Auto-Advance via VLC hier)
        - Nur Bilder: startet Slideshow
        - Audio + Bilder: startet Audio-Playlist und Slideshow
        - Nur Audio: startet Audio-Playlist
        """
        try:
            files = [f for f in files if os.path.exists(f)]
            if not files:
                print("[MediaPlayer] play_media_list: keine existierenden Dateien")
                return False

            if shuffle:
                random.shuffle(files)

            # Gruppen bilden
            videos = [f for f in files if self._classify_media(f) == 'video']
            images = [f for f in files if self._classify_media(f) == 'image']
            audios = [f for f in files if self._classify_media(f) == 'audio']

            # Vorheriges stoppen
            self.stop()

            if videos and not images and not audios:
                # Video-Wiedergabe: spiele erstes Video
                self.current_playlist = videos
                self.playlist_index = 0
                self.playlist_shuffle = shuffle
                self.is_playing = True
                self.play_video(self.current_playlist[self.playlist_index])
                return True

            if images and audios:
                # Audio+Bild Modus: starte Audio-Playlist und Slideshow
                self.start_audio_playlist(audios)
                ok = self._start_slideshow(images)
                return ok

            if images and not audios and not videos:
                # Nur Bilder → Slideshow
                return self._start_slideshow(images)

            if audios and not images and not videos:
                # Nur Audio → Audio-Playlist
                self.start_audio_playlist(audios)
                # Zeige Status im Fenster
                if self.media_window and self.media_label:
                    self.media_label.config(image="", text="🔊 AUDIO-PLAYLIST läuft...", font=('Arial', 18), fg='cyan')
                self.is_playing = True
                return True

            # Falls gemischt inkl. Videos vorhanden sind, priorisiere Video (erstes Element)
            if videos:
                self.current_playlist = videos
                self.playlist_index = 0
                self.is_playing = True
                self.play_video(self.current_playlist[self.playlist_index])
                return True

            return False
        except Exception as e:
            print(f"[MediaPlayer] play_media_list Fehler: {e}")
            return False

    def next_media(self):
        """Zum nächsten Medium in der aktuellen Playlist wechseln (einfach)."""
        if not self.current_playlist:
            return
        media_type = self._classify_media(self.current_playlist[0])
        if media_type == 'video':
            self.playlist_index = (self.playlist_index + 1) % len(self.current_playlist)
            self.play_video(self.current_playlist[self.playlist_index])
        elif media_type == 'image':
            # Sofort nächstes Bild anzeigen
            self.playlist_index = (self.playlist_index + 1) % len(self.current_playlist)
            self.show_image(self.current_playlist[self.playlist_index])

    def previous_media(self):
        """Zum vorherigen Medium wechseln."""
        if not self.current_playlist:
            return
        media_type = self._classify_media(self.current_playlist[0])
        if media_type == 'video':
            self.playlist_index = (self.playlist_index - 1) % len(self.current_playlist)
            self.play_video(self.current_playlist[self.playlist_index])
        elif media_type == 'image':
            self.playlist_index = (self.playlist_index - 1) % len(self.current_playlist)
            self.show_image(self.current_playlist[self.playlist_index])

    def pause(self):
        """Wiedergabe pausieren/fortsetzen (soweit unterstützt)."""
        try:
            # VLC Video pausieren
            if VLC_AVAILABLE and self.vlc_player and self.current_mode == 'video':
                self.vlc_player.pause()
                self.is_paused = not self.is_paused
                return
            # pygame Audio pausieren/fortsetzen
            if PYGAME_AVAILABLE and self.audio_playing:
                if not self.is_paused:
                    try:
                        pygame.mixer.music.pause()
                    except:
                        pass
                else:
                    try:
                        pygame.mixer.music.unpause()
                    except:
                        pass
                self.is_paused = not self.is_paused
        except Exception as e:
            print(f"[MediaPlayer] Pause-Fehler: {e}")

    def stop(self):
        """Alles stoppen und Status zurücksetzen."""
        # Slideshow stoppen
        self._stop_slideshow()
        # Audio stoppen
        self.stop_audio()
        # Video stoppen
        self._stop_video()
        # Status zurücksetzen
        self.is_playing = False
        self.is_paused = False
        self.current_playlist = []
        self.playlist_index = 0
        # Schwarzes Bild anzeigen
        self.show_black()

    def get_current_media_info(self):
        """Einfacher Infotext für GUI."""
        try:
            if self.current_mode == 'video' and self.current_file:
                return f"VIDEO: {os.path.basename(self.current_file)}"
            if self.current_mode == 'image' and self.current_file:
                return f"BILD: {os.path.basename(self.current_file)}"
            if self.audio_playing:
                info = self.get_current_audio_info()
                if info:
                    return f"AUDIO: {info}"
            return None
        except Exception:
            return None
    
    def set_audio_fade_time(self, fade_time):
        """Setzt die Fade-Zeit für Audio-Übergänge"""
        self.audio_fade_time = max(0.1, float(fade_time))
        print(f"[MediaPlayer] Audio Fade-Zeit: {self.audio_fade_time}s")
    
    def start_audio_playlist(self, audio_files):
        """Startet Audio-Playlist im Hintergrund"""
        global PYGAME_AVAILABLE
        if not audio_files:
            self.stop_audio()
            return
        
        # Aktuelle Audio stoppen
        self.stop_audio()
        
        # Pygame Mixer bei Bedarf initialisieren
        if PYGAME_AVAILABLE:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
            except Exception as e:
                print(f"[MediaPlayer] pygame Mixer init fehlgeschlagen: {e} - nutze externen Player")
                # Auf externen Player zurückfallen
                PYGAME_AVAILABLE = False
        
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
        """Audio mit externem Player abspielen"""
        try:
            # Versuche verschiedene Audio-Player
            players = ['vlc', 'mpv', 'wmplayer']
            
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
                    else:  # wmplayer
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

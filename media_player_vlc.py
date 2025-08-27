"""
VLC-basierter Media Player für alle Medientypen (Video, Audio, Bilder)
Vereinfachte und robuste Lösung mit einer einheitlichen Engine
"""
import os
import threading
import time
import tkinter as tk
from tkinter import Label
import platform
import random

# VLC-Integration
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("[VLC-MediaPlayer] VLC nicht verfügbar!")

# Singleton-Pattern für VLC-Instanz um mehrfache Initialisierung zu vermeiden
_vlc_instance_singleton = None
_vlc_player_singleton = None

class VLCMediaPlayer:
    def __init__(self):
        self.current_mode = "black"  # "black", "playing", "paused"
        self.current_playlist = []
        self.current_index = 0
        self.is_playing = False
        self.vlc_instance = None
        self.vlc_player = None
        self.media_window = None
        self.media_label = None
        
        # Instanz-Kontrolle
        self.is_initializing = False
        self.initialization_complete = False
        
        # Timing für Mindestlaufzeiten
        self.media_start_time = 0
        self.min_display_time = 3.0  # Standard: 3 Sekunden
        
        # Media-Fenster erstellen
        if not self.is_initializing:
            self.is_initializing = True
            self._init_media_window()
            
            # VLC initialisieren
            if VLC_AVAILABLE:
                self._init_vlc()
            else:
                print("[VLC-MediaPlayer] VLC fehlt - nur schwarzes Bild möglich")
            
            self.initialization_complete = True
            self.is_initializing = False
        else:
            print("[VLC-MediaPlayer] Initialisierung bereits im Gange - überspringe")
    
    def _init_media_window(self):
        """Separates Media-Fenster erstellen"""
        try:
            self.media_window = tk.Toplevel()
            self.media_window.title("Pi Media Station - VLC Player")
            self.media_window.configure(bg='black')
            self.media_window.geometry("800x600")
            
            # Frame für VLC-Video
            self.video_frame = tk.Frame(self.media_window, bg='black')
            self.video_frame.pack(fill='both', expand=True)
            
            # Label für Bilder/Status
            self.media_label = tk.Label(self.video_frame, text="VLC Media Player\n\nBereit für Medien...", 
                                      font=('Arial', 20), fg='white', bg='black', justify='center')
            self.media_label.pack(fill='both', expand=True)
            
            # Vollbild für Raspberry Pi
            if platform.system() == "Linux":
                try:
                    self.media_window.attributes('-fullscreen', True)
                except:
                    self.media_window.state('zoomed')
            else:
                self.media_window.state('zoomed')  # Windows
            
            # Tastenkombinationen
            self.media_window.bind('<Escape>', lambda e: self._toggle_fullscreen())
            self.media_window.bind('<F11>', lambda e: self._toggle_fullscreen())
            self.media_window.bind('<f>', lambda e: self._toggle_fullscreen())
            
            print("[VLC-MediaPlayer] Media-Fenster erstellt")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Media-Fenster: {e}")
    
    def _init_vlc(self):
        """VLC-Instanz initialisieren mit Singleton-Pattern"""
        global _vlc_instance_singleton, _vlc_player_singleton
        
        try:
            # Prüfe ob bereits eine VLC-Instanz existiert
            if _vlc_instance_singleton is not None and _vlc_player_singleton is not None:
                print("[VLC-MediaPlayer] Verwende bestehende VLC-Instanz (Singleton)")
                self.vlc_instance = _vlc_instance_singleton
                self.vlc_player = _vlc_player_singleton
            else:
                # VLC-Optionen wie in der funktionierenden media_player.py
                print("[VLC-MediaPlayer] Erstelle neue VLC-Instanz mit bewährten Parametern...")
                
                # Exakt die gleichen Parameter wie in der funktionierenden Version
                self.vlc_instance = vlc.Instance(
                    '--no-video-title-show',
                    '--no-osd', 
                    '--quiet'
                )
                
                if self.vlc_instance is None:
                    print("[VLC-MediaPlayer] VLC-Instance mit Parametern fehlgeschlagen - versuche ohne Parameter")
                    self.vlc_instance = vlc.Instance()
                
                if self.vlc_instance is None:
                    raise Exception("VLC-Instance konnte nicht erstellt werden")
                
                print("[VLC-MediaPlayer] VLC-Instance erfolgreich erstellt")
                self.vlc_player = self.vlc_instance.media_player_new()
                
                if self.vlc_player is None:
                    raise Exception("VLC Media Player konnte nicht erstellt werden")
                
                # Als Singleton speichern
                _vlc_instance_singleton = self.vlc_instance
                _vlc_player_singleton = self.vlc_player
                print("[VLC-MediaPlayer] VLC-Instanz als Singleton gespeichert")
            
            # VLC an unser video_frame binden
            self.media_window.update()  # GUI aktualisieren für korrekte IDs
            if platform.system() == "Windows":
                self.vlc_player.set_hwnd(self.video_frame.winfo_id())
            else:
                self.vlc_player.set_xwindow(self.video_frame.winfo_id())
            
            print(f"[VLC-MediaPlayer] VLC erfolgreich initialisiert und an Frame gebunden (ID: {self.video_frame.winfo_id()})")
            
            # Test-Ausgabe für VLC-Funktionalität
            try:
                vlc_version = vlc.libvlc_get_version().decode()
                print(f"[VLC-MediaPlayer] VLC-Version: {vlc_version}")
            except:
                print("[VLC-MediaPlayer] VLC-Version konnte nicht ermittelt werden")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] VLC-Initialisierung fehlgeschlagen: {e}")
            print("[VLC-MediaPlayer] Mögliche Lösungen:")
            print("  1. sudo apt install vlc vlc-bin vlc-plugin-base")
            print("  2. pip3 install python-vlc")
            print("  3. VLC-Installation prüfen: vlc --version")
            import traceback
            traceback.print_exc()
            global VLC_AVAILABLE
            VLC_AVAILABLE = False
    
    def show_black(self):
        """Schwarzes Bild anzeigen"""
        try:
            if self.vlc_player and self.is_playing:
                self.vlc_player.stop()
                self.is_playing = False
            
            self.current_mode = "black"
            if self.media_label:
                self.media_label.pack(fill='both', expand=True)  # Label wieder sichtbar machen
                self.media_label.config(
                    text="Media Player bereit\n\nSchwarzens Bild\nKein Media aktiv",
                    bg='black',
                    fg='gray'
                )
            
            print("[VLC-MediaPlayer] Schwarzes Bild angezeigt")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler bei schwarzem Bild: {e}")
    
    def play_media_list(self, media_files, shuffle=False):
        """Medienliste abspielen (Videos, Bilder, Audio gemischt)"""
        print(f"[VLC-MediaPlayer] play_media_list aufgerufen mit {len(media_files) if media_files else 0} Dateien")
        print(f"[VLC-MediaPlayer] VLC verfügbar: {VLC_AVAILABLE}")
        print(f"[VLC-MediaPlayer] Aktueller Status - is_playing: {self.is_playing}")
        
        # Instanz-Kontrolle: Stoppe laufende Wiedergabe zuerst
        if self.is_playing:
            print("[VLC-MediaPlayer] Stoppe aktuelle Wiedergabe vor Start einer neuen")
            self.stop()
            time.sleep(0.2)  # Kurz warten bis VLC gestoppt ist
        
        if not VLC_AVAILABLE:
            print("[VLC-MediaPlayer] VLC nicht verfügbar - zeige schwarzes Bild")
            self.show_black()
            return False
        
        if not self.initialization_complete:
            print("[VLC-MediaPlayer] Initialisierung noch nicht abgeschlossen - warte")
            time.sleep(0.5)
            if not self.initialization_complete:
                print("[VLC-MediaPlayer] Initialisierung fehlgeschlagen")
                return False
        
        if not media_files:
            print("[VLC-MediaPlayer] Keine Media-Dateien - zeige schwarzes Bild")
            self.show_black()
            return False
        
        try:
            # Playlist erstellen
            self.current_playlist = media_files.copy()
            if shuffle:
                random.shuffle(self.current_playlist)
                print(f"[VLC-MediaPlayer] Playlist gemischt")
            
            print(f"[VLC-MediaPlayer] Aktuelle Playlist: {[os.path.basename(f) for f in self.current_playlist]}")
            
            self.current_index = 0
            result = self._play_current_media()
            print(f"[VLC-MediaPlayer] _play_current_media Resultat: {result}")
            return result
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Abspielen der Medienliste: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def play_single_media(self, media_file):
        """Einzelne Mediendatei abspielen"""
        print(f"[VLC-MediaPlayer] play_single_media aufgerufen: {os.path.basename(media_file) if media_file else 'None'}")
        
        # Instanz-Kontrolle: Stoppe laufende Wiedergabe zuerst
        if self.is_playing:
            print("[VLC-MediaPlayer] Stoppe aktuelle Wiedergabe vor Einzelmedium")
            self.stop()
            time.sleep(0.1)
        
        if not VLC_AVAILABLE or not os.path.exists(media_file):
            print(f"[VLC-MediaPlayer] VLC nicht verfügbar oder Datei nicht gefunden: {media_file}")
            self.show_black()
            return False
        
        if not self.initialization_complete:
            print("[VLC-MediaPlayer] Initialisierung nicht abgeschlossen - überspringe Einzelmedium")
            return False
        
        try:
            self.current_playlist = [media_file]
            self.current_index = 0
            return self._play_current_media()
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Abspielen von {media_file}: {e}")
            return False
    
    def _play_current_media(self):
        """Aktuelles Media aus Playlist abspielen"""
        if not self.current_playlist or self.current_index >= len(self.current_playlist):
            print("[VLC-MediaPlayer] Keine gültige Playlist oder Index außerhalb Bereich")
            self.show_black()
            return False
        
        # Instanz-Kontrolle: Prüfe ob VLC-Player bereit ist
        if not self.vlc_player:
            print("[VLC-MediaPlayer] VLC-Player nicht initialisiert")
            return False
        
        # Stoppe aktuelle Wiedergabe sicher
        if self.is_playing:
            try:
                print("[VLC-MediaPlayer] Stoppe aktuelle Wiedergabe vor neuem Medium")
                self.vlc_player.stop()
                time.sleep(0.1)  # Kurz warten
                self.is_playing = False
            except Exception as e:
                print(f"[VLC-MediaPlayer] Fehler beim Stoppen: {e}")
        
        try:
            media_file = self.current_playlist[self.current_index]
            media_name = os.path.basename(media_file)
            media_ext = os.path.splitext(media_file)[1].lower()
            
            print(f"[VLC-MediaPlayer] Versuche abzuspielen: {media_name}")
            
            # VLC-Media erstellen und abspielen
            media = self.vlc_instance.media_new(media_file)
            if media is None:
                print(f"[VLC-MediaPlayer] Media-Objekt konnte nicht erstellt werden für: {media_name}")
                return False
            
            self.vlc_player.set_media(media)
            
            # Spezielle Optionen für Bildtypen
            if media_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                # Bilder länger anzeigen
                media.add_option(f'image-duration={int(self.min_display_time)}')
                if self.media_label:
                    self.media_label.config(
                        text=f"Zeigt Bild:\n{media_name}\n\n({self.current_index + 1}/{len(self.current_playlist)})",
                        bg='black', fg='cyan'
                    )
                    self.media_label.pack(fill='both', expand=True)  # Label sichtbar
                print(f"[VLC-MediaPlayer] Zeige Bild: {media_name} ({self.min_display_time}s)")
                
            elif media_ext in ['.mp3', '.wav', '.ogg', '.m4a']:
                # Audio-Datei mit Label-Info
                if self.media_label:
                    self.media_label.config(
                        text=f"Spielt Audio:\n{media_name}\n\n({self.current_index + 1}/{len(self.current_playlist)})",
                        bg='black', fg='yellow'
                    )
                    self.media_label.pack(fill='both', expand=True)  # Label sichtbar
                print(f"[VLC-MediaPlayer] Spiele Audio: {media_name}")
                
            else:
                # Video-Datei - Label verstecken damit VLC das Video zeigen kann
                if self.media_label:
                    self.media_label.pack_forget()  # Label verstecken für Video
                print(f"[VLC-MediaPlayer] Spiele Video: {media_name}")
            
            # Abspielen starten
            print(f"[VLC-MediaPlayer] Versuche VLC-Play für: {media_name}")
            result = self.vlc_player.play()
            print(f"[VLC-MediaPlayer] VLC-Play-Resultat: {result}")
            
            if result == 0:  # VLC-Erfolg
                self.is_playing = True
                self.current_mode = "playing"
                self.media_start_time = time.time()
                print(f"[VLC-MediaPlayer] ✓ Wiedergabe erfolgreich gestartet: {media_name}")
                
                # Kurz warten und Status prüfen
                time.sleep(0.5)
                state = self.vlc_player.get_state()
                print(f"[VLC-MediaPlayer] VLC-Player-Status nach Start: {state}")
                
                return True
            else:
                print(f"[VLC-MediaPlayer] ✗ VLC-Play fehlgeschlagen für: {media_name} (Resultat: {result})")
                # Zusätzliche Diagnostik
                state = self.vlc_player.get_state()
                print(f"[VLC-MediaPlayer] VLC-Player-Status bei Fehler: {state}")
                return False
                
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Abspielen: {e}")
            return False
    
    def next_media(self):
        """Nächstes Media in der Playlist"""
        if not self.current_playlist:
            return False
        
        self.current_index = (self.current_index + 1) % len(self.current_playlist)
        return self._play_current_media()
    
    def previous_media(self):
        """Vorheriges Media in der Playlist"""
        if not self.current_playlist:
            return False
        
        self.current_index = (self.current_index - 1) % len(self.current_playlist)
        return self._play_current_media()
    
    def stop(self):
        """Wiedergabe stoppen"""
        try:
            print("[VLC-MediaPlayer] Stoppe Wiedergabe...")
            
            if self.vlc_player and self.is_playing:
                # VLC-Player stoppen
                self.vlc_player.stop()
                
                # Warten bis VLC wirklich gestoppt ist
                max_wait = 20  # 2 Sekunden max warten
                while max_wait > 0 and self.vlc_player.get_state() != vlc.State.Stopped:
                    time.sleep(0.1)
                    max_wait -= 1
                
                self.is_playing = False
                self.current_mode = "black"
                print("[VLC-MediaPlayer] Wiedergabe erfolgreich gestoppt")
            else:
                print("[VLC-MediaPlayer] Keine aktive Wiedergabe zum Stoppen")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Stoppen: {e}")
            # Sicherheitshalber Status zurücksetzen
            self.is_playing = False
            self.current_mode = "black"
    
    def pause(self):
        """Wiedergabe pausieren/fortsetzen"""
        try:
            if self.vlc_player and self.is_playing:
                self.vlc_player.pause()
                is_paused = self.vlc_player.get_state() == vlc.State.Paused
                self.current_mode = "paused" if is_paused else "playing"
                print(f"[VLC-MediaPlayer] {'Pausiert' if is_paused else 'Fortgesetzt'}")
                
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Pausieren: {e}")
    
    def is_media_finished(self):
        """Prüft, ob aktuelles Media beendet ist"""
        if not self.vlc_player or not self.is_playing:
            return True
        
        try:
            state = self.vlc_player.get_state()
            # Media ist beendet wenn VLC im Ended-State ist
            finished = (state == vlc.State.Ended)
            
            if finished:
                print("[VLC-MediaPlayer] Media beendet - nächstes wird geladen")
            
            return finished
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Status-Check: {e}")
            return True
    
    def can_switch_media(self, min_runtime):
        """Prüft, ob Media gewechselt werden kann (Mindestlaufzeit)"""
        if not self.is_playing:
            return True
        
        elapsed = time.time() - self.media_start_time
        can_switch = elapsed >= min_runtime
        
        if not can_switch:
            remaining = min_runtime - elapsed
            print(f"[VLC-MediaPlayer] Media-Wechsel noch {remaining:.1f}s blockiert")
        
        return can_switch
    
    def get_current_media_info(self):
        """Aktuelle Media-Informationen"""
        if not self.current_playlist or self.current_index >= len(self.current_playlist):
            return None
        
        try:
            current_file = self.current_playlist[self.current_index]
            return {
                'file': current_file,
                'name': os.path.basename(current_file),
                'index': self.current_index + 1,
                'total': len(self.current_playlist),
                'playing': self.is_playing,
                'mode': self.current_mode
            }
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler bei Media-Info: {e}")
            return None
    
    def set_min_display_time(self, seconds):
        """Mindest-Anzeigezeit für Bilder setzen"""
        self.min_display_time = max(1.0, seconds)
        print(f"[VLC-MediaPlayer] Mindest-Anzeigezeit: {self.min_display_time}s")
    
    def _toggle_fullscreen(self):
        """Vollbild umschalten"""
        try:
            if self.media_window:
                is_fullscreen = self.media_window.attributes('-fullscreen')
                self.media_window.attributes('-fullscreen', not is_fullscreen)
                print(f"[VLC-MediaPlayer] Vollbild: {not is_fullscreen}")
                
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Vollbild-Wechsel: {e}")
    
    def cleanup(self):
        """Ressourcen freigeben - aber Singleton beibehalten"""
        try:
            print("[VLC-MediaPlayer] Cleanup - stoppe nur Wiedergabe, behalte VLC-Instanz")
            self.stop()
            
            # Media-Window schließen, aber VLC-Player behalten für andere Instanzen
            if self.media_window:
                self.media_window.destroy()
                self.media_window = None
            
            # VLC-Player und Instance NICHT freigeben - sie werden von anderen verwendet
            print("[VLC-MediaPlayer] Cleanup abgeschlossen (VLC-Instanz beibehalten)")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Cleanup: {e}")
    
    @staticmethod
    def cleanup_singleton():
        """Komplett-Cleanup der Singleton-Instanz - nur beim Programm-Ende aufrufen"""
        global _vlc_instance_singleton, _vlc_player_singleton
        
        try:
            print("[VLC-MediaPlayer] Singleton Cleanup...")
            
            if _vlc_player_singleton:
                _vlc_player_singleton.stop()
                _vlc_player_singleton.release()
                _vlc_player_singleton = None
                
            if _vlc_instance_singleton:
                _vlc_instance_singleton.release()
                _vlc_instance_singleton = None
            
            print("[VLC-MediaPlayer] Singleton Cleanup abgeschlossen")
            
        except Exception as e:
            print(f"[VLC-MediaPlayer] Fehler beim Singleton Cleanup: {e}")

# Kompatibilitäts-Alias für bestehenden Code
MediaPlayer = VLCMediaPlayer

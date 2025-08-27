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
        
        # VLC-Instanz für echte Implementierung
        if VLC_AVAILABLE:
            try:
                self.vlc_instance = vlc.Instance(
                    '--fullscreen', 
                    '--no-video-title-show',
                    '--no-osd',
                    '--quiet'
                )
                self.vlc_player = self.vlc_instance.media_player_new()
                print("[MediaPlayer] VLC erfolgreich initialisiert")
            except Exception as e:
                print(f"[MediaPlayer] VLC-Initialisierung fehlgeschlagen: {e}")
                VLC_AVAILABLE = False
        
        if not VLC_AVAILABLE:
            print("[MediaPlayer] Verwende tkinter Fallback für Medien-Anzeige")
            self._init_fallback_window()
        
    def _init_fallback_window(self):
        """Initialisiert separates tkinter-Fenster für Medien"""
        self.media_window = tk.Toplevel()
        self.media_window.title("Pi Media Station - Anzeige")
        self.media_window.configure(bg='black')
        self.media_window.attributes('-fullscreen', True)
        self.media_window.focus_force()
        
        # Label für Bilder/Text
        self.media_label = Label(
            self.media_window, 
            bg='black', 
            fg='white',
            text="Schwarzes Bild",
            font=('Arial', 24)
        )
        self.media_label.pack(fill=tk.BOTH, expand=True)
        
        # ESC zum Vollbild verlassen
        self.media_window.bind('<Escape>', self._toggle_fullscreen)
        self.media_window.bind('<F11>', self._toggle_fullscreen)
        
    def _toggle_fullscreen(self, event=None):
        """Vollbild ein/aus für tkinter Fallback"""
        if self.media_window:
            current = self.media_window.attributes('-fullscreen')
            self.media_window.attributes('-fullscreen', not current)
            
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
        
        if VLC_AVAILABLE and self.vlc_player:
            # VLC für Video-Wiedergabe
            try:
                media = self.vlc_instance.media_new(path)
                media.add_option('input-repeat=-1')  # Endlos-Loop
                self.vlc_player.set_media(media)
                self.vlc_player.set_fullscreen(True)
                self.vlc_player.play()
                self.is_playing = True
                print(f"[MediaPlayer] VLC spielt Video: {os.path.basename(path)}")
            except Exception as e:
                print(f"[MediaPlayer] VLC Video-Fehler: {e}")
                self._fallback_video(path)
        else:
            # Fallback: Externes Programm für Video
            self._fallback_video(path)
    
    def _fallback_video(self, path):
        """Fallback Video-Wiedergabe mit externem Player"""
        # Aktuellen Video-Prozess stoppen
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process.wait(timeout=2)
            except:
                pass
        
        try:
            # Versuche verschiedene Video-Player
            players = ['vlc', 'mpv', 'mplayer']
            for player in players:
                try:
                    if player == 'vlc':
                        self.video_process = subprocess.Popen([
                            player, path, 
                            '--fullscreen', 
                            '--loop',
                            '--no-video-title-show',
                            '--quiet'
                        ])
                    elif player == 'mpv':
                        self.video_process = subprocess.Popen([
                            player, path,
                            '--fullscreen',
                            '--loop-file=inf'
                        ])
                    else:  # mplayer
                        self.video_process = subprocess.Popen([
                            player, path,
                            '-fs',
                            '-loop', '0'
                        ])
                    
                    print(f"[MediaPlayer] {player} spielt Video: {os.path.basename(path)}")
                    break
                except FileNotFoundError:
                    continue
            else:
                # Kein externer Player gefunden - tkinter Fallback
                if self.media_window and self.media_label:
                    self.media_label.config(
                        text=f"VIDEO: {os.path.basename(path)}\n\n(Kein Video-Player verfügbar)",
                        font=('Arial', 20)
                    )
                    
        except Exception as e:
            print(f"[MediaPlayer] Fallback Video-Fehler: {e}")
            if self.media_window and self.media_label:
                self.media_label.config(text="Video-Wiedergabe fehlgeschlagen")

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
        
        # Video stoppen falls läuft
        self._stop_video()
        
        if VLC_AVAILABLE and self.vlc_player:
            # VLC für Bild-Anzeige
            try:
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
        
        # Video stoppen
        self._stop_video()
        
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
            except:
                pass
        
        # tkinter Fallback: Schwarzes Bild
        if self.media_window and self.media_label:
            self.media_label.config(
                image="",
                text="Schwarzes Bild", 
                fg='gray',
                font=('Arial', 24)
            )
            self.media_label.image = None
            
        print("[MediaPlayer] Schwarzes Bild")

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
        
        # tkinter Fenster schließen
        if self.media_window:
            try:
                self.media_window.destroy()
            except:
                pass

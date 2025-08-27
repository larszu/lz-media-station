"""
Media-Player für Video/Bild-Anzeige (Vollbild, nahtlos)
"""
import os
import threading
import time

# VLC-Integration aktiviert
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("[MediaPlayer] VLC nicht verfügbar - Fallback auf Dummy-Modus")

class MediaPlayer:
    def __init__(self):
        global VLC_AVAILABLE
        
        self.current_mode = "black"  # "black", "video", "image"
        self.current_file = None
        self.vlc_instance = None
        self.vlc_player = None
        self.is_playing = False
        
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
        else:
            print("[MediaPlayer] VLC nicht verfügbar - Dummy-Modus aktiv")
        
    def play_video(self, path):
        """Video im Loop und Vollbild abspielen"""
        if not os.path.exists(path):
            print(f"[MediaPlayer] Video nicht gefunden: {path}")
            self.show_black()
            return
            
        if self.current_mode == "video" and self.current_file == path:
            return  # Bereits das richtige Video am Laufen
            
        print(f"[MediaPlayer] Video abspielen: {os.path.basename(path)}")
        
        # VLC-Implementierung
        if VLC_AVAILABLE and self.vlc_player:
            try:
                # Vorherige Wiedergabe stoppen
                if self.is_playing:
                    self._stop_playback()
                
                # Neues Video laden
                media = self.vlc_instance.media_new(path)
                self.vlc_player.set_media(media)
                
                # Vollbild-Einstellungen
                self.vlc_player.set_fullscreen(True)
                
                # Video starten
                self.vlc_player.play()
                
                # Loop-Überwachung starten
                threading.Thread(target=self._video_loop_monitor, daemon=True).start()
                
                self.current_mode = "video"
                self.current_file = path
                self.is_playing = True
                
                print(f"[MediaPlayer] VLC Video gestartet: {os.path.basename(path)}")
                
            except Exception as e:
                print(f"[MediaPlayer] VLC-Fehler: {e}")
                self._fallback_video_display(path)
        else:
            self._fallback_video_display(path)

    def show_image(self, path):
        """Bild im Vollbild anzeigen"""
        if not os.path.exists(path):
            print(f"[MediaPlayer] Bild nicht gefunden: {path}")
            self.show_black()
            return
            
        if self.current_mode == "image" and self.current_file == path:
            return  # Bereits das richtige Bild angezeigt
            
        print(f"[MediaPlayer] Bild anzeigen: {os.path.basename(path)}")
        
        # Video stoppen falls läuft
        if self.is_playing:
            self._stop_playback()
        
        # VLC für Bilder verwenden (funktioniert auch für Bilder)
        if VLC_AVAILABLE and self.vlc_player:
            try:
                media = self.vlc_instance.media_new(path)
                self.vlc_player.set_media(media)
                self.vlc_player.set_fullscreen(True)
                self.vlc_player.play()
                
                # Für Bilder: nach dem Laden pausieren (statische Anzeige)
                time.sleep(0.5)  # Kurz warten bis geladen
                self.vlc_player.pause()
                
                print(f"[MediaPlayer] VLC Bild angezeigt: {os.path.basename(path)}")
                
            except Exception as e:
                print(f"[MediaPlayer] VLC-Bildanzeige-Fehler: {e}")
                self._fallback_image_display(path)
        else:
            self._fallback_image_display(path)
        
        self.current_mode = "image"
        self.current_file = path
        self.is_playing = False

    def show_black(self):
        """Schwarzen Bildschirm anzeigen"""
        if self.current_mode == "black":
            return  # Bereits schwarzer Bildschirm
            
        print("[MediaPlayer] Schwarzes Bild anzeigen")
        
        # Alle Wiedergabe stoppen
        if self.is_playing:
            self._stop_playback()
        
        # VLC für schwarzen Bildschirm
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
                # Alternativ: schwarzes Dummy-Video oder einfach stoppen
                print("[MediaPlayer] VLC gestoppt - schwarzer Bildschirm")
            except Exception as e:
                print(f"[MediaPlayer] VLC-Stop-Fehler: {e}")
        
        self.current_mode = "black"
        self.current_file = None
        self.is_playing = False
    
    def _stop_playback(self):
        """Aktuelle Wiedergabe stoppen"""
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.stop()
            except Exception as e:
                print(f"[MediaPlayer] VLC-Stop-Fehler: {e}")
        
        self.is_playing = False
    
    def _video_loop_monitor(self):
        """Überwacht Video-Wiedergabe für Loop-Funktion"""
        if not VLC_AVAILABLE or not self.vlc_player:
            return
            
        while self.current_mode == "video" and self.is_playing:
            try:
                state = self.vlc_player.get_state()
                # Wenn Video zu Ende, von vorne starten
                if state == vlc.State.Ended:
                    print("[MediaPlayer] Video beendet - Loop restart")
                    self.vlc_player.set_time(0)
                    self.vlc_player.play()
                elif state == vlc.State.Error:
                    print("[MediaPlayer] VLC-Wiedergabe-Fehler")
                    break
                    
                time.sleep(0.5)  # Alle 500ms prüfen
            except Exception as e:
                print(f"[MediaPlayer] Loop-Monitor-Fehler: {e}")
                break
    
    def _fallback_video_display(self, path):
        """Fallback wenn VLC nicht funktioniert"""
        print(f"[MediaPlayer] Fallback: Video-Dummy für {os.path.basename(path)}")
        self.current_mode = "video"
        self.current_file = path
        self.is_playing = True
    
    def _fallback_image_display(self, path):
        """Fallback wenn VLC nicht funktioniert"""
        print(f"[MediaPlayer] Fallback: Bild-Dummy für {os.path.basename(path)}")
        self.current_mode = "image"
        self.current_file = path
        self.is_playing = False
    
    def cleanup(self):
        """Ressourcen freigeben"""
        self._stop_playback()
        if VLC_AVAILABLE and self.vlc_player:
            try:
                self.vlc_player.release()
            except:
                pass
        if VLC_AVAILABLE and self.vlc_instance:
            try:
                self.vlc_instance.release()
            except:
                pass


# Alternative Implementierung mit tkinter für einfache Bildanzeige
class SimpleImageDisplay:
    """Einfache Bildanzeige mit tkinter als Fallback"""
    def __init__(self):
        self.window = None
        
    def show_image_tkinter(self, path):
        """Bild mit tkinter anzeigen"""
        try:
            import tkinter as tk
            from PIL import Image, ImageTk
            
            if self.window:
                self.window.destroy()
                
            self.window = tk.Toplevel()
            self.window.attributes('-fullscreen', True)
            self.window.configure(bg='black')
            self.window.config(cursor="none")
            
            # Bild laden und skalieren
            image = Image.open(path)
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            
            # Bild proportional skalieren
            image.thumbnail((screen_width, screen_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            
            label = tk.Label(self.window, image=photo, bg='black')
            label.image = photo  # Referenz behalten
            label.pack(expand=True)
            
        except ImportError:
            print("[MediaPlayer] PIL nicht verfügbar für Bildanzeige")
        except Exception as e:
            print(f"[MediaPlayer] Fehler bei Bildanzeige: {e}")
    
    def hide(self):
        """Bildanzeige schließen"""
        if self.window:
            self.window.destroy()
            self.window = None

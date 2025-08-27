"""
Media-Player für Video/Bild-Anzeige (Vollbild, nahtlos)
"""
import os
import threading
import time

# TODO: Für VLC-Integration diese Imports aktivieren:
# import vlc

class MediaPlayer:
    def __init__(self):
        self.current_mode = "black"  # "black", "video", "image"
        self.current_file = None
        self.vlc_instance = None
        self.vlc_player = None
        self.is_playing = False
        
        # TODO: VLC-Instanz für echte Implementierung
        # self.vlc_instance = vlc.Instance('--fullscreen', '--no-video-title-show')
        # self.vlc_player = self.vlc_instance.media_player_new()
        
    def play_video(self, path):
        """Video im Loop und Vollbild abspielen"""
        if not os.path.exists(path):
            print(f"[MediaPlayer] Video nicht gefunden: {path}")
            self.show_black()
            return
            
        if self.current_mode == "video" and self.current_file == path:
            return  # Bereits das richtige Video am Laufen
            
        print(f"[MediaPlayer] Video abspielen: {os.path.basename(path)}")
        
        # TODO: Echte VLC-Implementierung
        # media = self.vlc_instance.media_new(path)
        # self.vlc_player.set_media(media)
        # self.vlc_player.set_fullscreen(True)
        # self.vlc_player.play()
        
        # # Loop aktivieren
        # self.vlc_player.set_time(0)
        # threading.Thread(target=self._video_loop_monitor, daemon=True).start()
        
        self.current_mode = "video"
        self.current_file = path
        self.is_playing = True

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
        
        # TODO: Echte Bildanzeige mit VLC oder PIL
        # Für Bilder kann auch ein einfaches tkinter/PIL-Fenster verwendet werden
        # media = self.vlc_instance.media_new(path)
        # self.vlc_player.set_media(media)
        # self.vlc_player.set_fullscreen(True)
        # self.vlc_player.play()
        
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
        
        # TODO: Schwarzen Bildschirm mit VLC oder tkinter
        # Einfache Lösung: Leeres schwarzes Video oder Bild abspielen
        
        self.current_mode = "black"
        self.current_file = None
        self.is_playing = False
    
    def _stop_playback(self):
        """Aktuelle Wiedergabe stoppen"""
        # TODO: VLC stoppen
        # if self.vlc_player:
        #     self.vlc_player.stop()
        
        self.is_playing = False
    
    def _video_loop_monitor(self):
        """Überwacht Video-Wiedergabe für Loop-Funktion"""
        # TODO: VLC-Loop-Überwachung
        # while self.current_mode == "video" and self.is_playing:
        #     if self.vlc_player.get_state() == vlc.State.Ended:
        #         self.vlc_player.set_time(0)
        #         self.vlc_player.play()
        #     time.sleep(0.5)
        pass
    
    def cleanup(self):
        """Ressourcen freigeben"""
        self._stop_playback()
        # TODO: VLC cleanup
        # if self.vlc_player:
        #     self.vlc_player.release()
        # if self.vlc_instance:
        #     self.vlc_instance.release()


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

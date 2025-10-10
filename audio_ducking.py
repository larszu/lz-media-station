#!/usr/bin/env python3
"""
FACES Exhibition - Audio Ducking Feature
Einfaches Audio-Ducking für Ambient-Audio wenn Sensor ausgelöst wird
"""

import vlc
import threading
import time
import os

class AudioDuckingManager:
    def __init__(self):
        self.ambient_player = None
        self.interaction_player = None
        
        # Audio Settings
        self.ambient_volume = 0.3      # Normale Ambient Lautstärke
        self.ducking_volume = 0.1      # Gedämpfte Ambient Lautstärke
        self.interaction_volume = 0.8  # Interaktions-Content Lautstärke
        self.fade_duration = 2.0       # Fade-Zeit in Sekunden
        
        self.is_ducking = False
        self.fade_thread = None
        
    def load_ambient_audio(self, audio_file):
        """Lädt Ambient-Audio (Gemurmel) für kontinuierliche Wiedergabe"""
        try:
            # Prüfe ob Datei existiert
            if not os.path.exists(audio_file):
                print(f"❌ Audio-Datei nicht gefunden: {audio_file}")
                return False
            
            self.ambient_player = vlc.MediaPlayer(audio_file)
            # Loop aktivieren
            media = vlc.Media(audio_file)
            self.ambient_player.set_media(media)
            
            # Für Loop müssen wir Events nutzen
            event_manager = self.ambient_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_ambient_end)
            
            self.ambient_player.audio_set_volume(int(self.ambient_volume * 100))
            print(f"🎵 Ambient Audio geladen: {audio_file}")
            return True
        except Exception as e:
            print(f"❌ Fehler beim Laden Ambient Audio: {e}")
            return False
    
    def _on_ambient_end(self, event):
        """Ambient Audio Loop"""
        if self.ambient_player:
            self.ambient_player.stop()
            self.ambient_player.play()
    
    def start_ambient(self):
        """Startet Ambient-Audio"""
        if self.ambient_player:
            self.ambient_player.play()
            print("▶️ Ambient Audio gestartet")
    
    def stop_ambient(self):
        """Stoppt Ambient-Audio"""
        if self.ambient_player:
            self.ambient_player.stop()
            print("⏹️ Ambient Audio gestoppt")
    
    def trigger_interaction(self, media_file):
        """Löst Interaktion aus - duckt Ambient und spielt Content"""
        print(f"🎯 Interaktion ausgelöst: {media_file}")
        
        # Prüfe ob Datei existiert
        if not os.path.exists(media_file):
            print(f"❌ Interaktions-Datei nicht gefunden: {media_file}")
            return False
        
        # Audio Ducking starten
        self._start_ducking()
        
        # Interaction Content laden und abspielen
        try:
            if self.interaction_player:
                self.interaction_player.stop()
            
            self.interaction_player = vlc.MediaPlayer(media_file)
            self.interaction_player.audio_set_volume(int(self.interaction_volume * 100))
            
            # Event für Ende der Interaktion
            event_manager = self.interaction_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_interaction_end)
            
            self.interaction_player.play()
            print(f"▶️ Interaktions-Content gestartet: {media_file}")
            return True
            
        except Exception as e:
            print(f"❌ Fehler bei Interaktion: {e}")
            self._stop_ducking()  # Ducking beenden bei Fehler
            return False
    
    def _on_interaction_end(self, event):
        """Interaktion beendet - Ducking zurücknehmen"""
        print("✅ Interaktion beendet")
        self._stop_ducking()
    
    def _start_ducking(self):
        """Startet Audio-Ducking (Ambient leiser)"""
        if self.is_ducking or not self.ambient_player:
            return
        
        self.is_ducking = True
        print(f"🔽 Audio Ducking: {self.ambient_volume} → {self.ducking_volume}")
        
        # Fade-out in separatem Thread
        if self.fade_thread and self.fade_thread.is_alive():
            return
        
        self.fade_thread = threading.Thread(target=self._fade_volume, 
                                          args=(self.ambient_volume, self.ducking_volume))
        self.fade_thread.start()
    
    def _stop_ducking(self):
        """Beendet Audio-Ducking (Ambient wieder normal)"""
        if not self.is_ducking or not self.ambient_player:
            return
        
        self.is_ducking = False
        print(f"🔼 Audio Ducking Ende: {self.ducking_volume} → {self.ambient_volume}")
        
        # Fade-in in separatem Thread
        if self.fade_thread and self.fade_thread.is_alive():
            return
        
        self.fade_thread = threading.Thread(target=self._fade_volume,
                                          args=(self.ducking_volume, self.ambient_volume))
        self.fade_thread.start()
    
    def _fade_volume(self, start_vol, end_vol):
        """Smooth Volume Fade"""
        if not self.ambient_player:
            return
        
        steps = 20  # Fade-Schritte
        step_duration = self.fade_duration / steps
        volume_step = (end_vol - start_vol) / steps
        
        for i in range(steps + 1):
            current_vol = start_vol + (volume_step * i)
            try:
                self.ambient_player.audio_set_volume(int(current_vol * 100))
                time.sleep(step_duration)
            except:
                break
    
    def update_settings(self, ambient_vol=None, ducking_vol=None, interaction_vol=None, fade_dur=None):
        """Update Audio Settings from Web Interface"""
        if ambient_vol is not None:
            self.ambient_volume = float(ambient_vol)
        if ducking_vol is not None:
            self.ducking_volume = float(ducking_vol)
        if interaction_vol is not None:
            self.interaction_volume = float(interaction_vol)
        if fade_dur is not None:
            self.fade_duration = float(fade_dur)
        
        print(f"🎚️ Audio Settings Update - Ambient: {self.ambient_volume}, Ducking: {self.ducking_volume}, Interaction: {self.interaction_volume}")
        
        # Aktuelle Lautstärke anpassen falls gerade läuft
        if self.ambient_player and not self.is_ducking:
            self.ambient_player.audio_set_volume(int(self.ambient_volume * 100))

# Integration in bestehende GUI
def integrate_audio_ducking_to_gui():
    """Zeigt wie Audio Ducking in gui_vlc.py integriert werden kann"""
    integration_code = '''
    # In gui_vlc.py hinzufügen:
    
    from audio_ducking import AudioDuckingManager
    
    class VLCMediaPlayerGUI:
        def __init__(self):
            # ... bestehender Code ...
            
            # Audio Ducking Manager hinzufügen
            self.audio_manager = AudioDuckingManager()
            
        def start_exhibition(self):
            """Exhibition starten mit Ambient Audio"""
            ambient_file = "audio/gemurmel_basis.wav" 
            if self.audio_manager.load_ambient_audio(ambient_file):
                self.audio_manager.start_ambient()
                print("🎭 FACES Exhibition gestartet - Ambient Audio läuft")
        
        def handle_sensor_trigger(self):
            """Sensor ausgelöst - mit Audio Ducking"""
            try:
                # Bestehende Video/Audio-Logik...
                selected_videos = self.get_selected_videos()
                
                if selected_videos:
                    video_file = random.choice(selected_videos)
                    
                    # Audio Ducking aktivieren
                    self.audio_manager.trigger_interaction(video_file)
                    
                    # VLC-Player für Video (wie bisher)
                    if self.media_player.is_playing:
                        self.media_player.stop()
                    self.media_player.play_media_list([video_file])
                    
            except Exception as e:
                print(f"Sensor Trigger Fehler: {e}")
        
        def stop_exhibition(self):
            """Exhibition stoppen"""
            self.audio_manager.stop_ambient()
            if self.media_player.is_playing:
                self.media_player.stop()
    '''
    return integration_code

if __name__ == "__main__":
    # Test des Audio Ducking
    manager = AudioDuckingManager()
    
    print("🎭 FACES Audio Ducking Test")
    print("Integration Code:")
    print(integrate_audio_ducking_to_gui())
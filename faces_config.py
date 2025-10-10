#!/usr/bin/env python3
"""
FACES Exhibition - Enhanced Configuration System
Erweiterte Konfiguration für flexible Ausstellungs-Setups
"""

import json
import yaml
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class InteractionMode:
    """Interaktions-Modi für verschiedene Ausstellungs-Szenarien"""
    name: str
    proximity_distance: int = 100  # cm
    activation_delay: float = 2.0   # Sekunden
    deactivation_delay: float = 10.0
    content_selection_method: str = "random"  # random, sequential, weighted
    
    # Neue Features für FACES
    ambient_volume_when_active: float = 0.1  # Gemurmel dämpfen
    interaction_volume: float = 0.8
    fade_duration: float = 2.0
    
    # Multi-Visitor Behavior
    multi_visitor_mode: str = "group_conversation"  # individual, group_conversation, crowd_storytelling
    max_simultaneous_interactions: int = 1

@dataclass 
class StationPersonality:
    """Persönlichkeit pro Station für FACES Charaktere"""
    character_name: str = "Anonymous"
    voice_type: str = "neutral"  # friendly, mysterious, elderly, young
    interaction_style: str = "curious"  # shy, curious, talkative, observer
    
    # Content-Gewichtung basierend auf Charakter
    prefers_images: float = 0.4
    prefers_videos: float = 0.4  
    prefers_audio: float = 0.2
    
    # Reaktions-Wahrscheinlichkeiten
    reaction_friendly: float = 0.8
    reaction_neutral: float = 0.2
    reaction_mysterious: float = 0.0

@dataclass
class ExhibitionConfig:
    """Zentrale Ausstellungs-Konfiguration"""
    exhibition_name: str = "FACES"
    
    # Globale Audio-Einstellungen
    global_ambient_file: str = "gemurmel_basis.wav"
    global_ambient_volume: float = 0.3
    
    # Station Management
    stations: Dict[str, Dict[str, Any]] = None
    
    # Web-Interface Settings
    web_interface_port: int = 8080
    mobile_upload_enabled: bool = True
    
    # Analytics
    visitor_tracking_enabled: bool = True
    interaction_logging: bool = True
    
    def __post_init__(self):
        if self.stations is None:
            self.stations = {}

class FacesConfigManager:
    """Enhanced Configuration Manager für FACES Ausstellung"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.exhibition_config = ExhibitionConfig()
        self.station_configs = {}
        
    def create_station_config(self, station_id: str, personality: StationPersonality, 
                            interaction_mode: InteractionMode) -> Dict[str, Any]:
        """Erstellt Konfiguration für eine Station"""
        config = {
            'station_id': station_id,
            'personality': asdict(personality),
            'interaction_mode': asdict(interaction_mode),
            'content_paths': {
                'images': f'content/{station_id}/images/',
                'videos': f'content/{station_id}/videos/', 
                'audio': f'content/{station_id}/audio/',
                'playlists': f'config/{station_id}_playlists.json'
            },
            'sensor_config': {
                'trigger_pin': 18,
                'echo_pin': 24,
                'trigger_distance': interaction_mode.proximity_distance,
                'sensor_type': 'HC-SR04'
            }
        }
        
        self.station_configs[station_id] = config
        return config
    
    def save_configs(self):
        """Speichert alle Konfigurationen"""
        # Hauptkonfiguration
        with open(self.config_dir / "exhibition_config.yaml", 'w') as f:
            yaml.dump(asdict(self.exhibition_config), f, default_flow_style=False)
        
        # Station-Konfigurationen
        for station_id, config in self.station_configs.items():
            with open(self.config_dir / f"{station_id}_config.yaml", 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
    
    def load_configs(self):
        """Lädt alle Konfigurationen"""
        try:
            with open(self.config_dir / "exhibition_config.yaml", 'r') as f:
                config_data = yaml.safe_load(f)
                self.exhibition_config = ExhibitionConfig(**config_data)
        except FileNotFoundError:
            print("Exhibition config not found, using defaults")
    
    def create_faces_exhibition_template(self) -> Dict[str, Any]:
        """Erstellt Template für FACES Ausstellung"""
        
        # Beispiel-Charaktere für FACES
        characters = [
            StationPersonality(
                character_name="Der Beobachter",
                voice_type="mysterious", 
                interaction_style="observer",
                prefers_images=0.6, prefers_videos=0.3, prefers_audio=0.1,
                reaction_mysterious=0.5, reaction_neutral=0.5
            ),
            StationPersonality(
                character_name="Die Geschichtenerzählerin", 
                voice_type="elderly",
                interaction_style="talkative",
                prefers_audio=0.7, prefers_images=0.2, prefers_videos=0.1,
                reaction_friendly=0.9, reaction_neutral=0.1
            ),
            StationPersonality(
                character_name="Das Neugierige Kind",
                voice_type="young",
                interaction_style="curious", 
                prefers_videos=0.6, prefers_images=0.3, prefers_audio=0.1,
                reaction_friendly=1.0
            )
        ]
        
        # Interaktions-Modi für verschiedene Szenarien
        interaction_modes = {
            'intimate': InteractionMode(
                name="Intimate Conversation",
                proximity_distance=80,
                activation_delay=1.0,
                deactivation_delay=15.0,
                multi_visitor_mode="individual"
            ),
            'group': InteractionMode(
                name="Group Discussion", 
                proximity_distance=120,
                activation_delay=2.0,
                deactivation_delay=8.0,
                multi_visitor_mode="group_conversation",
                max_simultaneous_interactions=3
            ),
            'crowd': InteractionMode(
                name="Crowd Storytelling",
                proximity_distance=150, 
                activation_delay=3.0,
                deactivation_delay=5.0,
                multi_visitor_mode="crowd_storytelling",
                max_simultaneous_interactions=5
            )
        }
        
        # Template-Konfiguration erstellen
        template = {
            'exhibition': asdict(self.exhibition_config),
            'character_templates': [asdict(char) for char in characters],
            'interaction_mode_templates': {name: asdict(mode) for name, mode in interaction_modes.items()},
            'recommended_setup': {
                'min_stations': 2,
                'max_stations': 10,
                'optimal_stations': 5,
                'spacing_meters': 2.0,
                'ambient_audio_sync': True
            }
        }
        
        return template

# Verwendungsbeispiel für FACES
if __name__ == "__main__":
    manager = FacesConfigManager()
    
    # Template erstellen
    template = manager.create_faces_exhibition_template()
    
    # Beispiel-Station erstellen
    station_config = manager.create_station_config(
        "station_01",
        StationPersonality(character_name="Der Beobachter", voice_type="mysterious"),
        InteractionMode(name="intimate", proximity_distance=100)
    )
    
    manager.save_configs()
    print("FACES Exhibition Template erstellt!")
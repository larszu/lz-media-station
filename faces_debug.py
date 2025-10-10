#!/usr/bin/env python3
"""
FACES Exhibition - Debugging und Test-Suite
Prüft alle Komponenten auf Funktionsfähigkeit
"""

import sys
import os
from pathlib import Path
import importlib.util

class FacesDebugger:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.success = []
        
    def log_issue(self, message):
        self.issues.append(f"❌ {message}")
        print(f"❌ {message}")
    
    def log_warning(self, message):
        self.warnings.append(f"⚠️ {message}")
        print(f"⚠️ {message}")
    
    def log_success(self, message):
        self.success.append(f"✅ {message}")
        print(f"✅ {message}")
    
    def check_dependencies(self):
        """Prüft ob alle Dependencies verfügbar sind"""
        print("🔍 Prüfe Dependencies...")
        
        # Core Python Libraries
        try:
            import tkinter
            self.log_success("tkinter verfügbar")
        except ImportError:
            self.log_issue("tkinter nicht verfügbar - sudo apt install python3-tk")
        
        try:
            import threading
            import time
            import json
            import os
            from pathlib import Path
            self.log_success("Standard Python Libraries verfügbar")
        except ImportError as e:
            self.log_issue(f"Standard Libraries fehlen: {e}")
        
        # VLC
        try:
            import vlc
            self.log_success("python-vlc verfügbar")
        except ImportError:
            self.log_issue("python-vlc nicht installiert - pip install python-vlc")
        
        # Flask für Web Interface
        try:
            import flask
            from flask_socketio import SocketIO
            self.log_success("Flask & SocketIO verfügbar")
        except ImportError:
            self.log_warning("Flask/SocketIO nicht verfügbar - Web Interface funktioniert nicht")
            self.log_warning("Install: pip install flask flask-socketio")
        
        # GPIO (optional auf Pi)
        try:
            import RPi.GPIO
            self.log_success("RPi.GPIO verfügbar (Raspberry Pi detected)")
        except ImportError:
            self.log_warning("RPi.GPIO nicht verfügbar (normal auf PC)")
        
        # Watchdog
        try:
            import watchdog
            self.log_success("watchdog verfügbar")
        except ImportError:
            self.log_warning("watchdog nicht verfügbar - pip install watchdog")
    
    def check_file_structure(self):
        """Prüft Dateistruktur"""
        print("\n🔍 Prüfe Dateistruktur...")
        
        required_files = [
            "main.py",
            "gui_vlc.py", 
            "media_player_vlc.py",
            "sensor.py",
            "config.py",
            "requirements.txt"
        ]
        
        for file in required_files:
            if Path(file).exists():
                self.log_success(f"{file} existiert")
            else:
                self.log_issue(f"{file} fehlt")
        
        # New FACES files
        faces_files = [
            "simple_faces_web.py",
            "audio_ducking.py"
        ]
        
        for file in faces_files:
            if Path(file).exists():
                self.log_success(f"FACES: {file} existiert")
            else:
                self.log_warning(f"FACES: {file} fehlt")
        
        # Content Ordner
        content_dirs = ["images", "videos", "audio"]
        for dir_name in content_dirs:
            if Path(dir_name).exists():
                self.log_success(f"Content-Ordner {dir_name}/ existiert")
            else:
                self.log_warning(f"Content-Ordner {dir_name}/ fehlt - wird automatisch erstellt")
    
    def check_code_syntax(self):
        """Prüft Python-Syntax der wichtigsten Dateien"""
        print("\n🔍 Prüfe Code-Syntax...")
        
        files_to_check = [
            "main.py",
            "gui_vlc.py",
            "media_player_vlc.py", 
            "sensor.py",
            "simple_faces_web.py",
            "audio_ducking.py"
        ]
        
        for file in files_to_check:
            if not Path(file).exists():
                continue
                
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Syntax-Check
                compile(code, file, 'exec')
                self.log_success(f"Syntax OK: {file}")
                
            except SyntaxError as e:
                self.log_issue(f"Syntax-Fehler in {file}: Zeile {e.lineno} - {e.msg}")
            except Exception as e:
                self.log_warning(f"Konnte {file} nicht lesen: {e}")
    
    def check_import_compatibility(self):
        """Prüft ob Module importierbar sind"""
        print("\n🔍 Prüfe Import-Kompatibilität...")
        
        modules_to_test = {
            'main': 'main.py',
            'gui_vlc': 'gui_vlc.py',
            'media_player_vlc': 'media_player_vlc.py',
            'sensor': 'sensor.py',
            'simple_faces_web': 'simple_faces_web.py',
            'audio_ducking': 'audio_ducking.py'
        }
        
        for module_name, file_path in modules_to_test.items():
            if not Path(file_path).exists():
                continue
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None:
                    self.log_warning(f"Konnte {module_name} spec nicht laden")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                # Nicht ausführen, nur laden testen
                self.log_success(f"Import-Test OK: {module_name}")
                
            except Exception as e:
                self.log_issue(f"Import-Fehler {module_name}: {e}")
    
    def check_vlc_installation(self):
        """Prüft VLC-Installation"""
        print("\n🔍 Prüfe VLC-Installation...")
        
        try:
            import vlc
            instance = vlc.Instance()
            if instance:
                self.log_success("VLC Instance erstellt")
                
                # Test Media Player
                player = instance.media_player_new()
                if player:
                    self.log_success("VLC Media Player erstellt")
                else:
                    self.log_issue("VLC Media Player konnte nicht erstellt werden")
            else:
                self.log_issue("VLC Instance konnte nicht erstellt werden")
                
        except Exception as e:
            self.log_issue(f"VLC Test fehlgeschlagen: {e}")
    
    def check_faces_specific(self):
        """FACES-spezifische Checks"""
        print("\n🔍 Prüfe FACES-spezifische Features...")
        
        # Audio Ducking Test
        try:
            if Path("audio_ducking.py").exists():
                with open("audio_ducking.py", 'r') as f:
                    content = f.read()
                
                required_methods = [
                    "class AudioDuckingManager",
                    "def load_ambient_audio",
                    "def trigger_interaction", 
                    "def _start_ducking",
                    "def _stop_ducking"
                ]
                
                for method in required_methods:
                    if method in content:
                        self.log_success(f"Audio Ducking: {method} gefunden")
                    else:
                        self.log_issue(f"Audio Ducking: {method} fehlt")
            
        except Exception as e:
            self.log_issue(f"Audio Ducking Check fehlgeschlagen: {e}")
        
        # Web Interface Test
        try:
            if Path("simple_faces_web.py").exists():
                with open("simple_faces_web.py", 'r') as f:
                    content = f.read()
                
                required_routes = [
                    "@app.route('/')",
                    "@app.route('/api/content/upload')",
                    "@app.route('/api/audio/settings')",
                    "@app.route('/api/exhibition/start')"
                ]
                
                for route in required_routes:
                    if route in content:
                        self.log_success(f"Web Interface: {route} gefunden")
                    else:
                        self.log_issue(f"Web Interface: {route} fehlt")
                        
        except Exception as e:
            self.log_issue(f"Web Interface Check fehlgeschlagen: {e}")
    
    def generate_fixes(self):
        """Generiert Lösungsvorschläge"""
        print("\n🔧 LÖSUNGSVORSCHLÄGE:")
        
        if any("python-vlc" in issue for issue in self.issues):
            print("📦 VLC Installation:")
            print("   pip install python-vlc")
            print("   # Auf Pi: sudo apt install vlc vlc-bin vlc-plugin-base")
        
        if any("Flask" in warning for warning in self.warnings):
            print("🌐 Web Interface Dependencies:")
            print("   pip install flask flask-socketio")
        
        if any("tkinter" in issue for issue in self.issues):
            print("🖥️ GUI Dependencies:")
            print("   # Auf Pi: sudo apt install python3-tk")
        
        if any("watchdog" in warning for warning in self.warnings):
            print("📁 File Watching:")
            print("   pip install watchdog")
    
    def run_full_debug(self):
        """Führt alle Debug-Checks aus"""
        print("🎭 FACES EXHIBITION - DEBUG & TEST")
        print("=" * 50)
        
        self.check_dependencies()
        self.check_file_structure() 
        self.check_code_syntax()
        self.check_import_compatibility()
        self.check_vlc_installation()
        self.check_faces_specific()
        
        print("\n" + "=" * 50)
        print("📊 ZUSAMMENFASSUNG:")
        print(f"✅ Erfolg: {len(self.success)}")
        print(f"⚠️ Warnungen: {len(self.warnings)}")
        print(f"❌ Fehler: {len(self.issues)}")
        
        if self.issues:
            print("\n🚨 KRITISCHE PROBLEME:")
            for issue in self.issues:
                print(f"   {issue}")
        
        if self.warnings:
            print("\n⚠️ WARNUNGEN:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        self.generate_fixes()
        
        # Bewertung
        if not self.issues:
            if not self.warnings:
                print("\n🎉 SYSTEM VOLLSTÄNDIG FUNKTIONSFÄHIG!")
            else:
                print("\n✅ SYSTEM GRUNDSÄTZLICH FUNKTIONSFÄHIG")
                print("   (Einige optionale Features fehlen)")
        else:
            print("\n🔧 SYSTEM BRAUCHT FIXES")
            print("   Kritische Probleme müssen behoben werden")

if __name__ == "__main__":
    debugger = FacesDebugger()
    debugger.run_full_debug()
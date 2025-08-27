#!/usr/bin/env python3
"""
Test-Script für Raspberry Pi - prüft alle benötigten Imports
"""

print("=== Import-Test für Raspberry Pi ===")

# 1. Tkinter Test
try:
    import tkinter as tk
    from tkinter import ttk, simpledialog
    print("✓ Tkinter erfolgreich importiert")
    
    # Minimal GUI Test
    root = tk.Tk()
    root.withdraw()  # Verstecken
    print("✓ Tkinter GUI kann erstellt werden")
    root.destroy()
    
except ImportError as e:
    print(f"✗ Tkinter Import-Fehler: {e}")
    print("  → Führen Sie aus: sudo apt install python3-tk")

# 2. VLC Test
print("\n--- VLC Diagnose ---")

# Erst VLC-Befehlszeile testen
import subprocess
try:
    result = subprocess.run(['vlc', '--version'], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        vlc_version = result.stdout.split('\n')[0]
        print(f"✓ VLC Befehlszeile funktioniert: {vlc_version}")
    else:
        print(f"⚠ VLC Befehlszeile Problem: Return Code {result.returncode}")
except Exception as e:
    print(f"✗ VLC Befehlszeile Test fehlgeschlagen: {e}")

# Dann Python VLC-Modul testen
try:
    import vlc
    print("✓ VLC Python-Modul erfolgreich importiert")
    
    # VLC-Version über Python
    try:
        vlc_py_version = vlc.libvlc_get_version().decode()
        print(f"  Python VLC-Version: {vlc_py_version}")
    except Exception as e:
        print(f"  ⚠ VLC-Version über Python nicht abrufbar: {e}")
    
    # Verschiedene Instance-Methoden testen (basierend auf funktionierender gui.py)
    print("  Teste VLC Instance-Methoden (wie in funktionierender gui.py)...")
    
    instance = None
    
    # Methode 1: Wie in der funktionierenden media_player.py
    try:
        print("    Teste bewährte Parameter aus funktionierender media_player.py...")
        instance = vlc.Instance(
            '--no-video-title-show',
            '--no-osd',
            '--quiet'
        )
        if instance is not None:
            print("✓ VLC Instance (bewährte Parameter) erfolgreich")
        else:
            print("✗ VLC Instance mit bewährten Parametern ist None")
    except Exception as e:
        print(f"    Bewährte Parameter fehlgeschlagen: {e}")
    
    # Methode 2: Ohne Parameter (Fallback)
    if instance is None:
        try:
            print("    Teste ohne Parameter...")
            instance = vlc.Instance()
            if instance is not None:
                print("✓ VLC Instance (ohne Parameter) erfolgreich")
            else:
                print("✗ VLC Instance ohne Parameter ist None")
        except Exception as e:
            print(f"    Ohne Parameter fehlgeschlagen: {e}")
    
    # Methode 3: Mit anderen Parametern
    if instance is None:
        try:
            print("    Teste alternative Parameter...")
            instance = vlc.Instance(['--intf', 'dummy', '--quiet'])
            if instance is not None:
                print("✓ VLC Instance (alternative Parameter) erfolgreich")
            else:
                print("✗ VLC Instance mit alternativen Parametern ist None")
        except Exception as e:
            print(f"    Alternative Parameter fehlgeschlagen: {e}")
    
    # Media Player Test nur wenn Instance erfolgreich
    if instance is not None:
        try:
            player = instance.media_player_new()
            if player is None:
                print("✗ Media Player ist None trotz funktionierender Instance")
            else:
                print("✓ VLC Media Player erfolgreich erstellt")
                
                # Test-Media erstellen (ohne Datei)
                try:
                    media = instance.media_new("dummy://")
                    if media is not None:
                        print("✓ VLC Media-Objekt kann erstellt werden")
                    else:
                        print("⚠ VLC Media-Objekt ist None")
                except Exception as e:
                    print(f"  Media-Test fehlgeschlagen: {e}")
                    
        except Exception as e:
            print(f"  ✗ VLC Media Player-Erstellung fehlgeschlagen: {e}")
    else:
        print("✗ Keine funktionierende VLC Instance - Media Player Test übersprungen")
    
except ImportError as e:
    print(f"✗ VLC Import-Fehler: {e}")
    print("  → Führen Sie aus: pip3 install python-vlc")
except Exception as e:
    print(f"✗ VLC Runtime-Fehler: {e}")
    print("  → Möglicherweise python-vlc Version inkompatibel")
    print("  → Versuchen Sie: pip3 uninstall python-vlc && pip3 install python-vlc")

# 3. GPIO Test (optional)
try:
    import RPi.GPIO as GPIO
    print("✓ RPi.GPIO erfolgreich importiert")
except ImportError as e:
    print(f"⚠ RPi.GPIO Import-Fehler: {e}")
    print("  → Führen Sie aus: pip3 install RPi.GPIO")

# 4. Standard-Module
try:
    import os, time, json, datetime, subprocess, platform, threading
    print("✓ Alle Standard-Module verfügbar")
except ImportError as e:
    print(f"✗ Standard-Modul-Fehler: {e}")

print("\n=== Test abgeschlossen ===")
print("Falls Fehler auftreten, führen Sie die angegebenen Befehle aus.")

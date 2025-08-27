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
try:
    import vlc
    print("✓ VLC Python-Modul erfolgreich importiert")
    
    # VLC Instance Test
    instance = vlc.Instance()
    print("✓ VLC Instance kann erstellt werden")
    
except ImportError as e:
    print(f"✗ VLC Import-Fehler: {e}")
    print("  → Führen Sie aus: pip3 install python-vlc")
except Exception as e:
    print(f"✗ VLC Runtime-Fehler: {e}")
    print("  → Führen Sie aus: sudo apt install vlc")

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

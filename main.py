"""
Einstiegspunkt: Startet VLC-basierte GUI und Sensor-Thread
"""
from gui_vlc import VLCMediaStationGUI
from sensor import SensorThread
import threading
import signal
import sys

def signal_handler(sig, frame):
    """Graceful shutdown bei Ctrl+C"""
    print("\nBeende VLC Media Station...")
    sys.exit(0)

if __name__ == "__main__":
    # Signal-Handler für sauberes Beenden
    signal.signal(signal.SIGINT, signal_handler)
    
    # Konfiguration laden
    from config import DEFAULT_INTERVAL

    # Kiosk-Modus über Kommandozeilen-Argument steuern
    kiosk_mode = "--kiosk" in sys.argv

    if kiosk_mode:
        print("🎬 Starte Raspberry Pi Media Station - VLC KIOSK MODUS")
    else:
        print("🎬 Starte Raspberry Pi Media Station - VLC NORMAL MODUS")
        print("Für Kiosk-Modus: python3 main.py --kiosk")
    
    print("🔧 VLC-basierte einheitliche Media-Engine")
    print("📡 Verwende echten HC-SR04 Sensor")
    print("🎯 ESC = Vollbild-Toggle | Ctrl+C = Beenden")

    # Sensor-Thread starten (immer echter Sensor)
    sensor_thread = SensorThread(interval=DEFAULT_INTERVAL)
    sensor_thread.start()

    try:
        # VLC-GUI starten
        app = VLCMediaStationGUI(sensor_thread, kiosk_mode=kiosk_mode)
        app.run()
    except KeyboardInterrupt:
        print("\nProgramm beendet durch Benutzer")
    finally:
        # Cleanup
        sensor_thread.stop()
        sensor_thread.join(timeout=2)
        print("✅ VLC Media Station cleanup abgeschlossen")

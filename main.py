"""
Einstiegspunkt: Startet GUI und Sensor-Thread
"""
from gui import MediaStationGUI
from sensor import SensorThread
import threading
import signal
import sys

def signal_handler(sig, frame):
    """Graceful shutdown bei Ctrl+C"""
    print("\nBeende Programm...")
    sys.exit(0)

if __name__ == "__main__":
    # Signal-Handler für sauberes Beenden
    signal.signal(signal.SIGINT, signal_handler)
    
    # Konfiguration laden
    from config import DEFAULT_INTERVAL

    # Kiosk-Modus über Kommandozeilen-Argument steuern
    kiosk_mode = "--kiosk" in sys.argv

    if kiosk_mode:
        print("Starte Raspberry Pi Media Station - KIOSK MODUS")
    else:
        print("Starte Raspberry Pi Media Station - NORMAL MODUS")
        print("Für Kiosk-Modus: python3 main.py --kiosk")
    
    print("Verwende echten HC-SR04 Sensor")
    print("Drücke ESC in der GUI zum Beenden")
    print("Oder Ctrl+C im Terminal")

    # Sensor-Thread starten (immer echter Sensor)
    sensor_thread = SensorThread(interval=DEFAULT_INTERVAL)
    sensor_thread.start()

    try:
        # GUI starten
        app = MediaStationGUI(sensor_thread, kiosk_mode=kiosk_mode)
        app.run()  # Vollbild, Kiosk-Modus
    except KeyboardInterrupt:
        print("\nProgramm beendet durch Benutzer")
    finally:
        # Cleanup
        sensor_thread.stop()
        sensor_thread.join(timeout=2)
        print("Cleanup abgeschlossen")

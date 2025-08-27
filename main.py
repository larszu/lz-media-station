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
    
    # Dummy-Konfiguration laden
    from config import DEFAULT_INTERVAL

    print("Starte Raspberry Pi Media Station...")
    print("Drücke ESC in der GUI zum Beenden (Test-Modus)")
    print("Oder Ctrl+C im Terminal")

    # Sensor-Thread starten (use_dummy=False für echten HC-SR04)
    sensor_thread = SensorThread(interval=DEFAULT_INTERVAL, use_dummy=False)
    sensor_thread.start()

    try:
        # GUI starten
        app = MediaStationGUI(sensor_thread)
        app.run()  # Vollbild, Kiosk-Modus
    except KeyboardInterrupt:
        print("\nProgramm beendet durch Benutzer")
    finally:
        # Cleanup
        sensor_thread.stop()
        sensor_thread.join(timeout=2)
        print("Cleanup abgeschlossen")

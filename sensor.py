"""HC-SR04 Ultraschallsensor via gpiozero - Thread-basiert mit Mittelwertfilter"""
import threading
import time
import random

try:
    from gpiozero import DistanceSensor
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False


class SensorThread(threading.Thread):
    def __init__(self, trigger_pin=23, echo_pin=24, use_dummy=False):
        super().__init__(daemon=True)
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.use_dummy = use_dummy or not GPIOZERO_AVAILABLE
        self._distance = 0.0
        self._running = False
        self._sensor = None
        self._values = []
        self._filter_size = 5
        self._lock = threading.Lock()

    def run(self):
        self._running = True
        if not self.use_dummy:
            try:
                self._sensor = DistanceSensor(
                    echo=self.echo_pin,
                    trigger=self.trigger_pin,
                    max_distance=4.0,
                )
                print(f"[Sensor] HC-SR04 initialisiert (Trigger={self.trigger_pin}, Echo={self.echo_pin})")
            except Exception as e:
                print(f"[Sensor] GPIO-Fehler: {e} - verwende Dummy")
                self.use_dummy = True

        if self.use_dummy:
            print("[Sensor] Dummy-Modus aktiv")

        while self._running:
            try:
                if self.use_dummy:
                    raw = 1.5 + random.uniform(-0.5, 0.5)
                    if random.random() < 0.05:
                        raw = random.uniform(0.2, 0.6)
                else:
                    raw = self._sensor.distance  # meters

                self._values.append(raw)
                if len(self._values) > self._filter_size:
                    self._values.pop(0)

                with self._lock:
                    self._distance = sum(self._values) / len(self._values)

            except Exception as e:
                print(f"[Sensor] Messfehler: {e}")

            time.sleep(0.1)

    @property
    def distance(self):
        with self._lock:
            return self._distance

    def stop(self):
        self._running = False
        if self._sensor:
            try:
                self._sensor.close()
            except Exception:
                pass

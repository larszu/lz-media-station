"""HC-SR04 Ultraschallsensor via gpiozero - Thread-basiert mit Mittelwertfilter"""
import threading
import time
import random

# Wie lange ein Messwert gilt, wenn keiner nachkommt.
#
# Die Messschleife laeuft alle 0,1 s. Zwanzig Durchlaeufe hintereinander ohne
# gueltigen Wert sind kein Aussetzer, sondern ein Ausfall — dann sagt der
# Sensor „ich weiss es nicht" statt weiter den letzten Wert zu behaupten.
STALE_AFTER_S = 2.0

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
        # KEIN Startwert 0.0. Das war der Defekt: 0,0 m heisst nicht
        # „noch nichts gemessen", sondern „jemand steht direkt vor dem
        # Sensor" — und `dist <= threshold` ist damit ab dem allerersten
        # Schleifendurchlauf wahr. Die Station spielte die Nah-Szene beim
        # Start, ohne dass jemand da war, und bei einem Sensor, der gar nicht
        # antwortet, blieb sie dauerhaft dabei.
        self._distance = None
        self._measured_at = None
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

                self._uebernimm(raw)

            except Exception as e:
                # Der Zeitstempel wird NICHT fortgeschrieben. Damit veraltet
                # der letzte Wert von selbst, und `distance` faellt nach
                # STALE_AFTER_S auf None zurueck. Frueher blieb er ewig
                # stehen: ein toter Sensor sah aus wie ein ruhiger Besucher.
                print(f"[Sensor] Messfehler: {e}")

            time.sleep(0.1)

    def _uebernimm(self, raw):
        """Einen Rohwert in den gleitenden Mittelwert aufnehmen.

        Eigene Methode und nicht mehr im Rumpf der Schleife, weil der Test
        die Rechnung sonst NACHBAUEN muss — und ein Nachbau laeuft
        auseinander. Genau das war hier schon passiert: `tests/test_sensor.py`
        hatte einen `push`-Helfer, der Fenster und Mittelwert nachbildete;
        als der Zeitstempel dazukam, kannte ihn nur die Schleife, und der
        Nachbau lieferte Werte, die es im Betrieb nicht gibt.
        """
        jetzt = time.monotonic()

        # BEFUND (Defektformen-Sweep, Form `fixture-erreicht-grenze-nicht`,
        # gemessen 2026-09-08): Der Ablauf bewachte den ZEITSTEMPEL, das
        # Mittelwertfenster aber niemand. Nach einem Ausfall lagen die alten
        # Werte noch im Fenster: der erste neue Messwert wurde mit vier
        # Werten von VOR dem Ausfall gemittelt und galt sofort als frisch.
        #
        # Ein halbe Sekunde lang stand damit ein Abstand im Umlauf, den es nie
        # gegeben hat — und zwar genau in dem Moment, in dem die Station
        # entscheidet, ob jemand davorsteht. Wer waehrend des Ausfalls
        # herangetreten ist, wird dadurch spaeter erkannt, nicht frueher.
        #
        # Die Grenze ist dieselbe wie beim Ablauf: was aelter ist als
        # STALE_AFTER_S, gehoert nicht in denselben Mittelwert. Zwei Fenster
        # mit zwei Regeln waeren wieder zwei Rechnungen.
        if self._measured_at is None or jetzt - self._measured_at > STALE_AFTER_S:
            self._values.clear()

        self._values.append(raw)
        if len(self._values) > self._filter_size:
            self._values.pop(0)
        with self._lock:
            self._distance = sum(self._values) / len(self._values)
            self._measured_at = jetzt

    @property
    def distance(self):
        """Der gemessene Abstand in Metern — oder `None`.

        `None` heisst „kein gueltiger Messwert": entweder wurde noch nie
        gemessen, oder die letzte gueltige Messung ist aelter als
        STALE_AFTER_S. Der Aufrufer MUSS den Fall behandeln; genau das
        Weglassen war der Defekt.
        """
        with self._lock:
            if self._measured_at is None:
                return None
            if time.monotonic() - self._measured_at > STALE_AFTER_S:
                return None
            return self._distance

    def stop(self):
        self._running = False
        if self._sensor:
            try:
                self._sensor.close()
            except Exception:
                pass

"""Abstandsquellen der LZ Media Station.

Zwei Quellen liefern denselben Wert — den Abstand des naechsten Besuchers in
Metern, oder `None`, wenn gerade keiner gemessen werden kann:

* `SensorThread`   — HC-SR04 Ultraschallsensor am GPIO (dieser Datei).
* `CameraSensorThread` — Kamera-Erkennung (in `camera_sensor.py`).

Beide erben von `AbstandsQuelle`: der gleitende Mittelwert, das Veralten eines
Messwerts und die `distance`-Eigenschaft stehen NUR hier, an einer Stelle. Wer
eine dritte Quelle baut, erbt dieselbe Rechnung — nicht eine zweite, die
auseinanderlaeuft.

KEIN Demo-/Dummy-Modus mehr. Frueher hat der Sensor, wenn keiner angeschlossen
war, Zufallswerte um 1,5 m erzeugt. Das war fuer den Enduser irrefuehrend: die
Station tat so, als messe sie, obwohl gar keine Hardware da war — die
Abstandsanzeige zappelte, die Zonen schalteten scheinbar echt. Jetzt gilt: ist
kein Sensor da, gibt es keinen Messwert (`distance is None`), und `status`
sagt im Klartext, warum. `main.py` behandelt `None` als „nicht nah" — es wird
also nichts ausgeloest, und die Oberflaeche zeigt „--" statt einer erfundenen
Zahl.
"""
import threading
import time

# Wie lange ein Messwert gilt, wenn keiner nachkommt.
#
# Die Messschleife laeuft alle 0,1 s. Zwanzig Durchlaeufe hintereinander ohne
# gueltigen Wert sind kein Aussetzer, sondern ein Ausfall — dann sagt die
# Quelle „ich weiss es nicht" statt weiter den letzten Wert zu behaupten.
STALE_AFTER_S = 2.0

try:
    from gpiozero import DistanceSensor
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False


class AbstandsQuelle(threading.Thread):
    """Gemeinsame Basis aller Abstandsquellen.

    Haelt das eine Stueck Logik, das jede Quelle teilt: einen gleitenden
    Mittelwert ueber `_filter_size` Rohwerte und das Veralten nach
    `STALE_AFTER_S`. Unterklassen fuellen in ihrer `run`-Schleife Rohwerte
    ueber `_uebernimm(...)` ein und schliessen ihre Hardware in
    `_quelle_schliessen()`.
    """

    #: Kurzname der Quelle fuer Logs und `/api/status` (Unterklasse ueberschreibt).
    LABEL = "Abstandsquelle"

    def __init__(self):
        super().__init__(daemon=True)
        # KEIN Startwert 0.0. Das war ein alter Defekt: 0,0 m heisst nicht
        # „noch nichts gemessen", sondern „jemand steht direkt vor dem
        # Sensor" — und `dist <= threshold` ist damit ab dem allerersten
        # Schleifendurchlauf wahr.
        self._distance = None
        self._measured_at = None
        self._running = False
        self._values = []
        self._filter_size = 5
        self._lock = threading.Lock()
        # Klartext-Zustand fuer Log und Oberflaeche. Beginnt mit „startet",
        # weil vor dem ersten `run`-Durchlauf noch nichts feststeht.
        self._status = "startet"
        # Drei Zustaende, und der dritte ist der Punkt: `None` heisst NOCH
        # NICHT ENTSCHIEDEN. Eine Quelle, die gerade startet, ist nicht
        # dasselbe wie eine, die es nicht gibt — wer das gleichsetzt, schaltet
        # beim Start jedes Mal fuer einen Augenblick auf den Rueckfall um
        # (Issue #13).
        self._verfuegbar = None

    # -- von Unterklassen genutzt ------------------------------------------

    def _uebernimm(self, raw):
        """Einen Rohwert in den gleitenden Mittelwert aufnehmen.

        Eigene Methode und nicht im Rumpf der Schleife, weil der Test die
        Rechnung sonst NACHBAUEN muesste — und ein Nachbau laeuft auseinander.
        """
        jetzt = time.monotonic()

        # Nach einem Ausfall gehoeren die alten Werte nicht in denselben
        # Mittelwert: was aelter ist als STALE_AFTER_S, wird verworfen, sonst
        # wuerde der erste neue Messwert mit Werten von VOR dem Ausfall
        # gemittelt und gaelte sofort als frisch.
        if self._measured_at is None or jetzt - self._measured_at > STALE_AFTER_S:
            self._values.clear()

        self._values.append(raw)
        if len(self._values) > self._filter_size:
            self._values.pop(0)
        with self._lock:
            self._distance = sum(self._values) / len(self._values)
            self._measured_at = jetzt

    def _setze_status(self, text):
        """Klartext-Zustand setzen (Zuweisung ist unter dem GIL atomar)."""
        self._status = text

    def _setze_verfuegbar(self, wert):
        """Festhalten, ob es diese Quelle auf diesem Geraet ueberhaupt gibt.

        Von der Unterklasse gesetzt, sobald sie es WEISS — nach der
        Initialisierung der Hardware, nicht davor. `AutoAbstandsQuelle`
        (Issue #13) wartet darauf, statt aus einem fehlenden Messwert auf
        einen fehlenden Sensor zu schliessen: ein Besucher, der weit weg
        steht, liefert auch keinen.
        """
        self._verfuegbar = wert

    def _quelle_schliessen(self):
        """Hardware freigeben. Unterklasse ueberschreibt bei Bedarf."""
        pass

    # -- oeffentliche Schnittstelle ----------------------------------------

    @property
    def distance(self):
        """Der gemessene Abstand in Metern — oder `None`.

        `None` heisst „kein gueltiger Messwert": entweder wurde noch nie
        gemessen, oder die letzte gueltige Messung ist aelter als
        STALE_AFTER_S, oder es ist gar keine Hardware angeschlossen. Der
        Aufrufer MUSS den Fall behandeln.
        """
        with self._lock:
            if self._measured_at is None:
                return None
            if time.monotonic() - self._measured_at > STALE_AFTER_S:
                return None
            return self._distance

    @property
    def verfuegbar(self):
        """`True`/`False` — oder `None`, solange es noch nicht feststeht.

        Nicht aus `distance` abzuleiten: kein Messwert heisst „niemand da"
        genauso wie „kein Sensor da", und die beiden zu verwechseln ist
        genau der Fehler, den Issue #13 vermeidet.
        """
        return self._verfuegbar

    @property
    def status(self):
        """Klartext, warum es gerade einen (oder keinen) Messwert gibt.

        Fuer Log und `/api/status`. Beispiele: „HC-SR04 (Trigger=23, Echo=24)",
        „kein Sensor: gpiozero nicht installiert", „Kamera: opencv nicht
        installiert".
        """
        return self._status

    def stop(self):
        self._running = False
        self._quelle_schliessen()


class SensorThread(AbstandsQuelle):
    """HC-SR04 Ultraschallsensor via gpiozero — thread-basiert mit Mittelwert.

    Ist gpiozero nicht installiert oder schlaegt die GPIO-Initialisierung fehl
    (kein Pi, Pin belegt, Verdrahtung falsch), dann misst der Thread nichts:
    `distance` bleibt `None` und `status` nennt den Grund. Er erfindet KEINE
    Werte — ein nicht angeschlossener Sensor darf nicht wie ein ruhiger
    Besucher aussehen.
    """

    LABEL = "HC-SR04"

    def __init__(self, trigger_pin=23, echo_pin=24):
        super().__init__()
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self._sensor = None

    def run(self):
        self._running = True
        if not GPIOZERO_AVAILABLE:
            self._setze_verfuegbar(False)
            self._setze_status("kein Sensor: gpiozero nicht installiert")
            print(f"[Sensor] {self._status} — es wird nicht ausgeloest")
            return
        try:
            self._sensor = DistanceSensor(
                echo=self.echo_pin,
                trigger=self.trigger_pin,
                max_distance=4.0,
            )
            self._setze_verfuegbar(True)
            self._setze_status(f"HC-SR04 (Trigger={self.trigger_pin}, Echo={self.echo_pin})")
            print(f"[Sensor] {self._status} initialisiert")
        except Exception as e:
            # Kein Rueckfall auf erfundene Werte. Der Thread endet, `distance`
            # bleibt None, der Grund steht in `status` und im Log.
            self._setze_verfuegbar(False)
            self._setze_status(f"kein Sensor: GPIO-Fehler ({e})")
            print(f"[Sensor] {self._status} — es wird nicht ausgeloest")
            return

        while self._running:
            try:
                self._uebernimm(self._sensor.distance)  # meters
            except Exception as e:
                # Der Zeitstempel wird NICHT fortgeschrieben. Damit veraltet
                # der letzte Wert von selbst, und `distance` faellt nach
                # STALE_AFTER_S auf None zurueck: ein toter Sensor sieht nicht
                # aus wie ein ruhiger Besucher.
                print(f"[Sensor] Messfehler: {e}")
            time.sleep(0.1)

    def _quelle_schliessen(self):
        if self._sensor:
            try:
                self._sensor.close()
            except Exception:
                pass

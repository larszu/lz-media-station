"""Abstandsquelle mit Rueckfall — erst der Sensor, dann die Kamera (Issue #13).

NUTZER-MELDUNG: „Wenn kein Sensor verfuegbar, dann Abstandserkennung mit
Kamera."

Beides gab es schon einzeln: `SensorThread` (HC-SR04 am GPIO) und
`CameraSensorThread` (Webcam, siehe `camera_sensor.py`). Gewaehlt wurde
zwischen ihnen aber in der KONFIGURATION — wer eine Station ohne angeloeteten
Sensor startete, bekam nichts: `distance` blieb `None`, im Log stand „kein
Sensor: gpiozero nicht installiert", und die Station loeste nie aus. Jemand
haette in den Admin gehen und „Kamera" waehlen muessen; genau das soll der
Besucher-Aufbau nicht brauchen.

─── WORAN „NICHT VERFUEGBAR" ERKANNT WIRD, UND WORAN NICHT ──────────────────

NICHT an einem fehlenden Messwert. Kein Messwert heisst „niemand steht davor"
genauso wie „kein Sensor angeschlossen" — wer das gleichsetzt, schaltet mitten
im Betrieb auf die Kamera um, weil gerade niemand im Raum war, und wieder
zurueck, sobald jemand kommt. Das waere eine Station, die ihre eigene
Wahrnehmung wechselt, waehrend jemand davorsteht.

Erkannt wird es an `AbstandsQuelle.verfuegbar`: die Quelle sagt SELBST, ob es
sie auf diesem Geraet gibt, und zwar nach ihrer Initialisierung. Drei
Zustaende, und der dritte traegt die Sache: `None` heisst „steht noch nicht
fest". Solange der wartet, wird nicht umgeschaltet.

─── EINMAL, NICHT STAENDIG ──────────────────────────────────────────────────

Der Rueckfall passiert EINMAL beim Start. Ein Sensor, der spaeter ausfaellt,
wird nicht durch die Kamera ersetzt: ein Ausfall mitten im Betrieb gehoert
gemeldet und nicht kaschiert — `distance` faellt dann nach `STALE_AFTER_S` auf
`None` zurueck, und `status` sagt, warum. Die Kamera als stiller Ersatz haette
hier eine andere Reichweite, eine andere Genauigkeit und ein anderes
Blickfeld; dass die Station „irgendwie weiterlaeuft", waere schlimmer als dass
sie schweigt.
"""
import time

from sensor import SensorThread
from camera_sensor import CameraSensorThread

__all__ = ["AutoAbstandsQuelle", "WARTEZEIT_S"]

#: Wie lange auf die Entscheidung der ersten Quelle gewartet wird.
#:
#: `gpiozero` entscheidet in Millisekunden (Import da oder nicht), die
#: GPIO-Initialisierung braucht bei belegtem Pin bis zu einer Sekunde. Zwei
#: Sekunden sind darueber und bleiben unter dem, was ein Besucher als
#: „startet nicht" empfindet. Laeuft sie ab, OHNE dass die Quelle sich
#: erklaert hat, bleibt der Sensor aktiv — im Zweifel die konfigurierte
#: Quelle und nicht die geratene.
WARTEZEIT_S = 2.0


class AutoAbstandsQuelle:
    """Erfuellt dieselbe Schnittstelle wie `SensorThread` und delegiert.

    Absichtlich KEINE `AbstandsQuelle`-Unterklasse: sie misst nichts, sie
    waehlt. Erbte sie, haette sie einen eigenen Mittelwert und einen eigenen
    Zeitstempel neben denen der aktiven Quelle — zwei Rechnungen ueber
    dasselbe, und die zweite waere immer die falsche.
    """

    LABEL = "Automatik"

    def __init__(self, trigger_pin=23, echo_pin=24, camera_index=0,
                 focal_px=700.0, wartezeit_s=WARTEZEIT_S):
        self._sensor = SensorThread(trigger_pin=trigger_pin, echo_pin=echo_pin)
        self._kamera_bauen = lambda: CameraSensorThread(
            camera_index=camera_index, focal_px=focal_px,
        )
        self._wartezeit_s = wartezeit_s
        self._aktiv = self._sensor
        self._zurueckgefallen = False

    # -- Schnittstelle einer Abstandsquelle --------------------------------

    def start(self):
        self._sensor.start()
        if self._warte_auf_entscheidung() is False:
            grund = self._sensor.status
            self._sensor.stop()
            kamera = self._kamera_bauen()
            self._aktiv = kamera
            self._zurueckgefallen = True
            print(f"[Auto] {grund} — es wird auf die Kamera zurueckgefallen")
            kamera.start()

    def stop(self):
        self._aktiv.stop()

    @property
    def distance(self):
        return self._aktiv.distance

    @property
    def status(self):
        if not self._zurueckgefallen:
            return self._aktiv.status
        # Der Rueckfall steht MIT im Zustand. „Kamera aktiv" allein liesse
        # offen, ob jemand das so eingestellt hat oder ob der Sensor fehlt —
        # und das ist die Auskunft, die jemand am Aufbau sucht.
        return f"{self._aktiv.status} (Rueckfall: kein Ultraschallsensor)"

    @property
    def verfuegbar(self):
        return self._aktiv.verfuegbar

    @property
    def aktive_quelle(self):
        """Die Quelle, die gerade misst — fuer Tests und `/api/status`."""
        return self._aktiv

    # -- intern ------------------------------------------------------------

    def _warte_auf_entscheidung(self):
        """Auf `verfuegbar` warten. `None` heisst: hat sich nicht erklaert."""
        ende = time.monotonic() + self._wartezeit_s
        while time.monotonic() < ende:
            wert = self._sensor.verfuegbar
            if wert is not None:
                return wert
            time.sleep(0.05)
        return self._sensor.verfuegbar

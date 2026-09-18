"""Tests fuer den Rueckfall auf die Kamera (`auto_sensor.py`, Issue #13).

NUTZER-MELDUNG: „Wenn kein Sensor verfuegbar, dann Abstandserkennung mit
Kamera."

Die drei Aussagen, die hier haengen und die man beim Lesen des Codes uebersieht:

1. Umgeschaltet wird, weil die Quelle SAGT, dass es sie nicht gibt — nicht,
   weil gerade kein Messwert kommt. Kein Messwert heisst auch „niemand steht
   davor".
2. Solange sie sich nicht erklaert hat (`verfuegbar is None`), wird gewartet
   und NICHT umgeschaltet.
3. Der Rueckfall passiert einmal beim Start. Ein Sensor, der spaeter
   ausfaellt, wird nicht ersetzt — das gehoert gemeldet, nicht kaschiert.

Lauf: `python3 -m unittest discover -s tests -v`
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auto_sensor  # noqa: E402
import main  # noqa: E402
import sensor  # noqa: E402


class GefaelschteQuelle:
    """Eine Quelle, die sich so verhaelt, wie der Test es braucht."""

    def __init__(self, verfuegbar=True, distance=None, status="gefaelscht"):
        self._verfuegbar = verfuegbar
        self.distance = distance
        self.status = status
        self.gestartet = False
        self.gestoppt = False

    @property
    def verfuegbar(self):
        return self._verfuegbar

    def start(self):
        self.gestartet = True

    def stop(self):
        self.gestoppt = True


def baue(sensorquelle, kameraquelle, wartezeit_s=0.2):
    q = auto_sensor.AutoAbstandsQuelle(wartezeit_s=wartezeit_s)
    q._sensor = sensorquelle
    q._aktiv = sensorquelle
    q._kamera_bauen = lambda: kameraquelle
    return q


class Rueckfall(unittest.TestCase):
    def test_ohne_sensor_uebernimmt_die_kamera(self):
        s = GefaelschteQuelle(verfuegbar=False, status="kein Sensor: gpiozero nicht installiert")
        k = GefaelschteQuelle(verfuegbar=True, distance=1.2, status="Kamera aktiv (Index 0, YuNet)")
        q = baue(s, k)
        q.start()
        self.assertTrue(k.gestartet)
        self.assertTrue(s.gestoppt, "der tote Sensor-Thread wird nicht liegengelassen")
        self.assertEqual(q.distance, 1.2)
        self.assertIs(q.aktive_quelle, k)

    def test_mit_sensor_bleibt_die_kamera_aus(self):
        # Sie ist nicht nur ungenutzt — sie wird gar nicht erst gebaut. Eine
        # geoeffnete Webcam an einer Station, die einen Sensor hat, waere ein
        # Kamerabild, um das niemand gebeten hat.
        s = GefaelschteQuelle(verfuegbar=True, distance=0.8, status="HC-SR04 (Trigger=23, Echo=24)")
        k = GefaelschteQuelle(verfuegbar=True)
        q = baue(s, k)
        q.start()
        self.assertFalse(k.gestartet)
        self.assertFalse(s.gestoppt)
        self.assertEqual(q.distance, 0.8)

    def test_kein_messwert_ist_kein_grund_umzuschalten(self):
        # DIE Aussage dieser Datei. Ein Sensor, der da ist und gerade nichts
        # sieht, ist ein Sensor, vor dem niemand steht.
        s = GefaelschteQuelle(verfuegbar=True, distance=None)
        k = GefaelschteQuelle(verfuegbar=True)
        q = baue(s, k)
        q.start()
        self.assertFalse(k.gestartet)
        self.assertIsNone(q.distance)

    def test_wer_sich_nicht_erklaert_behaelt_den_sensor(self):
        # `verfuegbar is None` heisst „steht noch nicht fest". Nach der
        # Wartezeit bleibt es bei der konfigurierten Quelle: im Zweifel die
        # gewaehlte und nicht die geratene.
        s = GefaelschteQuelle(verfuegbar=None)
        k = GefaelschteQuelle(verfuegbar=True)
        q = baue(s, k)
        q.start()
        self.assertFalse(k.gestartet)
        self.assertIs(q.aktive_quelle, s)

    def test_der_zustand_nennt_den_rueckfall(self):
        # „Kamera aktiv" allein liesse offen, ob jemand das eingestellt hat
        # oder ob der Sensor fehlt — und das ist die Auskunft, die jemand am
        # Aufbau sucht.
        s = GefaelschteQuelle(verfuegbar=False, status="kein Sensor: GPIO-Fehler (Pin belegt)")
        k = GefaelschteQuelle(verfuegbar=True, status="Kamera aktiv (Index 0, Haar)")
        q = baue(s, k)
        q.start()
        self.assertIn("Kamera aktiv", q.status)
        self.assertIn("Rueckfall", q.status)

    def test_stop_trifft_die_aktive_quelle(self):
        s = GefaelschteQuelle(verfuegbar=False)
        k = GefaelschteQuelle(verfuegbar=True)
        q = baue(s, k)
        q.start()
        q.stop()
        self.assertTrue(k.gestoppt)


class Verfuegbarkeit(unittest.TestCase):
    def test_eine_frische_quelle_hat_sich_noch_nicht_erklaert(self):
        # Nicht `False`. Eine Quelle, die gerade startet, ist nicht dasselbe
        # wie eine, die es nicht gibt — wer das gleichsetzt, faellt beim Start
        # jedes Mal kurz auf die Kamera zurueck.
        self.assertIsNone(sensor.SensorThread().verfuegbar)

    def test_ohne_gpiozero_sagt_der_sensor_es(self):
        s = sensor.SensorThread()
        s.run()  # laeuft ohne gpiozero sofort durch
        if not sensor.GPIOZERO_AVAILABLE:
            self.assertIs(s.verfuegbar, False)


class Auswahl(unittest.TestCase):
    def test_auto_ist_die_vorgabe(self):
        import config_schema
        self.assertEqual(config_schema.DEFAULT_CONFIG["sensor_type"], "auto")

    def test_erzeuge_abstandsquelle_kennt_auto(self):
        q = main.erzeuge_abstandsquelle(
            {"sensor_type": "auto", "gpio_trigger": 23, "gpio_echo": 24},
        )
        self.assertIsInstance(q, auto_sensor.AutoAbstandsQuelle)

    def test_ultrasonic_bleibt_ohne_rueckfall(self):
        # Die Ansage „an dieser Station gehoert ein Sensor hin". Faellt er aus,
        # soll sie schweigen und es melden.
        q = main.erzeuge_abstandsquelle(
            {"sensor_type": "ultrasonic", "gpio_trigger": 23, "gpio_echo": 24},
        )
        self.assertIsInstance(q, sensor.SensorThread)
        self.assertNotIsInstance(q, auto_sensor.AutoAbstandsQuelle)


if __name__ == "__main__":
    unittest.main()

"""Tests fuer `SensorThread` in `sensor.py`.

Der Sensor misst den Abstand des Besuchers und entscheidet damit, ob die
Station die Nah- oder die Fern-Szene spielt. Die einzige Logik darin ist ein
gleitender Mittelwert ueber fuenf Messwerte -- der Rest ist GPIO.

Bewusst NICHT getestet: die Messschleife in `run()`. Sie laeuft mit
`time.sleep(0.1)` in einem Thread; sie zu testen hiesse, auf Zeit zu warten,
und zeitabhaengige Tests sind der zuverlaessigste Weg, eine CI unglaubwuerdig
zu machen. Geprueft wird stattdessen, was ohne Warten pruefbar ist: der
Aufbau, die Dummy-Erkennung, das Filterfenster und das Anhalten.

Lauf: `python3 -m unittest discover -s tests -v`
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sensor  # noqa: E402


class Aufbau(unittest.TestCase):
    def test_ohne_gpiozero_faellt_er_auf_dummy_zurueck(self):
        # Auf einem Rechner ohne gpiozero MUSS der Dummy greifen -- sonst
        # stuerzt die Station beim Start ab, statt ohne Sensor weiterzulaufen.
        s = sensor.SensorThread()
        if not sensor.GPIOZERO_AVAILABLE:
            self.assertTrue(s.use_dummy, 'ohne gpiozero muss use_dummy greifen')

    def test_dummy_laesst_sich_erzwingen(self):
        self.assertTrue(sensor.SensorThread(use_dummy=True).use_dummy)

    def test_pins_sind_uebernehmbar(self):
        s = sensor.SensorThread(trigger_pin=5, echo_pin=6)
        self.assertEqual((s.trigger_pin, s.echo_pin), (5, 6))

    def test_standardpins_sind_23_und_24(self):
        # Die Belegung steht so in der Verdrahtungsanleitung; sie still zu
        # aendern wuerde jede bestehende Installation stumm machen.
        s = sensor.SensorThread()
        self.assertEqual((s.trigger_pin, s.echo_pin), (23, 24))

    def test_laeuft_als_daemon(self):
        # Sonst haengt der Prozess beim Beenden am Sensor-Thread.
        self.assertTrue(sensor.SensorThread().daemon)

    def test_startwert_ist_null_nicht_none(self):
        # `distance` wird ohne Pruefung in Vergleiche gesteckt; None waere ein
        # TypeError im ersten Zehntelsekunden-Fenster nach dem Start.
        self.assertEqual(sensor.SensorThread().distance, 0.0)


class Filterfenster(unittest.TestCase):
    """Der gleitende Mittelwert -- ohne die Thread-Schleife nachgebaut.

    Der Test spiegelt die Rechnung aus `run()` gegen die Zusicherung, dass das
    Fenster genau `_filter_size` Werte haelt. Waechst das Fenster unbegrenzt,
    wird der Sensor mit der Laufzeit immer traeger; ist es zu klein, zittert
    die Zonenumschaltung.
    """

    def push(self, s, raw):
        s._values.append(raw)
        if len(s._values) > s._filter_size:
            s._values.pop(0)
        with s._lock:
            s._distance = sum(s._values) / len(s._values)

    def test_fenstergroesse_ist_fuenf(self):
        self.assertEqual(sensor.SensorThread()._filter_size, 5)

    def test_mittelwert_ueber_wenige_werte(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in (1.0, 2.0, 3.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 2.0)

    def test_fenster_waechst_nicht_ueber_die_grenze(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in range(20):
            self.push(s, float(v))
        self.assertEqual(len(s._values), 5, 'das Fenster laeuft voll statt zu rollen')

    def test_alte_werte_fallen_hinten_raus(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in (10.0, 10.0, 10.0, 10.0, 10.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 10.0)
        for v in (0.0, 0.0, 0.0, 0.0, 0.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 0.0, msg='ein alter Wert haengt noch im Fenster')


class Anhalten(unittest.TestCase):
    def test_stop_setzt_das_laufflag(self):
        s = sensor.SensorThread(use_dummy=True)
        s._running = True
        s.stop()
        self.assertFalse(s._running)

    def test_stop_ohne_sensor_wirft_nicht(self):
        # Wird gestoppt, bevor `run()` je lief, ist `_sensor` None.
        sensor.SensorThread(use_dummy=True).stop()


if __name__ == "__main__":
    unittest.main()

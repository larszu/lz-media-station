"""Tests fuer `camera_sensor.py` — die Kamera-Abstandsquelle.

Wie beim Ultraschallsensor wird die Thread-Schleife (`run`) bewusst NICHT
getestet: sie braucht eine Kamera und OpenCV und laeuft mit `time.sleep`. Die
CI hat weder das eine noch das andere. Geprueft wird, was ohne Kamera pruefbar
ist und was im Betrieb wirklich entscheidet:

* die reine Abstands-Rechnung (Lochkamera-Modell),
* die Auswahl des naechsten (breitesten) Gesichts,
* dass ohne OpenCV nichts erfunden wird — `distance` bleibt `None`,
* dass die Quelle dieselbe Schnittstelle wie `SensorThread` erfuellt.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import camera_sensor  # noqa: E402
import sensor  # noqa: E402


class Abstandsrechnung(unittest.TestCase):
    def test_lochkamera_formel(self):
        # distance = (GESICHTSBREITE_M * brennweite) / gesichtsbreite_px.
        # Bei brennweite == gesichtsbreite_px kommt genau die Gesichtsbreite
        # in Metern heraus.
        d = camera_sensor.schaetze_abstand(gesichtsbreite_px=100, brennweite_px=100)
        self.assertAlmostEqual(d, camera_sensor.GESICHTSBREITE_M)

    def test_naeher_heisst_breiteres_gesicht(self):
        # Doppelte Pixelbreite -> halber Abstand.
        weit = camera_sensor.schaetze_abstand(50, 700)
        nah = camera_sensor.schaetze_abstand(100, 700)
        self.assertAlmostEqual(nah, weit / 2)

    def test_keine_division_durch_null(self):
        # Ein Gesicht mit Breite 0 ist kein „direkt davor", sondern Unsinn --
        # es darf keinen Wert und keinen ZeroDivisionError geben.
        self.assertIsNone(camera_sensor.schaetze_abstand(0, 700))
        self.assertIsNone(camera_sensor.schaetze_abstand(-5, 700))
        self.assertIsNone(camera_sensor.schaetze_abstand(None, 700))


class NaechstesGesicht(unittest.TestCase):
    def test_breitestes_ist_das_naechste(self):
        gesichter = [(0, 0, 30, 40), (10, 10, 90, 120), (5, 5, 60, 80)]
        self.assertEqual(camera_sensor.groesstes_gesicht(gesichter), (10, 10, 90, 120))

    def test_leere_liste_hat_kein_gesicht(self):
        self.assertIsNone(camera_sensor.groesstes_gesicht([]))


class OhneKamera(unittest.TestCase):
    def test_vor_der_ersten_messung_kein_abstand(self):
        # Kein erfundener Wert -- genau wie beim Ultraschallsensor.
        self.assertIsNone(camera_sensor.CameraSensorThread().distance)

    def test_erfuellt_die_abstandsquelle(self):
        # Muss im Controller gegen den SensorThread austauschbar sein.
        s = camera_sensor.CameraSensorThread()
        self.assertIsInstance(s, sensor.AbstandsQuelle)
        self.assertTrue(hasattr(s, "distance"))
        self.assertTrue(hasattr(s, "start"))
        self.assertTrue(hasattr(s, "stop"))
        self.assertTrue(hasattr(s, "status"))

    def test_laeuft_als_daemon(self):
        self.assertTrue(camera_sensor.CameraSensorThread().daemon)

    def test_stop_ohne_kamera_wirft_nicht(self):
        # `_cap` ist None, bevor `run()` je lief.
        camera_sensor.CameraSensorThread().stop()

    def test_parameter_werden_uebernommen(self):
        s = camera_sensor.CameraSensorThread(camera_index=2, focal_px=850.0)
        self.assertEqual(s.camera_index, 2)
        self.assertEqual(s.focal_px, 850.0)


class QuellenwahlNachKonfiguration(unittest.TestCase):
    """`sensor_type` entscheidet, welche Quelle der Controller baut — an EINER
    Stelle (`erzeuge_abstandsquelle`), damit `main` und Tests dieselbe
    bekommen."""

    def test_kamera_wird_gewaehlt(self):
        import main
        cfg = dict(main.DEFAULT_CONFIG)
        cfg["sensor_type"] = "camera"
        cfg["camera_index"] = 3
        q = main.erzeuge_abstandsquelle(cfg)
        self.assertIsInstance(q, camera_sensor.CameraSensorThread)
        self.assertEqual(q.camera_index, 3)

    def test_ultraschall_ist_die_vorgabe(self):
        import main
        q = main.erzeuge_abstandsquelle(dict(main.DEFAULT_CONFIG))
        self.assertIsInstance(q, sensor.SensorThread)


if __name__ == "__main__":
    unittest.main()

"""Tests fuer `button_sensor.py` — der Taster als Ausloeser.

Die Thread-Schleife wird wie bei den anderen Quellen nicht getestet (sie
braucht GPIO und `time.sleep`). Geprueft wird, was im Betrieb entscheidet:
die Uebersetzung in die Abstands-Sprache, das Fehlen des Mittelwerts und die
Auswahl ueber `sensor_type`.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import button_sensor  # noqa: E402
import config_schema as cs  # noqa: E402
import main  # noqa: E402
import sensor  # noqa: E402


class UebersetzungInAbstand(unittest.TestCase):
    """Der Taster spricht die Sprache der Station: einen Abstand."""

    def test_gedrueckt_liegt_unter_jeder_erlaubten_schwelle(self):
        # Die kleinste erlaubte Schwelle ist 0,05 m. Laege NAH_M darueber,
        # koennte man eine Station so einstellen, dass der Taster nie wirkt.
        kleinste_schwelle = 0.05
        self.assertLessEqual(button_sensor.NAH_M, kleinste_schwelle)

    def test_frei_liegt_ueber_jeder_erlaubten_schwelle(self):
        # Die groesste erlaubte Schwelle ist 20 m. Laege FERN_M darunter,
        # waere der Taster bei grosser Schwelle dauerhaft „gedrueckt".
        groesste_schwelle = 20.0
        self.assertGreater(button_sensor.FERN_M, groesste_schwelle)

    def test_die_grenzen_passen_zum_schema(self):
        # Die Gegenprobe gegen die Tabelle statt gegen abgeschriebene Zahlen:
        # wer die Schwellengrenzen in config_schema aendert, wird hier rot.
        _typ, erlaubt, _text = cs.GRENZEN["threshold_m"]
        self.assertTrue(erlaubt(button_sensor.NAH_M + 0.05))
        self.assertFalse(erlaubt(button_sensor.FERN_M),
                         "FERN_M muss ausserhalb des erlaubten Schwellenbereichs liegen")


class KeinMittelwert(unittest.TestCase):
    """Ein Taster ist digital — zwischen „gedrueckt" und „frei" gibt es nichts."""

    def test_filterfenster_ist_eins(self):
        self.assertEqual(button_sensor.ButtonSensorThread()._filter_size, 1)

    def test_der_wechsel_erzeugt_keinen_zwischenwert(self):
        # DER KERN: mit dem Fenster der Basis (fuenf Werte) kaeme zwischen
        # 25,0 und 0,0 ein Mittel heraus, das es nie gab — und je nach
        # Schwelle schaltete die Station auf einem Wert, den niemand
        # ausgeloest hat.
        t = button_sensor.ButtonSensorThread()
        t._uebernimm(button_sensor.FERN_M)
        t._uebernimm(button_sensor.NAH_M)
        self.assertEqual(t.distance, button_sensor.NAH_M,
                         "der Taster darf nicht mitteln")

    def test_zum_vergleich_mittelt_der_ultraschall_sehr_wohl(self):
        # Die Gegenprobe: dort ist der Mittelwert gewollt (Ausreisser
        # daempfen), und dieser Test haelt fest, dass er nicht versehentlich
        # ueberall abgeschaltet wurde.
        u = sensor.SensorThread()
        u._uebernimm(2.0)
        u._uebernimm(1.0)
        self.assertAlmostEqual(u.distance, 1.5)


class Aufbau(unittest.TestCase):
    def test_erfuellt_die_abstandsquelle(self):
        t = button_sensor.ButtonSensorThread()
        self.assertIsInstance(t, sensor.AbstandsQuelle)
        self.assertTrue(t.daemon)

    def test_vor_dem_ersten_druck_gibt_es_keinen_wert(self):
        self.assertIsNone(button_sensor.ButtonSensorThread().distance)

    def test_parameter_werden_uebernommen(self):
        t = button_sensor.ButtonSensorThread(pin=22, haltezeit_s=90.0)
        self.assertEqual(t.pin, 22)
        self.assertEqual(t.haltezeit_s, 90.0)

    def test_stop_ohne_gpio_wirft_nicht(self):
        button_sensor.ButtonSensorThread().stop()

    def test_ohne_gpiozero_wird_nichts_erfunden(self):
        # Wie bei Ultraschall und Kamera: kein Demo-Modus.
        t = button_sensor.ButtonSensorThread()
        t.run()
        self.assertIsNone(t.distance)
        self.assertIn("gpiozero", t.status)


class Quellenwahl(unittest.TestCase):
    def test_button_wird_gewaehlt(self):
        cfg = dict(main.DEFAULT_CONFIG)
        cfg["sensor_type"] = "button"
        cfg["button_pin"] = 22
        q = main.erzeuge_abstandsquelle(cfg)
        self.assertIsInstance(q, button_sensor.ButtonSensorThread)
        self.assertEqual(q.pin, 22)

    def test_button_ist_ein_erlaubter_typ(self):
        geprueft = cs.pruefe_patch({"sensor_type": "button"})
        self.assertEqual(geprueft["sensor_type"], "button")

    def test_unsinniger_typ_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"sensor_type": "telepathie"})

    def test_pin_und_haltezeit_haben_grenzen(self):
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"button_pin": 99})
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"button_haltezeit_s": 0})


if __name__ == "__main__":
    unittest.main()

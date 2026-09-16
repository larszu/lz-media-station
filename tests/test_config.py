"""Tests fuer `load_config` in `main.py` — die Schema-Heilungsschicht.

WARUM DAS DIE WICHTIGSTE REINE FUNKTION HIER IST. `load_config` ist die einzige
Stelle, an der eine unvollstaendige oder beschaedigte `config.json` wieder auf
eine brauchbare Form gebracht wird. Sie laeuft bei jedem Start, auf einem
Geraet, das unbeaufsichtigt in einer Ausstellung steht. Faellt sie aus, faellt
die Station aus -- und niemand ist da, der eine Fehlermeldung liest.

Drei Zusicherungen darin sind leicht zu zerstoeren, ohne dass es auffaellt:

1. **Fehlende Schluessel werden ergaenzt, vorhandene NICHT ueberschrieben.**
   `setdefault` statt `update` -- ein vertauschtes Paar wuerde die Konfiguration
   des Nutzers bei jedem Start stillschweigend auf die Defaults zuruecksetzen.

2. **Eine Zone, die kein Objekt ist, wird ersetzt statt zu werfen.**
   Steht in `near` versehentlich eine Liste oder `null`, muss die Station
   trotzdem hochkommen.

3. **Der Rueckfall auf die Defaults ist eine TIEFE Kopie**
   (`json.loads(json.dumps(DEFAULT_CONFIG))`). Waere es eine flache, teilten
   sich Rueckgabewert und Modul-Konstante dieselben Listen -- die erste
   Aenderung zur Laufzeit wuerde die Defaults dauerhaft verbiegen, und der
   naechste Rueckfall gaebe nicht mehr die Defaults zurueck.

Lauf: `python3 -m unittest discover -s tests -v`
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


class LoadConfigBasis(unittest.TestCase):
    def setUp(self):
        self._orig = main.CONFIG_FILE
        self._tmp = tempfile.TemporaryDirectory()
        main.CONFIG_FILE = os.path.join(self._tmp.name, "config.json")

    def tearDown(self):
        main.CONFIG_FILE = self._orig
        self._tmp.cleanup()

    def schreibe(self, obj):
        with open(main.CONFIG_FILE, "w") as f:
            json.dump(obj, f)


class OhneDatei(LoadConfigBasis):
    def test_ohne_datei_kommen_die_defaults(self):
        cfg = main.load_config()
        self.assertEqual(set(cfg), set(main.DEFAULT_CONFIG))

    def test_der_rueckfall_ist_eine_tiefe_kopie(self):
        # Waere es eine flache Kopie, wuerde diese Aenderung die Modul-Konstante
        # dauerhaft verbiegen und jeder spaetere Rueckfall etwas anderes liefern.
        a = main.load_config()
        for zone in ("near", "far"):
            if isinstance(a.get(zone), dict):
                a[zone].setdefault("videos", []).append("verunreinigt.mp4")
        b = main.load_config()
        for zone in ("near", "far"):
            if isinstance(b.get(zone), dict):
                self.assertNotIn(
                    "verunreinigt.mp4",
                    b[zone].get("videos", []),
                    f"{zone}: die Defaults wurden von einem frueheren Aufruf veraendert",
                )

    def test_kaputtes_json_wirft_nicht(self):
        with open(main.CONFIG_FILE, "w") as f:
            f.write("{ das ist kein json")
        cfg = main.load_config()
        self.assertEqual(set(cfg), set(main.DEFAULT_CONFIG))


class FehlendeSchluessel(LoadConfigBasis):
    def test_fehlende_oberste_schluessel_werden_ergaenzt(self):
        self.schreibe({})
        cfg = main.load_config()
        for k in main.DEFAULT_CONFIG:
            self.assertIn(k, cfg, f"{k} wurde nicht ergaenzt")

    def test_vorhandene_werte_bleiben_stehen(self):
        # Der Kern von `setdefault`: die Konfiguration des Nutzers gewinnt.
        # Mit `update` statt `setdefault` wuerde sie bei jedem Start verschwinden.
        schluessel = next(k for k in main.DEFAULT_CONFIG if k not in ("near", "far"))
        eigen = {schluessel: "vom-nutzer-gesetzt"}
        self.schreibe(eigen)
        cfg = main.load_config()
        self.assertEqual(
            cfg[schluessel],
            "vom-nutzer-gesetzt",
            f"{schluessel} wurde vom Default ueberschrieben",
        )


class ZonenHeilung(LoadConfigBasis):
    def test_zone_als_liste_wird_ersetzt(self):
        self.schreibe({"near": [], "far": {}})
        cfg = main.load_config()
        self.assertIsInstance(cfg["near"], dict)
        # Gegen `standard_zone()` und nicht gegen eine abgeschriebene Liste:
        # eine Zone traegt inzwischen auch Wiedergabe-Optionen (shuffle,
        # einmal, bildzeiten). Ein abgeschriebenes Objekt muesste bei jeder
        # neuen Option hier nachgezogen werden — und faellt sonst rot aus,
        # ohne dass etwas kaputt ist.
        self.assertEqual(cfg["near"], main.standard_zone())

    def test_zone_als_null_wird_ersetzt(self):
        self.schreibe({"near": None})
        cfg = main.load_config()
        self.assertIsInstance(cfg["near"], dict)

    def test_fehlende_medienlisten_werden_ergaenzt(self):
        self.schreibe({"near": {"videos": ["a.mp4"]}})
        cfg = main.load_config()
        self.assertEqual(cfg["near"]["videos"], ["a.mp4"], "vorhandene Liste ueberlebt")
        self.assertEqual(cfg["near"]["images"], [])
        self.assertEqual(cfg["near"]["audio"], [])

    def test_beide_zonen_werden_geheilt(self):
        self.schreibe({"near": "unsinn", "far": 42})
        cfg = main.load_config()
        for zone in ("near", "far"):
            self.assertIsInstance(cfg[zone], dict, zone)
            for key in ("videos", "images", "audio"):
                self.assertIn(key, cfg[zone], f"{zone}.{key}")


if __name__ == "__main__":
    unittest.main()

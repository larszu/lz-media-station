"""Waechter: die Umbenennung des Station Managers verschiebt keine Daten.

Electron leitet `userData` vom Produktnamen ab. Seit der Umbenennung in
"LZ Media Station Manager" muss die gepackte App den alten Ordner
"LZ Station Manager" weiter benutzen, sonst sind die gespeicherten
Stationen nach dem Update weg.
"""
import json
import re
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
MAIN = (WURZEL / "station-manager/main.js").read_text(encoding="utf-8")
PAKET = json.loads((WURZEL / "station-manager/package.json").read_text(encoding="utf-8"))


class UserDataPin(unittest.TestCase):
    def test_produktname(self):
        self.assertEqual(PAKET["build"]["productName"], "LZ Media Station Manager")
        self.assertEqual(PAKET["build"]["appId"], "de.zumpelars.station-manager")

    def test_alter_ordner_ist_festgenagelt(self):
        self.assertIn("const USERDATA_ORDNER = 'LZ Station Manager';", MAIN)
        self.assertRegex(
            MAIN,
            r"if \(app\.isPackaged\) app\.setPath\('userData', path\.join\(app\.getPath\('appData'\), USERDATA_ORDNER\)\);",
        )

    def test_pin_vor_jedem_zugriff(self):
        pin = MAIN.index("app.setPath('userData'")
        zugriffe = [m.start() for m in re.finditer(r"getPath\('userData'\)", MAIN)]
        self.assertTrue(zugriffe)
        self.assertTrue(all(z > pin for z in zugriffe), "userData wird vor dem Pin gelesen")


if __name__ == "__main__":
    unittest.main()

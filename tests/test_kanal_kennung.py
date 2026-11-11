"""Der Multicast-Kanal als eigene, erkennbare Anzeige (#51).

WARUM. Im Modus `anzeige` oeffnet multicast.py die Anzeigeseite in einem
zweiten, unsichtbaren Chromium. Der meldete Puls und Wiedergaben unter einer
zufaelligen Tab-Kennung — im Proof-of-Play stand jeder Clip dann zweimal,
ohne dass man sah, woher der zweite Eintrag kam, und jeder Neustart des
Kanals legte eine weitere „Anzeige" an.

Jetzt ruft der Kanal `/display?…&kanal=1`, und puls.js meldet sich dort fest
als `kanal`. Der Kanal bleibt ein eigener Ausgang (er spielt ja wirklich, an
die Fernseher), ist aber in Liste und CSV als solcher zu erkennen.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import tempfile
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from wiedergabe_log import WiedergabeLog  # noqa: E402


class KanalKennung(unittest.TestCase):
    def test_der_kanal_ruft_die_anzeige_mit_kanal_1(self):
        quelle = (WURZEL / "api_multicast.py").read_text(encoding="utf-8")
        self.assertIn("/display?lang={cfg['sprache']}&kanal=1", quelle)

    def test_puls_meldet_den_kanal_fest_als_kanal(self):
        js = (WURZEL / "static" / "anzeige" / "puls.js").read_text(encoding="utf-8")
        self.assertIn("get('kanal') === '1'", js)
        self.assertIn("if (istKanal) return 'kanal';", js)
        self.assertIn("kanal: istKanal,", js)

    def test_kanal_und_schirm_sind_zwei_anzeigen_im_log(self):
        with tempfile.TemporaryDirectory() as d:
            log = WiedergabeLog(str(Path(d) / "w.sqlite"))
            start = {"zeit": "2026-11-11T10:00:00", "region": "haupt", "typ": "video", "name": "clip.mp4"}
            self.assertEqual(log.eintragen("a-schirm", [start]), 1)
            self.assertEqual(log.eintragen("kanal", [start]), 1)
            # derselbe Puffer nach einem Kanal-Neustart zaehlt nicht noch einmal
            self.assertEqual(log.eintragen("kanal", [start]), 0)
            z = log.zusammenfassung()
            self.assertEqual((z["starts_gesamt"], z["anzeigen"]), (2, 2))
            self.assertIn(";kanal", log.als_csv())
            log.schliessen()


if __name__ == "__main__":
    unittest.main()

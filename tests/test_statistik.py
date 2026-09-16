"""Tests fuer `statistik.py` — Besuche zaehlen, ohne Personen zu speichern.

Die Uhrzeit wird hereingereicht, nie gelesen: sonst haengt der Test an der
Systemuhr und wird gegen Mitternacht unberechenbar.

Der wichtigste Fall ist `verfolge`: es gibt EINEN Eingang statt eines
`beginnt`/`endet`-Paares an verstreuten Stellen der Zustandsmaschine. Genau
deshalb kann kein Pfad — auch nicht der Wochenplan, der mitten im Besuch
zumacht — das Beenden vergessen.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import statistik  # noqa: E402

START = datetime(2026, 9, 14, 10, 30)     # Montag, 10:30


def spaeter(sekunden):
    return START + timedelta(seconds=sekunden)


class BesucheZaehlen(unittest.TestCase):
    def test_ein_besuch_wird_gezaehlt(self):
        s = statistik.Statistik()
        s.verfolge(True, START)
        dauer = s.verfolge(False, spaeter(30))
        self.assertAlmostEqual(dauer, 30.0)
        self.assertEqual(s.tage["2026-09-14"]["besuche"], 1)
        self.assertAlmostEqual(s.tage["2026-09-14"]["dauer_s"], 30.0)

    def test_waehrend_des_besuchs_wird_nichts_gezaehlt(self):
        # Erst das Ende macht den Besuch — sonst zaehlte jeder Durchlauf.
        s = statistik.Statistik()
        for sek in range(0, 5):
            self.assertIsNone(s.verfolge(True, spaeter(sek)))
        self.assertEqual(s.tage, {})

    def test_zwei_besuche_summieren_sich(self):
        s = statistik.Statistik()
        s.verfolge(True, START)
        s.verfolge(False, spaeter(10))
        s.verfolge(True, spaeter(100))
        s.verfolge(False, spaeter(120))
        self.assertEqual(s.tage["2026-09-14"]["besuche"], 2)
        self.assertAlmostEqual(s.tage["2026-09-14"]["dauer_s"], 30.0)

    def test_durchgaenger_zaehlt_nicht(self):
        # Ohne Mindestdauer zaehlt jeder, der vorbeigeht, und die Zahlen
        # werden wertlos.
        s = statistik.Statistik()
        s.verfolge(True, START)
        self.assertIsNone(s.verfolge(False, spaeter(0.3)))
        self.assertEqual(s.tage, {})

    def test_ohne_besuch_endet_nichts(self):
        s = statistik.Statistik()
        self.assertIsNone(s.verfolge(False, START))
        self.assertIsNone(s.abschliessen(START))

    def test_die_stunde_des_beginns_wird_vermerkt(self):
        s = statistik.Statistik()
        s.verfolge(True, START)          # 10:30
        s.verfolge(False, spaeter(30))
        self.assertEqual(s.tage["2026-09-14"]["stunden"]["10"], 1)

    def test_laeuft_gerade(self):
        s = statistik.Statistik()
        self.assertFalse(s.laeuft_gerade)
        s.verfolge(True, START)
        self.assertTrue(s.laeuft_gerade)
        s.verfolge(False, spaeter(5))
        self.assertFalse(s.laeuft_gerade)


class AbschliessenVonAussen(unittest.TestCase):
    """Der Fall, den ein `beginnt`/`endet`-Paar verloren haette."""

    def test_abschliessen_beendet_einen_offenen_besuch(self):
        # Passiert beim Stoppen des Controllers und wenn der Wochenplan
        # mitten im Besuch zumacht.
        s = statistik.Statistik()
        s.verfolge(True, START)
        dauer = s.abschliessen(spaeter(12))
        self.assertAlmostEqual(dauer, 12.0)
        self.assertEqual(s.tage["2026-09-14"]["besuche"], 1)

    def test_zweimal_abschliessen_zaehlt_einmal(self):
        s = statistik.Statistik()
        s.verfolge(True, START)
        s.abschliessen(spaeter(12))
        self.assertIsNone(s.abschliessen(spaeter(20)))
        self.assertEqual(s.tage["2026-09-14"]["besuche"], 1)


class Auswertung(unittest.TestCase):
    def bau(self):
        s = statistik.Statistik()
        s.verfolge(True, START)
        s.verfolge(False, spaeter(20))
        s.verfolge(True, spaeter(100))
        s.verfolge(False, spaeter(140))
        return s

    def test_heute_wird_zusammengefasst(self):
        z = self.bau().zusammenfassung(START)
        self.assertEqual(z["heute"]["besuche"], 2)
        self.assertAlmostEqual(z["heute"]["dauer_s"], 60.0)
        self.assertAlmostEqual(z["heute"]["schnitt_s"], 30.0)

    def test_stunden_sind_immer_vierundzwanzig(self):
        # Sonst muesste die Oberflaeche die Luecken auffuellen und die Kurve
        # haette je nach Tag eine andere Breite.
        z = self.bau().zusammenfassung(START)
        self.assertEqual(len(z["heute"]["stunden"]), 24)
        self.assertEqual(z["heute"]["stunden"][10], 2)
        self.assertEqual(z["heute"]["stunden"][0], 0)

    def test_leerer_tag_teilt_nicht_durch_null(self):
        z = statistik.Statistik().zusammenfassung(START)
        self.assertEqual(z["heute"]["besuche"], 0)
        self.assertEqual(z["heute"]["schnitt_s"], 0.0)

    def test_csv_hat_kopfzeile_und_komma_als_dezimalzeichen(self):
        text = self.bau().als_csv()
        zeilen = text.strip().split("\n")
        self.assertTrue(zeilen[0].startswith("Datum;Besuche"))
        self.assertIn("2026-09-14;2;", zeilen[1])
        # Deutsche Excel-Installation: Semikolon trennt, Komma ist Dezimal.
        self.assertIn(",", zeilen[1])

    def test_leeren_setzt_zurueck(self):
        s = self.bau()
        s.leeren()
        self.assertEqual(s.tage, {})


class AelteresWirdVergessen(unittest.TestCase):
    def test_nicht_mehr_als_max_tage(self):
        # Ohne Grenze waechst die Datei auf einem Geraet, das jahrelang steht.
        s = statistik.Statistik()
        for tag in range(statistik.MAX_TAGE + 20):
            zeit = datetime(2026, 1, 1) + timedelta(days=tag)
            s.verfolge(True, zeit)
            s.verfolge(False, zeit + timedelta(seconds=10))
        self.assertEqual(len(s.tage), statistik.MAX_TAGE)
        # Die JUENGSTEN bleiben, die aeltesten fallen weg — andersherum waere
        # die Kuerzung schlimmer als keine.
        self.assertNotIn("2026-01-01", s.tage, "der aelteste Tag haette wegfallen muessen")
        juengster = (datetime(2026, 1, 1) + timedelta(days=statistik.MAX_TAGE + 19)
                     ).strftime("%Y-%m-%d")
        self.assertEqual(sorted(s.tage)[-1], juengster)


class Persistenz(unittest.TestCase):
    def test_speichern_und_laden(self):
        s = statistik.Statistik()
        s.verfolge(True, START)
        s.verfolge(False, spaeter(25))
        with tempfile.TemporaryDirectory() as d:
            pfad = str(Path(d) / "statistik.json")
            self.assertTrue(statistik.speichern(s, pfad))
            zurueck = statistik.laden(pfad)
        self.assertEqual(zurueck.tage["2026-09-14"]["besuche"], 1)
        self.assertAlmostEqual(zurueck.tage["2026-09-14"]["dauer_s"], 25.0)

    def test_fehlende_datei_ist_kein_fehler(self):
        with tempfile.TemporaryDirectory() as d:
            s = statistik.laden(str(Path(d) / "gibtsnicht.json"))
        self.assertEqual(s.tage, {})

    def test_kaputte_datei_faengt_neu_an_statt_zu_werfen(self):
        # Die Station wird per Stecker ausgeschaltet. Eine halb geschriebene
        # Datei darf den Start nicht verhindern.
        with tempfile.TemporaryDirectory() as d:
            pfad = Path(d) / "statistik.json"
            pfad.write_text("{kein json", encoding="utf-8")
            s = statistik.laden(str(pfad))
        self.assertEqual(s.tage, {})

    def test_halb_beschaedigte_tage_werden_uebersprungen(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = Path(d) / "statistik.json"
            pfad.write_text(json.dumps({"version": 1, "tage": {
                "2026-09-14": {"besuche": 3, "dauer_s": 30.0, "stunden": {"10": 3}},
                "2026-09-15": "kaputt",
            }}), encoding="utf-8")
            s = statistik.laden(str(pfad))
        self.assertIn("2026-09-14", s.tage)
        self.assertNotIn("2026-09-15", s.tage)
        # Und die Auswertung laeuft danach ohne TypeError durch.
        s.zusammenfassung(START)


class UeberDieApi(unittest.TestCase):
    """Die Endpunkte, die die Verwaltung benutzt."""

    def app(self):
        import main
        from web_ui import create_app
        self.controller = main.Controller(dict(main.DEFAULT_CONFIG))
        # Nicht die echte Datei der Station anfassen: der Test soll keine
        # Betriebsdaten ueberschreiben.
        self.controller.statistik = statistik.Statistik()
        self.controller.statistik_speichern = lambda: True
        return create_app(self.controller)

    def test_zusammenfassung_kommt_als_json(self):
        with self.app().test_client() as c:
            d = c.get("/api/statistik").get_json()
        self.assertIn("heute", d)
        self.assertIn("letzte_tage", d)
        self.assertEqual(len(d["heute"]["stunden"]), 24)

    def test_csv_wird_als_download_ausgeliefert(self):
        app = self.app()
        self.controller.statistik.verfolge(True, START)
        self.controller.statistik.verfolge(False, spaeter(20))
        with app.test_client() as c:
            antwort = c.get("/api/statistik.csv")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("attachment", antwort.headers["Content-Disposition"])
        self.assertIn("Datum;Besuche", antwort.get_data(as_text=True))

    def test_zuruecksetzen_leert_die_zahlen(self):
        app = self.app()
        self.controller.statistik.verfolge(True, START)
        self.controller.statistik.verfolge(False, spaeter(20))
        with app.test_client() as c:
            self.assertEqual(c.post("/api/statistik/reset").status_code, 200)
        self.assertEqual(self.controller.statistik.tage, {})


class ControllerVerdrahtung(unittest.TestCase):
    def test_der_controller_bringt_eine_statistik_mit(self):
        import main
        c = main.Controller(dict(main.DEFAULT_CONFIG))
        self.assertIsInstance(c.statistik, statistik.Statistik)

    def test_stoppen_schliesst_einen_offenen_besuch(self):
        # Gestoppt wird typischerweise am Ende eines Ausstellungstages -- der
        # laufende Besuch darf dabei nicht verloren gehen.
        import main
        c = main.Controller(dict(main.DEFAULT_CONFIG))
        c.statistik = statistik.Statistik()
        c.statistik_speichern = lambda: True
        c.statistik.verfolge(True, START)
        c.active = True
        c.stop()
        self.assertFalse(c.statistik.laeuft_gerade)


if __name__ == "__main__":
    unittest.main()

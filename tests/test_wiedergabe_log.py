"""Proof-of-Play (3.0): was die Anzeige wann gespielt hat — nachweisbar.

WARUM. Wer eine Ausstellung im Auftrag bespielt, muss sagen koennen, wie oft
der Clip des Sponsors lief. Die Besucher-Statistik weiss das nicht; sie
zaehlt Menschen, nicht Dateien. Was hier still kaputtgehen kann:

- ein Browser schickt seinen Puffer nach einem Netzabriss ERNEUT — und jeder
  Start zaehlt doppelt (Deduplizierung ueber Kennung, Zeit, Region)
- ein kaputter Eintrag im Puffer reisst die ordentlichen mit
- die Datei waechst jahrelang (Aufbewahrung)
- die CSV verspricht Spalten, die nicht da sind

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import api_wiedergabe  # noqa: E402
import main  # noqa: E402
import wiedergabe_log as W  # noqa: E402
from web_ui import create_app  # noqa: E402


def eintrag(zeit="2026-09-28T10:00:00", name="film.mp4", typ="video", region="haupt", **rest):
    e = {"zeit": zeit, "typ": typ, "name": name, "region": region,
         "layout_id": "zone-near", "zone": "near"}
    e.update(rest)
    return e


class DieDatei(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.log = W.WiedergabeLog(os.path.join(self.ordner.name, "w.sqlite"))

    def tearDown(self):
        self.log.schliessen()
        self.ordner.cleanup()

    def test_starts_werden_gezaehlt_und_nach_datei_gruppiert(self):
        self.log.eintragen("a1", [eintrag(), eintrag(zeit="2026-09-28T10:01:00"),
                                  eintrag(zeit="2026-09-28T10:02:00", name="tafel.jpg", typ="image")])
        z = self.log.zusammenfassung(gruppe="datei")
        self.assertEqual(z["starts_gesamt"], 3)
        self.assertEqual(z["zeilen"][0]["schluessel"], "film.mp4")
        self.assertEqual(z["zeilen"][0]["starts"], 2)

    def test_ein_erneut_geschickter_puffer_zaehlt_nicht_doppelt(self):
        # Der Kern des Moduls: Netzabriss, der Browser schickt alles noch einmal.
        puffer = [eintrag(), eintrag(zeit="2026-09-28T10:01:00")]
        self.assertEqual(self.log.eintragen("a1", puffer), 2)
        self.assertEqual(self.log.eintragen("a1", puffer), 0)
        self.assertEqual(self.log.anzahl(), 2)

    def test_zwei_anzeigen_zur_selben_zeit_sind_zwei_starts(self):
        self.log.eintragen("a1", [eintrag()])
        self.log.eintragen("a2", [eintrag()])
        self.assertEqual(self.log.anzahl(), 2)
        self.assertEqual(self.log.zusammenfassung()["anzeigen"], 2)

    def test_ein_kaputter_eintrag_reisst_die_anderen_nicht_mit(self):
        n = self.log.eintragen("a1", [eintrag(), "unsinn", {"zeit": "gestern", "typ": "video", "name": "x"},
                                      eintrag(zeit="2026-09-28T10:05:00", typ="dvd")])
        self.assertEqual(n, 1)

    def test_ohne_kennung_wird_nichts_aufgenommen(self):
        self.assertEqual(self.log.eintragen(None, [eintrag()]), 0)
        self.assertEqual(self.log.eintragen("x" * 70, [eintrag()]), 0)

    def test_aufbewahrung_loescht_nur_das_alte(self):
        self.log.aufbewahrung_tage = 30
        self.log.eintragen("a1", [eintrag(zeit="2026-06-01T10:00:00"), eintrag(zeit="2026-09-20T10:00:00")])
        geloescht = self.log.aufraeumen(datetime(2026, 9, 28, 12, 0))
        self.assertEqual(geloescht, 1)
        self.assertEqual(self.log.anzahl(), 1)

    def test_zeitraum_grenzt_ein_und_bis_schliesst_den_tag_ein(self):
        self.log.eintragen("a1", [eintrag(zeit="2026-09-01T10:00:00"), eintrag(zeit="2026-09-15T23:30:00"),
                                  eintrag(zeit="2026-09-16T00:10:00")])
        z = self.log.zusammenfassung(von="2026-09-10", bis="2026-09-15")
        self.assertEqual(z["starts_gesamt"], 1)

    def test_gruppe_nach_stunde_und_tag(self):
        self.log.eintragen("a1", [eintrag(zeit="2026-09-28T10:00:00"), eintrag(zeit="2026-09-28T10:30:00"),
                                  eintrag(zeit="2026-09-29T11:00:00")])
        stunden = {z["schluessel"]: z["starts"] for z in self.log.zusammenfassung(gruppe="stunde")["zeilen"]}
        self.assertEqual(stunden, {"10": 2, "11": 1})
        tage = {z["schluessel"]: z["starts"] for z in self.log.zusammenfassung(gruppe="tag")["zeilen"]}
        self.assertEqual(tage, {"2026-09-28": 2, "2026-09-29": 1})

    def test_unbekannte_gruppe_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            self.log.zusammenfassung(gruppe="farbe")

    def test_csv_hat_kopf_und_eine_zeile_je_start(self):
        self.log.eintragen("a1", [eintrag(), eintrag(zeit="2026-09-28T10:01:00", name="tafel.jpg", typ="image")])
        zeilen = self.log.als_csv().strip().splitlines()
        self.assertEqual(zeilen[0], "zeit;typ;name;region;layout;zone;anzeige")
        self.assertEqual(len(zeilen), 3)
        self.assertIn("tafel.jpg", zeilen[2])

    def test_web_eintraege_nehmen_die_url_als_namen(self):
        e = W.pruefe_eintrag({"zeit": "2026-09-28T10:00:00", "typ": "web", "url": "https://example.org/x"})
        self.assertEqual(e["name"], "https://example.org/x")

    def test_zeit_mit_zeitzone_wird_verstanden(self):
        e = W.pruefe_eintrag({"zeit": "2026-09-28T08:00:00Z", "typ": "video", "name": "a.mp4"})
        self.assertIsNotNone(e)
        self.assertRegex(e["zeit"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self._alt = api_wiedergabe.DB_PFAD
        api_wiedergabe.DB_PFAD = os.path.join(self.ordner.name, "w.sqlite")
        self.controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)

    def tearDown(self):
        api_wiedergabe.DB_PFAD = self._alt
        log = getattr(self.controller, "wiedergabe", None)
        if log:
            log.schliessen()
        self.ordner.cleanup()

    def test_melden_zusammenfassen_csv(self):
        with self.app.test_client() as c:
            r = c.post("/api/wiedergabe", json={"kennung": "a1", "eintraege": [eintrag(), eintrag(zeit="2026-09-28T10:01:00")]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json()["neu"], 2)
            z = c.get("/api/wiedergabe/zusammenfassung?gruppe=datei").get_json()
            self.assertEqual(z["starts_gesamt"], 2)
            csv = c.get("/api/wiedergabe.csv?von=2026-09-01&bis=2026-09-30")
            self.assertEqual(csv.status_code, 200)
            self.assertIn("film.mp4", csv.get_data(as_text=True))

    def test_die_datei_entsteht_erst_beim_ersten_zugriff(self):
        # Eine Test-App oder ein Kern ohne Anzeige legt keine leere Datenbank an.
        self.assertFalse(os.path.exists(api_wiedergabe.DB_PFAD))
        with self.app.test_client() as c:
            c.get("/api/wiedergabe/zusammenfassung")
        self.assertTrue(os.path.exists(api_wiedergabe.DB_PFAD))

    def test_unsinn_wird_abgelehnt(self):
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/wiedergabe", json=[1, 2]).status_code, 400)
            self.assertEqual(c.post("/api/wiedergabe", json={"kennung": "a", "eintraege": "x"}).status_code, 400)
            self.assertEqual(c.get("/api/wiedergabe/zusammenfassung?von=gestern").status_code, 400)
            self.assertEqual(c.get("/api/wiedergabe/zusammenfassung?gruppe=farbe").status_code, 400)

    def test_aufbewahrung_ist_ein_konfigurationsfeld(self):
        with self.app.test_client() as c:
            r = c.post("/api/config", json={"wiedergabe_aufbewahrung_tage": 0})
            self.assertEqual(r.status_code, 400)
            r = c.post("/api/config", json={"wiedergabe_aufbewahrung_tage": 30})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.controller.config["wiedergabe_aufbewahrung_tage"], 30)
            c.post("/api/wiedergabe", json={"kennung": "a1", "eintraege": [eintrag()]})
            self.assertEqual(self.controller.wiedergabe.aufbewahrung_tage, 30)


if __name__ == "__main__":
    unittest.main()

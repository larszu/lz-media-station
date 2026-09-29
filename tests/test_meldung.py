"""Sofortmeldung (3.0, Welle 2): eine Zeile ueber allem, sofort, auf jedem Schirm.

WARUM. Eine Raeumungsmeldung, die erst beim naechsten Poll kommt oder nach
einem Neuladen der Anzeige weg ist, ist keine. Was hier festgehalten wird:

- Setzen schickt den Befehl SOFORT an die Anzeigen UND legt die Meldung in
  die Szene — eine Anzeige, die spaeter laedt, zeigt sie auch
- `dauer_s` wird zu `bis`; danach ist die Meldung aus, ohne Server
- nach einem Neustart ist eine abgelaufene Meldung aus (sonst steht die
  Raeumung von gestern auf dem Schirm)
- die Anzeige-Seite hat das Skript, das den Befehl versteht

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import queue
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import main  # noqa: E402
import programm as P  # noqa: E402
from web_ui import create_app  # noqa: E402


def frische_config():
    return json.loads(json.dumps(main.DEFAULT_CONFIG))


class DasSchema(unittest.TestCase):
    def test_dauer_wird_zu_bis(self):
        jetzt = datetime(2026, 9, 14, 10, 0, 0)
        m = P.pruefe_meldung({"text": "Pause", "dauer_s": 300}, jetzt)
        self.assertEqual(m["bis"], "2026-09-14T10:05:00")
        self.assertTrue(P.meldung_gilt(m, jetzt + timedelta(minutes=4)))
        self.assertFalse(P.meldung_gilt(m, jetzt + timedelta(minutes=6)))

    def test_ohne_dauer_gilt_bis_zum_beenden(self):
        m = P.pruefe_meldung({"text": "Hinweis"})
        self.assertIsNone(m["bis"])
        self.assertTrue(P.meldung_gilt(m, datetime(2030, 1, 1)))

    def test_lehnt_ab_und_nennt_das_feld(self):
        for kaputt, feld in (({"text": ""}, "text"), ({"text": "x", "farbe": "rot"}, "farbe"),
                             ({"text": "x", "dauer_s": -5}, "dauer_s"), ({"text": "x", "ton": 1}, "ton"),
                             ({"text": "x" * 201}, "text")):
            with self.assertRaises(ValueError, msg=str(kaputt)) as ctx:
                P.pruefe_meldung(kaputt)
            self.assertIn(feld, str(ctx.exception))

    def test_der_ladeweg_schaltet_eine_abgelaufene_meldung_aus(self):
        gestern = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        m = P.heile_meldung({"aktiv": True, "text": "Raeumung", "bis": gestern})
        self.assertFalse(m["aktiv"])
        m = P.heile_meldung({"aktiv": True, "text": "Raeumung", "bis": None})
        self.assertTrue(m["aktiv"], "ohne Ende bleibt sie — jemand muss sie beenden")
        self.assertEqual(P.heile_meldung("Unsinn"), P.standard_meldung())


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.c.ausloeser_faden = False
        self.app = create_app(self.c)
        self.q = self.c.bus.abonnieren()

    def ereignisse(self):
        heraus = []
        while True:
            try:
                heraus.append(self.q.get_nowait())
            except queue.Empty:
                return heraus

    def test_setzen_schickt_sofort_einen_befehl_und_legt_sie_in_die_szene(self):
        with self.app.test_client() as k:
            a = k.post("/api/meldung", json={"text": "Bitte das Gebaeude verlassen", "dauer_s": 600, "ton": True})
            self.assertEqual(a.status_code, 200, a.get_json())
            self.assertEqual(a.get_json()["empfaenger"], 1)
            befehle = [e["daten"] for e in self.ereignisse() if e["typ"] == "befehl"]
            self.assertEqual(len(befehle), 1)
            self.assertEqual(befehle[0]["typ"], "meldung")
            self.assertTrue(befehle[0]["aktiv"])
            self.assertTrue(befehle[0]["ton"])
            szene = k.get("/api/scene").get_json()
            self.assertTrue(szene["meldung"]["aktiv"])
            self.assertEqual(szene["meldung"]["text"], "Bitte das Gebaeude verlassen")
            self.assertTrue(k.get("/api/meldung").get_json()["aktiv"])

    def test_beenden(self):
        with self.app.test_client() as k:
            k.post("/api/meldung", json={"text": "Pause"})
            self.ereignisse()
            a = k.delete("/api/meldung")
            self.assertEqual(a.status_code, 200)
            self.assertFalse(a.get_json()["meldung"]["aktiv"])
            befehle = [e["daten"] for e in self.ereignisse() if e["typ"] == "befehl"]
            self.assertFalse(befehle[0]["aktiv"])
            self.assertFalse(k.get("/api/scene").get_json()["meldung"]["aktiv"])

    def test_lehnt_ab(self):
        with self.app.test_client() as k:
            a = k.post("/api/meldung", json={"text": ""})
            self.assertEqual(a.status_code, 400)
            self.assertIn("text", a.get_json()["error"])
            self.assertFalse(self.c.config["meldung"]["aktiv"])

    def test_eine_abgelaufene_meldung_ist_in_der_szene_aus(self):
        self.c.config["meldung"] = P.pruefe_meldung({"text": "alt", "dauer_s": 60}, datetime(2020, 1, 1))
        with self.app.test_client() as k:
            self.assertFalse(k.get("/api/scene").get_json()["meldung"]["aktiv"])


class DieAnzeigeVersteht(unittest.TestCase):
    """Quelltext-Zusicherungen — es gibt keinen JS-Lauf."""

    def test_das_skript_hoert_auf_szene_und_befehl(self):
        js = (WURZEL / "static/anzeige/meldung.js").read_text(encoding="utf-8")
        self.assertIn("'lz-szene'", js)
        self.assertIn("'lz-befehl'", js)
        self.assertIn("'meldung'", js)
        self.assertIn("'schwarz'", js)
        self.assertIn("vorschau", js, "in der Vorschau keine Meldung ueber dem Editor")

    def test_die_anzeige_seite_bindet_anzeige_skripte_ein(self):
        html = (WURZEL / "templates/display.html").read_text(encoding="utf-8")
        self.assertIn("anzeige_skripte", html)

    def test_display_js_meldet_seine_ereignisse(self):
        js = (WURZEL / "static/display.js").read_text(encoding="utf-8")
        for typ in ("melde('befehl'", "melde('szene'", "melde('eintrag'"):
            self.assertIn(typ, js)


class ReviewFunde(unittest.TestCase):
    """Funde aus dem Code-Review von PR #27, je einer als Waechter."""

    def test_ein_zeitpunkt_mit_zeitzone_wird_ortszeit_und_stuerzt_nicht(self):
        # Vorher: `bis` mit `+02:00` kam durch die Pruefung, und der Vergleich
        # mit `datetime.now()` warf TypeError — nach dem Speichern, bei jedem
        # Laden. Die Station kam nicht mehr hoch.
        from datetime import timezone
        jetzt = datetime(2026, 9, 29, 12, 0)
        bis_utc = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
        m = P.pruefe_meldung({"text": "x", "bis": bis_utc.isoformat()}, jetzt)
        self.assertNotIn("+", m["bis"], "als Ortszeit ohne Zone abgelegt")
        self.assertEqual(m["bis"], bis_utc.astimezone().replace(tzinfo=None).isoformat(timespec="seconds"))
        self.assertIsInstance(P.meldung_gilt(m, jetzt), bool)
        # Ein alter Stand mit Zone in der Datei: heilen statt sterben.
        alt = dict(P.standard_meldung(), aktiv=True, text="x", bis="2026-09-29T10:00:00+02:00")
        self.assertIsInstance(P.heile_meldung(alt, jetzt)["aktiv"], bool)
        self.assertIsInstance(P.meldung_gilt(alt, jetzt), bool)

    def test_post_ohne_objekt_ist_400_nicht_500(self):
        c = main.Controller(frische_config())
        c.save_config = lambda: None
        c.ausloeser_faden = False
        with create_app(c).test_client() as k:
            for kaputt in ([], "text", 5):
                r = k.post("/api/meldung", json=kaputt)
                self.assertEqual(r.status_code, 400, kaputt)
                self.assertIn("Objekt", r.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

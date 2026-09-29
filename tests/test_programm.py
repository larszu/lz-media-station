"""Wochenprogramm (3.0, Welle 2): welches Layout eine Zone WANN spielt.

WARUM. Der Wochenplan sagt, ob die Station wach ist; das Programm sagt, was
sie zeigt. Was daran still kaputtgeht, wenn niemand hinsieht:

- ein Eintrag ueber Mitternacht, der nach 00:00 nicht mehr gilt (die
  Abendveranstaltung faellt genau in die Stunden, fuer die sie gemacht ist)
- zwei Eintraege gleicher Prioritaet, bei denen der falsche gewinnt
- ein Ausnahmetag, der das Programm nicht uebersteuert (Feiertag, Kneipe
  zeigt die Wochenkarte)
- ein Eintrag mit einem Layout, das es nicht mehr gibt — der Schirm darf
  dann nicht schwarz bleiben
- ein Programmwechsel zur vollen Stunde, den die Anzeige nicht erfaehrt

Die Uhrzeit wird HEREINGEREICHT (wie in test_zeitplan.py): 2026-09-14 ist ein
Montag.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import queue
import sys
import unittest
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import config_schema as cs  # noqa: E402
import main  # noqa: E402
import programm as P  # noqa: E402
from web_ui import create_app  # noqa: E402


def montag(stunde, minute=0):
    return datetime(2026, 9, 14, stunde, minute)


def dienstag(stunde, minute=0):
    return datetime(2026, 9, 15, stunde, minute)


def eintrag(**k):
    e = {"id": "e1", "name": "Eintrag", "layout_id": "menue", "zonen": [],
         "tage": ["mo"], "von": "09:00", "bis": "12:00", "prioritaet": 5,
         "gueltig_von": None, "gueltig_bis": None, "aktiv": True}
    e.update(k)
    return e


def frische_config():
    cfg = json.loads(json.dumps(main.DEFAULT_CONFIG))
    cfg["layouts"]["menue"] = {"name": "Menue", "vorlage": "vollbild", "hintergrund": "#000000",
                               "regionen": [{"id": "haupt", "name": "Haupt", "x": 0, "y": 0, "w": 100, "h": 100,
                                             "z": 0, "typ": "medien", "ton": True, "playlist": [],
                                             "shuffle": False, "einmal": False, "uebergang": "blende", "widget": {}}]}
    cfg["layouts"]["abend"] = json.loads(json.dumps(cfg["layouts"]["menue"]))
    cfg["layouts"]["abend"]["name"] = "Abend"
    return cfg


class DieAufloesung(unittest.TestCase):
    def test_ohne_eintrag_spielt_die_zone(self):
        self.assertEqual(P.aufloesen(P.standard_programm(), "near", montag(10)), (None, "zone", None))

    def test_ein_passender_eintrag_gewinnt(self):
        prog = {"eintraege": [eintrag()], "ausnahmen": []}
        lid, quelle, e = P.aufloesen(prog, "near", montag(10))
        self.assertEqual((lid, quelle, e["id"]), ("menue", "programm", "e1"))
        self.assertEqual(P.layout_jetzt(prog, "near", montag(12)), None, "12:00 ist schon zu")
        self.assertEqual(P.layout_jetzt(prog, "near", dienstag(10)), None, "Dienstag steht nicht drin")

    def test_ueber_mitternacht_gilt_der_eintrag_von_gestern(self):
        prog = {"eintraege": [eintrag(von="20:00", bis="02:00")], "ausnahmen": []}
        self.assertEqual(P.layout_jetzt(prog, "near", montag(23)), "menue")
        self.assertEqual(P.layout_jetzt(prog, "near", dienstag(1, 30)), "menue", "nach Mitternacht: Montags-Eintrag")
        self.assertIsNone(P.layout_jetzt(prog, "near", dienstag(2)))
        self.assertIsNone(P.layout_jetzt(prog, "near", montag(1)), "Sonntag stand nicht drin")

    def test_ende_24_00_ist_tagesende(self):
        prog = {"eintraege": [eintrag(von="18:00", bis="24:00")], "ausnahmen": []}
        self.assertEqual(P.layout_jetzt(prog, "near", montag(23, 59)), "menue")
        self.assertIsNone(P.layout_jetzt(prog, "near", dienstag(0)))

    def test_hoehere_prioritaet_gewinnt(self):
        prog = {"eintraege": [eintrag(id="a", layout_id="menue", prioritaet=3),
                              eintrag(id="b", layout_id="abend", prioritaet=7)], "ausnahmen": []}
        self.assertEqual(P.layout_jetzt(prog, "near", montag(10)), "abend")

    def test_bei_gleichstand_gewinnt_der_spaetere_beginn(self):
        # Eine Sonderschicht ueber einem Dauerprogramm — ohne die Prioritaet
        # anzufassen, soll sie sichtbar sein.
        prog = {"eintraege": [eintrag(id="tag", layout_id="menue", von="08:00", bis="20:00"),
                              eintrag(id="aktion", layout_id="abend", von="11:00", bis="13:00")], "ausnahmen": []}
        self.assertEqual(P.layout_jetzt(prog, "near", montag(12)), "abend")
        self.assertEqual(P.layout_jetzt(prog, "near", montag(14)), "menue")

    def test_zonen_und_inaktiv(self):
        prog = {"eintraege": [eintrag(zonen=["far"])], "ausnahmen": []}
        self.assertIsNone(P.layout_jetzt(prog, "near", montag(10)))
        self.assertEqual(P.layout_jetzt(prog, "far", montag(10)), "menue")
        prog = {"eintraege": [eintrag(aktiv=False)], "ausnahmen": []}
        self.assertIsNone(P.layout_jetzt(prog, "near", montag(10)))

    def test_gueltigkeit_nach_kalendertag(self):
        prog = {"eintraege": [eintrag(gueltig_von="2026-09-15")], "ausnahmen": []}
        self.assertIsNone(P.layout_jetzt(prog, "near", montag(10)), "gilt erst ab Dienstag")
        prog = {"eintraege": [eintrag(gueltig_bis="2026-09-13")], "ausnahmen": []}
        self.assertIsNone(P.layout_jetzt(prog, "near", montag(10)), "galt bis Sonntag")

    def test_ein_ausnahmetag_gewinnt_vor_allem(self):
        prog = {"eintraege": [eintrag(prioritaet=9)],
                "ausnahmen": [{"datum": "2026-09-14", "layout_id": "abend", "name": "Feiertag"}]}
        lid, quelle, a = P.aufloesen(prog, "near", montag(10))
        self.assertEqual((lid, quelle, a["name"]), ("abend", "ausnahme", "Feiertag"))
        # „Standard der Zone": an dem Tag gilt KEIN Programm.
        prog["ausnahmen"][0]["layout_id"] = None
        self.assertEqual(P.aufloesen(prog, "near", montag(10))[:2], (None, "ausnahme"))
        self.assertEqual(P.layout_jetzt(prog, "near", dienstag(10)), None, "Dienstag: kein Eintrag, keine Ausnahme")

    def test_das_raster_fasst_gleiche_abschnitte_zusammen(self):
        prog = {"eintraege": [eintrag()], "ausnahmen": []}
        teile = P.raster(prog, "near", montag(8), montag(13), 30)
        self.assertEqual([(t["von"][-5:], t["bis"][-5:], t["layout_id"]) for t in teile],
                         [("08:00", "09:00", None), ("09:00", "12:00", "menue"), ("12:00", "13:00", None)])


class SchreibwegUndLadeweg(unittest.TestCase):
    def test_pruefe_lehnt_ab_und_nennt_das_feld(self):
        for kaputt, feld in ((eintrag(von="25:00"), "eintraege[0]"),
                             (eintrag(tage=["xx"]), "tage"),
                             (eintrag(prioritaet=0), "prioritaet"),
                             (eintrag(prioritaet=True), "prioritaet"),
                             (eintrag(zonen=["oben"]), "zonen"),
                             (eintrag(von="10:00", bis="10:00"), "eintraege[0]"),
                             (eintrag(gueltig_von="2026-13-01"), "gueltig_von"),
                             (eintrag(gueltig_von="2026-09-20", gueltig_bis="2026-09-10"), "gueltig_bis"),
                             (eintrag(id="Gross"), "id"),
                             (eintrag(name=""), "name")):
            with self.assertRaises(ValueError, msg=str(kaputt)) as ctx:
                P.pruefe_programm({"eintraege": [kaputt], "ausnahmen": []})
            self.assertIn(feld, str(ctx.exception))

    def test_doppelte_kennung_und_doppelter_ausnahmetag(self):
        with self.assertRaises(ValueError) as ctx:
            P.pruefe_programm({"eintraege": [eintrag(), eintrag()], "ausnahmen": []})
        self.assertIn("gibt es schon", str(ctx.exception))
        with self.assertRaises(ValueError):
            P.pruefe_programm({"eintraege": [], "ausnahmen": [{"datum": "2026-01-01"}, {"datum": "2026-01-01"}]})

    def test_heile_wirft_nur_den_kaputten_eintrag_weg(self):
        prog = P.heile_programm({"eintraege": [eintrag(id="gut"), eintrag(id="kaputt", von="25:00")],
                                 "ausnahmen": [{"datum": "Ostern"}, {"datum": "2026-04-05", "name": "Ostern"}]})
        self.assertEqual([e["id"] for e in prog["eintraege"]], ["gut"])
        self.assertEqual([a["datum"] for a in prog["ausnahmen"]], ["2026-04-05"])

    def test_heile_vergibt_fehlende_kennungen_aus_dem_namen(self):
        prog = P.heile_programm({"eintraege": [eintrag(id=None, name="Speisekarte mittags")]})
        self.assertEqual(prog["eintraege"][0]["id"], "speisekarte-mittags")

    def test_die_vorgabe_ist_leer_und_liegt_in_der_konfiguration(self):
        self.assertEqual(cs.DEFAULT_CONFIG["programm"], {"eintraege": [], "ausnahmen": []})
        cfg = cs.heile_config({"programm": "Unsinn", "meldung": 5, "ausloeser": "nix"})
        self.assertEqual(cfg["programm"], P.standard_programm())
        self.assertEqual(cfg["meldung"], P.standard_meldung())
        self.assertEqual(cfg["ausloeser"], [])


class ImController(unittest.TestCase):
    """Die Regel haengt sich ueber `create_app` ein — der Kern kennt sie nicht."""

    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.c.ausloeser_faden = False
        self.app = create_app(self.c)
        self.c.config["programm"] = {"eintraege": [eintrag(tage=list(P.TAGE), von="00:00", bis="24:00")], "ausnahmen": []}

    def test_die_szene_spielt_das_layout_des_programms(self):
        self.c.active = True
        self.c.zone = "near"
        self.assertEqual(self.c.layout_fuer_zone("near", montag(10)), "menue")
        self.assertEqual(self.c.get_scene(jetzt=montag(10))["layout_id"], "menue")

    def test_ein_unbekanntes_layout_zaehlt_nicht(self):
        self.c.config["programm"]["eintraege"][0]["layout_id"] = "weg"
        self.assertEqual(self.c.layout_fuer_zone("near", montag(10)), "zone-near")

    def test_die_vorschau_ignoriert_das_programm(self):
        self.assertEqual(self.c.get_scene(layout_id="abend", zone="near", jetzt=montag(10))["layout_id"], "abend")

    def test_ein_programmwechsel_meldet_die_szene(self):
        # Ohne Zonenwechsel, ohne Start/Stopp: nur die Uhr ist weitergelaufen.
        # `melde_szene` liest die echte Uhr — deshalb ein Tag, der NIE heute
        # ist (sonst haengt der Test vom Wochentag ab, an dem er laeuft).
        nicht_heute = P.TAGE[(datetime.now().weekday() + 3) % 7]
        self.c.config["programm"]["eintraege"][0]["tage"] = [nicht_heute]
        self.c.active = True
        self.c.zone = "near"
        q = self.c.bus.abonnieren()
        self.c.melde_szene()
        q.get_nowait()
        self.c.melde_szene()
        self.assertTrue(q.empty(), "nichts geaendert, nichts gemeldet")
        self.c.config["programm"]["eintraege"][0]["tage"] = list(P.TAGE)
        self.c.melde_szene()
        self.assertEqual(q.get_nowait()["typ"], "scene")


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.c.ausloeser_faden = False
        self.app = create_app(self.c)

    def test_put_speichert_und_get_liest(self):
        with self.app.test_client() as k:
            a = k.put("/api/programm", json={"eintraege": [eintrag()], "ausnahmen": []})
            self.assertEqual(a.status_code, 200, a.get_json())
            self.assertEqual(k.get("/api/programm").get_json()["eintraege"][0]["id"], "e1")

    def test_put_lehnt_ab_und_nennt_das_feld(self):
        with self.app.test_client() as k:
            a = k.put("/api/programm", json={"eintraege": [eintrag(prioritaet=12)], "ausnahmen": []})
            self.assertEqual(a.status_code, 400)
            self.assertIn("prioritaet", a.get_json()["error"])
            a = k.put("/api/programm", json={"eintraege": [eintrag(layout_id="gibtsnicht")], "ausnahmen": []})
            self.assertEqual(a.status_code, 400)
            self.assertIn("gibt es nicht", a.get_json()["error"])
            self.assertEqual(self.c.config["programm"], P.standard_programm(), "nichts uebernommen")

    def test_put_meldet_config_und_szene(self):
        q = self.c.bus.abonnieren()
        with self.app.test_client() as k:
            k.put("/api/programm", json={"eintraege": [], "ausnahmen": []})
        typen = []
        while True:
            try:
                typen.append(q.get_nowait()["typ"])
            except queue.Empty:
                break
        self.assertIn("config", typen)
        self.assertIn("scene", typen)

    def test_jetzt_und_vorschau(self):
        with self.app.test_client() as k:
            k.put("/api/programm", json={"eintraege": [eintrag(tage=list(P.TAGE), von="00:00", bis="24:00")], "ausnahmen": []})
            j = k.get("/api/programm/jetzt").get_json()
            self.assertEqual(j["zonen"]["near"]["layout_id"], "menue")
            self.assertEqual(j["zonen"]["near"]["quelle"], "programm")
            v = k.get("/api/programm/vorschau?von=2026-09-14T00:00&bis=2026-09-14T06:00&zone=near&raster=60").get_json()
            self.assertEqual(len(v["abschnitte"]), 1)
            self.assertEqual(v["abschnitte"][0]["layout_id"], "menue")
            self.assertEqual(k.get("/api/programm/vorschau?von=kaputt").status_code, 400)
            self.assertEqual(k.get("/api/programm/vorschau?zone=oben").status_code, 400)


if __name__ == "__main__":
    unittest.main()

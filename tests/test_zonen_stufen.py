"""Drei Stufen statt zwei: fern -> mitte -> nah.

Das Herantreten wird damit zur Dramaturgie statt zum Schalter. Die Vorgabe
bleibt bei ZWEI Stufen — eine bestehende Installation verhaelt sich exakt wie
vorher.

WAS HIER BESONDERS ZAEHLT: die Zustandsmaschine wurde dabei ersetzt. Vorher
standen vier Faelle einzeln da (far/near/pending_near/pending_far); mit einer
dritten Stufe waeren daraus neun geworden. Jetzt gibt es EINE Regel: das Ziel
ergibt sich aus dem Abstand, und ein Wechsel gilt, wenn dasselbe Ziel
`delay_s` lang stabil war. Diese Tests halten fest, dass die alte Zusicherung
dabei erhalten blieb.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config_schema as cs  # noqa: E402
import main  # noqa: E402


def controller(stufen=2, nah=1.0, mitte=2.5):
    cfg = dict(main.DEFAULT_CONFIG)
    cfg["zonen_stufen"] = stufen
    cfg["threshold_m"] = nah
    cfg["threshold_mid_m"] = mitte
    return main.Controller(cfg)


class ZweiStufenVerhaltenSichWieFrueher(unittest.TestCase):
    def test_vorgabe_ist_zwei(self):
        self.assertEqual(main.DEFAULT_CONFIG["zonen_stufen"], 2)

    def test_nur_nah_und_fern_sind_aktiv(self):
        self.assertEqual(controller(2).zonen(), ("near", "far"))

    def test_nah_und_fern_wie_bisher(self):
        c = controller(2, nah=1.0)
        self.assertEqual(c.zone_fuer(0.5), "near")
        self.assertEqual(c.zone_fuer(1.0), "near", "die Schwelle gehoert zu nah")
        self.assertEqual(c.zone_fuer(1.01), "far")

    def test_die_mitte_kommt_bei_zwei_stufen_nie_vor(self):
        # Sie steht zwar in der Konfiguration (damit die Zuweisung beim
        # Umschalten nicht verloren geht), darf aber nie gewaehlt werden.
        c = controller(2, nah=1.0, mitte=2.5)
        for abstand in (0.1, 1.5, 2.0, 2.4, 3.0, 10.0):
            self.assertNotEqual(c.zone_fuer(abstand), "mid")

    def test_ohne_messung_gilt_fern(self):
        # Dieselbe Regel wie frueher: ohne Messung wird nicht ausgeloest.
        self.assertEqual(controller(2).zone_fuer(None), "far")

    def test_die_szene_nennt_nur_die_aktiven_zonen(self):
        szene = controller(2).get_scene()
        self.assertIn("near", szene)
        self.assertIn("far", szene)
        self.assertNotIn("mid", szene, "eine unbenutzte Zone gehoert nicht in die Szene")
        self.assertEqual(szene["zonen"], ["near", "far"])


class DreiStufen(unittest.TestCase):
    def setUp(self):
        self.c = controller(3, nah=1.0, mitte=2.5)

    def test_alle_drei_sind_aktiv(self):
        self.assertEqual(self.c.zonen(), ("near", "mid", "far"))

    def test_die_stufen_greifen_an_den_richtigen_stellen(self):
        self.assertEqual(self.c.zone_fuer(0.5), "near")
        self.assertEqual(self.c.zone_fuer(1.0), "near")
        self.assertEqual(self.c.zone_fuer(1.01), "mid")
        self.assertEqual(self.c.zone_fuer(2.5), "mid")
        self.assertEqual(self.c.zone_fuer(2.51), "far")

    def test_die_szene_bringt_die_mitte_mit(self):
        szene = self.c.get_scene()
        self.assertIn("mid", szene)
        self.assertEqual(szene["zonen"], ["near", "mid", "far"])

    def test_ohne_messung_gilt_weiterhin_fern(self):
        self.assertEqual(self.c.zone_fuer(None), "far")


class ZustandsText(unittest.TestCase):
    """`state` ist abgeleitet, nicht gespeichert — und behaelt die Form, die
    `/api/status` seit jeher nennt."""

    def test_gestoppt_ist_idle(self):
        self.assertEqual(controller().state, "idle")

    def test_laufend_nennt_die_zone(self):
        c = controller()
        c.active = True
        c.zone = "near"
        self.assertEqual(c.state, "near")

    def test_waehrend_der_hysterese_pending(self):
        c = controller()
        c.active = True
        c.zone = "far"
        c._kandidat = "near"
        self.assertEqual(c.state, "pending_near")

    def test_waehrend_der_hysterese_spielt_die_alte_zone_weiter(self):
        # DIE ZUSICHERUNG, die beim Umbau leicht verloren geht: der Kandidat
        # darf die Wiedergabe NICHT umschalten — sonst flackert genau das, was
        # die Verzoegerung verhindern soll.
        c = controller()
        c.active = True
        c.zone = "far"
        c._kandidat = "near"
        self.assertEqual(c.get_scene()["zone"], "far")

    def test_die_dritte_stufe_hat_auch_einen_pending_zustand(self):
        c = controller(3)
        c.active = True
        c.zone = "far"
        c._kandidat = "mid"
        self.assertEqual(c.state, "pending_mid")


class SchwellenKreuzbedingung(unittest.TestCase):
    """Wieder ein Fall, den KEIN Feld fuer sich sieht."""

    def test_mitte_muss_weiter_weg_sein_als_nah(self):
        with self.assertRaises(ValueError) as f:
            cs.pruefe_schwellen({"zonen_stufen": 3, "threshold_m": 3.0,
                                 "threshold_mid_m": 2.0}, {})
        self.assertIn("threshold_mid_m", str(f.exception))

    def test_bei_zwei_stufen_ist_die_mitte_egal(self):
        # Sie wird nicht benutzt — eine Meldung darueber waere nur Laerm.
        cs.pruefe_schwellen({"zonen_stufen": 2, "threshold_m": 3.0,
                             "threshold_mid_m": 2.0}, {})

    def test_geprueft_wird_der_zusammengefuehrte_stand(self):
        # Sonst rutscht es ueber zwei getrennte Anfragen durch: erst die
        # Nah-Schwelle hochsetzen, dann ist die Mitte ploetzlich kleiner.
        bestand = {"zonen_stufen": 3, "threshold_m": 1.0, "threshold_mid_m": 2.0}
        with self.assertRaises(ValueError):
            cs.pruefe_schwellen(bestand, {"threshold_m": 3.0})

    def test_heile_config_repariert_statt_abzubrechen(self):
        cfg = dict(main.DEFAULT_CONFIG)
        cfg.update({"zonen_stufen": 3, "threshold_m": 3.0, "threshold_mid_m": 2.0})
        geheilt = main.heile_config(cfg)
        self.assertLess(geheilt["threshold_m"], geheilt["threshold_mid_m"])


class UeberDieApi(unittest.TestCase):
    def app(self):
        from web_ui import create_app
        self.controller = main.Controller(dict(main.DEFAULT_CONFIG))
        self.controller.save_config = lambda: None
        return create_app(self.controller)

    def test_drei_stufen_lassen_sich_setzen(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "zonen_stufen": 3, "threshold_m": 1.0, "threshold_mid_m": 2.5})
            self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.zonen(), ("near", "mid", "far"))

    def test_verdrehte_schwellen_werden_abgelehnt(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "zonen_stufen": 3, "threshold_m": 3.0, "threshold_mid_m": 2.0})
            self.assertEqual(antwort.status_code, 400)
            self.assertIn("threshold_mid_m", antwort.get_json()["error"])

    def test_unsinnige_stufenzahl_wird_abgelehnt(self):
        with self.app().test_client() as c:
            self.assertEqual(
                c.post("/api/config", json={"zonen_stufen": 7}).status_code, 400)

    def test_medien_der_mitte_lassen_sich_zuweisen(self):
        app = self.app()
        with app.test_client() as c:
            antwort = c.post("/api/config", json={"mid": {"videos": ["m.mp4"]}})
            self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.config["mid"]["videos"], ["m.mp4"])

    def test_die_zustandspruefung_meldet_die_unbenutzte_mitte_nicht(self):
        # Sonst meldete jede gewoehnliche Station dauerhaft „Zone Mitte hat
        # keine Medien" — und ein Melder, der immer anschlaegt, wird ignoriert.
        app = self.app()   # Vorgabe: zwei Stufen
        with app.test_client() as c:
            themen = {b["thema"] for b in c.get("/api/health").get_json()["befunde"]}
        self.assertNotIn("zone_mid", themen)

    def test_bei_drei_stufen_wird_die_mitte_geprueft(self):
        app = self.app()
        self.controller.config["zonen_stufen"] = 3
        with app.test_client() as c:
            themen = {b["thema"] for b in c.get("/api/health").get_json()["befunde"]}
        self.assertIn("zone_mid", themen, "eine benutzte Zone ohne Medien gehoert gemeldet")


if __name__ == "__main__":
    unittest.main()

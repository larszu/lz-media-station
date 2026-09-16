"""Die Zeitsteuerung im Controller — greift sie dort, wo es zaehlt?

`tests/test_zeitplan.py` prueft die Rechnung. Hier geht es um die Verdrahtung:
ausserhalb der Oeffnungszeit darf die Anzeigeseite NICHTS zu spielen bekommen,
und zwar unabhaengig davon, ob die Steuerschleife gerade laeuft.

WARUM DAS EIN EIGENER TEST IST. Die Absicherung sitzt an zwei Stellen, und das
ist Absicht: die Schleife loest nicht aus, UND `get_scene()` gibt keine Zone
heraus. Faellt eine davon weg, merkt man es im Betrieb erst nachts — wenn
niemand hinsieht. Der Test haelt beide fest.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
import zeitplan  # noqa: E402


def config_mit_plan(aktiv, von="09:00", bis="18:00"):
    cfg = dict(main.DEFAULT_CONFIG)
    plan = zeitplan.standard_zeitplan()
    plan["aktiv"] = aktiv
    for tag in zeitplan.TAGE:
        plan["tage"][tag] = {"an": True, "von": von, "bis": bis}
    cfg["zeitplan"] = plan
    cfg["near"] = {"videos": ["a.mp4"], "images": [], "audio": []}
    cfg["far"] = {"videos": ["b.mp4"], "images": [], "audio": []}
    return cfg


MITTAGS = datetime(2026, 9, 14, 12, 0)     # Montag, innerhalb 09:00-18:00
NACHTS = datetime(2026, 9, 14, 3, 0)       # Montag, ausserhalb


class ControllerFragtDenPlan(unittest.TestCase):
    def test_innerhalb_ist_offen(self):
        c = main.Controller(config_mit_plan(True))
        self.assertTrue(c.ist_offen(MITTAGS))

    def test_ausserhalb_ist_zu(self):
        c = main.Controller(config_mit_plan(True))
        self.assertFalse(c.ist_offen(NACHTS))

    def test_ausgeschaltet_ist_immer_offen(self):
        c = main.Controller(config_mit_plan(False))
        self.assertTrue(c.ist_offen(NACHTS))


class GeschlossenGibtKeineZoneHeraus(unittest.TestCase):
    """Die zweite Absicherung: selbst bei laufendem Controller und
    passendem Zustand darf ausserhalb der Zeit keine Zone herauskommen."""

    def test_offen_liefert_eine_zone(self):
        c = main.Controller(config_mit_plan(False))   # Zeitsteuerung aus
        c.active = True
        c.state = "near"
        szene = c.get_scene()
        self.assertEqual(szene["zone"], "near")
        self.assertFalse(szene["geschlossen"])

    def test_geschlossen_liefert_keine_zone(self):
        # Der Kern: `state` sagt "near", der Plan sagt "zu" -- es darf nichts
        # gespielt werden. Sonst haette ein gestoppter Controller (dessen
        # Schleife nicht laeuft) nachts die alte Nah-Szene stehen lassen.
        plan = zeitplan.standard_zeitplan()
        plan["aktiv"] = True
        for tag in zeitplan.TAGE:
            plan["tage"][tag] = {"an": False, "von": "00:00", "bis": "24:00"}
        cfg = config_mit_plan(True)
        cfg["zeitplan"] = plan
        c = main.Controller(cfg)
        c.active = True
        c.state = "near"
        szene = c.get_scene()
        self.assertIsNone(szene["zone"], "ausserhalb der Zeit darf nichts spielen")
        self.assertTrue(szene["geschlossen"])

    def test_die_szene_nennt_den_zustand(self):
        # Die Anzeigeseite braucht das Flag, um schwarz zu bleiben, ohne einen
        # Hinweistext einzublenden.
        c = main.Controller(config_mit_plan(False))
        self.assertIn("geschlossen", c.get_scene())


class SchemaUndHeilung(unittest.TestCase):
    def test_vorgabe_hat_einen_plan_und_er_ist_aus(self):
        # Rueckwaertskompatibel: ohne Zutun verhaelt sich die Station wie
        # vorher.
        self.assertIn("zeitplan", main.DEFAULT_CONFIG)
        self.assertFalse(main.DEFAULT_CONFIG["zeitplan"]["aktiv"])

    def test_heile_config_repariert_einen_kaputten_plan(self):
        cfg = dict(main.DEFAULT_CONFIG)
        cfg["zeitplan"] = "jeden tag"
        geheilt = main.heile_config(cfg)
        self.assertEqual(set(geheilt["zeitplan"]["tage"]), set(zeitplan.TAGE))

    def test_heile_config_ergaenzt_einen_fehlenden_plan(self):
        cfg = {k: v for k, v in main.DEFAULT_CONFIG.items() if k != "zeitplan"}
        geheilt = main.heile_config(cfg)
        self.assertIn("zeitplan", geheilt)


class SchreibwegUeberDieApi(unittest.TestCase):
    def app(self, cfg=None):
        from web_ui import create_app
        return create_app(main.Controller(cfg or dict(main.DEFAULT_CONFIG)))

    def test_gueltiger_plan_wird_uebernommen(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "zeitplan": {"aktiv": True,
                             "tage": {"mo": {"an": True, "von": "09:00", "bis": "18:00"}}}})
            self.assertEqual(antwort.status_code, 200)
            self.assertTrue(antwort.get_json()["config"]["zeitplan"]["aktiv"])

    def test_kaputte_uhrzeit_wird_abgelehnt_mit_feldnamen(self):
        # Ablehnen statt heilen: wer eine Oeffnungszeit setzt, soll erfahren,
        # dass sie nicht angekommen ist.
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "zeitplan": {"aktiv": True,
                             "tage": {"mo": {"an": True, "von": "25:00", "bis": "18:00"}}}})
            self.assertEqual(antwort.status_code, 400)
            self.assertIn("mo", antwort.get_json()["error"])

    def test_status_nennt_den_zustand(self):
        with self.app().test_client() as c:
            self.assertIn("geschlossen", c.get("/api/status").get_json())


if __name__ == "__main__":
    unittest.main()

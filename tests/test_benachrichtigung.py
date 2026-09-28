"""Benachrichtigung (3.0): die Station meldet sich — aber nur bei einem Wechsel.

WARUM. Ein Melder, der alle 30 s „immer noch kaputt" schreibt, wird
stummgeschaltet und meldet dann auch den echten Ausfall nicht mehr. Was
hier gesichert wird:

- gemeldet wird der UEBERGANG, nicht der Zustand
- der erste Durchlauf nach dem Start meldet nichts (kein „Anzeige wieder da"
  bei jedem Neustart)
- die Konfiguration waehlt, was gemeldet wird; aus heisst aus
- ntfy bekommt Titel und Prioritaet, der Webhook JSON
- ein Netzfehler wird geloggt, nicht geworfen

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import sys
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import benachrichtigung as bn  # noqa: E402
import config_schema as cs  # noqa: E402
import main  # noqa: E402
from web_ui import create_app  # noqa: E402

JETZT = datetime(2026, 9, 28, 10, 0)


def ereignisse(nachrichten):
    return [n["ereignis"] for n in nachrichten]


class DerMelder(unittest.TestCase):
    def setUp(self):
        self.m = bn.Melder()

    def test_der_erste_durchlauf_meldet_nichts(self):
        self.assertEqual(self.m.pruefe(JETZT, "fehler", False, True), [])

    def test_stoerung_wird_beim_wechsel_gemeldet_nicht_bei_jedem_tick(self):
        self.m.pruefe(JETZT, "ok", True, True)
        self.assertEqual(ereignisse(self.m.pruefe(JETZT, "fehler", True, True)), ["gesundheit_fehler"])
        self.assertEqual(self.m.pruefe(JETZT, "fehler", True, True), [])
        self.assertEqual(ereignisse(self.m.pruefe(JETZT, "warnung", True, True)), ["gesundheit_ok"])

    def test_anzeige_verloren_und_zurueck(self):
        self.m.pruefe(JETZT, "ok", True, True)
        self.assertEqual(ereignisse(self.m.pruefe(JETZT, "ok", False, True)), ["anzeige_verloren"])
        self.assertEqual(ereignisse(self.m.pruefe(JETZT, "ok", True, True)), ["anzeige_zurueck"])

    def test_keine_anzeige_bekannt_ist_kein_wechsel(self):
        # None = niemand hat sich je gemeldet: das ist die Zustandspruefung,
        # kein Ereignis des Melders.
        self.m.pruefe(JETZT, "ok", None, True)
        self.assertEqual(self.m.pruefe(JETZT, "ok", None, True), [])

    def test_oeffnungszeit_beginnt_wird_einmal_gemeldet(self):
        self.m.pruefe(JETZT, "ok", True, False)
        self.assertEqual(ereignisse(self.m.pruefe(JETZT, "ok", True, True)), ["offline_ende"])
        self.assertEqual(self.m.pruefe(JETZT, "ok", True, True), [])
        # Schliessen meldet nichts — das ist der Plan, der seine Arbeit tut.
        self.assertEqual(self.m.pruefe(JETZT, "ok", True, False), [])

    def test_der_befundtext_steht_in_der_nachricht(self):
        self.m.pruefe(JETZT, "ok", True, True)
        n = self.m.pruefe(JETZT, "fehler", True, True, station="Foyer", befundtext="Platte voll")[0]
        self.assertEqual((n["station"], n["text"]), ("Foyer", "Platte voll"))


class DieKonfiguration(unittest.TestCase):
    def test_vorgabe_ist_aus_und_gueltig(self):
        self.assertFalse(bn.standard()["aktiv"])
        self.assertEqual(bn.pruefe(bn.standard())["ziel_typ"], "ntfy")
        self.assertIn("benachrichtigung", cs.DEFAULT_CONFIG)

    def test_pruefe_lehnt_ab_und_nennt_das_feld(self):
        for roh, feld in (({"aktiv": "ja"}, "aktiv"), ({"ziel_typ": "sms"}, "ziel_typ"),
                          ({"url": "ftp://x"}, "url"), ({"topic": "a b"}, "topic"),
                          ({"ereignisse": ["kaffee"]}, "ereignisse"),
                          ({"aktiv": True, "ziel_typ": "ntfy", "topic": ""}, "topic"),
                          ({"aktiv": True, "ziel_typ": "webhook", "url": ""}, "url")):
            with self.assertRaises(ValueError) as e:
                bn.pruefe(roh)
            self.assertIn(feld, str(e.exception))

    def test_heile_repariert_statt_zu_werfen(self):
        h = bn.heile({"aktiv": True, "ziel_typ": "sms", "url": "ftp://x", "topic": "a b"})
        self.assertEqual(h["ziel_typ"], "ntfy")
        self.assertEqual(h["url"], "https://ntfy.sh")
        self.assertEqual(h["topic"], "")
        self.assertFalse(h["aktiv"], "ohne Topic kann ntfy nicht senden — aktiv bleibt aus")
        self.assertEqual(bn.heile("unsinn"), bn.standard())

    def test_filtere_beachtet_aktiv_und_auswahl(self):
        n = [bn.nachricht("gesundheit_fehler", "S", "t", JETZT), bn.nachricht("offline_ende", "S", "t", JETZT)]
        self.assertEqual(bn.filtere({"aktiv": False, "ereignisse": list(bn.EREIGNISSE)}, n), [])
        self.assertEqual(ereignisse(bn.filtere({"aktiv": True, "ereignisse": ["offline_ende"]}, n)), ["offline_ende"])


class Antwort:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class DasSenden(unittest.TestCase):
    def test_ntfy_bekommt_titel_prioritaet_und_klartext(self):
        gesehen = {}
        def oeffne(req, timeout):
            gesehen.update(url=req.full_url, headers=dict(req.header_items()), body=req.data, timeout=timeout)
            return Antwort()
        n = bn.nachricht("gesundheit_fehler", "Foyer", "Platte voll", JETZT)
        ok = bn.sende({"ziel_typ": "ntfy", "url": "https://ntfy.sh", "topic": "foyer-1"}, n, oeffne=oeffne)
        self.assertTrue(ok)
        self.assertEqual(gesehen["url"], "https://ntfy.sh/foyer-1")
        self.assertEqual(gesehen["headers"]["Priority"], "4")
        self.assertIn(b"Platte voll", gesehen["body"])
        self.assertEqual(gesehen["timeout"], bn.ZEITLIMIT_S)

    def test_webhook_bekommt_json(self):
        gesehen = {}
        def oeffne(req, timeout):
            gesehen["json"] = json.loads(req.data.decode("utf-8"))
            gesehen["typ"] = req.get_header("Content-type")
            return Antwort()
        n = bn.nachricht("anzeige_zurueck", "Foyer", "da", JETZT)
        bn.sende({"ziel_typ": "webhook", "url": "https://example.org/hook"}, n, oeffne=oeffne)
        self.assertEqual(gesehen["json"]["ereignis"], "anzeige_zurueck")
        self.assertEqual(gesehen["typ"], "application/json")

    def test_ein_netzfehler_wird_nicht_geworfen(self):
        def oeffne(req, timeout):
            raise urllib.error.URLError("kein Netz")
        n = bn.nachricht("offline_ende", "S", "t", JETZT)
        self.assertFalse(bn.sende({"ziel_typ": "webhook", "url": "https://example.org"}, n, oeffne=oeffne))


class DerWaechter(unittest.TestCase):
    def test_einmal_sendet_nur_gewollte_uebergaenge(self):
        lage = {"stufe": "ok", "anzeige_online": True, "offen": True, "station": "S"}
        ziel = {"aktiv": True, "ziel_typ": "webhook", "url": "https://x", "ereignisse": ["gesundheit_fehler"]}
        gesendet = []
        w = bn.Waechter(lambda: lage, lambda: ziel, sende=lambda z, n: gesendet.append(n) or True,
                        uhr=lambda: JETZT)
        self.assertEqual(w.einmal(), 0)          # erster Durchlauf: nur merken
        lage["anzeige_online"] = False
        self.assertEqual(w.einmal(), 0)          # nicht gewollt
        lage["stufe"] = "fehler"
        self.assertEqual(w.einmal(), 1)
        self.assertEqual(gesendet[0]["ereignis"], "gesundheit_fehler")
        self.assertEqual(w.gesendet, 1)

    def test_ausgeschaltet_liest_er_die_lage_nicht_einmal(self):
        gelesen = []
        w = bn.Waechter(lambda: gelesen.append(1) or {}, lambda: {"aktiv": False})
        self.assertEqual(w.einmal(), 0)
        self.assertEqual(gelesen, [])

    def test_eine_kaputte_lage_toetet_den_faden_nicht(self):
        def lage():
            raise RuntimeError("Sensor weg")
        w = bn.Waechter(lage, lambda: {"aktiv": True, "ziel_typ": "webhook", "url": "https://x",
                                       "ereignisse": list(bn.EREIGNISSE)})
        self.assertEqual(w.einmal(), 0)


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
        self.controller.save_config = lambda: None
        self.controller.ohne_waechter = True     # kein Faden im Test
        self.app = create_app(self.controller)

    def test_lesen_und_setzen(self):
        with self.app.test_client() as c:
            d = c.get("/api/benachrichtigung").get_json()
            self.assertFalse(d["aktiv"])
            self.assertEqual(d["ereignisse_moeglich"], list(bn.EREIGNISSE))
            r = c.put("/api/benachrichtigung", json={"aktiv": True, "ziel_typ": "ntfy", "topic": "foyer"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.controller.config["benachrichtigung"]["topic"], "foyer")
            r = c.put("/api/benachrichtigung", json={"aktiv": True, "ziel_typ": "ntfy", "topic": ""})
            self.assertEqual(r.status_code, 400)
            self.assertIn("topic", r.get_json()["error"])

    def test_probenachricht_mit_unbrauchbarem_ziel_ist_400(self):
        with self.app.test_client() as c:
            r = c.post("/api/benachrichtigung/test", json={"ziel_typ": "webhook", "url": ""})
        self.assertEqual(r.status_code, 400)

    def test_eine_alte_sicherung_ohne_benachrichtigung_wird_geheilt(self):
        with self.app.test_client() as c:
            r = c.post("/api/restore", json={"system_name": "Alt"})
            self.assertEqual(r.status_code, 200)
        self.assertEqual(self.controller.config["benachrichtigung"], bn.standard())


if __name__ == "__main__":
    unittest.main()

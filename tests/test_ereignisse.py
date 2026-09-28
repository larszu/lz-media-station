"""Ereignisse (SSE, 3.0): die Anzeige erfaehrt eine neue Szene sofort.

WARUM. Zweimal je Sekunde `/api/scene` zu fragen war Last ohne Gegenwert und
trotzdem langsam: eine Zuweisung im Admin erschien erst beim naechsten Poll.
Der Bus schickt die Szene, wenn sie feststeht. Was daran still kaputtgeht:

- ein Zonenwechsel, der niemandem gemeldet wird (die Anzeige bleibt stehen)
- ein Abonnent, der nicht liest und den Kern wachsen laesst
- ein Befehl (`/api/befehl`), der auf ein Layout zeigt, das es nicht gibt

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import queue
import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import ereignisse  # noqa: E402
import main  # noqa: E402
from web_ui import create_app  # noqa: E402


def frische_config():
    return json.loads(json.dumps(main.DEFAULT_CONFIG))


class DerBus(unittest.TestCase):
    def test_jeder_abonnent_bekommt_jedes_ereignis(self):
        bus = ereignisse.Ereignisbus()
        a, b = bus.abonnieren(), bus.abonnieren()
        bus.senden("scene", {"zone": "near"})
        self.assertEqual(a.get_nowait()["daten"], {"zone": "near"})
        self.assertEqual(b.get_nowait()["typ"], "scene")
        bus.abmelden(a)
        self.assertEqual(bus.anzahl, 1)

    def test_ein_abonnent_der_nicht_liest_laesst_den_kern_nicht_wachsen(self):
        bus = ereignisse.Ereignisbus()
        q = bus.abonnieren()
        for i in range(ereignisse.WARTESCHLANGE + 50):
            bus.senden("status", i)
        self.assertEqual(q.qsize(), ereignisse.WARTESCHLANGE)

    def test_die_form_ist_die_von_eventsource(self):
        zeile = ereignisse.formatiere("befehl", {"typ": "reload"})
        self.assertEqual(zeile, 'event: befehl\ndata: {"typ": "reload"}\n\n')

    def test_der_strom_liefert_ereignis_und_status(self):
        bus = ereignisse.Ereignisbus()
        bus_strom = ereignisse.strom(bus, status=lambda: {"distance": 1.0}, intervall_s=0.01)
        self.assertTrue(next(bus_strom).startswith(":"))          # verbunden
        bus.senden("scene", {"zone": "far"})
        self.assertIn("event: scene", next(bus_strom))
        self.assertIn("event: status", next(bus_strom))          # nach dem Intervall
        bus_strom.close()
        self.assertEqual(bus.anzahl, 0, "das Abonnement endet mit der Verbindung")

    def test_ohne_status_kommt_ein_puls(self):
        bus = ereignisse.Ereignisbus()
        zeit = [0.0]
        s = ereignisse.strom(bus, intervall_s=0.01, heartbeat_s=0.0, uhr=lambda: zeit[0])
        next(s)
        zeit[0] = 100.0
        self.assertEqual(next(s), ": puls\n\n")
        s.close()


class DerController(unittest.TestCase):
    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.q = self.c.bus.abonnieren()

    def alle(self):
        heraus = []
        while True:
            try:
                heraus.append(self.q.get_nowait())
            except queue.Empty:
                return heraus

    def test_start_und_stopp_melden_die_szene(self):
        self.c.start()
        self.c.stop()
        typen = [e["typ"] for e in self.alle()]
        self.assertGreaterEqual(typen.count("scene"), 2)

    def test_ohne_wechsel_wird_nicht_gemeldet(self):
        self.c.melde_szene()
        self.alle()
        self.c.melde_szene()
        self.c.melde_szene()
        self.assertEqual(self.alle(), [])

    def test_eine_konfigurationsaenderung_meldet_config_und_szene(self):
        self.alle()
        self.c.melde_config()
        typen = [e["typ"] for e in self.alle()]
        self.assertEqual(typen, ["config", "scene"])


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.controller = main.Controller(frische_config())
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)

    def test_api_config_schickt_die_neue_szene(self):
        q = self.controller.bus.abonnieren()
        with self.app.test_client() as c:
            c.post("/api/config", json={"far": {"videos": ["f.mp4"]}})
        typen = []
        while True:
            try:
                typen.append(q.get_nowait()["typ"])
            except queue.Empty:
                break
        self.assertIn("config", typen)
        self.assertIn("scene", typen)

    def test_api_events_ist_ein_ereignisstrom(self):
        with self.app.test_client() as c:
            antwort = c.get("/api/events", buffered=False)
            self.assertEqual(antwort.mimetype, "text/event-stream")
            erste = next(antwort.response)
            self.assertTrue(erste.decode().startswith(":"))
            antwort.close()

    def test_befehl_wird_an_alle_anzeigen_gereicht(self):
        q = self.controller.bus.abonnieren()
        with self.app.test_client() as c:
            a = c.post("/api/befehl", json={"typ": "zeige_layout", "layout_id": "zone-far", "dauer_s": 10})
            self.assertEqual(a.status_code, 200)
            self.assertEqual(a.get_json()["empfaenger"], 1)
        e = q.get_nowait()
        self.assertEqual(e["typ"], "befehl")
        self.assertEqual(e["daten"], {"typ": "zeige_layout", "layout_id": "zone-far", "dauer_s": 10})

    def test_befehl_lehnt_unsinn_ab(self):
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/befehl", json={"typ": "explodiere"}).status_code, 400)
            self.assertEqual(c.post("/api/befehl", json={"typ": "zeige_layout", "layout_id": "nix"}).status_code, 404)
            self.assertEqual(c.post("/api/befehl", json={"typ": "zeige_layout", "layout_id": "zone-near",
                                                          "dauer_s": -1}).status_code, 400)
            self.assertEqual(c.post("/api/befehl", json={"typ": "reload"}).status_code, 200)


class DieAnzeigeLeitetNichtMehrUm(unittest.TestCase):
    """Quelltext-Zusicherungen fuer display.js — es gibt keinen JS-Lauf."""

    def setUp(self):
        self.js = (WURZEL / "static/display.js").read_text(encoding="utf-8")

    def test_der_einzige_weg_zum_admin_ist_esc(self):
        # Bis 3.0 sprang die Seite bei leerer Zone oder kaputtem Video nach
        # /admin — ein Schirm im Foyer zeigte dann die Verwaltung.
        self.assertEqual(self.js.count("window.location.href = '/admin'"), 1)
        self.assertNotIn("scheduleAdminRedirect", self.js)

    def test_ereignisse_zuerst_polling_als_rueckfall(self):
        self.assertIn("new EventSource('/api/events')", self.js)
        self.assertIn("setInterval(hole, 5000)", self.js)
        self.assertNotIn("setInterval(poll, 500)", self.js)

    def test_regionen_und_widgets(self):
        self.assertIn("LZ_WIDGETS", self.js)
        self.assertIn("'zeige_layout'", self.js)
        self.assertIn("vorschau", self.js)

    def test_die_verwaltung_hoert_auch_zu(self):
        app_js = (WURZEL / "static/app.js").read_text(encoding="utf-8")
        self.assertIn("new EventSource('/api/events?status=1')", app_js)
        self.assertNotIn("setInterval(fetchStatus, 500)", app_js)


if __name__ == "__main__":
    unittest.main()

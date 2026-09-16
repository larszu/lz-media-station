"""Tests fuer den Gleichtakt mehrerer Stationen (`sync.py`).

Eine Videowand aus drei Schirmen braucht nicht drei Sensoren — drei Sensoren
nebeneinander schalten nie gleichzeitig. Stattdessen folgt eine Station der
anderen.

Die Netz-Schleife selbst wird nicht getestet (sie braucht einen zweiten
laufenden Server und `time.sleep`). Geprueft wird, was im Betrieb entscheidet:
das Veralten ohne Kontakt, die Verdrahtung im Controller und der Endpunkt.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config_schema as cs  # noqa: E402
import gesundheit  # noqa: E402
import main  # noqa: E402
import sync  # noqa: E402


def follower_mit(zone, alter_s=0.0, geschlossen=False):
    f = sync.SyncFollower("192.168.1.50")
    f._zone = zone
    f._geschlossen = geschlossen
    f._empfangen_at = time.monotonic() - alter_s
    return f


class KeinKontaktHeisstKeinWert(unittest.TestCase):
    """Dieselbe Regel wie beim Sensor — und aus demselben Grund."""

    def test_vor_dem_ersten_kontakt_keine_zone(self):
        self.assertIsNone(sync.SyncFollower("192.168.1.50").zone)

    def test_frischer_wert_gilt(self):
        self.assertEqual(follower_mit("near").zone, "near")

    def test_alter_wert_gilt_nicht_mehr(self):
        # Ein abgerissenes Netzkabel darf nicht aussehen wie ein Besucher, der
        # sich nicht vom Fleck ruehrt.
        f = follower_mit("near", alter_s=sync.STALE_AFTER_S + 0.5)
        self.assertIsNone(f.zone)

    def test_die_grenze_ist_grosszuegiger_als_der_takt(self):
        # Ein einzelner Aussetzer im WLAN darf die Szene nicht abraeumen.
        self.assertGreater(sync.STALE_AFTER_S, sync.INTERVALL_S * 3)

    def test_ein_aussetzer_innerhalb_der_grenze_gilt_weiter(self):
        self.assertEqual(follower_mit("near", alter_s=sync.STALE_AFTER_S - 0.5).zone, "near")


class Aufbau(unittest.TestCase):
    def test_url_wird_gebaut(self):
        f = sync.SyncFollower("pi-zwei.local", port=5001)
        self.assertEqual(f.url, "http://pi-zwei.local:5001/api/sync")

    def test_laeuft_als_daemon(self):
        self.assertTrue(sync.SyncFollower("x").daemon)

    def test_ohne_taktgeber_wird_nichts_erfunden(self):
        f = sync.SyncFollower("")
        f.run()
        self.assertIsNone(f.zone)
        self.assertIn("kein Taktgeber", f.status)

    def test_es_gibt_eine_zeitgrenze(self):
        # Ohne sie blockierte ein haengender Taktgeber den Thread ueber den
        # Ablauf hinaus — und der Wert gaelte laenger als er duerfte.
        self.assertLess(sync.ZEITGRENZE_S, sync.STALE_AFTER_S)


class ControllerFolgt(unittest.TestCase):
    def controller(self, rolle="follower", host="192.168.1.50"):
        cfg = dict(main.DEFAULT_CONFIG)
        cfg["sync_rolle"] = rolle
        cfg["sync_master"] = host
        return main.Controller(cfg)

    def test_ohne_rolle_gibt_es_keinen_follower(self):
        # Vorgabe: alles bleibt wie bisher.
        self.assertEqual(main.DEFAULT_CONFIG["sync_rolle"], "aus")
        self.assertIsNone(self.controller(rolle="aus").follower)

    def test_mit_rolle_wird_einer_gebaut(self):
        c = self.controller()
        self.assertIsInstance(c.follower, sync.SyncFollower)
        self.assertEqual(c.follower.host, "192.168.1.50")

    def test_die_betriebsruhe_wird_uebernommen(self):
        # Sonst spielte eine Wand nachts zur Haelfte weiter, weil nur eine der
        # Stationen einen Zeitplan hat.
        c = self.controller()
        c.follower = follower_mit("near", geschlossen=True)
        self.assertFalse(c.ist_offen())

    def test_ohne_betriebsruhe_gilt_der_eigene_plan(self):
        c = self.controller()
        c.follower = follower_mit("near", geschlossen=False)
        self.assertTrue(c.ist_offen())


class Endpunkt(unittest.TestCase):
    def app(self):
        from web_ui import create_app
        self.controller = main.Controller(dict(main.DEFAULT_CONFIG))
        self.controller.save_config = lambda: None
        return create_app(self.controller)

    def test_jede_station_gibt_takt(self):
        # Genau deshalb gibt es keine „master"-Rolle einzustellen.
        app = self.app()
        self.controller.active = True
        self.controller.zone = "near"
        with app.test_client() as c:
            d = c.get("/api/sync").get_json()
        self.assertEqual(d["zone"], "near")
        self.assertIn("geschlossen", d)
        self.assertIn("zonen", d)

    def test_die_antwort_bleibt_schmal(self):
        # Der Follower fragt mehrmals je Sekunde; die ganze Szene mitzusenden
        # waere Last ohne Gegenwert.
        with self.app().test_client() as c:
            d = c.get("/api/sync").get_json()
        self.assertEqual(set(d), {"zone", "geschlossen", "zonen", "name"})

    def test_rolle_und_taktgeber_lassen_sich_setzen(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "sync_rolle": "follower", "sync_master": "192.168.1.50"})
            self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.config["sync_rolle"], "follower")

    def test_unsinnige_rolle_wird_abgelehnt(self):
        with self.app().test_client() as c:
            self.assertEqual(
                c.post("/api/config", json={"sync_rolle": "chef"}).status_code, 400)

    def test_es_gibt_keine_master_rolle(self):
        # Deklarative Konfiguration, die nichts bewirkt, ist schlimmer als
        # keine — irgendwann verlaesst sich jemand darauf.
        _typ, erlaubt, _text = cs.GRENZEN["sync_rolle"]
        self.assertFalse(erlaubt("master"))


class ZustandspruefungBeimFolgen(unittest.TestCase):
    def pruefe(self, **ueber):
        argumente = dict(
            config=dict(main.DEFAULT_CONFIG),
            sensor_ok=False, sensor_status="kein Sensor",
            freier_platz_b=50 * 1024 ** 3,
            vorhandene={"videos": set(), "images": set(), "audio": set()},
            aktiv=True, geschlossen=False,
            zonen=[("near", "Nah")],
        )
        argumente.update(ueber)
        return {b["thema"] for b in gesundheit.pruefe(**argumente)}

    def test_ohne_kontakt_wird_gemeldet(self):
        themen = self.pruefe(sync_ok=False, sync_status="kein Kontakt zu x")
        self.assertIn("sync", themen)

    def test_mit_kontakt_ist_ruhe(self):
        self.assertNotIn("sync", self.pruefe(sync_ok=True))

    def test_beim_folgen_wird_der_eigene_sensor_nicht_gemeldet(self):
        # DER KERN: ein Follower wertet seinen Sensor gar nicht aus. Ihn zu
        # melden waere ein Dauerfehler ohne Ursache — und ein Melder, der
        # immer anschlaegt, wird ignoriert.
        self.assertNotIn("sensor", self.pruefe(sync_ok=True))

    def test_ohne_gleichtakt_wird_der_sensor_sehr_wohl_gemeldet(self):
        # Die Gegenprobe: `sync_ok=None` heisst „eigener Sensor".
        self.assertIn("sensor", self.pruefe(sync_ok=None))


if __name__ == "__main__":
    unittest.main()

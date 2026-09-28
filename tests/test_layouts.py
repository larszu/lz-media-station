"""Layouts, Regionen und Playlists (3.0) — Schema, Migration, Spiegel, API.

WARUM. Bis 3.0 kannte eine Zone drei Listen und spielte sie im Vollbild.
Ein Layout teilt den Schirm in Regionen mit eigenen, gemischten Playlists.
Drei Dinge daran gehen still kaputt, wenn niemand hinsieht:

1. **Die Migration.** Eine `config.json` von vor 3.0 traegt ihre Videos in
   der Zone. Beim ersten Start muessen sie im Zonen-Layout landen — sonst
   steht die Station nach dem Update mit leerem Schirm in der Ausstellung.

2. **Der Spiegel.** Der Manager und alte Skripte schicken weiterhin
   `{"near": {"videos": [...]}}`. Das muss in der Hauptregion ankommen, und
   die Zone muss danach dasselbe sagen wie das Layout.

3. **Die Gueltigkeit.** Ein Eintrag mit `bis` gestern darf heute nicht mehr
   ausgeliefert werden — gefiltert an der Quelle, nicht im Browser.

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

import config_schema as cs  # noqa: E402
import layouts as L  # noqa: E402
import main  # noqa: E402
from web_ui import create_app  # noqa: E402


def frische_config():
    return json.loads(json.dumps(main.DEFAULT_CONFIG))


class Schema(unittest.TestCase):
    def test_eine_frische_station_hat_je_zone_ein_leeres_vollbild_layout(self):
        cfg = frische_config()
        for zone in ("near", "mid", "far"):
            layout = cfg["layouts"]["zone-" + zone]
            self.assertEqual(len(layout["regionen"]), 1)
            self.assertEqual(layout["regionen"][0]["playlist"], [])
            self.assertEqual(cs.standard_zone()["layout"], "")

    def test_pruefe_item_lehnt_ab_und_nennt_das_feld(self):
        with self.assertRaises(ValueError) as e:
            L.pruefe_item({"typ": "web", "url": "ftp://x"})
        self.assertIn("url", str(e.exception))
        with self.assertRaises(ValueError) as e:
            L.pruefe_item({"typ": "image", "name": "a.jpg", "dauer_s": 0})
        self.assertIn("dauer_s", str(e.exception))
        with self.assertRaises(ValueError) as e:
            L.pruefe_item({"typ": "video", "name": "a.mp4", "von": "2026-02-01", "bis": "2026-01-01"})
        self.assertIn("von/bis", str(e.exception))

    def test_heile_item_verwirft_unsinn_statt_zu_werfen(self):
        self.assertIsNone(L.heile_item({"typ": "video"}))
        item = L.heile_item({"typ": "image", "name": "a.jpg", "dauer_s": "lang", "von": "gestern"})
        self.assertEqual(item["dauer_s"], None)
        self.assertEqual(item["von"], None)

    def test_region_darf_nicht_ueber_den_schirm_ragen(self):
        with self.assertRaises(ValueError):
            L.pruefe_region({"id": "r", "x": 60, "w": 50})
        # Ladeweg: eingekuerzt statt weggeworfen.
        r = L.heile_region({"id": "r", "x": 60, "w": 50}, "ersatz")
        self.assertAlmostEqual(r["x"] + r["w"], 100.0)

    def test_layout_grenzen(self):
        with self.assertRaises(ValueError):
            L.pruefe_layout({"name": "x", "regionen": [{"id": "a"}] * (L.MAX_REGIONEN + 1)})
        with self.assertRaises(ValueError) as e:
            L.pruefe_layout({"name": "x", "regionen": [{"id": "a"}, {"id": "a"}]})
        self.assertIn("doppelt", str(e.exception))
        with self.assertRaises(ValueError):
            L.pruefe_layout({"name": "x", "hintergrund": "rot"})

    def test_vorlagen_belegen_regionen_vor(self):
        self.assertEqual(len(L.vorlage_regionen("vollbild")), 1)
        self.assertEqual(len(L.vorlage_regionen("geteilt")), 2)
        self.assertEqual(len(L.vorlage_regionen("l-form")), 3)
        self.assertEqual(L.vorlage_regionen("frei"), [])
        for v in L.VORLAGEN:
            for r in L.vorlage_regionen(v):
                L.pruefe_region(r)  # jede Vorlage ist selbst gueltig

    def test_kennung_aus_name(self):
        self.assertEqual(L.kennung_aus_name("Foyer links"), "foyer-links")
        self.assertEqual(L.kennung_aus_name("Übersicht Küche"), "uebersicht-kueche")
        self.assertEqual(L.kennung_aus_name("Foyer", vergeben={"foyer"}), "foyer-2")
        self.assertEqual(L.kennung_aus_name("???"), "layout")


class Migration(unittest.TestCase):
    def setUp(self):
        self._orig = main.CONFIG_FILE
        self._tmp = tempfile.TemporaryDirectory()
        main.CONFIG_FILE = os.path.join(self._tmp.name, "config.json")

    def tearDown(self):
        main.CONFIG_FILE = self._orig
        self._tmp.cleanup()

    def schreibe(self, obj):
        with open(main.CONFIG_FILE, "w") as f:
            json.dump(obj, f)

    def test_alte_zonenlisten_wandern_ins_zonen_layout(self):
        # Eine config.json von vor 3.0: kein `layouts`, Listen in der Zone.
        self.schreibe({"near": {"videos": ["a.mp4"], "images": ["b.jpg"],
                                "bildzeiten": {"b.jpg": 12}, "shuffle": True},
                       "far": {"videos": ["c.mp4"]}})
        cfg = main.load_config()
        region = cfg["layouts"]["zone-near"]["regionen"][0]
        self.assertEqual([i["name"] for i in region["playlist"]], ["a.mp4", "b.jpg"])
        self.assertEqual(region["playlist"][1]["dauer_s"], 12.0)
        self.assertTrue(region["shuffle"])
        self.assertEqual(cfg["layouts"]["zone-far"]["regionen"][0]["playlist"][0]["name"], "c.mp4")
        # Und der Spiegel sagt dasselbe.
        self.assertEqual(cfg["near"]["videos"], ["a.mp4"])
        self.assertEqual(cfg["near"]["bildzeiten"], {"b.jpg": 12.0})

    def test_das_layout_ist_die_wahrheit_wenn_es_eins_gibt(self):
        cfg = frische_config()
        cfg["layouts"]["zone-near"]["regionen"][0]["playlist"] = [
            {"typ": "video", "name": "neu.mp4"}]
        cfg["near"]["videos"] = ["veraltet.mp4"]   # ein veralteter Spiegel
        self.schreibe(cfg)
        geladen = main.load_config()
        self.assertEqual(geladen["near"]["videos"], ["neu.mp4"])

    def test_zone_mit_unbekanntem_layout_faellt_auf_die_vorgabe(self):
        cfg = frische_config()
        cfg["near"]["layout"] = "gibt-es-nicht"
        self.schreibe(cfg)
        geladen = main.load_config()
        self.assertEqual(geladen["near"]["layout"], "")
        self.assertEqual(L.layout_id_der_zone(geladen, "near"), "zone-near")

    def test_ein_kaputtes_layout_verhindert_den_start_nicht(self):
        cfg = frische_config()
        cfg["layouts"]["kaputt"] = "kein objekt"
        cfg["layouts"]["Gross"] = {"name": "x"}   # ungueltige Kennung
        self.schreibe(cfg)
        geladen = main.load_config()
        self.assertEqual(geladen["layouts"]["kaputt"]["regionen"], [])
        self.assertNotIn("Gross", geladen["layouts"])

    def test_save_config_schreibt_atomar(self):
        c = main.Controller(frische_config())
        c.save_config()
        self.assertTrue(os.path.isfile(main.CONFIG_FILE))
        self.assertFalse(os.path.exists(main.CONFIG_FILE + ".tmp"))
        with open(main.CONFIG_FILE) as f:
            self.assertIn("layouts", json.load(f))


class SpiegelUndSchreibweg(unittest.TestCase):
    def test_alte_listen_landen_in_der_hauptregion(self):
        cfg = frische_config()
        L.schreibe_zonen_teil(cfg, "near", {"videos": ["a.mp4", "b.mp4"], "images": ["c.jpg"]})
        region = cfg["layouts"]["zone-near"]["regionen"][0]
        self.assertEqual([i["name"] for i in region["playlist"]], ["a.mp4", "b.mp4", "c.jpg"])
        self.assertEqual(cfg["near"]["videos"], ["a.mp4", "b.mp4"])

    def test_ein_patch_behaelt_die_gueltigkeit_der_eintraege(self):
        cfg = frische_config()
        region = cfg["layouts"]["zone-near"]["regionen"][0]
        region["playlist"] = [{"typ": "video", "name": "a.mp4", "dauer_s": None,
                               "von": "2026-01-01", "bis": "2030-01-01"},
                              {"typ": "web", "url": "https://example.org", "dauer_s": 20}]
        L.spiegle_zone(cfg, "near")
        # Ein alter Manager sortiert um — die Gueltigkeit bleibt, die Webseite auch.
        L.schreibe_zonen_teil(cfg, "near", {"videos": ["a.mp4"], "images": []})
        self.assertEqual(region["playlist"][0]["von"], "2026-01-01")
        self.assertEqual(region["playlist"][-1]["typ"], "web")

    def test_audio_bleibt_bei_der_zone(self):
        cfg = frische_config()
        L.schreibe_zonen_teil(cfg, "far", {"audio": ["x.mp3"]})
        self.assertEqual(cfg["far"]["audio"], ["x.mp3"])
        self.assertEqual(cfg["layouts"]["zone-far"]["regionen"][0]["playlist"], [])

    def test_entfernen_trifft_alle_layouts_und_die_mitte(self):
        cfg = frische_config()
        for zone in ("near", "mid", "far"):
            L.schreibe_zonen_teil(cfg, zone, {"videos": ["weg.mp4", "bleibt.mp4"]})
        cfg["layouts"]["extra"] = L.standard_layout("Extra")
        cfg["layouts"]["extra"]["regionen"][0]["playlist"] = [{"typ": "video", "name": "weg.mp4"}]
        self.assertTrue(L.entferne_datei(cfg, "videos", "weg.mp4"))
        for zone in ("near", "mid", "far"):
            self.assertEqual(cfg[zone]["videos"], ["bleibt.mp4"], zone)
        self.assertEqual(cfg["layouts"]["extra"]["regionen"][0]["playlist"], [])

    def test_abgelaufene_eintraege_werden_nicht_ausgeliefert(self):
        layout = L.standard_layout("x")
        layout["regionen"][0]["playlist"] = [
            {"typ": "image", "name": "immer.jpg", "von": None, "bis": None},
            {"typ": "image", "name": "vorbei.jpg", "von": None, "bis": "2026-01-31"},
            {"typ": "image", "name": "spaeter.jpg", "von": "2027-01-01", "bis": None},
            {"typ": "image", "name": "heute.jpg", "von": "2026-06-01", "bis": "2026-06-01"},
        ]
        namen = [i["name"] for i in L.filtere_layout(layout, "2026-06-01")["regionen"][0]["playlist"]]
        self.assertEqual(namen, ["immer.jpg", "heute.jpg"])


class Zustandspruefung(unittest.TestCase):
    def test_eine_fehlende_datei_in_der_seitenleiste_wird_gemeldet(self):
        import gesundheit
        cfg = frische_config()
        cfg["layouts"]["zone-near"] = L.standard_layout("Nah", "geteilt")
        cfg["layouts"]["zone-near"]["regionen"][1]["playlist"] = [{"typ": "image", "name": "fehlt.jpg"}]
        cfg["layouts"]["zone-near"]["regionen"][0]["playlist"] = [{"typ": "video", "name": "da.mp4"}]
        L.spiegle_zone(cfg, "near")
        befunde = gesundheit.pruefe(
            cfg, sensor_ok=True, sensor_status="", freier_platz_b=10 ** 12,
            vorhandene={"videos": {"da.mp4"}, "images": set(), "audio": set()},
            aktiv=True, geschlossen=False)
        themen = {b["thema"] for b in befunde}
        self.assertIn("medien_near", themen)
        self.assertNotIn("zone_near", themen)

    def test_ein_widget_ist_inhalt(self):
        import gesundheit
        cfg = frische_config()
        cfg["layouts"]["zone-near"] = L.standard_layout("Nah", "ticker")
        cfg["layouts"]["zone-near"]["regionen"][0]["playlist"] = [{"typ": "video", "name": "a.mp4"}]
        cfg["layouts"]["zone-far"]["regionen"][0]["playlist"] = [{"typ": "web", "url": "https://x.org"}]
        befunde = gesundheit.pruefe(
            cfg, sensor_ok=True, sensor_status="", freier_platz_b=10 ** 12,
            vorhandene={"videos": {"a.mp4"}, "images": set(), "audio": set()},
            aktiv=True, geschlossen=False)
        self.assertEqual([b for b in befunde if b["thema"].startswith("zone_")], [])


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.controller = main.Controller(frische_config())
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)

    def test_layouts_anlegen_aendern_duplizieren_loeschen(self):
        with self.app.test_client() as c:
            a = c.post("/api/layouts", json={"name": "Foyer links", "vorlage": "geteilt"})
            self.assertEqual(a.status_code, 201)
            lid = a.get_json()["id"]
            self.assertEqual(lid, "foyer-links")
            self.assertEqual(len(c.get("/api/layouts/" + lid).get_json()["layout"]["regionen"]), 2)

            layout = c.get("/api/layouts/" + lid).get_json()["layout"]
            layout["regionen"][0]["playlist"] = [{"typ": "web", "url": "https://example.org", "dauer_s": 15}]
            self.assertEqual(c.put("/api/layouts/" + lid, json=layout).status_code, 200)
            self.assertEqual(self.controller.config["layouts"][lid]["regionen"][0]["playlist"][0]["url"],
                             "https://example.org")

            k = c.post("/api/layouts/" + lid + "/duplizieren")
            self.assertEqual(k.status_code, 201)
            self.assertEqual(k.get_json()["layout"]["name"], "Foyer links (Kopie)")

            self.assertEqual(c.delete("/api/layouts/" + lid).status_code, 200)
            self.assertEqual(c.get("/api/layouts/" + lid).status_code, 404)

    def test_ein_gespieltes_layout_laesst_sich_nicht_loeschen(self):
        with self.app.test_client() as c:
            self.assertEqual(c.delete("/api/layouts/zone-near").status_code, 409)
            c.post("/api/layouts", json={"name": "Extra", "id": "extra"})
            c.post("/api/config", json={"far": {"layout": "extra"}})
            self.assertEqual(c.delete("/api/layouts/extra").status_code, 409)
            c.post("/api/config", json={"far": {"layout": ""}})
            self.assertEqual(c.delete("/api/layouts/extra").status_code, 200)

    def test_schreibweg_lehnt_ab_und_nennt_das_feld(self):
        with self.app.test_client() as c:
            a = c.put("/api/layouts/zone-near", json={"name": "x", "regionen": [{"id": "r", "x": 90, "w": 20}]})
            self.assertEqual(a.status_code, 400)
            self.assertIn("regionen[0]", a.get_json()["error"])
            a = c.post("/api/config", json={"near": {"layout": "gibt-es-nicht"}})
            self.assertEqual(a.status_code, 400)
            self.assertIn("layout", a.get_json()["error"])
            self.assertEqual(c.post("/api/layouts", json={"name": ""}).status_code, 400)

    def test_alte_zonenlisten_kommen_ueber_api_config_an(self):
        # Der Manager schickt weiterhin die Listen — so muss es ankommen.
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/config", json={"mid": {"videos": ["m.mp4"]}}).status_code, 200)
        region = self.controller.config["layouts"]["zone-mid"]["regionen"][0]
        self.assertEqual(region["playlist"][0]["name"], "m.mp4")
        self.assertEqual(self.controller.config["mid"]["videos"], ["m.mp4"])

    def test_die_szene_traegt_das_layout_der_aktiven_zone(self):
        with self.app.test_client() as c:
            c.post("/api/config", json={"far": {"videos": ["f.mp4"]}})
        self.controller.active = True
        szene = self.controller.get_scene()
        self.assertEqual(szene["zone"], "far")
        self.assertEqual(szene["layout_id"], "zone-far")
        self.assertEqual(szene["layout"]["regionen"][0]["playlist"][0]["name"], "f.mp4")
        self.assertEqual(szene["far"]["layout"], "zone-far")   # aufgeloest, nicht leer

    def test_die_szene_filtert_nach_datum(self):
        region = self.controller.config["layouts"]["zone-far"]["regionen"][0]
        region["playlist"] = [{"typ": "image", "name": "alt.jpg", "bis": "2020-01-01"},
                              {"typ": "image", "name": "neu.jpg"}]
        self.controller.active = True
        namen = [i["name"] for i in self.controller.get_scene()["layout"]["regionen"][0]["playlist"]]
        self.assertEqual(namen, ["neu.jpg"])

    def test_vorschau_zeigt_ein_layout_ohne_sensor(self):
        with self.app.test_client() as c:
            c.post("/api/layouts", json={"name": "Probe", "id": "probe", "vorlage": "l-form"})
            szene = c.get("/api/scene?layout=probe&zone=near&zeit=2026-06-01T10:00").get_json()
            self.assertTrue(szene["vorschau"])
            self.assertTrue(szene["active"])
            self.assertEqual(szene["zone"], "near")
            self.assertEqual(szene["layout_id"], "probe")
            self.assertEqual(len(szene["layout"]["regionen"]), 3)
            self.assertEqual(c.get("/api/scene?layout=nix").status_code, 404)
            self.assertEqual(c.get("/api/scene?layout=probe&zeit=gestern").status_code, 400)

    def test_eine_alte_sicherung_wird_migriert(self):
        alt = {"system_name": "Alt", "near": {"videos": ["a.mp4"], "images": [], "audio": []},
               "far": {"videos": [], "images": ["b.jpg"], "audio": ["c.mp3"]}}
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/restore", json=alt).status_code, 200)
        cfg = self.controller.config
        self.assertEqual(cfg["layouts"]["zone-near"]["regionen"][0]["playlist"][0]["name"], "a.mp4")
        self.assertEqual(cfg["layouts"]["zone-far"]["regionen"][0]["playlist"][0]["name"], "b.jpg")
        self.assertEqual(cfg["far"]["audio"], ["c.mp3"])

    def test_loeschen_einer_datei_trifft_auch_die_mitte(self):
        # Hier stand `for zone in ("near", "far")`, und die Mitte behielt die Datei.
        with self.app.test_client() as c:
            c.post("/api/config", json={"mid": {"videos": ["m.mp4"]}, "near": {"videos": ["m.mp4"]}})
            a = c.delete("/api/media/videos/m.mp4")
            self.assertTrue(a.get_json()["removed_from_zones"])
        self.assertEqual(self.controller.config["mid"]["videos"], [])
        self.assertEqual(self.controller.config["near"]["videos"], [])

    def test_die_version_kommt_aus_der_einen_datei(self):
        version = (WURZEL / "VERSION").read_text(encoding="utf-8").strip()
        with self.app.test_client() as c:
            self.assertEqual(c.get("/api/identity").get_json()["version"], version)
            self.assertEqual(c.get("/api/status").get_json()["version"], version)
        quelle = (WURZEL / "web_ui.py").read_text(encoding="utf-8")
        self.assertNotIn('"version": "2.', quelle, "die Version steht wieder als Text im Code")


class Erweiterungspunkte(unittest.TestCase):
    """Welle 2 legt nur Dateien hin — das muss so bleiben."""

    def test_admin_bindet_zusatzkarten_und_module_ein(self):
        html = (WURZEL / "templates/admin.html").read_text(encoding="utf-8")
        self.assertIn("zusatz_templates", html)
        self.assertIn("module_skripte", html)
        self.assertIn("i18n_extra", html)
        display = (WURZEL / "templates/display.html").read_text(encoding="utf-8")
        self.assertIn("anzeige_skripte", display)
        self.assertIn('id="buehne"', display)

    def test_blueprints_werden_automatisch_registriert(self):
        c = main.Controller(frische_config())
        c.save_config = lambda: None
        app = create_app(c)
        regeln = {r.rule for r in app.url_map.iter_rules()}
        self.assertIn("/api/layouts", regeln)
        self.assertIn("/api/layouts/vorlagen", regeln)
        self.assertNotIn("api_layouts", (WURZEL / "web_ui.py").read_text(encoding="utf-8"),
                         "web_ui.py soll die Erweiterung nicht beim Namen kennen")

    def test_i18n_kern_mischt_zusatzwoerterbuecher(self):
        js = (WURZEL / "static/i18n.js").read_text(encoding="utf-8")
        self.assertIn("LZ_I18N_EN_EXTRA", js)
        self.assertTrue((WURZEL / "static/i18n/layouts.en.js").is_file())


if __name__ == "__main__":
    unittest.main()

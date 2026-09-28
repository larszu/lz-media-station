"""Puls und Screenshot der Anzeigeseiten (3.0, api_anzeige.py).

WARUM. Der Kern glaubte bis 3.0, er spiele — ob irgendwo ein Schirm das
zeigte, wusste niemand. Jetzt meldet sich jede Anzeigeseite alle 10 s. Was
daran still kaputtgehen kann:

- eine Anzeige, die sich nie gemeldet hat, sieht aus wie eine, die gerade
  online ist (Zusammenfassung, Befund der Zustandspruefung)
- die Vorschau im Editor zaehlt als Schirm im Foyer
- ein riesiges Bild fuellt den Speicher des Pi
- `anfordern` wartet ewig, wenn kein Bild kommt

Lauf: `python3 -m unittest discover -s tests -v`
"""
import base64
import json
import sys
import threading
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import api_anzeige as A  # noqa: E402
import gesundheit  # noqa: E402
import main  # noqa: E402
from web_ui import create_app  # noqa: E402

PIXEL = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 20).decode()


class Uhr:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def puls(kennung="a1", **rest):
    d = {"kennung": kennung, "layout_id": "zone-near", "zone": "near", "vorschau": False,
         "regionen": [{"id": "haupt", "typ": "medien", "idx": 0, "item": {"typ": "video", "name": "film.mp4"}}],
         "fehler": []}
    d.update(rest)
    return d


class DasRegister(unittest.TestCase):
    def setUp(self):
        self.uhr = Uhr()
        self.reg = A.Anzeigenregister(uhr=self.uhr)

    def test_ohne_puls_gibt_es_keine_anzeige(self):
        z = self.reg.zusammenfassung()
        self.assertEqual(z, {"anzahl": 0, "online": 0, "alter_s": None})
        self.assertIsNone(self.reg.online())

    def test_eine_anzeige_ist_online_solange_der_puls_frisch_ist(self):
        self.reg.puls("a1", puls(), "192.168.1.20")
        self.assertEqual(self.reg.zusammenfassung()["online"], 1)
        self.uhr.t += A.OFFLINE_S + 1
        z = self.reg.zusammenfassung()
        self.assertEqual((z["anzahl"], z["online"]), (1, 0))
        self.assertGreater(z["alter_s"], A.OFFLINE_S)
        self.assertFalse(self.reg.online())

    def test_die_vorschau_im_editor_zaehlt_nicht_als_schirm(self):
        self.reg.puls("v1", puls(vorschau=True))
        self.assertEqual(self.reg.zusammenfassung()["anzahl"], 0)
        # ... steht aber in der Liste, damit man sie sieht.
        self.assertEqual(self.reg.liste()[0]["vorschau"], True)

    def test_die_liste_nennt_was_je_region_laeuft(self):
        self.reg.puls("a1", puls(fehler=["TypeError x", "y"] * 4))
        a = self.reg.liste()[0]
        self.assertEqual(a["regionen"][0]["item"]["name"], "film.mp4")
        self.assertEqual(len(a["fehler"]), A.FEHLER_MAX)
        self.assertTrue(a["online"])

    def test_unbrauchbare_kennung_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            self.reg.puls("", puls())
        with self.assertRaises(ValueError):
            self.reg.puls("a b", puls())

    def test_alte_anzeigen_fallen_aus_der_liste(self):
        self.reg.puls("a1", puls())
        self.uhr.t += A.VERGESSEN_S + 1
        self.reg.puls("a2", puls())
        self.assertEqual([a["kennung"] for a in self.reg.liste()], ["a2"])

    def test_screenshot_wird_abgelegt_und_der_juengste_geliefert(self):
        self.reg.bild_ablegen("a1", (b"alt", "image/jpeg"))
        self.uhr.t += 5
        self.reg.bild_ablegen("a2", (b"neu", "image/jpeg"))
        self.assertEqual(self.reg.bild()[0][0], b"neu")
        self.assertEqual(self.reg.bild("a1")[0][0], b"alt")
        self.assertIsNone(self.reg.bild("gibtsnicht"))

    def test_warte_auf_bild_endet_ohne_bild_nach_der_frist(self):
        self.assertIsNone(self.reg.warte_auf_bild(self.uhr.t, 0.05))

    def test_warte_auf_bild_weckt_auf_wenn_eins_kommt(self):
        ab = self.uhr.t
        def spaeter():
            self.uhr.t += 1
            self.reg.bild_ablegen("a1", (b"jpg", "image/jpeg"))
        threading.Timer(0.05, spaeter).start()
        bild = self.reg.warte_auf_bild(ab, 2.0)
        self.assertIsNotNone(bild)
        self.assertEqual(bild[0][0], b"jpg")


class DataUrl(unittest.TestCase):
    def test_png_und_jpeg_werden_verstanden(self):
        daten, typ = A.dataurl_zu_bytes(PIXEL)
        self.assertEqual(typ, "image/png")
        self.assertTrue(daten.startswith(b"\x89PNG"))

    def test_alles_andere_wird_abgelehnt(self):
        for roh in ("text", "data:text/html;base64,PGI+", "data:image/svg+xml;base64,PHN2Zz4=",
                    "data:image/png;base64,***", None):
            with self.assertRaises(ValueError):
                A.dataurl_zu_bytes(roh)

    def test_ein_riesiges_bild_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            A.dataurl_zu_bytes("data:image/jpeg;base64," + "A" * (A.SCREENSHOT_MAX_B + 10))


class Bildschirmaufnahme(unittest.TestCase):
    def test_ohne_grafische_sitzung_wird_nichts_versucht(self):
        aufrufe = []
        def lauf(*a, **k):
            aufrufe.append(a)
        self.assertIsNone(A.bildschirm_aufnehmen(which=lambda n: "/usr/bin/" + n, umgebung={}, lauf=lauf))
        self.assertEqual(aufrufe, [])

    def test_grim_wird_unter_wayland_genommen(self):
        class R:
            returncode, stdout = 0, b"\xff\xd8jpeg"
        ergebnis = A.bildschirm_aufnehmen(which=lambda n: "/usr/bin/grim" if n == "grim" else None,
                                          umgebung={"WAYLAND_DISPLAY": "wayland-0"},
                                          lauf=lambda *a, **k: R())
        self.assertEqual(ergebnis, (b"\xff\xd8jpeg", "image/jpeg"))

    def test_ein_scheiterndes_werkzeug_gibt_none(self):
        class R:
            returncode, stdout = 1, b""
        self.assertIsNone(A.bildschirm_aufnehmen(which=lambda n: "/x", umgebung={"WAYLAND_DISPLAY": "w"},
                                                 lauf=lambda *a, **k: R()))


class Zustandspruefung(unittest.TestCase):
    def pruefe(self, anzeige, **rest):
        args = dict(config={"near": {"videos": ["a.mp4"]}, "far": {"videos": ["b.mp4"]}},
                    sensor_ok=True, sensor_status="ok", freier_platz_b=10 ** 12,
                    vorhandene={"videos": {"a.mp4", "b.mp4"}}, aktiv=True, geschlossen=False,
                    anzeige=anzeige)
        args.update(rest)
        return {b["thema"]: b for b in gesundheit.pruefe(**args)}

    def test_ohne_register_kein_befund(self):
        # None = niemand sammelt Puls (alter Kern, Test): wie vor 3.0.
        self.assertNotIn("anzeige", self.pruefe(None))

    def test_nie_gemeldet_ist_ein_befund(self):
        self.assertEqual(self.pruefe({"anzahl": 0, "online": 0, "alter_s": None})["anzeige"]["stufe"], "warnung")

    def test_puls_zu_alt_ist_ein_befund_mit_der_zeit_im_text(self):
        b = self.pruefe({"anzahl": 1, "online": 0, "alter_s": 95.0})["anzeige"]
        self.assertIn("95 s", b["text"])

    def test_frischer_puls_ist_kein_befund(self):
        self.assertNotIn("anzeige", self.pruefe({"anzahl": 1, "online": 1, "alter_s": 4.0}))

    def test_nachts_oder_gestoppt_ist_keine_anzeige_kein_befund(self):
        self.assertNotIn("anzeige", self.pruefe({"anzahl": 0, "online": 0, "alter_s": None}, geschlossen=True))
        self.assertNotIn("anzeige", self.pruefe({"anzahl": 0, "online": 0, "alter_s": None}, aktiv=False))

    def test_systemwerte_heiss_und_knapp(self):
        befunde = self.pruefe(None, system={"temp_c": 82.0, "ram_frei_mb": 50, "ram_gesamt_mb": 1000,
                                             "last_1m": 9.0, "kerne": 4})
        self.assertEqual(befunde["temperatur"]["stufe"], "fehler")
        self.assertIn("speicher", befunde)
        self.assertIn("last", befunde)

    def test_systemwerte_ohne_werte_melden_nichts(self):
        self.assertEqual(set(self.pruefe(None, system=gesundheit.systemwerte(thermal_glob="/nirgends/*",
                                                                             meminfo="/nirgends")).keys())
                         - {"last"}, set())


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)

    def test_puls_erscheint_in_liste_status_und_zustand(self):
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/anzeige/puls", json=puls()).status_code, 200)
            liste = c.get("/api/anzeige").get_json()
            self.assertEqual(liste["online"], 1)
            self.assertIn("system", liste)
            self.assertEqual(c.get("/api/status").get_json()["anzeige"]["anzahl"], 1)

    def test_ohne_puls_meldet_der_zustand_die_fehlende_anzeige(self):
        self.controller.active = True
        with self.app.test_client() as c:
            themen = {b["thema"] for b in c.get("/api/health").get_json()["befunde"]}
        self.assertIn("anzeige", themen)

    def test_puls_ohne_kennung_ist_400(self):
        with self.app.test_client() as c:
            self.assertEqual(c.post("/api/anzeige/puls", json={"regionen": []}).status_code, 400)

    def test_screenshot_ablegen_und_holen(self):
        with self.app.test_client() as c:
            self.assertEqual(c.get("/api/anzeige/screenshot").status_code, 404)
            r = c.post("/api/anzeige/screenshot", json={"kennung": "a1", "bild": PIXEL})
            self.assertEqual(r.status_code, 200)
            bild = c.get("/api/anzeige/screenshot?kennung=a1")
            self.assertEqual(bild.status_code, 200)
            self.assertEqual(bild.mimetype, "image/png")
            self.assertIn("X-LZ-Zeit", bild.headers)

    def test_anfordern_ohne_zuhoerer_ist_409(self):
        with self.app.test_client() as c:
            r = c.post("/api/anzeige/screenshot/anfordern", json={})
        self.assertEqual(r.status_code, 409)

    def test_anfordern_wartet_nur_bis_zur_frist(self):
        q = self.controller.bus.abonnieren()   # jemand hoert zu, liefert aber nichts
        with self.app.test_client() as c:
            r = c.post("/api/anzeige/screenshot/anfordern", json={"timeout_s": 0.1})
        self.assertEqual(r.status_code, 504)
        self.assertEqual(q.get_nowait()["daten"], {"typ": "screenshot"})

    def test_anfordern_liefert_das_frische_bild(self):
        self.controller.bus.abonnieren()
        def liefere():
            with self.app.test_client() as c2:
                c2.post("/api/anzeige/screenshot", json={"kennung": "a9", "bild": PIXEL})
        threading.Timer(0.05, liefere).start()
        with self.app.test_client() as c:
            r = c.post("/api/anzeige/screenshot/anfordern", json={"timeout_s": 2})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["kennung"], "a9")


if __name__ == "__main__":
    unittest.main()

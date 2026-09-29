"""Ausloeser (3.0, Welle 2): wenn … dann …

WARUM. Ein Webhook ohne Token-Pruefung ist eine Fernbedienung fuer jeden im
Netz; ein Zeit-Ausloeser, der je Tick feuert, blendet die Durchsage 240-mal je
Minute ein; ein Taster am Pin des Sensors macht beide tot. Und ein Ausloeser,
der schiefgeht, darf die Wiedergabe nicht anhalten. Das alles ist ohne
Hardware pruefbar — die GPIO-Fabrik wird hereingereicht.

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

import ausloeser as A  # noqa: E402
import main  # noqa: E402
from web_ui import create_app  # noqa: E402


def frische_config():
    return json.loads(json.dumps(main.DEFAULT_CONFIG))


def ausloeser(**k):
    e = {"id": "a1", "name": "Test", "aktiv": True,
         "quelle": {"typ": "webhook", "token": ""},
         "aktion": {"typ": "zeige_layout", "layout_id": "zone-far", "dauer_s": 30}}
    e.update(k)
    return e


class DasSchema(unittest.TestCase):
    def test_gueltige_eintraege_kommen_durch(self):
        liste = A.pruefe_ausloeser([
            ausloeser(),
            ausloeser(id="t", quelle={"typ": "taster", "pin": 27}, aktion={"typ": "display_aus"}),
            ausloeser(id="z", quelle={"typ": "zeit", "tage": ["mo"], "zeit": "18:00"}, aktion={"typ": "stop"}),
            ausloeser(id="v", quelle={"typ": "video_ende", "datei": "film.mp4"}, aktion={"typ": "zurueck"}),
            ausloeser(id="n", quelle={"typ": "zone", "zone": "near"},
                      aktion={"typ": "meldung", "text": "Willkommen", "dauer_s": 10}),
        ], frische_config())
        self.assertEqual(len(liste), 5)
        self.assertEqual(liste[4]["aktion"]["farbe"], "#B04A3F", "Vorgabe ergaenzt")

    def test_lehnt_ab_und_nennt_das_feld(self):
        for kaputt, feld in ((ausloeser(quelle={"typ": "funk"}), "quelle.typ"),
                             (ausloeser(aktion={"typ": "explodiere"}), "aktion.typ"),
                             (ausloeser(quelle={"typ": "taster", "pin": 99}), "pin"),
                             (ausloeser(quelle={"typ": "zeit", "tage": ["mo"], "zeit": "25:00"}), "zeit"),
                             (ausloeser(quelle={"typ": "zone", "zone": "oben"}), "zone"),
                             (ausloeser(aktion={"typ": "zeige_layout"}), "layout_id"),
                             (ausloeser(aktion={"typ": "meldung", "text": ""}), "text"),
                             (ausloeser(quelle={"typ": "webhook", "token": "mit leerzeichen"}), "token"),
                             (ausloeser(id="_intern"), "id")):
            with self.assertRaises(ValueError, msg=str(kaputt)) as ctx:
                A.pruefe_ausloeser([kaputt])
            self.assertIn(feld, str(ctx.exception))

    def test_ein_taster_am_pin_des_sensors_wird_abgelehnt(self):
        cfg = frische_config()   # sensor_type auto: Trigger 23, Echo 24
        with self.assertRaises(ValueError) as ctx:
            A.pruefe_ausloeser([ausloeser(quelle={"typ": "taster", "pin": 24})], cfg)
        self.assertIn("gpio_echo", str(ctx.exception))
        # Bei einer Kamera-Station sind die Pins frei.
        cfg["sensor_type"] = "camera"
        A.pruefe_ausloeser([ausloeser(quelle={"typ": "taster", "pin": 24})], cfg)
        # Zwei Taster am selben Pin: der zweite wird genannt.
        with self.assertRaises(ValueError) as ctx:
            A.pruefe_ausloeser([ausloeser(id="a", quelle={"typ": "taster", "pin": 5}),
                                ausloeser(id="b", quelle={"typ": "taster", "pin": 5})], cfg)
        self.assertIn("ausloeser[1]", str(ctx.exception))

    def test_heile_wirft_nur_den_kaputten_weg(self):
        liste = A.heile_ausloeser([ausloeser(id="gut"), ausloeser(id="kaputt", quelle={"typ": "funk"}),
                                   ausloeser(id="kollision", quelle={"typ": "taster", "pin": 23})], frische_config())
        self.assertEqual([e["id"] for e in liste], ["gut"])
        self.assertEqual(A.heile_ausloeser("Unsinn"), [])


class DieMaschine(unittest.TestCase):
    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.meldungen = []
        self.m = A.Ausloeser(self.c, meldung_setzen=self.meldungen.append, gpio=self.fabrik)
        self.knoepfe = {}
        self.q = self.c.bus.abonnieren()

    def fabrik(self, pin, when_pressed):
        self.knoepfe[pin] = when_pressed
        klasse = self

        class Knopf:
            def close(self):
                klasse.knoepfe.pop(pin, None)
        return Knopf()

    def befehle(self):
        heraus = []
        while True:
            try:
                e = self.q.get_nowait()
            except queue.Empty:
                return heraus
            if e["typ"] == "befehl":
                heraus.append(e["daten"])

    def test_webhook_mit_und_ohne_token(self):
        self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "webhook", "token": "geheim"})]
        self.assertEqual(self.m.webhook("a1", "falsch")[0], 403)
        self.assertEqual(self.befehle(), [], "abgelehnt heisst: nichts passiert")
        status, _ = self.m.webhook("a1", "geheim")
        self.assertEqual(status, 200)
        self.assertEqual(self.befehle()[0], {"typ": "zeige_layout", "layout_id": "zone-far", "dauer_s": 30})
        self.assertEqual(self.m.webhook("gibtsnicht", "")[0], 404)
        self.c.config["ausloeser"][0]["aktiv"] = False
        self.assertEqual(self.m.webhook("a1", "geheim")[0], 409)
        protokoll = self.m.protokoll()
        self.assertEqual(protokoll[0]["anlass"], "Webhook")
        self.assertIn("abgelehnt", protokoll[-1]["ergebnis"])

    def test_zeit_feuert_einmal_je_minute(self):
        self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "zeit", "tage": ["mo"], "zeit": "18:00"},
                                                aktion={"typ": "stop"})]
        montag = datetime(2026, 9, 14, 18, 0, 5)
        self.c.active = True
        for sekunde in range(0, 60, 15):
            self.m.tick(montag.replace(second=sekunde))
        self.assertEqual(len(self.m.protokoll()), 1, "vier Ticks in derselben Minute, eine Ausloesung")
        self.m.tick(datetime(2026, 9, 15, 18, 0))
        self.assertEqual(len(self.m.protokoll()), 1, "Dienstag steht nicht drin")
        self.m.tick(datetime(2026, 9, 21, 18, 0))
        self.assertEqual(len(self.m.protokoll()), 2, "naechster Montag: wieder")

    def test_zonenwechsel_feuert(self):
        self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "zone", "zone": "near"},
                                                aktion={"typ": "meldung", "text": "Willkommen", "dauer_s": 5,
                                                        "farbe": "#000000", "textfarbe": "#FFFFFF", "ton": False,
                                                        "untertext": ""})]
        self.c.active = True
        self.m.tick(datetime.now())            # merkt sich „far"
        self.c.zone = "near"
        self.m.tick(datetime.now())
        self.assertEqual(len(self.meldungen), 1)
        self.assertEqual(self.meldungen[0]["text"], "Willkommen")
        self.c.zone = "far"
        self.m.tick(datetime.now())
        self.assertEqual(len(self.meldungen), 1, "nur der Wechsel ZU near")

    def test_video_ende_filtert_nach_datei(self):
        self.c.config["ausloeser"] = [ausloeser(id="alle", quelle={"typ": "video_ende", "datei": "", "region": ""},
                                                aktion={"typ": "zurueck"}),
                                      ausloeser(id="film", quelle={"typ": "video_ende", "datei": "film.mp4", "region": ""},
                                                aktion={"typ": "zurueck"})]
        self.assertEqual(self.m.video_ende("anderes.mp4", "haupt"), ["alle"])
        self.assertEqual(self.m.video_ende("film.mp4", "haupt"), ["alle", "film"])
        self.assertTrue(self.m.hat_quelle("video_ende"))

    def test_schirm_schwarz_und_an(self):
        self.c.config["ausloeser"] = [ausloeser(id="aus", aktion={"typ": "display_aus"}),
                                      ausloeser(id="an", aktion={"typ": "display_an"})]
        self.m.feuere("aus")
        self.assertTrue(self.m.schwarz)
        self.assertIn({"typ": "schwarz", "an": True}, self.befehle())
        self.m.feuere("an")
        self.assertFalse(self.m.schwarz)

    def test_taster_werden_geoeffnet_und_geschlossen(self):
        self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "taster", "pin": 27})]
        self.m.synchronisiere_taster()
        self.assertIn(27, self.knoepfe)
        self.knoepfe[27]()                      # gedrueckt
        self.assertEqual(self.befehle()[0]["typ"], "zeige_layout")
        self.assertIn("Taster BCM 27", self.m.protokoll()[0]["anlass"])
        self.c.config["ausloeser"] = []
        self.m.synchronisiere_taster()
        self.assertEqual(self.knoepfe, {})

    def test_ohne_gpio_sagt_die_maschine_das(self):
        m = A.Ausloeser(self.c, gpio=None)
        if m._fabrik() is None:                 # kein gpiozero auf diesem Rechner (CI, Mac)
            self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "taster", "pin": 27})]
            m.synchronisiere_taster()
            self.assertIn("gpiozero", m.taster_status[27])

    def test_ein_kaputter_ausloeser_haelt_nichts_an(self):
        self.c.config["ausloeser"] = [ausloeser(aktion={"typ": "meldung", "text": "x"})]
        m = A.Ausloeser(self.c, meldung_setzen=None)
        self.assertIn("keine Sofortmeldung", m.feuere("a1"))
        self.c.config["ausloeser"][0]["aktion"] = {"typ": "zeige_layout", "layout_id": "weg"}
        self.assertIn("gibt es nicht", m.feuere("a1"))
        self.assertEqual(self.befehle(), [])


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.c.ausloeser_faden = False
        self.app = create_app(self.c)

    def test_put_get_test_und_webhook(self):
        with self.app.test_client() as k:
            a = k.put("/api/ausloeser", json=[ausloeser(quelle={"typ": "webhook", "token": "geheim"})])
            self.assertEqual(a.status_code, 200, a.get_json())
            self.assertEqual(k.get("/api/ausloeser").get_json()["ausloeser"][0]["id"], "a1")
            self.assertEqual(k.post("/api/trigger/a1").status_code, 403)
            self.assertEqual(k.post("/api/trigger/a1", headers={"X-LZ-Token": "geheim"}).status_code, 200)
            self.assertEqual(k.post("/api/trigger/a1?token=geheim").status_code, 200)
            self.assertEqual(k.post("/api/trigger/a1", json={"token": "geheim"}).status_code, 200)
            self.assertEqual(k.post("/api/trigger/nix").status_code, 404)
            t = k.post("/api/ausloeser/a1/test")
            self.assertEqual(t.status_code, 200)
            self.assertIn("eingeblendet", t.get_json()["ergebnis"])
            self.assertEqual(k.post("/api/ausloeser/nix/test").status_code, 404)
            self.assertGreaterEqual(len(k.get("/api/ausloeser/protokoll").get_json()), 4)

    def test_put_lehnt_ab(self):
        with self.app.test_client() as k:
            a = k.put("/api/ausloeser", json=[ausloeser(quelle={"typ": "taster", "pin": 23})])
            self.assertEqual(a.status_code, 400)
            self.assertIn("gpio_trigger", a.get_json()["error"])
            a = k.put("/api/ausloeser", json=[ausloeser(aktion={"typ": "zeige_layout", "layout_id": "weg"})])
            self.assertEqual(a.status_code, 400)
            self.assertIn("gibt es nicht", a.get_json()["error"])
            self.assertEqual(self.c.config["ausloeser"], [])

    def test_die_szene_traegt_schwarz_und_video_ende(self):
        with self.app.test_client() as k:
            s = k.get("/api/scene").get_json()
            self.assertFalse(s["schwarz"])
            self.assertFalse(s["ausloeser_video_ende"])
            k.put("/api/ausloeser", json=[ausloeser(quelle={"typ": "video_ende", "datei": "", "region": ""},
                                                    aktion={"typ": "zurueck"}),
                                          ausloeser(id="aus", aktion={"typ": "display_aus"})])
            self.assertTrue(k.get("/api/scene").get_json()["ausloeser_video_ende"])
            k.post("/api/ausloeser/aus/test")
            self.assertTrue(k.get("/api/scene").get_json()["schwarz"])
            v = k.post("/api/trigger/_video_ende", json={"datei": "film.mp4", "region": "haupt"})
            self.assertEqual(v.get_json()["ausgeloest"], ["a1"])

    def test_ein_ausloeser_kann_die_sofortmeldung_setzen(self):
        with self.app.test_client() as k:
            k.put("/api/ausloeser", json=[ausloeser(aktion={"typ": "meldung", "text": "Am Empfang melden"})])
            k.post("/api/ausloeser/a1/test")
            self.assertEqual(k.get("/api/meldung").get_json()["text"], "Am Empfang melden")

    def test_die_anzeige_meldet_video_enden(self):
        js = (WURZEL / "static/anzeige/ausloeser.js").read_text(encoding="utf-8")
        self.assertIn("/api/trigger/_video_ende", js)
        self.assertIn("ausloeser_video_ende", js, "nur, wenn es einen solchen Ausloeser gibt")
        self.assertIn("vorschau", js, "nie aus der Vorschau")


class ReviewFunde(unittest.TestCase):
    """Funde aus dem Code-Review von PR #27, je einer als Waechter."""

    def setUp(self):
        self.c = main.Controller(frische_config())
        self.c.save_config = lambda: None
        self.c.ausloeser_faden = False

    def test_eine_uhrzeit_ohne_fuehrende_null_feuert_trotzdem(self):
        # `9:00` kam durch die Pruefung, aber `tick()` verglich Text mit
        # `strftime("%H:%M")` = "09:00" — der Ausloeser feuerte nie.
        liste = A.pruefe_ausloeser([ausloeser(quelle={"typ": "zeit", "tage": ["mo"], "zeit": "9:00"},
                                              aktion={"typ": "stop"})], frische_config())
        self.assertEqual(liste[0]["quelle"]["zeit"], "09:00", "beim Speichern normiert")
        self.c.config["ausloeser"] = [ausloeser(quelle={"typ": "zeit", "tage": ["mo"], "zeit": "9:00"},
                                                aktion={"typ": "stop"})]
        m = A.Ausloeser(self.c, gpio=lambda pin, wp: None)
        self.c.active = True
        m.tick(datetime(2026, 9, 14, 9, 0, 5))
        self.assertEqual(len(m.protokoll()), 1, "auch ein alter Stand `9:00` in der Datei feuert")

    def test_der_sensor_darf_nicht_auf_den_pin_eines_tasters_ziehen(self):
        # Vorher nur eine Richtung: der Taster pruefte gegen den Sensor, aber
        # `/api/config` durfte den Sensor auf den Taster-Pin legen — beim
        # naechsten Start verlor der Taster still.
        self.c.config["ausloeser"] = [ausloeser(id="t", quelle={"typ": "taster", "pin": 27},
                                                aktion={"typ": "display_aus"})]
        with create_app(self.c).test_client() as k:
            r = k.post("/api/config", json={"gpio_echo": 27})
            self.assertEqual(r.status_code, 400, r.get_json())
            self.assertIn("'t'", r.get_json()["error"])
            self.assertEqual(k.post("/api/config", json={"gpio_echo": 26}).status_code, 200)
            # Sensortyp „Taster" reserviert button_pin (17) — auch das kollidiert.
            self.c.config["ausloeser"][0]["quelle"]["pin"] = 17
            r = k.post("/api/config", json={"sensor_type": "button"})
            self.assertEqual(r.status_code, 400)

    def test_ein_restore_synchronisiert_die_taster(self):
        # `/api/restore` tauscht die Liste aus, ohne die PUT-Route zu beruehren;
        # der neue Taster wurde vorher erst nach einem Neustart geoeffnet.
        knoepfe = {}

        class Knopf:
            def __init__(self, pin):
                self.pin = pin

            def close(self):
                knoepfe.pop(self.pin, None)

        def fabrik(pin, when_pressed):
            knoepfe[pin] = when_pressed
            return Knopf(pin)
        m = A.Ausloeser(self.c, gpio=fabrik)
        self.c.ausloeser = m
        app = create_app(self.c)
        self.assertIn(m.synchronisiere_taster, self.c.config_beobachter)
        with app.test_client() as k:
            sicherung = json.loads(json.dumps(self.c.config))
            sicherung["ausloeser"] = [ausloeser(id="t", quelle={"typ": "taster", "pin": 27},
                                                aktion={"typ": "display_aus"})]
            self.assertEqual(k.post("/api/restore", json=sicherung).status_code, 200)
            self.assertIn(27, knoepfe, "Taster nach dem Restore offen")
            sicherung["ausloeser"] = []
            k.post("/api/restore", json=sicherung)
            self.assertNotIn(27, knoepfe, "und nach dem naechsten Restore wieder zu")

    def test_eine_maschine_je_controller_und_kein_faden_ohne_bestellung(self):
        # Zwei `create_app` = zwei Maschinen = jeder Zeit-Ausloeser doppelt.
        create_app(self.c)
        erste = self.c.ausloeser
        create_app(self.c)
        self.assertIs(self.c.ausloeser, erste)
        self.assertFalse(erste._laeuft, "ohne `ausloeser_faden` laeuft kein Faden")
        self.assertEqual(len([z for z in self.c.szene_zusatz if z.__name__ == "ausloeser"]), 1)
        # main() bestellt den Faden ausdruecklich.
        quelle = (WURZEL / "main.py").read_text(encoding="utf-8")
        self.assertIn("controller.ausloeser_faden = True", quelle)

    def test_schirm_schwarz_geht_ueber_melde_config(self):
        # Vorher griff die Aktion in `controller._gemeldete_szene` und baute
        # `melde_config` zur Haelfte nach.
        aufrufe = []
        self.c.melde_config = lambda: aufrufe.append(1)
        m = A.Ausloeser(self.c, gpio=lambda pin, wp: None)
        m.fuehre_aus({"typ": "display_aus"})
        self.assertEqual(aufrufe, [1])
        quelle = (WURZEL / "ausloeser.py").read_text(encoding="utf-8")
        self.assertNotIn("_gemeldete_szene", quelle)

    def test_die_grenzen_gibt_es_nur_einmal(self):
        quelle = (WURZEL / "ausloeser.py").read_text(encoding="utf-8")
        for doppelt in ("def _text(", "def _farbe(", "def _dauer(", "TEXT_MAX = ", 'ZONEN = ('):
            self.assertNotIn(doppelt, quelle, f"{doppelt} gehoert nach programm.py/layouts.py")
        self.assertEqual(A.pruefe_ausloeser([ausloeser(name="Empfang Knopf", id="",
                                                       quelle={"typ": "webhook", "token": ""})],
                                            frische_config())[0]["id"], "empfang-knopf")

    def test_die_webhook_adresse_kommt_von_der_seite(self):
        # `http://` + display_ip: hinter einem Reverse-Proxy oder unter einem
        # Hostnamen stand da eine Adresse, die niemand beantwortet.
        js = (WURZEL / "static/module/ausloeser.js").read_text(encoding="utf-8")
        self.assertIn("location.protocol + '//' + location.host", js)
        self.assertNotIn("'http://' + host", js)


if __name__ == "__main__":
    unittest.main()

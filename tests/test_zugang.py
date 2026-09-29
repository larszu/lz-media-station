"""Zugangsschutz (3.0): eine PIN vor der Verwaltung — wenn jemand sie setzt.

WARUM. Die Station steht in einem Gastnetz. Bis 3.0 konnte jeder darin
Videos loeschen und den Pi neu starten. Was hier gesichert wird:

- OHNE PIN bleibt alles offen wie bisher (rueckwaertskompatibel)
- MIT PIN: /admin verlangt Anmeldung, Schreibzugriffe 401 — ausser mit
  Sitzung, Kopf X-LZ-Pin oder von 127.0.0.1 (der Kiosk selbst)
- die Meldewege der Anzeige bleiben frei (Puls, Screenshot, Proof-of-Play,
  Auto-Start), lesende GETs auch
- fuenf Fehlversuche je Minute, dann 429
- die PIN steht NICHT in der Konfiguration (Backup, /api/status)

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import api_wiedergabe  # noqa: E402
import api_zugang  # noqa: E402
import main  # noqa: E402
import zugang as Z  # noqa: E402
from web_ui import create_app  # noqa: E402


class DerKern(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.z = Z.Zugang(os.path.join(self.ordner.name, "zugang.json"))

    def tearDown(self):
        self.ordner.cleanup()

    def test_ohne_datei_ist_nichts_gesetzt(self):
        self.assertFalse(self.z.gesetzt)
        self.assertFalse(self.z.stimmt("1234"))

    def test_setzen_speichert_hash_und_salz_mit_0600(self):
        self.z.setzen("1234")
        self.assertTrue(self.z.gesetzt)
        self.assertTrue(self.z.stimmt("1234"))
        self.assertFalse(self.z.stimmt("4321"))
        with open(self.z.pfad) as f:
            d = json.load(f)
        self.assertNotIn('"1234"', json.dumps(d), "die PIN steht nirgends im Klartext")
        self.assertEqual(len(d["salz"]), 32)
        self.assertEqual(oct(os.stat(self.z.pfad).st_mode & 0o777), "0o600")
        # Neu geladen gilt dieselbe PIN.
        self.assertTrue(Z.Zugang(self.z.pfad).stimmt("1234"))

    def test_pin_form(self):
        for pin in ("123", "x" * 13, "12 34", 1234, None):
            with self.assertRaises(ValueError):
                self.z.setzen(pin)

    def test_aufheben(self):
        self.z.setzen("1234")
        self.z.aufheben()
        self.assertFalse(self.z.gesetzt)
        self.assertFalse(Z.Zugang(self.z.pfad).gesetzt)

    def test_fuenf_fehlversuche_je_minute_sperren(self):
        for i in range(Z.FEHLVERSUCHE):
            self.assertFalse(self.z.gesperrt("10.0.0.5", jetzt=100.0 + i))
            self.z.fehlversuch("10.0.0.5", jetzt=100.0 + i)
        self.assertTrue(self.z.gesperrt("10.0.0.5", jetzt=110.0))
        self.assertFalse(self.z.gesperrt("10.0.0.6", jetzt=110.0), "eine andere Adresse ist nicht gesperrt")
        self.assertFalse(self.z.gesperrt("10.0.0.5", jetzt=100.0 + Z.FENSTER_S + 1), "nach dem Fenster frei")

    def test_entscheide_ohne_pin_laesst_alles_durch(self):
        self.assertIsNone(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", None, None, 0))
        self.assertIsNone(Z.entscheide(self.z, "GET", "/admin", "10.0.0.5", None, None, 0))

    def test_entscheide_mit_pin(self):
        self.z.setzen("1234")
        e = lambda m, p, adr="10.0.0.5", sitz=None, kopf=None: Z.entscheide(
            self.z, m, p, adr, sitz, kopf, 1000.0, sitzung_gen=self.z.generation)
        self.assertEqual(e("GET", "/admin"), "anmelden")
        self.assertIsNone(e("GET", "/admin", sitz=2000.0))
        self.assertEqual(e("GET", "/admin", sitz=500.0), "anmelden", "abgelaufene Sitzung")
        self.assertIsNone(e("GET", "/api/scene"), "lesen bleibt offen")
        self.assertEqual(e("POST", "/api/config"), "pin")
        self.assertIsNone(e("POST", "/api/config", adr="127.0.0.1"), "der Kiosk selbst")
        self.assertIsNone(e("POST", "/api/config", sitz=2000.0))
        self.assertIsNone(e("POST", "/api/config", kopf="1234"))
        self.assertEqual(e("POST", "/api/config", kopf="0000"), "falsche_pin")
        for frei in ("/api/anzeige/puls", "/api/anzeige/screenshot", "/api/wiedergabe", "/api/start",
                     "/api/trigger/knopf", "/api/zugang/login"):
            self.assertIsNone(e("POST", frei), frei)
        self.assertEqual(e("POST", "/api/anzeige/screenshot/anfordern"), "pin", "anfordern ist nicht frei")

    def test_falsche_pins_im_kopf_zaehlen_als_fehlversuch(self):
        self.z.setzen("1234")
        for _ in range(Z.FEHLVERSUCHE):
            Z.entscheide(self.z, "POST", "/api/config", "10.0.0.7", None, "0000", 0)
        self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.7", None, "1234", 0), "gesperrt")


class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self._alt = (api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD)
        api_zugang.ZUGANG_PFAD = os.path.join(self.ordner.name, "zugang.json")
        api_zugang.GEHEIM_PFAD = os.path.join(self.ordner.name, "geheim.key")
        api_wiedergabe.DB_PFAD = os.path.join(self.ordner.name, "w.sqlite")
        self.controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)

    def tearDown(self):
        api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD = self._alt
        log = getattr(self.controller, "wiedergabe", None)
        if log:
            log.schliessen()
        self.ordner.cleanup()

    def client(self, adresse="10.0.0.5"):
        return self.app.test_client(), {"REMOTE_ADDR": adresse}

    def test_ohne_pin_ist_alles_offen_wie_bisher(self):
        c, env = self.client()
        self.assertEqual(c.get("/admin", environ_base=env).status_code, 200)
        self.assertEqual(c.post("/api/start", environ_base=env).status_code, 200)
        self.assertEqual(c.post("/api/config", json={"system_name": "X"}, environ_base=env).status_code, 200)
        self.assertEqual(c.get("/login", environ_base=env).status_code, 302, "ohne PIN gibt es nichts anzumelden")
        self.assertFalse(c.get("/api/zugang").get_json()["gesetzt"])

    def test_der_sitzungsschluessel_entsteht_erst_mit_der_ersten_pin(self):
        # Eine Station ohne PIN legt keine Datei an — auch keine Test-App.
        self.assertFalse(os.path.exists(api_zugang.GEHEIM_PFAD))
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        self.assertTrue(os.path.exists(api_zugang.GEHEIM_PFAD))
        self.assertEqual(oct(os.stat(api_zugang.GEHEIM_PFAD).st_mode & 0o777), "0o600")
        self.assertEqual(Z.lade_geheim(api_zugang.GEHEIM_PFAD), self.app.secret_key)

    def test_pin_setzen_schuetzt_admin_und_schreibzugriffe(self):
        c, env = self.client()
        r = c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        self.assertEqual(r.status_code, 200)
        # Wer die PIN setzt, ist danach angemeldet (Cookie) …
        self.assertEqual(c.get("/admin", environ_base=env).status_code, 200)
        # … ein fremder Browser nicht.
        fremd = self.app.test_client()
        r = fremd.get("/admin", environ_base=env)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(fremd.get("/login", environ_base=env).status_code, 200)
        r = fremd.post("/api/config", json={"system_name": "X"}, environ_base=env)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["zugang"], "pin")

    def test_lesen_und_die_meldewege_der_anzeige_bleiben_frei(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        fremd = self.app.test_client()
        self.assertEqual(fremd.get("/api/scene", environ_base=env).status_code, 200)
        self.assertEqual(fremd.get("/api/identity", environ_base=env).status_code, 200)
        self.assertEqual(fremd.get("/display", environ_base=env).status_code, 200)
        self.assertEqual(fremd.post("/api/start", environ_base=env).status_code, 200)
        self.assertEqual(fremd.post("/api/anzeige/puls", json={"kennung": "t1"}, environ_base=env).status_code, 200)
        self.assertEqual(fremd.post("/api/wiedergabe", json={"kennung": "t1", "eintraege": []},
                                    environ_base=env).status_code, 200)

    def test_kopf_x_lz_pin_und_localhost_duerfen_schreiben(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        fremd = self.app.test_client()
        r = fremd.post("/api/config", json={"system_name": "Manager"}, headers={"X-LZ-Pin": "1234"}, environ_base=env)
        self.assertEqual(r.status_code, 200)
        r = fremd.post("/api/config", json={"system_name": "Falsch"}, headers={"X-LZ-Pin": "0000"}, environ_base=env)
        self.assertEqual(r.status_code, 401)
        lokal = self.app.test_client()
        r = lokal.post("/api/config", json={"system_name": "Kiosk"}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 200)

    def test_login_logout_und_rate_limit(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        fremd = self.app.test_client()
        for _ in range(Z.FEHLVERSUCHE):
            self.assertEqual(fremd.post("/api/zugang/login", json={"pin": "0000"}, environ_base=env).status_code, 401)
        self.assertEqual(fremd.post("/api/zugang/login", json={"pin": "1234"}, environ_base=env).status_code, 429)
        anderer = self.app.test_client()
        env2 = {"REMOTE_ADDR": "10.0.0.9"}
        self.assertEqual(anderer.post("/api/zugang/login", json={"pin": "1234"}, environ_base=env2).status_code, 200)
        self.assertEqual(anderer.get("/admin", environ_base=env2).status_code, 200)
        self.assertTrue(anderer.get("/api/zugang", environ_base=env2).get_json()["angemeldet"])
        anderer.post("/api/zugang/logout", environ_base=env2)
        self.assertEqual(anderer.get("/admin", environ_base=env2).status_code, 302)

    def test_aendern_braucht_die_alte_pin_aufheben_die_sitzung(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        fremd = self.app.test_client()
        self.assertEqual(fremd.post("/api/zugang", json={"pin": "5678"}, environ_base=env).status_code, 401)
        self.assertEqual(fremd.post("/api/zugang", json={"pin": "5678", "alt": "0000"}, environ_base=env).status_code, 401)
        self.assertEqual(fremd.post("/api/zugang", json={"pin": "5678", "alt": "1234"}, environ_base=env).status_code, 200)
        self.assertTrue(self.controller.zugang.stimmt("5678"))
        # Aufheben: ohne Nachweis nein, mit Kopf ja.
        neu = self.app.test_client()
        self.assertEqual(neu.delete("/api/zugang", environ_base=env).status_code, 401)
        self.assertEqual(neu.delete("/api/zugang", headers={"X-LZ-Pin": "5678"}, environ_base=env).status_code, 200)
        self.assertFalse(self.controller.zugang.gesetzt)

    def test_die_pin_steht_nirgends_in_der_konfiguration(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        status = json.dumps(c.get("/api/status", environ_base=env).get_json())
        backup = c.get("/api/backup", environ_base=env).get_data(as_text=True)
        for text in (status, backup):
            self.assertNotIn("pin_hash", text)
            self.assertNotIn(self.controller.zugang.pin_hash, text)
            self.assertNotIn("1234", text)

    def test_vergessene_pin_laesst_sich_vom_pi_selbst_neu_setzen(self):
        c, env = self.client()
        c.post("/api/zugang", json={"pin": "1234"}, environ_base=env)
        lokal = self.app.test_client()
        r = lokal.post("/api/zugang", json={"pin": "9999"}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.controller.zugang.stimmt("9999"))


class ReviewFunde(unittest.TestCase):
    """Was der Review zu PR #25 gefunden hat — jeder Fund ein Waechter.

    WARUM. Vier davon betreffen die Sicherheit (offene Weiterleitung, Sitzungen
    ueberleben den PIN-Wechsel, eine halb gesetzte PIN, ein CPU-Loch durch
    PBKDF2 je Anfrage). Keiner faellt im Alltag auf, jeder faellt auf, wenn
    ihn jemand ausnutzt.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.z = Z.Zugang(os.path.join(self.ordner.name, "zugang.json"))

    def tearDown(self):
        self.ordner.cleanup()

    def test_ungueltige_sitzungsdauer_laesst_die_alte_pin_stehen(self):
        # Vorher: Hash und Salz waren schon getauscht, wenn die Dauer abgelehnt
        # wurde — die NEUE PIN galt bis zum Neustart, die Datei hatte die alte.
        self.z.setzen("1234")
        with self.assertRaises(ValueError):
            self.z.setzen("9999", sitzungsdauer_h=5000)
        self.assertTrue(self.z.stimmt("1234"), "die alte PIN gilt weiter")
        self.assertFalse(self.z.stimmt("9999"))
        self.assertTrue(Z.Zugang(self.z.pfad).stimmt("1234"), "Datei und Speicher stimmen ueberein")

    def test_pin_wechsel_macht_alte_sitzungen_ungueltig(self):
        self.z.setzen("1234")
        gen_alt = self.z.generation
        self.assertIsNone(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", 2000.0, None, 1000.0,
                                       sitzung_gen=gen_alt))
        self.z.setzen("4321")
        self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", 2000.0, None, 1000.0,
                                      sitzung_gen=gen_alt), "pin", "Cookie von vor dem Wechsel")
        self.assertEqual(Z.entscheide(self.z, "GET", "/admin", "10.0.0.5", 2000.0, None, 1000.0,
                                      sitzung_gen=gen_alt), "anmelden")
        # Aufheben + neu setzen ebenso — und die Generation ueberlebt den Neustart.
        self.z.aufheben(); self.z.setzen("1234")
        self.assertNotEqual(Z.Zugang(self.z.pfad).generation, gen_alt)

    def test_ohne_generation_im_cookie_gilt_keine_sitzung(self):
        self.z.setzen("1234")
        self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", 2000.0, None, 1000.0), "pin")

    def test_der_kopf_wird_nur_einmal_teuer_geprueft(self):
        self.z.setzen("1234")
        from unittest.mock import patch
        with patch.object(Z, "hash_pin", wraps=Z.hash_pin) as h:
            for _ in range(5):
                self.assertIsNone(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", None, "1234", 0))
            self.assertEqual(h.call_count, 1, "PBKDF2 nur beim ersten richtigen Kopf")
            # Ein falscher Kopf wird nie gemerkt: er kostet jedes Mal — und zaehlt.
            self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", None, "0000", 0), "falsche_pin")
            self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.5", None, "0000", 0), "falsche_pin")
            self.assertEqual(h.call_count, 3)
        # Nach einem Wechsel gilt der gemerkte Wert nicht mehr.
        self.z.setzen("4321")
        self.assertEqual(Z.entscheide(self.z, "POST", "/api/config", "10.0.0.9", None, "1234", 0), "falsche_pin")

    def test_weiter_ist_nur_ein_pfad_dieser_station(self):
        for boese in ("https://fremd.example/admin", "//fremd.example", "/\\fremd.example",
                      "/admin\r\nSet-Cookie: x", "admin", "", None, 7):
            self.assertEqual(Z.sicherer_weiter(boese), "/admin", repr(boese))
        self.assertEqual(Z.sicherer_weiter("/admin?tab=zonen"), "/admin?tab=zonen")
        self.assertEqual(Z.sicherer_weiter("/display"), "/display")

    def test_login_seite_leitet_nie_nach_aussen(self):
        # Ueber die App: ohne PIN geht /login sofort weiter — aber nur intern.
        ordner = tempfile.TemporaryDirectory()
        alt = (api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD)
        api_zugang.ZUGANG_PFAD = os.path.join(ordner.name, "zugang.json")
        api_zugang.GEHEIM_PFAD = os.path.join(ordner.name, "geheim.key")
        api_wiedergabe.DB_PFAD = os.path.join(ordner.name, "w.sqlite")
        try:
            controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
            controller.save_config = lambda: None
            app = create_app(controller)
            with app.test_client() as c:
                r = c.get("/login?weiter=https://fremd.example/")
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers["Location"], "/admin")
                r = c.get("/login?weiter=//fremd.example")
                self.assertEqual(r.headers["Location"], "/admin")
                # Mit PIN: das Formular bekommt nur den bereinigten Pfad.
                c.post("/api/zugang", json={"pin": "1234"}, environ_base={"REMOTE_ADDR": "10.0.0.5"})
                c.post("/api/zugang/logout")
                seite = c.get("/login?weiter=//fremd.example", environ_base={"REMOTE_ADDR": "10.0.0.5"})
                self.assertEqual(seite.status_code, 200)
                self.assertIn('window.LZ_WEITER = "/admin";', seite.get_data(as_text=True))
            wl = getattr(controller, "wiedergabe", None)
            if wl:
                wl.schliessen()
        finally:
            api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD = alt
            ordner.cleanup()

    def test_auch_die_anmeldeseite_prueft_den_pfad_wie_der_kern(self):
        # Der Client-Test in login.html muss `//` und Backslash ebenso abweisen.
        quelle = (WURZEL / "templates" / "login.html").read_text(encoding="utf-8")
        self.assertNotIn("indexOf('/') === 0", quelle, "der alte Test liess //fremd durch")
        self.assertRegex(quelle, r"\(\?!\[\\/\\\\\]\)", "Lookahead gegen // und /\\ fehlt")

    def test_sitzung_ueber_die_api_stirbt_mit_dem_pin_wechsel(self):
        ordner = tempfile.TemporaryDirectory()
        alt = (api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD)
        api_zugang.ZUGANG_PFAD = os.path.join(ordner.name, "zugang.json")
        api_zugang.GEHEIM_PFAD = os.path.join(ordner.name, "geheim.key")
        api_wiedergabe.DB_PFAD = os.path.join(ordner.name, "w.sqlite")
        try:
            controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
            controller.save_config = lambda: None
            app = create_app(controller)
            env = {"REMOTE_ADDR": "10.0.0.5"}
            tablet = app.test_client()
            tablet.post("/api/zugang", json={"pin": "1234"}, environ_base=env)   # setzt und meldet an
            self.assertEqual(tablet.post("/api/config", json={"system_name": "T"}, environ_base=env).status_code, 200)
            # Jemand anderes aendert die PIN vom Pi aus.
            app.test_client().post("/api/zugang", json={"pin": "4321"}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
            self.assertEqual(tablet.post("/api/config", json={"system_name": "T"}, environ_base=env).status_code, 401)
            self.assertEqual(tablet.get("/admin", environ_base=env).status_code, 302)
            wl = getattr(controller, "wiedergabe", None)
            if wl:
                wl.schliessen()
        finally:
            api_zugang.ZUGANG_PFAD, api_zugang.GEHEIM_PFAD, api_wiedergabe.DB_PFAD = alt
            ordner.cleanup()


if __name__ == "__main__":
    unittest.main()

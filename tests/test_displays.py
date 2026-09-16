"""
Findet die Station die Bildschirme DIESES Rechners — auf Mac und Windows?

─── DIE MELDUNG DAHINTER (Nutzer, 2026-09-15) ──────────────────────────────

„im mediaplayer das endgeraet selbst und externe displays die ans endgeraet
angeschlossen sind als mediaplayer nutzen koennen. mac und windows"

─── WAS ES VORHER GAB ──────────────────────────────────────────────────────

Genau EINEN Schirm, und der war der HDMI-Ausgang eines Raspberry Pi. Die
Anzeige ist seit jeher eine Browser-Seite (`/display`); auf dem Pi oeffnet
sie ein Chromium im Kiosk-Betrieb, und mehr Bildschirme hat ein Pi in
diesem Aufbau nicht. Auf einem Notebook haengt oft mehr als einer, und der
eingebaute zaehlt mit — die Station konnte davon nichts nutzen.

─── WARUM GEGEN AUFGEZEICHNETE AUSGABEN UND NICHT GEGEN DAS SYSTEM ─────────

Weil CI genau einen Kern und keinen Bildschirm hat, und weil die Frage eine
andere ist: ob die AUSWERTUNG stimmt. `system_profiler` und `xrandr` geben
Text zurueck; ob daraus die richtige Ecke und die richtige Groesse wird,
laesst sich mit ihrem Text pruefen — und nur so laesst es sich ueberhaupt
pruefen, ohne einen Mac in die CI zu stellen.

Die Texte hier sind echte Ausgaben in der Form, die die Programme liefern.
NICHT GEMESSEN ist damit, ob `system_profiler` auf einer kuenftigen
macOS-Fassung dieselbe Form liefert, und ob ein Fenster auf dem zweiten
Schirm wirklich ankommt. Das zweite haengt an einem Browser und an einer
Anordnung, die es hier beide nicht gibt.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import displays  # noqa: E402


# `system_profiler SPDisplaysDataType -json` auf einem MacBook mit einem
# externen 4K-Schirm.
MACOS_JSON = json.dumps({
    "SPDisplaysDataType": [{
        "_name": "Apple M2",
        "spdisplays_ndrvs": [
            {
                "_name": "Color LCD",
                "_spdisplays_resolution": "3024 x 1964 Retina",
                "spdisplays_main": "spdisplays_yes",
            },
            {
                "_name": "LG UltraFine",
                "_spdisplays_resolution": "3840 x 2160 (2160p/4K UHD)",
            },
        ],
    }]
})

# `xrandr --listmonitors` auf einem Notebook mit externem Schirm rechts.
XRANDR = """Monitors: 2
 0: +*eDP-1 1920/344x1080/193+0+0  eDP-1
 1: +HDMI-1 2560/597x1440/336+1920+0  HDMI-1
"""


class MacOS(unittest.TestCase):
    def test_zwei_schirme_mit_groesse(self):
        s = displays._macos_schirme(MACOS_JSON)
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0]["name"], "Color LCD")
        self.assertEqual((s[0]["breite"], s[0]["hoehe"]), (3024, 1964))
        self.assertEqual((s[1]["breite"], s[1]["hoehe"]), (3840, 2160))

    def test_hauptschirm_steht_vorn_und_bei_null(self):
        s = displays._macos_schirme(MACOS_JSON)
        self.assertTrue(s[0]["haupt"])
        self.assertEqual((s[0]["x"], s[0]["y"]), (0, 0))

    def test_der_zweite_liegt_rechts_daneben(self):
        """Die Aufreihung ist eine ANNAHME — sie muss trotzdem stimmen.

        macOS nennt in dieser Ausgabe keine Koordinaten. Der zweite Schirm
        beginnt deshalb dort, wo der erste aufhoert.
        """
        s = displays._macos_schirme(MACOS_JSON)
        self.assertEqual(s[1]["x"], s[0]["breite"])

    def test_leere_ausgabe_ist_leere_liste_und_kein_absturz(self):
        self.assertEqual(displays._macos_schirme('{"SPDisplaysDataType": []}'), [])

    def test_unlesbare_aufloesung_wirft_nicht(self):
        roh = json.dumps({"SPDisplaysDataType": [{
            "spdisplays_ndrvs": [{"_name": "X", "_spdisplays_resolution": "unbekannt"}]
        }]})
        s = displays._macos_schirme(roh)
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["breite"], 0)


class Linux(unittest.TestCase):
    def test_geometrie_wird_richtig_zerlegt(self):
        s = displays._linux_schirme(XRANDR)
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0], {"name": "eDP-1", "breite": 1920, "hoehe": 1080,
                                "x": 0, "y": 0, "haupt": True})
        self.assertEqual(s[1], {"name": "HDMI-1", "breite": 2560, "hoehe": 1440,
                                "x": 1920, "y": 0, "haupt": False})

    def test_die_kopfzeile_zaehlt_nicht_als_schirm(self):
        self.assertEqual(len(displays._linux_schirme("Monitors: 0\n")), 0)

    def test_muellzeile_wird_uebersprungen_statt_zu_werfen(self):
        s = displays._linux_schirme(XRANDR + " 2: kaputt\n")
        self.assertEqual(len(s), 2)

    def test_schirm_links_vom_hauptschirm_hat_negatives_x(self):
        """Ein negatives `x` ist kein Fehler, sondern die uebliche Anordnung
        fuer einen Schirm, der links steht.

        DIESER TEST HAT EINEN ECHTEN DEFEKT GEFUNDEN. Der erste Anlauf
        trennte die Geometrie an `+` — bei `-1920+0` fiel der Eintrag damit
        still aus der Liste, also ausgerechnet der zweite Schirm, um den es
        hier geht. Jetzt trennt ein Mustervergleich mit Vorzeichen.
        """
        s = displays._linux_schirme(
            "Monitors: 1\n 0: +*HDMI-1 1920/509x1080/286-1920+0  HDMI-1\n")
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["x"], -1920)
        self.assertEqual(s[0]["breite"], 1920)


class OhneAlles(unittest.TestCase):
    def test_schirme_wirft_nie(self):
        """Ein Rechner ohne Grafik ist kein Fehlerfall.

        Ein Pi ohne X, ein Server, ein CI-Container: `schirme()` gibt dort
        eine leere Liste zurueck, und die Station laeuft weiter — sie
        bespielt nur nichts vor Ort.
        """
        with mock.patch.object(displays.subprocess, "run",
                               side_effect=OSError("kein xrandr")):
            self.assertEqual(displays.schirme(), [])

    def test_ohne_browser_sagt_das_modul_wo_es_gesucht_hat(self):
        """Ein „geht nicht" ohne Ort ist fuer den Nutzer dasselbe wie
        Schweigen."""
        with mock.patch.object(displays, "finde_browser", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                displays.oeffne_auf_schirm(
                    "http://127.0.0.1:5000/display",
                    {"x": 0, "y": 0, "breite": 1920, "hoehe": 1080}, 0)
        text = str(ctx.exception)
        self.assertIn("Gesucht", text)
        for ort in displays.suchorte():
            self.assertIn(ort, text)


class FensterAufDemRichtigenSchirm(unittest.TestCase):
    """Die Position IST die Schirmwahl — einen anderen Weg gibt es nicht."""

    def _argumente(self, schirm, index=0):
        with mock.patch.object(displays.subprocess, "Popen") as popen:
            displays.oeffne_auf_schirm("http://127.0.0.1:5000/display",
                                       schirm, index, browser="/usr/bin/chromium")
            return popen.call_args[0][0]

    def test_ecke_und_groesse_kommen_aus_dem_schirm(self):
        args = self._argumente({"x": 1920, "y": 0, "breite": 2560, "hoehe": 1440})
        self.assertIn("--window-position=1920,0", args)
        self.assertIn("--window-size=2560,1440", args)

    def test_vollbild_und_eigenes_fenster(self):
        args = self._argumente({"x": 0, "y": 0, "breite": 1920, "hoehe": 1080})
        self.assertIn("--start-fullscreen", args)
        self.assertIn("--new-window", args)

    def test_je_schirm_ein_eigenes_profil(self):
        """OHNE DAS BLEIBT DER ZWEITE SCHIRM SCHWARZ.

        Ein zweiter Chrome-Aufruf mit demselben Profil faltet sich in das
        bestehende Fenster, statt ein neues zu oeffnen.
        """
        eins = self._argumente({"x": 0, "y": 0, "breite": 1920, "hoehe": 1080}, 0)
        zwei = self._argumente({"x": 1920, "y": 0, "breite": 1920, "hoehe": 1080}, 1)
        profil = lambda a: next(x for x in a if x.startswith("--user-data-dir="))
        self.assertNotEqual(profil(eins), profil(zwei))

    def test_kein_erststart_dialog_auf_dem_aufbau(self):
        args = self._argumente({"x": 0, "y": 0, "breite": 1920, "hoehe": 1080})
        self.assertIn("--no-first-run", args)
        self.assertIn("--autoplay-policy=no-user-gesture-required", args)


class AnzeigenVerwaltung(unittest.TestCase):
    def setUp(self):
        self.a = displays.Anzeigen()
        self.schirme = [
            {"name": "A", "x": 0, "y": 0, "breite": 1920, "hoehe": 1080, "haupt": True},
            {"name": "B", "x": 1920, "y": 0, "breite": 2560, "hoehe": 1440, "haupt": False},
        ]

    def test_ohne_schirme_wird_nichts_behauptet(self):
        with mock.patch.object(displays, "schirme", return_value=[]):
            gestartet, meldungen = self.a.starte("http://x/display")
            self.assertEqual(gestartet, [])
            self.assertIn("Keine Bildschirme gefunden.", meldungen)

    def test_alle_schirme_wenn_keine_auswahl(self):
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm") as auf:
            auf.return_value = mock.Mock(poll=lambda: None)
            gestartet, _ = self.a.starte("http://x/display")
            self.assertEqual(gestartet, [0, 1])

    def test_ein_schirm_der_nicht_existiert_wird_gemeldet_statt_geraten(self):
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm") as auf:
            auf.return_value = mock.Mock(poll=lambda: None)
            gestartet, meldungen = self.a.starte("http://x/display", [0, 5])
            self.assertEqual(gestartet, [0])
            self.assertTrue(any("Schirm 5 gibt es nicht" in m for m in meldungen))

    def test_zweimal_starten_oeffnet_kein_zweites_fenster(self):
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm") as auf:
            auf.return_value = mock.Mock(poll=lambda: None)
            self.a.starte("http://x/display", [0])
            gestartet, meldungen = self.a.starte("http://x/display", [0])
            self.assertEqual(gestartet, [])
            self.assertTrue(any("zeigt schon" in m for m in meldungen))

    def test_teilerfolg_ist_der_normalfall(self):
        """Drei Schirme, auf einem klemmt der Browser — die anderen gehen auf."""
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm") as auf:
            auf.side_effect = [mock.Mock(poll=lambda: None),
                               RuntimeError("kein Browser")]
            gestartet, meldungen = self.a.starte("http://x/display")
            self.assertEqual(gestartet, [0])
            self.assertTrue(any("kein Browser" in m for m in meldungen))

    def test_beenden_schliesst_nur_das_selbst_geoeffnete(self):
        p = mock.Mock(poll=lambda: None)
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm", return_value=p):
            self.a.starte("http://x/display", [1])
        self.assertEqual(self.a.beende(), [1])
        p.terminate.assert_called_once()

    def test_zustand_nennt_je_schirm_ob_er_zeigt(self):
        with mock.patch.object(displays, "schirme", return_value=self.schirme), \
             mock.patch.object(displays, "oeffne_auf_schirm",
                               return_value=mock.Mock(poll=lambda: None)):
            self.a.starte("http://x/display", [1])
            z = self.a.zustand()
        self.assertEqual([s["zeigt"] for s in z], [False, True])
        self.assertEqual([s["index"] for s in z], [0, 1])


class DieOberflaecheKennDieSchirme(unittest.TestCase):
    """Ohne Endpunkt kann die Verwaltung sie nicht bedienen."""

    def test_api_ohne_spieler_antwortet_statt_zu_werfen(self):
        import main
        from web_ui import create_app
        controller = main.Controller(main.load_config())
        app = create_app(controller)  # ohne `anzeigen` — wie auf einem Pi ohne X
        with app.test_client() as c:
            antwort = c.get("/api/displays")
            self.assertEqual(antwort.status_code, 200)
            self.assertEqual(antwort.get_json()["schirme"], [])
            self.assertIn("grund", antwort.get_json())

    def test_spielen_und_beenden_gehen_ueber_die_api(self):
        import main
        from web_ui import create_app
        controller = main.Controller(main.load_config())
        anzeigen = displays.Anzeigen()
        app = create_app(controller, anzeigen)
        with mock.patch.object(displays, "schirme", return_value=[
                {"name": "A", "x": 0, "y": 0, "breite": 1920, "hoehe": 1080,
                 "haupt": True}]), \
             mock.patch.object(displays, "oeffne_auf_schirm",
                               return_value=mock.Mock(poll=lambda: None)):
            with app.test_client() as c:
                auf = c.post("/api/displays/play", json={})
                self.assertEqual(auf.get_json()["gestartet"], [0])
                zu = c.post("/api/displays/stop", json={})
                self.assertEqual(zu.get_json()["beendet"], [0])

    def test_falsche_eingabe_wird_abgewiesen_statt_geraten(self):
        import main
        from web_ui import create_app
        controller = main.Controller(main.load_config())
        app = create_app(controller, displays.Anzeigen())
        with app.test_client() as c:
            antwort = c.post("/api/displays/play", json={"schirme": "alle"})
            self.assertEqual(antwort.status_code, 400)


if __name__ == "__main__":
    unittest.main()

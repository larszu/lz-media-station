"""Der Layout-Editor (Karte „Layouts", Welle 2) — Waechter am Quelltext.

WARUM. Der Editor ist JavaScript, und dieses Repo hat keinen JavaScript-Lauf.
Was sich pruefen laesst, ist das, was sonst still zurueckfaellt: dass die
Karte ueberhaupt eingebunden ist, dass sie nur ueber `PUT /api/layouts/<id>`
schreibt (und nie zwischendurch), dass ein Dialog uebersetzt wird, dass der
Zuschauer-Modus der Anzeige die Steuerung NICHT anwirft, und dass die
Startseite eine Zone mit Webseite oder Widget als Inhalt zaehlt.

Am 2026-09-28 wurde der Editor zusaetzlich im echten Chromium (headless, per
DevTools-Protokoll) durchgespielt: Region anlegen, mit Maus und Finger
ziehen, Ecke skalieren, Webseite in die Playlist, speichern, Vorschau laedt,
`zuschauen=1` startet nicht. Das hier ist der Rest, der ohne Browser geht.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import re
import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import main  # noqa: E402
from web_ui import create_app  # noqa: E402

MODUL = (WURZEL / "static/module/layout-editor.js").read_text(encoding="utf-8")
KARTE = (WURZEL / "templates/admin/_layouts.html").read_text(encoding="utf-8")
CSS = (WURZEL / "static/layout-editor.css").read_text(encoding="utf-8")
DISPLAY = (WURZEL / "static/display.js").read_text(encoding="utf-8")
LAUNCH = (WURZEL / "templates/launch.html").read_text(encoding="utf-8")
APP = (WURZEL / "static/app.js").read_text(encoding="utf-8")


def frische_app():
    c = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
    c.save_config = lambda: None
    return create_app(c)


class DieKarteIstEingebunden(unittest.TestCase):
    def test_admin_liefert_editor_skript_stil_und_woerterbuch(self):
        html = frische_app().test_client().get("/admin").get_data(as_text=True)
        self.assertIn("/static/module/layout-editor.js", html)
        self.assertIn("/static/layout-editor.css", html)
        self.assertIn("/static/i18n/layout-editor.en.js", html)
        for kennung in ("le-leinwand", "le-region-panel", "le-playlist", "le-speichern",
                        "le-vorschau", "le-zeit", "laeuft-gerade"):
            self.assertIn(f'id="{kennung}"', html, kennung)

    def test_die_alte_listenkarte_ist_weg(self):
        # Die Karte gehoert jetzt dem Editor; app.js zeichnet keine Liste mehr,
        # sondern meldet neue Layouts als Ereignis.
        self.assertNotIn("function renderLayouts", APP)
        self.assertIn("lz-layouts", APP)
        self.assertIn("addEventListener('lz-layouts'", MODUL)


class DerEditorSchreibtNurGanz(unittest.TestCase):
    def test_speichern_ist_ein_put_des_ganzen_layouts(self):
        self.assertRegex(MODUL, r"method:\s*'PUT'")
        self.assertIn("JSON.stringify(entwurf)", MODUL)

    def test_kein_schreibzugriff_ausser_ueber_die_layout_schnittstelle(self):
        # Kein POST /api/config aus dem Editor: die Zonenzuordnung macht die
        # Zonen-Uebersicht, der Editor kuemmert sich nur um das Layout.
        self.assertNotIn("/api/config", MODUL)
        for pfad in re.findall(r"fetch\('(/api/[^']+)", MODUL):
            self.assertTrue(pfad.startswith("/api/layouts"), pfad)

    def test_dialoge_werden_uebersetzt_und_es_gibt_keine_prompts(self):
        for treffer in re.finditer(r"\bconfirm\(", MODUL):
            self.assertEqual(MODUL[treffer.end():treffer.end() + 3], "tr(",
                             "confirm() ohne tr(): der Dialog bliebe deutsch")
        self.assertNotRegex(MODUL, r"\b(prompt|alert)\(")


class MausUndFinger(unittest.TestCase):
    def test_die_leinwand_nimmt_pointer_events_und_scrollt_nicht_weg(self):
        self.assertIn("pointerdown", MODUL)
        self.assertIn("setPointerCapture", MODUL)
        self.assertRegex(CSS, r"\.le-leinwand\s*\{[^}]*touch-action:\s*none")

    def test_die_griffe_sind_gross_genug_fuer_den_daumen(self):
        # 18 px, nicht 8: WCAG 2.2 SC 2.5.8 nennt 24, die Ecke einer Region
        # liegt aber ohnehin am Rand der Trefferflaeche.
        m = re.search(r"\.le-griff\s*\{[^}]*width:\s*(\d+)px", CSS)
        self.assertTrue(m and int(m.group(1)) >= 16, "Griffe zu klein")

    def test_das_raster_ist_fuenf_prozent(self):
        self.assertRegex(MODUL, r"var RASTER = 5;")


class Markenregeln(unittest.TestCase):
    def test_keine_rundungen_schatten_oder_verlaeufe(self):
        for radius in re.findall(r"border-radius:\s*([^;]+);", CSS):
            self.assertIn(radius.strip(), ("0", "0px"))
        self.assertNotIn("box-shadow", CSS)
        self.assertNotIn("gradient", CSS)


class ZuschauerModusDerAnzeige(unittest.TestCase):
    def test_zuschauen_startet_die_steuerung_nicht(self):
        # Der Auto-Start steht in genau einem Zweig; er muss den Zuschauer
        # ausnehmen — sonst wirft „Was laeuft gerade?" die Station an.
        self.assertRegex(DISPLAY, r"if \(!startAttempted && !zuschauen\)")
        self.assertRegex(DISPLAY, r"var master = zuschauen \? 0 : anteil\(scene\.master_volume\)")

    def test_die_anzeige_liefert_den_zuschauer_modus_aus(self):
        r = frische_app().test_client().get("/display?zuschauen=1")
        self.assertEqual(r.status_code, 200)

    def test_die_statuskarte_oeffnet_den_zuschauer(self):
        self.assertIn("/display?zuschauen=1", MODUL)
        self.assertIn("zeigeLaeuftGerade", (WURZEL / "templates/admin/_status.html").read_text(encoding="utf-8"))


class DieStartseiteZaehltLayouts(unittest.TestCase):
    def test_auto_start_misst_am_layout_nicht_nur_an_den_listen(self):
        self.assertIn("regionen", LAUNCH)
        self.assertIn("zonen_stufen", LAUNCH)
        self.assertRegex(LAUNCH, r"r\.typ === 'widget' \|\| \(r\.playlist \|\| \[\]\)\.length")

    def test_ohne_layouts_gilt_der_alte_weg(self):
        # Ein Kern von vor 3.0: die Listen der Zone entscheiden weiter.
        self.assertRegex(LAUNCH, r"if \(!layouts\) return \(z\.videos \|\| \[\]\)\.length")


class Woerterbuch(unittest.TestCase):
    def test_die_karte_hat_ein_eigenes_woerterbuch(self):
        text = (WURZEL / "static/i18n/layout-editor.en.js").read_text(encoding="utf-8")
        wb = json.loads(text.split("/*JSON*/")[1])
        for schluessel in ("Layout speichern", "Live-Vorschau", "Zeitpunkt simulieren", "Was läuft gerade?"):
            self.assertIn(schluessel, wb["texte"])
        for muster, _ in wb["muster"]:
            re.compile(muster)


if __name__ == "__main__":
    unittest.main()

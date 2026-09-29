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
        # Der Zuschauer kehrt VOR dem Auto-Start um — sonst wirft „Was laeuft
        # gerade?" die Station an. Und er sagt nicht „Starte...", wenn er es
        # nicht tut (Review 2026-09-28).
        zweig = re.search(r"if \(zuschauen\) \{(.*?)\}", DISPLAY, re.S)
        self.assertTrue(zweig and "return;" in zweig.group(1) and "Steuerung ist aus" in zweig.group(1))
        self.assertLess(DISPLAY.index("if (zuschauen) {"), DISPLAY.index("if (!startAttempted) {"))
        self.assertRegex(DISPLAY, r"var master = zuschauen \? 0 : anteil\(scene\.master_volume\)")

    def test_escape_fuehrt_im_iframe_nicht_zum_admin(self):
        # Die Vorschau ist /display in einem iframe des Admins. ESC dort darf
        # nicht den ganzen Admin verschachtelt in die Karte laden.
        self.assertRegex(DISPLAY, r"eingebettet = window\.top !== window")
        self.assertRegex(DISPLAY, r"e\.keyCode === 27\) && !eingebettet")

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


class ReviewFunde(unittest.TestCase):
    """Zehn Funde des Code-Reviews vom 2026-09-28 — jeder als Waechter, damit
    er nicht still zurueckkommt."""

    STYLE = (WURZEL / "static/style.css").read_text(encoding="utf-8")
    I18N = json.loads((WURZEL / "static/i18n/layout-editor.en.js").read_text(encoding="utf-8").split("/*JSON*/")[1])

    def test_hidden_gewinnt_gegen_eigene_display_regeln(self):
        # Autor-CSS schlaegt die Browser-Vorgabe [hidden]{display:none}; ohne
        # diesen Reset blieben `.le-web{display:flex}` und
        # `.checkbox-label{display:flex !important}` trotz `hidden` sichtbar.
        self.assertRegex(self.STYLE, r"\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}")

    def test_kein_neuzeichnen_waehrend_zug_oder_eingabe(self):
        u = re.search(r"function uebernimm\(\) \{(.*?)\n    \}", MODUL, re.S).group(1)
        self.assertIn("if (zug) { nachholen = true; return; }", u)
        self.assertIn("if (eingabeLaeuft())", u)
        self.assertIn("if (nachholen) { nachholen = false; uebernimm(); return; }", MODUL)

    def test_playlist_zug_wird_bei_dragend_geloescht_und_dateien_haben_vorrang(self):
        self.assertRegex(MODUL, r"addEventListener\('dragend', function \(\) \{ zugEintrag = null; \}\)")
        drop = re.search(r"var nach = Number\(z\.getAttribute\('data-i'\)\);(.*?)\}\);", MODUL, re.S).group(1)
        self.assertLess(drop.index("getData('lz-datei')"), drop.index("bewegeEintrag"))

    def test_freiform_widget_behaelt_seine_einstellungen_beim_typwechsel(self):
        w = re.search(r"API\.widgetTyp = function \(typ\) \{(.*?)\n    \};", MODUL, re.S).group(1)
        self.assertIn("} else if (typ) {", w)
        self.assertRegex(w, r"Object\.keys\(alt\)\.forEach\(function \(k\) \{ if \(k !== 'typ'\) r\.widget\[k\] = alt\[k\]; \}\)")

    def test_layoutwahl_vergleicht_mit_dem_erzeugten_string_und_schont_den_fokus(self):
        self.assertNotIn("if (sel.innerHTML !== html) sel.innerHTML = html;", MODUL)
        self.assertIn("if (document.activeElement !== sel && html !== wahlHtml) { wahlHtml = html; sel.innerHTML = html; }", MODUL)

    def test_dynamische_texte_haben_ein_muster(self):
        muster = [m for m, _ in self.I18N["muster"]]
        for text in ("Zonen: Nah, Fern", 'Layout "Foyer" löschen? Die Medien bleiben erhalten.'):
            self.assertTrue(any(re.match(m, text) for m in muster), text)
        self.assertIn("Steuerung ist aus", self.I18N["texte"])

    def test_heute_kommt_aus_der_ortszeit(self):
        # Der Kern filtert mit datetime.now().date(); toISOString() waere UTC
        # und um 00:30 in Berlin noch beim Vortag.
        h = re.search(r"function heute\(\) \{(.*?)\n    \}", MODUL, re.S).group(1)
        self.assertNotIn("toISOString", h)
        self.assertIn("getFullYear()", h)

    def test_keine_doppelten_oder_toten_konstanten(self):
        self.assertNotIn("TYP_ZU_ART", MODUL)
        self.assertNotIn("ZONEN_TEXT", MODUL)
        self.assertIn("window.ZONEN_NAMEN", MODUL)


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

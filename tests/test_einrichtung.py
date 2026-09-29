"""Erste Schritte (3.0): QR-Code auf der Startseite, Karte „In 3 Schritten"
in der Verwaltung, und die Anzeige in der Vorschau ohne eigene
Ereignis-Verbindung.

WARUM. Die Startseite ist das Erste, was auf einem frisch aufgebauten Schirm
steht. Wer davor steht, soll die Verwaltung mit dem Handy oeffnen koennen,
ohne eine Adresse abzutippen — und eine leere Station soll in der
Verwaltung sagen, was als Naechstes zu tun ist, statt nur leere Karten zu
zeigen. Beides ist JavaScript; geprueft wird hier, was ohne Browser geht.

Am 2026-09-29 im Gesamtlauf (headless Chrome, DE und EN) gesehen:
QR-Code erscheint, Karte steht oben und verschwindet mit dem ersten Inhalt.
Dabei fielen zwei Fehler auf, die hier festgehalten sind: ein
Zusatzwoerterbuch mit `"muster": {}` legte die ganze englische Verwaltung
still, und Vorschau-iframes hielten je eine eigene Ereignis-Verbindung offen,
bis der Browser keine weiteren Anfragen an die Station mehr schickte.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import sys
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import main  # noqa: E402
from web_ui import create_app  # noqa: E402

LAUNCH = (WURZEL / "templates/launch.html").read_text(encoding="utf-8")
KARTE = (WURZEL / "templates/admin/zusatz/00-einrichtung.html").read_text(encoding="utf-8")
MODUL = (WURZEL / "static/module/einrichtung.js").read_text(encoding="utf-8")
DISPLAY = (WURZEL / "static/display.js").read_text(encoding="utf-8")
I18N = (WURZEL / "static/i18n.js").read_text(encoding="utf-8")


def frische_app():
    c = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
    c.save_config = lambda: None
    return create_app(c)


class DieStartseiteZeigtEinenQrCode(unittest.TestCase):

    def test_der_encoder_kommt_aus_den_widgets_nicht_von_aussen(self):
        # Offline-Faehigkeit: kein CDN, keine zweite QR-Bibliothek.
        self.assertIn('src="/static/anzeige/widgets.js"', LAUNCH)
        self.assertIn("LZ_WIDGETS.qr", LAUNCH)
        self.assertNotIn("http://cdn", LAUNCH)
        self.assertNotIn("https://cdn", LAUNCH)

    def test_der_code_zeigt_auf_die_verwaltung(self):
        self.assertIn("zeigeQr(d.remote_url", LAUNCH)

    def test_ohne_code_bleibt_der_block_verborgen(self):
        # Kein leerer weisser Kasten, wenn der Encoder fehlt.
        self.assertIn('id="pairing" hidden', LAUNCH)
        self.assertIn("if (!svg) return;", LAUNCH)

    def test_eine_pin_wird_angekuendigt(self):
        self.assertIn("fetch('/api/zugang')", LAUNCH)
        self.assertIn('id="pin-hinweis" hidden', LAUNCH)

    def test_der_countdown_ueberlebt_klicks_ohne_element(self):
        # Ein Klick-Ereignis am document selbst hat kein `closest`.
        self.assertIn("e.target.closest && e.target.closest('#card-present')", LAUNCH)

    def test_die_startseite_laedt(self):
        with frische_app().test_client() as c:
            r = c.get("/")
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"Mit dem Handy einrichten", r.data)


class DieErsteinrichtungSagtWasZuTunIst(unittest.TestCase):

    def test_die_karte_ist_eingebunden_und_springt_zu_den_karten(self):
        with frische_app().test_client() as c:
            html = c.get("/admin").get_data(as_text=True)
        self.assertIn('id="card-einrichtung"', html)
        for ziel in ("card-medien", "card-layouts", "card-zonen"):
            with self.subTest(ziel=ziel):
                self.assertIn(f'href="#{ziel}"', KARTE)
                self.assertIn(f'id="{ziel}"', html)

    def test_die_karte_steht_oben_und_ist_zunaechst_verborgen(self):
        # Verborgen, bis der Status sagt, dass nichts da ist — sonst blitzt
        # sie bei einer eingerichteten Station beim Laden auf.
        self.assertIn('id="card-einrichtung" hidden', KARTE)
        self.assertIn("main.insertBefore(karte, main.firstElementChild)", MODUL)

    def test_inhalt_wird_gemessen_wie_beim_autostart(self):
        # Dieselbe Regel wie templates/launch.html: Ton, Playlist, Widget.
        for teil in ("(z.audio || []).length", "r.typ === 'widget'", "(r.playlist || []).length"):
            with self.subTest(teil=teil):
                self.assertIn(teil, MODUL)
                self.assertIn(teil, LAUNCH)

    def test_ohne_daten_wird_nichts_behauptet(self):
        self.assertIn("if (!cfg) return true;", MODUL)


class DieVorschauBelegtKeineVerbindung(unittest.TestCase):

    def test_eingebettete_anzeige_ohne_eventsource(self):
        self.assertIn("var eingebettet = (vorschau || zuschauen) && window.top !== window;", DISPLAY)
        self.assertIn("if (!eingebettet) verbinde();", DISPLAY)


class EinKaputtesWoerterbuchKipptNichtDieSeite(unittest.TestCase):

    def test_nur_echte_paare_werden_uebernommen(self):
        self.assertIn("Array.isArray(t.muster) ? t.muster : []", I18N)
        self.assertIn("typeof m[0] === 'string' && typeof m[1] === 'string'", I18N)

    def test_manager_kopie_ist_gleich(self):
        manager = (WURZEL / "station-manager/renderer/i18n.js").read_text(encoding="utf-8")
        self.assertEqual(I18N, manager)


if __name__ == "__main__":
    unittest.main()

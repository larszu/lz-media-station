"""Tests fuer Untertitel und Sprachwahl.

In einer Ausstellung ist Mehrsprachigkeit fast immer ein Thema. Umgesetzt als
Untertitelspuren je Video (WebVTT) mit Sprachknoepfen auf der Anzeigeseite.

Geprueft wird der Kern (Pruefung, Heilung, der Weg durch `/api/config` und
`get_scene`) sowie am Quelltext die Stellen in `display.js`, die sonst still
zurueckfallen — das Repo hat keinen JavaScript-Lauf.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config_schema as cs  # noqa: E402
import main  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent


class Sprachliste(unittest.TestCase):
    def test_gueltige_codes(self):
        self.assertEqual(cs.pruefe_sprachen(["de", "en", "fr"]), ["de", "en", "fr"])

    def test_doppelte_werden_zusammengefasst(self):
        # Zwei gleiche Knoepfe waeren nur verwirrend.
        self.assertEqual(cs.pruefe_sprachen(["de", "en", "de"]), ["de", "en"])

    def test_die_reihenfolge_bleibt(self):
        # Sie bestimmt die Reihenfolge der Knoepfe und die Vorgabesprache.
        self.assertEqual(cs.pruefe_sprachen(["en", "de"]), ["en", "de"])

    def test_dreibuchstabiges_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            cs.pruefe_sprachen(["deu"])

    def test_grossbuchstaben_werden_abgelehnt(self):
        # Der Browser vergleicht `srclang` klein; „DE" faende nie eine Spur.
        with self.assertRaises(ValueError):
            cs.pruefe_sprachen(["DE"])

    def test_keine_liste_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            cs.pruefe_sprachen("de")

    def test_heilung_laesst_unbrauchbares_weg(self):
        self.assertEqual(cs.heile_sprachen(["de", "XX", 7, "en", None]), ["de", "en"])

    def test_heilung_von_unsinn_ergibt_leer(self):
        self.assertEqual(cs.heile_sprachen("de"), [])


class Untertitelspuren(unittest.TestCase):
    def test_gueltige_zuordnung(self):
        raus = cs.pruefe_untertitel({"f.mp4": {"de": "f-de.vtt", "en": "f-en.vtt"}})
        self.assertEqual(raus["f.mp4"]["de"], "f-de.vtt")

    def test_nur_vtt(self):
        # Eine .srt anzunehmen und stumm nicht anzuzeigen waere schlimmer als
        # sie abzulehnen: der Browser spielt nur WebVTT.
        with self.assertRaises(ValueError) as f:
            cs.pruefe_untertitel({"f.mp4": {"de": "f-de.srt"}})
        self.assertIn("vtt", str(f.exception).lower())

    def test_leerer_dateiname_loescht_die_zuordnung(self):
        # Sonst gaebe es keinen Weg, eine falsch gesetzte Spur zu entfernen.
        raus = cs.pruefe_untertitel({"f.mp4": {"de": "f-de.vtt", "en": ""}})
        self.assertNotIn("en", raus["f.mp4"])

    def test_video_ohne_spuren_faellt_weg(self):
        self.assertEqual(cs.pruefe_untertitel({"f.mp4": {"de": ""}}), {})

    def test_falscher_sprachcode_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            cs.pruefe_untertitel({"f.mp4": {"deutsch": "f.vtt"}})

    def test_heilung_verwirft_nur_den_kaputten_eintrag(self):
        # DER KERN: wer zehn Videos untertitelt hat und bei EINEM eine .srt
        # erwischt, soll die neun anderen behalten. Ein try/except um die
        # Pruefung herum wuerde alle mit wegwerfen.
        geheilt = cs.heile_untertitel({
            "a.mp4": {"de": "a.vtt"},
            "b.mp4": {"de": "b.srt"},
            "c.mp4": {"de": "c.vtt", "en": "c-en.vtt"},
        })
        self.assertIn("a.mp4", geheilt)
        self.assertNotIn("b.mp4", geheilt)
        self.assertEqual(len(geheilt["c.mp4"]), 2)

    def test_heilung_von_unsinn_ergibt_leer(self):
        self.assertEqual(cs.heile_untertitel("nichts"), {})


class UeberDieApi(unittest.TestCase):
    def app(self):
        from web_ui import create_app
        self.controller = main.Controller(main.load_config())
        self.controller.save_config = lambda: None
        return create_app(self.controller)

    def test_sprachen_und_spuren_werden_gespeichert(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "sprachen": ["de", "en"],
                "untertitel": {"f.mp4": {"de": "f-de.vtt"}}})
            self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.config["sprachen"], ["de", "en"])
        self.assertEqual(self.controller.config["untertitel"]["f.mp4"]["de"], "f-de.vtt")

    def test_kaputter_code_wird_abgelehnt(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={"sprachen": ["deutsch"]})
            self.assertEqual(antwort.status_code, 400)
            self.assertIn("sprachen", antwort.get_json()["error"])

    def test_die_szene_bringt_sprachen_und_spuren_mit(self):
        app = self.app()
        self.controller.config["sprachen"] = ["de", "en"]
        self.controller.config["untertitel"] = {"f.mp4": {"de": "f-de.vtt"}}
        with app.test_client() as c:
            szene = c.get("/api/scene").get_json()
        self.assertEqual(szene["sprachen"], ["de", "en"])
        self.assertIn("f.mp4", szene["untertitel"])

    def test_untertitel_sind_eine_eigene_medienart(self):
        with self.app().test_client() as c:
            self.assertEqual(c.get("/api/media/subtitles").status_code, 200)

    def test_untertitel_lassen_sich_keiner_zone_zuweisen(self):
        # Sie haengen an einem VIDEO, nicht an einer Entfernung. Stuenden sie
        # in MEDIENARTEN, liesse sich eine .vtt einer Zone zuordnen und
        # niemand wuesste, was das bedeuten soll.
        self.assertNotIn("subtitles", cs.MEDIENARTEN)


class Anzeigeseite(unittest.TestCase):
    """Quelltext-Zusicherungen fuer `display.js`."""

    def setUp(self):
        quelle = (WURZEL / "static/display.js").read_text(encoding="utf-8")
        quelle = re.sub(r"/\*.*?\*/", "", quelle, flags=re.S)
        self.quelle = re.sub(r"(?m)//.*$", "", quelle)

    def test_alte_spuren_werden_entfernt(self):
        # Die Video-Elemente werden wiederverwendet (A/B-Paar); uebrig
        # gebliebene <track> eines anderen Films wuerden mitlaufen.
        self.assertIn("removeChild", self.quelle)

    def test_die_sprachliste_wird_vor_der_hash_abkuerzung_uebernommen(self):
        # Stuende `uebernimmSprachen` dahinter, erschienen die Knoepfe erst
        # beim naechsten Zonenwechsel — also womoeglich nie.
        vor_abkuerzung = self.quelle.index("uebernimmSprachen(scene)")
        abkuerzung = self.quelle.index("if (hash === currentHash) return;")
        self.assertLess(vor_abkuerzung, abkuerzung)

    def test_die_spur_wird_erst_nach_canplay_gesetzt(self):
        # Vorher ist `textTracks` noch leer, und die Auswahl liefe ins Leere.
        self.assertIn("wendeSpracheAn", self.quelle)

    def test_eine_einzige_sprache_ist_keine_wahl(self):
        self.assertIn("sprachen.length < 2", self.quelle)


if __name__ == "__main__":
    unittest.main()

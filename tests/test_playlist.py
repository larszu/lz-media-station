"""Tests fuer die Wiedergabe-Optionen einer Zone.

Eine Zone traegt seit 2026-09-16 mehr als drei Medienlisten: `shuffle`
(zufaellige Reihenfolge), `einmal` (einmal durchspielen statt zu wiederholen)
und `bildzeiten` (eigene Standzeit je Bild).

WAS HIER GEPRUEFT WIRD: der Kern — Heilung, Pruefung, der Weg durch
`/api/config` und `get_scene`. Die Wiedergabe selbst liegt in `display.js`;
dieses Repo hat keinen JavaScript-Lauf, und ein Waechter, der nur den
Quelltext sehen kann, ist ehrlicher als gar keiner — deshalb am Ende ein paar
Quelltext-Zusicherungen fuer die Stellen, die sonst still zurueckfallen.

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


class StandardZone(unittest.TestCase):
    def test_eine_zone_hat_alle_optionen(self):
        z = cs.standard_zone()
        for schluessel in ("videos", "images", "audio", "shuffle", "einmal", "bildzeiten"):
            self.assertIn(schluessel, z)

    def test_die_vorgabe_aendert_das_verhalten_nicht(self):
        # Rueckwaertskompatibel: ohne Zutun spielt die Station wie vorher.
        z = cs.standard_zone()
        self.assertFalse(z["shuffle"])
        self.assertFalse(z["einmal"])
        self.assertEqual(z["bildzeiten"], {})

    def test_zonen_teilen_sich_keine_objekte(self):
        # Sonst aendert das Verstellen von `near` auch `far`.
        a, b = cs.standard_zone(), cs.standard_zone()
        a["videos"].append("x.mp4")
        a["bildzeiten"]["y.jpg"] = 5
        self.assertEqual(b["videos"], [])
        self.assertEqual(b["bildzeiten"], {})


class Heilung(unittest.TestCase):
    def test_unsinn_wird_zur_leeren_zone(self):
        for murks in (None, [], "nah", 42):
            self.assertEqual(cs.heile_zone(murks), cs.standard_zone())

    def test_vorhandene_listen_ueberleben(self):
        z = cs.heile_zone({"videos": ["a.mp4"], "shuffle": True})
        self.assertEqual(z["videos"], ["a.mp4"])
        self.assertTrue(z["shuffle"])

    def test_kaputte_bildzeiten_werden_verworfen_statt_zu_werfen(self):
        z = cs.heile_zone({"bildzeiten": {"a.jpg": "lang", "b.jpg": 8, "c.jpg": 99999}})
        self.assertEqual(z["bildzeiten"], {"b.jpg": 8.0},
                         "nur der brauchbare Wert bleibt")

    def test_nicht_listen_in_medienarten_werden_ersetzt(self):
        z = cs.heile_zone({"videos": "a.mp4"})
        self.assertEqual(z["videos"], [])


class Schreibweg(unittest.TestCase):
    def test_gueltige_optionen_kommen_durch(self):
        teil = cs.pruefe_zone({"shuffle": True, "einmal": True,
                               "bildzeiten": {"a.jpg": 12}})
        self.assertTrue(teil["shuffle"])
        self.assertEqual(teil["bildzeiten"]["a.jpg"], 12.0)

    def test_schalter_muss_ein_schalter_sein(self):
        with self.assertRaises(ValueError):
            cs.pruefe_zone({"shuffle": "ja"})

    def test_bildzeit_ausserhalb_wird_abgelehnt(self):
        # Ablehnen statt heilen: wer eine Standzeit setzt, soll erfahren, dass
        # sie nicht angekommen ist.
        with self.assertRaises(ValueError) as f:
            cs.pruefe_zone({"bildzeiten": {"a.jpg": 0}})
        self.assertIn("a.jpg", str(f.exception))

    def test_nur_genannte_felder_kommen_zurueck(self):
        # Sonst ueberschriebe ein Patch mit nur `shuffle` die Medienlisten.
        teil = cs.pruefe_zone({"shuffle": True})
        self.assertEqual(set(teil), {"shuffle"})


class UeberDieApi(unittest.TestCase):
    def app(self):
        from web_ui import create_app
        self.controller = main.Controller(main.load_config())
        self.controller.save_config = lambda: None
        return create_app(self.controller)

    def test_optionen_werden_gespeichert(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "near": {"shuffle": True, "einmal": True}})
            self.assertEqual(antwort.status_code, 200)
        self.assertTrue(self.controller.config["near"]["shuffle"])
        self.assertTrue(self.controller.config["near"]["einmal"])

    def test_ein_patch_loescht_die_medienlisten_nicht(self):
        # Der Fall, der im Betrieb wehtut: ein Klick auf „Zufaellige
        # Reihenfolge" darf nicht die Zuweisung der Zone leeren.
        app = self.app()
        self.controller.config["near"]["videos"] = ["a.mp4"]
        with app.test_client() as c:
            c.post("/api/config", json={"near": {"shuffle": True}})
        self.assertEqual(self.controller.config["near"]["videos"], ["a.mp4"])

    def test_kaputte_bildzeit_wird_mit_feldnamen_abgelehnt(self):
        with self.app().test_client() as c:
            antwort = c.post("/api/config", json={
                "near": {"bildzeiten": {"a.jpg": 99999}}})
            self.assertEqual(antwort.status_code, 400)
            self.assertIn("near", antwort.get_json()["error"])

    def test_die_szene_reicht_die_optionen_durch(self):
        # Waeren sie im Kern da und auf dem Schirm nicht, liesse sich der
        # Fehler nur am Verhalten erraten.
        app = self.app()
        self.controller.config["near"]["shuffle"] = True
        with app.test_client() as c:
            szene = c.get("/api/scene").get_json()
        self.assertTrue(szene["near"]["shuffle"])
        self.assertIn("bildzeiten", szene["near"])


def ohne_kommentare(js):
    """Kommentare raus, BEVOR gemessen wird.

    Sonst misst der Waechter seine eigene Begruendung: der Kommentar ueber der
    Stelle nennt den alten, falschen Ausdruck beim Namen — und ein Test, der
    danach sucht, wuerde ihn genau dort finden, wo erklaert wird, warum es ihn
    nicht mehr gibt. (Dasselbe Vorgehen wie in `test_schieberegler.py`.)
    """
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)//.*$", "", js)


class Anzeigeseite(unittest.TestCase):
    """Quelltext-Zusicherungen fuer `display.js` — das Repo hat keinen
    JavaScript-Lauf, und diese Stellen fallen sonst still zurueck."""

    def setUp(self):
        self.quelle = ohne_kommentare(
            (WURZEL / "static/display.js").read_text(encoding="utf-8"))

    def teil(self, name):
        """Den Rumpf EINER Funktion herausschneiden.

        Ohne diesen Zuschnitt misst der Test die ganze Datei: `setInterval`
        steht dort voellig zu Recht (die Ton-Blende), und ein Waechter, der
        deshalb rot wird, wird beim naechsten Mal angepasst statt gelesen.
        """
        start = self.quelle.index("function " + name)
        rest = self.quelle[start:]
        naechste = re.search(r"\n    function ", rest[1:])
        return rest[:naechste.start()] if naechste else rest

    def test_die_liste_wird_auf_einer_kopie_gemischt(self):
        # An Ort und Stelle zu mischen waere wirkungslos: `/api/scene` liefert
        # die Liste bei jedem Poll neu.
        self.assertIn("liste.slice()", self.teil("mischen"))

    def test_die_wiedergabe_haengt_nicht_mehr_an_videos_null(self):
        # DER DEFEKT, den die Kennung abloest: der Vergleich mit dem ERSTEN
        # Eintrag sprang nach dem ersten Video zurueck auf das erste, weil der
        # naechste Poll ihn wieder wahr fand. Eine Playlist mit mehreren
        # Videos spielte faktisch nur das erste.
        rumpf = self.teil("applyScene")
        self.assertNotIn("currentVideoFile !== videos[0]", rumpf)
        self.assertNotIn("currentAudioFile !== audio[0]", rumpf)
        self.assertIn("currentVideoSet", rumpf)
        self.assertIn("currentAudioSet", rumpf)

    def test_die_diashow_laeuft_ueber_eine_timeout_kette(self):
        # Mit `setInterval` haetten alle Bilder dieselbe Standzeit, und
        # `bildzeiten` waere wirkungslos.
        rumpf = self.teil("startSlideshow")
        self.assertNotIn("setInterval", rumpf)
        self.assertIn("setTimeout(", rumpf)
        self.assertIn("standzeit", rumpf)

    def test_einmal_wird_an_allen_drei_stellen_beachtet(self):
        # Video, Audio und Diashow — faellt eine weg, laeuft die Zone dort
        # weiter in der Schleife, und das faellt erst in der Ausstellung auf.
        self.assertIn("zoneEinmal", self.teil("startSlideshow"), "Diashow")
        self.assertIn("zoneEinmal", self.teil("crossfadeVideo"), "Video")
        self.assertIn("zoneEinmal", self.teil("playAudio"), "Audio")


if __name__ == "__main__":
    unittest.main()

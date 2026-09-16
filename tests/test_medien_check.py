"""Tests fuer `medien_check.py` und die Sicherung/Wiederherstellung.

Der haeufigste Ausfallgrund einer Medienstation ist kein Defekt, sondern eine
Datei: ein 4K-Video mit 60 fps sieht auf dem Notebook grossartig aus und
ruckelt auf dem Pi zur Diashow.

WARUM `beurteile` rein ist: ein echtes 4K-Video in die CI zu legen, nur um
eine Warnung auszuloesen, waere absurd. Die Messung (`ffprobe`) ist deshalb
vom Urteil getrennt — und genau das Urteil wird hier geprueft.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
import medien_check as mc  # noqa: E402


class Beurteilung(unittest.TestCase):
    def test_gutes_video_bekommt_keine_hinweise(self):
        self.assertEqual(
            mc.beurteile(breite=1920, hoehe=1080, codec="h264",
                         bildrate=25.0, bitrate=8_000_000),
            [])

    def test_vier_k_wird_gemeldet(self):
        hinweise = mc.beurteile(breite=3840, hoehe=2160, codec="h264", bildrate=25.0)
        self.assertEqual(len(hinweise), 1)
        self.assertIn("3840x2160", hinweise[0])

    def test_fremder_codec_wird_gemeldet(self):
        hinweise = mc.beurteile(breite=1280, hoehe=720, codec="vp9", bildrate=25.0)
        self.assertTrue(any("vp9" in h for h in hinweise))

    def test_hohe_bildrate_wird_gemeldet(self):
        hinweise = mc.beurteile(breite=1920, hoehe=1080, codec="h264", bildrate=60.0)
        self.assertTrue(any("Bilder/s" in h for h in hinweise))

    def test_hohe_bitrate_wird_gemeldet(self):
        hinweise = mc.beurteile(breite=1920, hoehe=1080, codec="h264",
                                bildrate=25.0, bitrate=80_000_000)
        self.assertTrue(any("Mbit/s" in h for h in hinweise))

    def test_mehrere_probleme_geben_mehrere_hinweise(self):
        hinweise = mc.beurteile(breite=3840, hoehe=2160, codec="vp9",
                                bildrate=60.0, bitrate=90_000_000)
        self.assertEqual(len(hinweise), 4)

    def test_fehlende_angaben_erfinden_nichts(self):
        # Konnte etwas nicht ermittelt werden, darf daraus keine Warnung
        # entstehen — und auch keine Entwarnung.
        self.assertEqual(mc.beurteile(), [])

    def test_1080p_genau_an_der_grenze_ist_in_ordnung(self):
        # Die Grenze ist einschliessend: 1920x1080 ist genau das, was der Pi
        # zuverlaessig schafft.
        self.assertEqual(mc.beurteile(breite=1920, hoehe=1080, codec="h264"), [])


class Bildrate(unittest.TestCase):
    def test_bruch_wird_gerechnet(self):
        self.assertAlmostEqual(mc._bildrate("30000/1001"), 29.97, places=2)

    def test_ganze_zahl_als_bruch(self):
        self.assertAlmostEqual(mc._bildrate("25/1"), 25.0)

    def test_null_nenner_wirft_nicht(self):
        # ffprobe liefert "0/0" fuer Spuren ohne Bildrate.
        self.assertIsNone(mc._bildrate("0/0"))

    def test_unsinn_wirft_nicht(self):
        for text in (None, "", "25", "abc/def"):
            self.assertIsNone(mc._bildrate(text))


class OhneFfprobe(unittest.TestCase):
    def test_fehlendes_programm_ist_kein_fehler(self):
        # Ein fehlendes Hilfsprogramm darf keinen Upload verhindern.
        with mock.patch.object(mc.shutil, "which", return_value=None):
            geprueft, hinweise = mc.pruefe_datei("/tmp/irgendwas.mp4")
        self.assertFalse(geprueft, 'nicht geprueft ist keine Entwarnung')
        self.assertEqual(hinweise, [])

    def test_kaputte_datei_wirft_nicht(self):
        with mock.patch.object(mc.shutil, "which", return_value="/usr/bin/ffprobe"), \
             mock.patch.object(mc.subprocess, "run", side_effect=OSError("kaputt")):
            geprueft, hinweise = mc.pruefe_datei("/tmp/kaputt.mp4")
        self.assertFalse(geprueft)
        self.assertEqual(hinweise, [])


class MitFfprobe(unittest.TestCase):
    def laufe(self, spur, format_=None):
        antwort = mock.Mock()
        antwort.stdout = json.dumps({"streams": [spur], "format": format_ or {}})
        with mock.patch.object(mc.shutil, "which", return_value="/usr/bin/ffprobe"), \
             mock.patch.object(mc.subprocess, "run", return_value=antwort):
            return mc.pruefe_datei("/tmp/x.mp4")

    def test_gutes_video(self):
        geprueft, hinweise = self.laufe(
            {"width": 1920, "height": 1080, "codec_name": "h264",
             "avg_frame_rate": "25/1", "bit_rate": "8000000"})
        self.assertTrue(geprueft)
        self.assertEqual(hinweise, [])

    def test_vier_k_video(self):
        geprueft, hinweise = self.laufe(
            {"width": 3840, "height": 2160, "codec_name": "h264",
             "avg_frame_rate": "60/1"})
        self.assertTrue(geprueft)
        self.assertEqual(len(hinweise), 2)

    def test_bitrate_aus_dem_container(self):
        # Je nach Container steht die Bitrate nicht in der Spur, sondern im
        # Format. Wer nur die Spur liest, uebersieht sie.
        _geprueft, hinweise = self.laufe(
            {"width": 1920, "height": 1080, "codec_name": "h264", "avg_frame_rate": "25/1"},
            format_={"bit_rate": "90000000"})
        self.assertTrue(any("Mbit/s" in h for h in hinweise))

    def test_ohne_videospur(self):
        antwort = mock.Mock()
        antwort.stdout = json.dumps({"streams": []})
        with mock.patch.object(mc.shutil, "which", return_value="/usr/bin/ffprobe"), \
             mock.patch.object(mc.subprocess, "run", return_value=antwort):
            geprueft, _ = mc.pruefe_datei("/tmp/x.mp4")
        self.assertFalse(geprueft)


class SicherungUndWiederherstellung(unittest.TestCase):
    def app(self):
        from web_ui import create_app
        self.controller = main.Controller(json.loads(json.dumps(main.DEFAULT_CONFIG)))
        self.controller.save_config = lambda: None
        return create_app(self.controller)

    def test_sicherung_kommt_als_download(self):
        with self.app().test_client() as c:
            antwort = c.get("/api/backup")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("attachment", antwort.headers["Content-Disposition"])
        self.assertIn("system_name", antwort.get_json())

    def test_wiederherstellen_uebernimmt_die_werte(self):
        app = self.app()
        sicherung = dict(main.DEFAULT_CONFIG)
        sicherung["system_name"] = "Aus der Sicherung"
        sicherung["threshold_m"] = 2.5
        with app.test_client() as c:
            antwort = c.post("/api/restore", json=sicherung)
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.config["system_name"], "Aus der Sicherung")
        self.assertEqual(self.controller.config["threshold_m"], 2.5)

    def test_eine_alte_sicherung_wird_geheilt_statt_abgelehnt(self):
        # DER KERN: anders als /api/config wird hier GEHEILT. Eine Sicherung
        # kann aus einer aelteren Fassung stammen; eine Wiederherstellung, die
        # an einem veralteten Feld scheitert, ist im Ernstfall (Karte tot,
        # Ausstellung oeffnet) genau das, was niemand gebrauchen kann.
        app = self.app()
        alt = {"system_name": "Alt", "threshold_m": "unsinn", "near": []}
        with app.test_client() as c:
            antwort = c.post("/api/restore", json=alt)
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.controller.config["system_name"], "Alt")
        self.assertEqual(self.controller.config["threshold_m"],
                         main.DEFAULT_CONFIG["threshold_m"])
        self.assertIsInstance(self.controller.config["near"], dict)

    def test_fehlende_felder_werden_ergaenzt(self):
        app = self.app()
        with app.test_client() as c:
            c.post("/api/restore", json={"system_name": "Knapp"})
        for schluessel in main.DEFAULT_CONFIG:
            self.assertIn(schluessel, self.controller.config)

    def test_unbekannte_felder_wandern_nicht_ein(self):
        # Sonst waechst die Konfiguration mit jedem Einspielen um Altlasten.
        app = self.app()
        with app.test_client() as c:
            c.post("/api/restore", json={"system_name": "X", "erfunden": 1})
        self.assertNotIn("erfunden", self.controller.config)

    def test_unlesbares_wird_abgelehnt(self):
        with self.app().test_client() as c:
            self.assertEqual(c.post("/api/restore", json=["liste"]).status_code, 400)


if __name__ == "__main__":
    unittest.main()

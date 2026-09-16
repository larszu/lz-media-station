"""Tests fuer `gesundheit.py` — was an der Station gerade nicht stimmt.

Die Lage wird HEREINGEREICHT (Sensorzustand, freier Platz, vorhandene
Dateien). Genau darum sind die unangenehmen Faelle ueberhaupt pruefbar: eine
fast volle Platte oder eine fehlende Mediendatei liessen sich mit echtem
Dateisystem in einer CI nicht herstellen.

Der lehrreichste Fall ist die Stille: ausserhalb der Oeffnungszeiten darf
„keine Messung" KEIN Fehler sein. Ein Melder, der jede Nacht anschlaegt, wird
abgeschaltet — und meldet dann auch den echten Ausfall nicht mehr.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gesundheit  # noqa: E402

VIEL_PLATZ = 50 * 1024 * 1024 * 1024


def config(near=("a.mp4",), far=("b.mp4",)):
    return {
        "near": {"videos": list(near), "images": [], "audio": []},
        "far": {"videos": list(far), "images": [], "audio": []},
    }


def vorhanden(*namen):
    return {"videos": set(namen), "images": set(), "audio": set()}


def pruefe(**ueberschreiben):
    argumente = dict(
        config=config(),
        sensor_ok=True,
        sensor_status="HC-SR04",
        freier_platz_b=VIEL_PLATZ,
        vorhandene=vorhanden("a.mp4", "b.mp4"),
        aktiv=True,
        geschlossen=False,
    )
    argumente.update(ueberschreiben)
    return gesundheit.pruefe(**argumente)


def themen(befunde):
    return {b["thema"] for b in befunde}


class AllesInOrdnung(unittest.TestCase):
    def test_gesunde_station_meldet_nichts(self):
        self.assertEqual(pruefe(), [])

    def test_gesamtstufe_ohne_befunde_ist_ok(self):
        self.assertEqual(gesundheit.gesamtstufe([]), "ok")


class Sensor(unittest.TestCase):
    def test_keine_messung_ist_ein_fehler(self):
        befunde = pruefe(sensor_ok=False, sensor_status="kein Sensor: gpiozero fehlt")
        self.assertIn("sensor", themen(befunde))
        self.assertEqual(gesundheit.gesamtstufe(befunde), "fehler")

    def test_der_grund_steht_im_text(self):
        # Sonst muss jemand ins Log steigen, um zu erfahren, was fehlt.
        befunde = pruefe(sensor_ok=False, sensor_status="kein Sensor: gpiozero fehlt")
        text = [b["text"] for b in befunde if b["thema"] == "sensor"][0]
        self.assertIn("gpiozero", text)

    def test_nachts_ist_keine_messung_KEIN_fehler(self):
        # Der Kern dieses Moduls. Ausserhalb der Oeffnungszeit soll gar nicht
        # ausgeloest werden -- das jede Nacht zu melden waere ein Daueralarm.
        befunde = pruefe(sensor_ok=False, geschlossen=True)
        self.assertNotIn("sensor", themen(befunde))


class Platte(unittest.TestCase):
    def test_fast_voll_ist_ein_fehler(self):
        befunde = pruefe(freier_platz_b=50 * 1024 * 1024)
        self.assertIn("platte", themen(befunde))
        self.assertEqual(gesundheit.gesamtstufe(befunde), "fehler")

    def test_knapp_ist_eine_warnung(self):
        befunde = pruefe(freier_platz_b=500 * 1024 * 1024)
        platte = [b for b in befunde if b["thema"] == "platte"][0]
        self.assertEqual(platte["stufe"], "warnung")

    def test_genug_platz_meldet_nichts(self):
        self.assertNotIn("platte", themen(pruefe()))

    def test_unbekannter_platz_meldet_nichts(self):
        # Laesst sich der Platz nicht ermitteln, ist das kein Befund -- lieber
        # nichts sagen als etwas Falsches.
        self.assertNotIn("platte", themen(pruefe(freier_platz_b=None)))


class MedienJeZone(unittest.TestCase):
    def test_leere_zone_wird_gemeldet(self):
        befunde = pruefe(config=config(near=()))
        self.assertIn("zone_near", themen(befunde))

    def test_fehlende_datei_ist_ein_fehler(self):
        # Zugewiesen, aber nicht mehr auf der Platte -- passiert, wenn jemand
        # Dateien per SSH/USB entfernt. Die Zuweisung bleibt, die Anzeige
        # laeuft ins Leere.
        befunde = pruefe(vorhandene=vorhanden("b.mp4"))
        self.assertIn("medien_near", themen(befunde))
        self.assertEqual(gesundheit.gesamtstufe(befunde), "fehler")

    def test_der_dateiname_steht_im_text(self):
        befunde = pruefe(vorhandene=vorhanden("b.mp4"))
        text = [b["text"] for b in befunde if b["thema"] == "medien_near"][0]
        self.assertIn("a.mp4", text)

    def test_leere_zone_meldet_nicht_zusaetzlich_fehlende_dateien(self):
        # Sonst stuenden fuer dieselbe Ursache zwei Befunde da.
        befunde = pruefe(config=config(near=()))
        self.assertNotIn("medien_near", themen(befunde))

    def test_beide_zonen_werden_geprueft(self):
        befunde = pruefe(config=config(near=(), far=()))
        self.assertIn("zone_near", themen(befunde))
        self.assertIn("zone_far", themen(befunde))


class Betriebszustand(unittest.TestCase):
    def test_gestoppt_wird_gemeldet(self):
        self.assertIn("gestoppt", themen(pruefe(aktiv=False)))

    def test_geschlossen_ist_nur_ein_hinweis(self):
        befunde = pruefe(geschlossen=True)
        zeitplan = [b for b in befunde if b["thema"] == "zeitplan"][0]
        self.assertEqual(zeitplan["stufe"], "hinweis")
        # Ein Hinweis darf die Gesamtstufe nicht auf "warnung" heben.
        self.assertEqual(gesundheit.gesamtstufe(befunde), "hinweis")


class Gesamtstufe(unittest.TestCase):
    def test_die_schlimmste_stufe_gewinnt(self):
        befunde = [{"stufe": "hinweis"}, {"stufe": "fehler"}, {"stufe": "warnung"}]
        self.assertEqual(gesundheit.gesamtstufe(befunde), "fehler")

    def test_warnung_schlaegt_hinweis(self):
        self.assertEqual(
            gesundheit.gesamtstufe([{"stufe": "hinweis"}, {"stufe": "warnung"}]),
            "warnung")


class UeberDieApi(unittest.TestCase):
    def app(self):
        import main
        from web_ui import create_app
        self.controller = main.Controller(dict(main.DEFAULT_CONFIG))
        return create_app(self.controller)

    def test_health_liefert_stufe_und_befunde(self):
        with self.app().test_client() as c:
            d = c.get("/api/health").get_json()
        self.assertIn("stufe", d)
        self.assertIn("befunde", d)
        self.assertIn(d["stufe"], gesundheit.STUFEN)

    def test_identity_nennt_die_stufe_mit(self):
        # Der Station Manager fragt beim Scannen ohnehin die Identitaet ab --
        # ein zweiter Aufruf je Station nur fuer die Gesundheit waere dieselbe
        # Runde ein zweites Mal.
        with self.app().test_client() as c:
            d = c.get("/api/identity").get_json()
        self.assertIn("health", d)
        self.assertIn("health_anzahl", d)


if __name__ == "__main__":
    unittest.main()

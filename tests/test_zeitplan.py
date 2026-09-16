"""Tests fuer `zeitplan.py` — wann die Station spielt.

Die Uhrzeit wird hereingereicht, nie gelesen: ein Test, der um 23:59 anders
ausgeht als um 00:01, macht eine CI unglaubwuerdig. Deshalb sind hier feste
`datetime`-Werte eingesetzt, und die Logik ist rein.

Der lehrreichste Fall ist das Fenster UEBER MITTERNACHT (20:00 bis 02:00). Wer
nur `von <= t < bis` rechnet, sperrt genau die Stunden aus, fuer die eine
Spaetoeffnung gemacht ist — und merkt es erst am Abend der Veranstaltung.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zeitplan  # noqa: E402


# 2026-09-14 ist ein MONTAG. Alle Zeitpunkte unten haengen daran, damit der
# Wochentag im Test sichtbar ist statt gerechnet werden zu muessen.
def montag(stunde, minute=0):
    return datetime(2026, 9, 14, stunde, minute)


def dienstag(stunde, minute=0):
    return datetime(2026, 9, 15, stunde, minute)


def plan(aktiv=True, **tage):
    """Kleiner Bauhelfer: nur die genannten Tage abweichend, Rest zu."""
    p = zeitplan.standard_zeitplan()
    p["aktiv"] = aktiv
    for tag in zeitplan.TAGE:
        p["tage"][tag] = {"an": False, "von": "00:00", "bis": "24:00"}
    for tag, wert in tage.items():
        p["tage"][tag] = wert
    return p


class Uhrzeiten(unittest.TestCase):
    def test_gewoehnliche_zeit(self):
        self.assertEqual(zeitplan.minuten("09:30"), 9 * 60 + 30)

    def test_mitternacht_als_ende_ist_erlaubt(self):
        # Sonst muesste man 23:59 schreiben und haette eine Minute Luecke.
        self.assertEqual(zeitplan.minuten("24:00", ende=True), 24 * 60)

    def test_mitternacht_als_beginn_ist_nicht_erlaubt(self):
        with self.assertRaises(ValueError):
            zeitplan.minuten("24:00")

    def test_nach_24_uhr_gibt_es_keine_minuten(self):
        with self.assertRaises(ValueError):
            zeitplan.minuten("24:30", ende=True)

    def test_unsinn_wirft(self):
        for text in ("neun", "9.30", "09:70", "25:00", "", None, 930):
            with self.assertRaises(ValueError, msg=f"{text!r} durfte nicht durchgehen"):
                zeitplan.minuten(text)


class AusgeschalteteZeitsteuerung(unittest.TestCase):
    def test_aus_heisst_immer_offen(self):
        # Vorgabe ist AUS -- eine bestehende Installation darf sich durch das
        # neue Feature nicht anders verhalten.
        p = zeitplan.standard_zeitplan()
        self.assertFalse(p["aktiv"])
        self.assertTrue(zeitplan.ist_offen(p, montag(3)))

    def test_kaputter_plan_sperrt_nicht(self):
        # Eine verhunzte Konfiguration darf eine Ausstellung nicht stumm
        # schalten -- im Zweifel spielt sie.
        for murks in (None, "jeden tag", 42, {}, {"aktiv": True}):
            self.assertTrue(zeitplan.ist_offen(murks, montag(12)),
                            f"{murks!r} haette nicht sperren duerfen")


class GewoehnlichesFenster(unittest.TestCase):
    def setUp(self):
        self.p = plan(mo={"an": True, "von": "09:00", "bis": "18:00"})

    def test_mitten_drin_offen(self):
        self.assertTrue(zeitplan.ist_offen(self.p, montag(12)))

    def test_beginn_ist_offen(self):
        self.assertTrue(zeitplan.ist_offen(self.p, montag(9, 0)))

    def test_ende_ist_zu(self):
        # 18:00 ist das Ende, nicht die letzte offene Minute.
        self.assertFalse(zeitplan.ist_offen(self.p, montag(18, 0)))
        self.assertTrue(zeitplan.ist_offen(self.p, montag(17, 59)))

    def test_davor_und_danach_zu(self):
        self.assertFalse(zeitplan.ist_offen(self.p, montag(8, 59)))
        self.assertFalse(zeitplan.ist_offen(self.p, montag(23)))

    def test_anderer_tag_ist_zu(self):
        self.assertFalse(zeitplan.ist_offen(self.p, dienstag(12)))


class FensterUeberMitternacht(unittest.TestCase):
    """Der Fall, den eine naive `von <= t < bis`-Rechnung falsch macht."""

    def setUp(self):
        # Montag 20:00 bis Dienstag 02:00.
        self.p = plan(mo={"an": True, "von": "20:00", "bis": "02:00"})

    def test_abends_am_selben_tag_offen(self):
        self.assertTrue(zeitplan.ist_offen(self.p, montag(21)))

    def test_nach_mitternacht_noch_offen(self):
        # Das ist der Kern: 01:00 am DIENSTAG gehoert zum Fenster des MONTAGS.
        self.assertTrue(zeitplan.ist_offen(self.p, dienstag(1)))

    def test_ende_nach_mitternacht_schliesst(self):
        self.assertFalse(zeitplan.ist_offen(self.p, dienstag(2, 0)))
        self.assertTrue(zeitplan.ist_offen(self.p, dienstag(1, 59)))

    def test_montag_frueh_ist_zu(self):
        # Der Sonntag ist zu, also darf der Montagmorgen nicht offen sein --
        # sonst wuerde das Uebernacht-Stueck vom falschen Tag geerbt.
        self.assertFalse(zeitplan.ist_offen(self.p, montag(1)))

    def test_luecke_am_tag_bleibt_zu(self):
        self.assertFalse(zeitplan.ist_offen(self.p, montag(12)))


class Ganztags(unittest.TestCase):
    def test_null_bis_vierundzwanzig_ist_immer_offen(self):
        p = plan(mo={"an": True, "von": "00:00", "bis": "24:00"})
        for stunde in (0, 7, 12, 23):
            self.assertTrue(zeitplan.ist_offen(p, montag(stunde)))

    def test_gleicher_beginn_und_ende_ist_zu(self):
        # Ein Null-Fenster. Absichtlich NICHT als "ganztags" gedeutet: dafuer
        # gibt es 00:00 bis 24:00, und Raten waere hier gefaehrlich.
        p = plan(mo={"an": True, "von": "10:00", "bis": "10:00"})
        self.assertFalse(zeitplan.ist_offen(p, montag(10, 30)))

    def test_tag_ausgeschaltet_ist_zu(self):
        p = plan(mo={"an": False, "von": "00:00", "bis": "24:00"})
        self.assertFalse(zeitplan.ist_offen(p, montag(12)))


class Schreibweg(unittest.TestCase):
    def test_gueltiger_plan_kommt_durch(self):
        roh = {"aktiv": True, "tage": {"mo": {"an": True, "von": "09:00", "bis": "18:00"}}}
        raus = zeitplan.pruefe_zeitplan(roh)
        self.assertTrue(raus["aktiv"])
        self.assertEqual(raus["tage"]["mo"]["von"], "09:00")
        # Nicht genannte Tage bekommen die Vorgabe, nicht "fehlt".
        self.assertEqual(set(raus["tage"]), set(zeitplan.TAGE))

    def test_unbekannter_tag_wird_abgelehnt(self):
        with self.assertRaises(ValueError) as f:
            zeitplan.pruefe_zeitplan({"tage": {"montag": dict(zeitplan.STANDARD_TAG)}})
        self.assertIn("montag", str(f.exception))

    def test_kaputte_uhrzeit_wird_abgelehnt(self):
        with self.assertRaises(ValueError) as f:
            zeitplan.pruefe_zeitplan({"tage": {"mo": {"an": True, "von": "25:00", "bis": "18:00"}}})
        self.assertIn("mo", str(f.exception))

    def test_leeres_fenster_wird_abgelehnt(self):
        # Sonst legt jemand still eine Station lahm.
        with self.assertRaises(ValueError):
            zeitplan.pruefe_zeitplan({"tage": {"mo": {"an": True, "von": "10:00", "bis": "10:00"}}})

    def test_aktiv_muss_ein_schalter_sein(self):
        with self.assertRaises(ValueError):
            zeitplan.pruefe_zeitplan({"aktiv": "ja"})


class Ladeweg(unittest.TestCase):
    def test_fehlender_plan_wird_zur_vorgabe(self):
        self.assertEqual(zeitplan.heile_zeitplan(None), zeitplan.standard_zeitplan())

    def test_kaputter_tag_wird_geheilt_statt_zu_werfen(self):
        roh = {"aktiv": True, "tage": {"mo": {"an": True, "von": "25:00", "bis": "18:00"}}}
        geheilt = zeitplan.heile_zeitplan(roh)
        self.assertTrue(geheilt["aktiv"])
        self.assertEqual(geheilt["tage"]["mo"], zeitplan.STANDARD_TAG)

    def test_alle_sieben_tage_sind_danach_da(self):
        geheilt = zeitplan.heile_zeitplan({"aktiv": True, "tage": {"mo": dict(zeitplan.STANDARD_TAG)}})
        self.assertEqual(set(geheilt["tage"]), set(zeitplan.TAGE))

    def test_gueltiges_bleibt_erhalten(self):
        roh = {"aktiv": True, "tage": {"fr": {"an": True, "von": "20:00", "bis": "02:00"}}}
        geheilt = zeitplan.heile_zeitplan(roh)
        self.assertEqual(geheilt["tage"]["fr"]["bis"], "02:00")

    def test_die_tage_teilen_sich_kein_objekt(self):
        # Sonst aendert das Verstellen eines Tages alle sieben.
        p = zeitplan.standard_zeitplan()
        p["tage"]["mo"]["von"] = "09:00"
        self.assertEqual(p["tage"]["di"]["von"], "00:00")


if __name__ == "__main__":
    unittest.main()

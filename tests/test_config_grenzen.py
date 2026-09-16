"""Der Vertrag kennt die Bedeutung der Felder, nicht nur ihre Namen.

BEFUND (Defektformen-Sweep, Form `vertrag-nur-feldnamen`, gemessen
2026-09-07). `web_ui.api_config` hatte einen Vertrag — eine Tabelle aus
FELDNAME auf Typ:

    simple = { "system_name": str, "threshold_m": float, "delay_s": float,
               "gpio_trigger": int, "gpio_echo": int, "web_port": int, ... }
    for key, cast in simple.items():
        if key in data:
            try: controller.config[key] = cast(data[key])
            except (ValueError, TypeError): pass

Der Name stimmte, der Typ stimmte, und damit war die Pruefung zu Ende. Was
durchging und erst beim naechsten Start auffiel — auf einem Geraet, das
unbeaufsichtigt in einer Ausstellung steht:

  gpio_trigger: 99          den Pin gibt es am Pi nicht
  gpio_echo == gpio_trigger derselbe Pin zum Senden und Empfangen
  threshold_m: -5           `dist <= -5` ist nie wahr, die Nah-Szene ist tot
  delay_s: -1               die Hysterese schaltet sofort
  web_port: 0               die Oberflaeche ist beim naechsten Start weg
  image_interval_s: 0       Diashow ohne Wechselpause
  master_volume: 500        der Regler zeigt Unsinn

Der Fall `gpio_echo == gpio_trigger` ist der lehrreichste: KEIN Feld fuer
sich ist falsch. Ein Vertrag, der nur Feldnamen kennt, kann so etwas
grundsaetzlich nicht sehen.

Lauf: `python3 -m unittest discover -s tests`.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config_schema as cs  # noqa: E402


class SchreibwegLehntAb(unittest.TestCase):
    """`pruefe_patch` — wer einen Wert setzt, erfaehrt, wenn er nicht ankommt."""

    def test_gueltige_werte_kommen_durch(self):
        # Gegenprobe zuerst: ohne sie waere „alles ablehnen" ebenfalls gruen.
        heraus = cs.pruefe_patch({
            "system_name": "Foyer", "threshold_m": 1.5, "delay_s": 0,
            "gpio_trigger": 23, "gpio_echo": 24, "web_port": 8080,
            "image_interval_s": 5, "master_volume": 0, "video_resume": True,
        })
        self.assertEqual(heraus["master_volume"], 0, "0 % ist ein gueltiger Wert")
        self.assertEqual(heraus["delay_s"], 0.0, "0 s Hysterese ist erlaubt")
        self.assertEqual(heraus["gpio_trigger"], 23)
        self.assertIs(heraus["video_resume"], True)

    def test_unbekannte_felder_werden_ignoriert_nicht_uebernommen(self):
        self.assertEqual(cs.pruefe_patch({"gibtsNicht": 1}), {})

    def test_pin_ausserhalb_des_headers(self):
        for pin in (0, 1, 28, 99, -3):
            with self.assertRaises(ValueError, msg=f"BCM {pin}") as ctx:
                cs.pruefe_patch({"gpio_trigger": pin})
            self.assertIn("gpio_trigger", str(ctx.exception))

    def test_schwelle_und_verzoegerung(self):
        for feld, wert in (("threshold_m", -5), ("threshold_m", 0),
                           ("delay_s", -1), ("image_interval_s", 0)):
            with self.assertRaises(ValueError, msg=f"{feld}={wert}") as ctx:
                cs.pruefe_patch({feld: wert})
            self.assertIn(feld, str(ctx.exception))

    def test_port_und_lautstaerken(self):
        for feld, wert in (("web_port", 0), ("web_port", 70000),
                           ("master_volume", 500), ("audio_volume", -1)):
            with self.assertRaises(ValueError, msg=f"{feld}={wert}"):
                cs.pruefe_patch({feld: wert})

    def test_ein_schalter_ist_keine_zahl(self):
        # `True` ist in Python eine 1. Ohne eigene Pruefung waere
        # `web_port: true` ein gueltiger Port.
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"web_port": True})
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"video_resume": 1})

    def test_texte_haben_grenzen(self):
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"system_name": ""})
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"system_name": "x" * 65})
        # `display_ip` landet in einer URL, die jemand anklickt.
        with self.assertRaises(ValueError):
            cs.pruefe_patch({"display_ip": "10.0.0.1 ; rm -rf /"})
        self.assertEqual(cs.pruefe_patch({"display_ip": "station-1.local"})["display_ip"],
                         "station-1.local")
        self.assertEqual(cs.pruefe_patch({"display_ip": ""})["display_ip"], "",
                         "leer heisst: die Station findet ihre IP selbst; das muss erlaubt bleiben")

    def test_die_meldung_nennt_das_feld(self):
        with self.assertRaises(ValueError) as ctx:
            cs.pruefe_patch({"threshold_m": 99})
        self.assertIn("threshold_m", str(ctx.exception))
        self.assertIn("0.05", str(ctx.exception), "und sagt, was erlaubt waere")


class DasWasKeinFeldAlleinSagt(unittest.TestCase):
    """`pruefe_pins` — der Fall, den ein Feldnamen-Vertrag nicht sehen kann."""

    def test_trigger_und_echo_duerfen_nicht_derselbe_pin_sein(self):
        with self.assertRaises(ValueError) as ctx:
            cs.pruefe_pins({"gpio_trigger": 23, "gpio_echo": 24}, {"gpio_echo": 23})
        self.assertIn("23", str(ctx.exception))

    def test_geprueft_wird_der_zusammengefuehrte_stand(self):
        # Der Kern des Befundes: der Konflikt entsteht ueber ZWEI Anfragen
        # hinweg. Wer nur den Patch ansieht, sieht ihn nie.
        vorher = {"gpio_trigger": 23, "gpio_echo": 24}
        with self.assertRaises(ValueError):
            cs.pruefe_pins(vorher, {"gpio_trigger": 24})
        # Gegenprobe: ein Tausch auf zwei freie Pins ist in Ordnung.
        cs.pruefe_pins(vorher, {"gpio_trigger": 5, "gpio_echo": 6})


class LadewegHeiltStattAbzubrechen(unittest.TestCase):
    """`heile_config` — ein Geraet ohne Tastatur muss hochkommen."""

    def test_unbrauchbare_werte_werden_zur_vorgabe(self):
        cfg = cs.heile_config({
            "gpio_trigger": 99, "threshold_m": -5, "web_port": 0,
            "master_volume": 500,
        })
        self.assertEqual(cfg["gpio_trigger"], cs.DEFAULT_CONFIG["gpio_trigger"])
        self.assertEqual(cfg["threshold_m"], cs.DEFAULT_CONFIG["threshold_m"])
        self.assertEqual(cfg["web_port"], cs.DEFAULT_CONFIG["web_port"])
        self.assertEqual(cfg["master_volume"], cs.DEFAULT_CONFIG["master_volume"])

    def test_gueltige_werte_bleiben_unangetastet(self):
        cfg = cs.heile_config({"threshold_m": 2.5, "web_port": 8080, "master_volume": 0})
        self.assertEqual(cfg["threshold_m"], 2.5)
        self.assertEqual(cfg["web_port"], 8080)
        self.assertEqual(cfg["master_volume"], 0, "0 ist ein Wert, kein Fehler")

    def test_gleiche_pins_werden_beide_zurueckgesetzt(self):
        cfg = cs.heile_config({"gpio_trigger": 5, "gpio_echo": 5})
        self.assertEqual(cfg["gpio_trigger"], cs.DEFAULT_CONFIG["gpio_trigger"])
        self.assertEqual(cfg["gpio_echo"], cs.DEFAULT_CONFIG["gpio_echo"])
        self.assertNotEqual(cfg["gpio_trigger"], cfg["gpio_echo"])

    def test_heilen_bricht_nicht_ab(self):
        # Die eigentliche Zusicherung dieses Weges: es fliegt nichts.
        cs.heile_config({"web_port": "acht", "video_resume": "vielleicht",
                         "gpio_echo": None, "threshold_m": [1]})


class JedesFeldDerVorgabeHatEineGrenze(unittest.TestCase):
    """Sonst waechst die Vorgabe und der Vertrag bleibt stehen."""

    # Verschachtelte Felder, die NICHT in die flache GRENZEN-Tabelle passen und
    # deshalb einen EIGENEN Pruefer haben. Die Ausnahme gilt nur mit dem
    # Nachweis, wo geprueft wird -- sonst waere sie ein Loch im Vertrag:
    #   near/mid/far -> Medienlisten + Wiedergabe-Optionen, eigene Pruefung in
    #                `config_schema.pruefe_zone` / `heile_zone`
    #   zeitplan  -> `zeitplan.pruefe_zeitplan` (Schreibweg) und
    #                `zeitplan.heile_zeitplan` (Ladeweg, aus `heile_config`)
    OHNE_GRENZE = {"near", "mid", "far", "zeitplan"}

    def test_kein_feld_ohne_grenze(self):
        fehlen = sorted(set(cs.DEFAULT_CONFIG) - set(cs.GRENZEN) - self.OHNE_GRENZE)
        self.assertEqual(fehlen, [],
                         f"Felder in DEFAULT_CONFIG ohne Eintrag in GRENZEN: {fehlen}")

    def test_keine_grenze_ohne_feld(self):
        # Die Gegenrichtung: eine Grenze fuer ein Feld, das es nicht mehr gibt,
        # sieht aus wie eine Pruefung und ist keine.
        ueberzaehlig = sorted(set(cs.GRENZEN) - set(cs.DEFAULT_CONFIG))
        self.assertEqual(ueberzaehlig, [])

    def test_die_vorgaben_bestehen_ihre_eigenen_grenzen(self):
        # Waere eine Vorgabe selbst ungueltig, wuerde `heile_config` sie
        # einsetzen und der naechste Lauf sie wieder beanstanden.
        cs.pruefe_patch({k: v for k, v in cs.DEFAULT_CONFIG.items() if k in cs.GRENZEN})
        cs.pruefe_pins({}, cs.DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()

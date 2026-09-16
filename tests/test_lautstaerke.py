"""Die Vorgabe fuer die Lautstaerke steht an EINER Stelle, und 0 % ist 0 %.

BEFUND (Defektformen-Sweep, Form `zwei-rechnungen`, gemessen 2026-09-07).
`Controller.get_scene()` setzt die Vorgaben aus `DEFAULT_CONFIG` bereits ein --
`master_volume` 100, `video_volume` 100, `audio_volume` 80. Die Anzeigeseite
setzte sie ein ZWEITES Mal:

    var master = (scene.master_volume || 100) / 100;
    var vidVol = ((scene.video_volume || 100) / 100) * master;
    var audVol = ((scene.audio_volume || 80) / 100) * master;

Der zweite Satz war nicht nur ueberfluessig, sondern falsch: `0 || 100` ist in
JavaScript 100. Der Gesamt-Regler in `templates/admin.html` geht bis
`min="0"`, `web_ui.py` nimmt die 0 per `int()` an und schreibt sie in die
Konfiguration, `get_scene()` reicht sie durch -- und die Anzeigeseite machte
daraus wieder volle Lautstaerke. Fuer Video und Audio galt dasselbe.

Die Station steht unbeaufsichtigt in einer Ausstellung, und der Gesamt-Regler
ist der einzige Stumm-Schalter, den sie hat.

Diese Datei prueft die Kern-Haelfte im Verhalten (die 0 ueberlebt den Weg
durch `get_scene`) und die Browser-Haelfte am Quelltext -- das Repo hat
keinen JavaScript-Lauf, und ein Waechter, der nur den Quelltext sehen kann,
ist ehrlicher als gar keiner.

Lauf: `python3 -m unittest discover -s tests`.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


def controller(**overrides):
    cfg = dict(main.DEFAULT_CONFIG)
    cfg.update(overrides)
    return main.Controller(cfg)


class DerKernFuelltDieVorgaben(unittest.TestCase):
    """Die eine Stelle: `Controller.get_scene()`."""

    def test_fehlende_werte_bekommen_die_vorgabe(self):
        cfg = {k: v for k, v in main.DEFAULT_CONFIG.items()
               if k not in ("master_volume", "video_volume", "audio_volume")}
        szene = main.Controller(cfg).get_scene()
        self.assertEqual(szene["master_volume"], 100)
        self.assertEqual(szene["video_volume"], 100)
        self.assertEqual(szene["audio_volume"], 80)

    def test_die_vorgaben_stehen_in_default_config(self):
        # Damit der Test nicht seine eigene dritte Kopie wird: die Zahlen
        # oben muessen die aus `DEFAULT_CONFIG` sein.
        self.assertEqual(main.DEFAULT_CONFIG["master_volume"], 100)
        self.assertEqual(main.DEFAULT_CONFIG["video_volume"], 100)
        self.assertEqual(main.DEFAULT_CONFIG["audio_volume"], 80)


class NullIstNull(unittest.TestCase):
    """Der Weg, den der Defekt zerstoerte: Regler auf 0 -> Szene sagt 0."""

    def test_stumm_ueberlebt_get_scene(self):
        szene = controller(master_volume=0).get_scene()
        self.assertEqual(szene["master_volume"], 0,
                         "0 % darf nicht unterwegs zu 100 % werden")

    def test_video_und_audio_stumm_ueberleben_auch(self):
        szene = controller(video_volume=0, audio_volume=0).get_scene()
        self.assertEqual(szene["video_volume"], 0)
        self.assertEqual(szene["audio_volume"], 0)

    def test_die_konfiguration_kennt_die_null_ueberhaupt(self):
        # Gegenprobe zu den beiden darueber: der Regler geht wirklich bis 0.
        # Waere `min="1"`, waere der ganze Befund keiner.
        admin = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
        for regler in ("cfg-mastervol", "cfg-vidvol", "cfg-audvol"):
            zeile = next(z for z in admin.splitlines() if f'id="{regler}"' in z)
            self.assertIn('min="0"', zeile,
                          f"{regler} laesst 0 % gar nicht zu -- dann stimmt "
                          "die Begruendung dieses Tests nicht mehr")


class DieAnzeigeErfindetKeineVorgabe(unittest.TestCase):
    """Quelltext-Waechter fuer die zweite Rechnung im Browser."""

    QUELLE = ROOT / "static" / "display.js"

    def _code(self):
        # Zeilenkommentare raus: der erklaerende Kommentar an der Fundstelle
        # ZITIERT die alte Zeile absichtlich, damit man den Befund
        # wiederfindet.
        text = self.QUELLE.read_text(encoding="utf-8")
        return "\n".join(z for z in text.splitlines()
                         if not z.lstrip().startswith("//"))

    def test_kein_oder_faellt_auf_eine_lautstaerke_zurueck(self):
        code = self._code()
        treffer = re.findall(r"scene\.(?:master|video|audio)_volume\s*\|\|", code)
        self.assertEqual(
            treffer, [],
            "die Anzeigeseite faellt wieder auf eine eigene Vorgabe zurueck; "
            "`0 || 100` ist 100, und damit ist der Stumm-Schalter wirkungslos")

    def test_die_lautstaerke_geht_durch_die_eine_pruefung(self):
        # Gegenstueck zum Waechter darueber: er waere auch gruen, wenn die
        # Seite die Lautstaerke gar nicht mehr setzte.
        code = self._code()
        for feld in ("master_volume", "video_volume", "audio_volume"):
            self.assertIn(f"anteil(scene.{feld})", code,
                          f"{feld} wird nicht mehr uebernommen")
        self.assertIn("videoA.volume", code)
        self.assertIn("audioEl.volume", code)

    def test_die_pruefung_kennt_die_null(self):
        # `anteil` darf nicht selbst wieder ein `||` sein.
        code = self.QUELLE.read_text(encoding="utf-8")
        koerper = code.split("function anteil(")[1].split("\n    }")[0]
        self.assertIn("isFinite", koerper,
                      "`anteil` muss ein fehlendes Feld von einer 0 unterscheiden koennen")
        self.assertNotIn("||", koerper)


if __name__ == "__main__":
    unittest.main()

"""Sind die Schieberegler zu treffen?

Nutzer-Meldung 2026-09-09: „Passe auch die Ui von allen slidern an sodass man
sie gut bedienen kann."

GEMESSEN VORHER: `input[type="range"] { height: 5px }` mit einem 16 x 16 px
grossen Griff. Fuenf Pixel waren die GANZE Trefferflaeche in der Hoehe — das
Element war so hoch wie seine Bahn. WCAG 2.2, Erfolgskriterium 2.5.8 („Target
Size (Minimum)", Stufe AA), nennt 24 px als Mindestmass. Apples 44 pt sind
eine Herstellerempfehlung und keine Norm; deshalb steht hier die 24.

WARUM DAS HIER MEHR IST ALS KOSMETIK. Diese Seite wird von einem HANDY
bedient — sie ist die Verwaltung neben dem Aufbau, dafuer ist sie gebaut. An
den sechs Reglern haengen die Ausloese-Schwelle des Sensors, die Verzoegerung,
der Bildwechsel und drei Lautstaerken. Wer mit dem Daumen danebengreift,
verstellt die Schwelle einer laufenden Installation.

WAS DIESER TEST NICHT KANN, und das gehoert hierher statt in eine Fussnote:
er liest das Stilblatt. Was Zeilenhoehe, Raster und ein umgebendes
`transform` daraus machen, sieht er nicht — dafuer braeuchte es ein
gerendertes Fenster. Er faengt den einen Weg ab, auf dem die Regler hier
wieder schrumpfen: jemand dreht die Zahl im Stilblatt zurueck.
"""
import re
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
# Die Kommentare RAUS, bevor gemessen wird: der Kommentar ueber der Regel
# erklaert `height: 24px` und wuerde sonst als Regel gelesen. Ein Test, der
# seine eigene Begruendung wiederfindet, ist gruen auf dem Defekt.
CSS = re.sub(
    r"/\*.*?\*/", "", (WURZEL / "static/style.css").read_text(encoding="utf-8"), flags=re.S
)
HTML = (WURZEL / "templates/admin.html").read_text(encoding="utf-8")

#: WCAG 2.2 SC 2.5.8, Stufe AA.
MINDESTHOEHE = 24
#: Der sichtbare Griff. Kleiner als das findet der Daumen die Bahn nicht.
MINDESTGRIFF = 18


def block(selektor: str) -> str:
    """Der Rumpf einer Regel, oder '' wenn es sie nicht gibt."""
    i = CSS.find(selektor)
    if i < 0:
        return ""
    auf = CSS.find("{", i)
    zu = CSS.find("}", auf)
    return CSS[auf + 1 : zu] if auf >= 0 and zu >= 0 else ""


def px(rumpf: str, eigenschaft: str):
    treffer = re.search(rf"{eigenschaft}\s*:\s*(\d+(?:\.\d+)?)px", rumpf)
    return float(treffer.group(1)) if treffer else None


class Trefferflaeche(unittest.TestCase):
    def test_element_ist_24px_hoch(self):
        hoehe = px(block('input[type="range"] {'), "height")
        self.assertIsNotNone(hoehe, "input[type=range] hat keine Hoehe in px")
        self.assertGreaterEqual(
            hoehe, MINDESTHOEHE, "WCAG 2.2 SC 2.5.8 (Stufe AA) nennt 24 px"
        )

    def test_griff_in_beiden_browser_familien(self):
        # Ohne den Firefox-Zweig bliebe es dort beim Standardaussehen, und die
        # Messung stuende nur fuer einen Browser.
        for selektor in (
            'input[type="range"]::-webkit-slider-thumb {',
            'input[type="range"]::-moz-range-thumb {',
        ):
            with self.subTest(selektor=selektor):
                rumpf = block(selektor)
                self.assertTrue(rumpf, f"{selektor} fehlt")
                breite = px(rumpf, "width")
                self.assertIsNotNone(breite, f"{selektor} hat keine Breite in px")
                self.assertGreaterEqual(breite, MINDESTGRIFF)

    def test_die_bahn_bleibt_schmal(self):
        # Der Sinn der Uebung: die TREFFERFLAECHE waechst, nicht der Balken.
        # Waere die Bahn 24 px hoch, spraengte sie das Raster der Verwaltung —
        # und jemand drehte die Hoehe wieder zurueck.
        for selektor in (
            'input[type="range"]::-webkit-slider-runnable-track {',
            'input[type="range"]::-moz-range-track {',
        ):
            with self.subTest(selektor=selektor):
                rumpf = block(selektor)
                self.assertTrue(rumpf, f"{selektor} fehlt")
                self.assertLess(px(rumpf, "height"), MINDESTHOEHE)

    def test_fokusring_liegt_aussen(self):
        # Vorher stand hier `outline: none` — der Regler ist mit Pfeiltasten
        # bedienbar, und man sah nicht, wann er dran ist.
        rumpf = block('input[type="range"]:focus-visible {')
        self.assertTrue(rumpf, "kein Fokusring fuer den Regler")
        self.assertNotIn("none", rumpf.split("outline-offset")[0])
        self.assertGreater(px(rumpf, "outline-offset"), 0)

    def test_es_gibt_ueberhaupt_regler(self):
        # Die Gegenprobe zum Test selbst: ohne sie waere ein Lauf, der KEINEN
        # Regler findet, gruen — und genau so sieht ein kaputtes Muster aus.
        self.assertGreater(len(re.findall(r'type="range"', HTML)), 0)


if __name__ == "__main__":
    unittest.main()

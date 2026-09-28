"""Waechter fuer die Oberflaechen-Regeln (ADR-007 der av-planner-suite).

Nutzer-Rueckmeldung 2026-09-07: "die ui ist nicht konsistent. lege globale ui
regeln fest die fuer alle repos gelten."

WARUM DIE WERTE HIER EIN ZWEITES MAL STEHEN: sie stehen maschinenlesbar in
`@avplan/ui` (`src/brand.ts`), aber dieses Repo ist Python und haengt an
keinem npm-Paket. Ohne diesen Test waere der Rueckweg in die alte Neon-Welt
eine Zeile, die niemandem auffaellt.

WAS ER NICHT PRUEFT: `static/display.css`. Das ist die WIEDERGABE-Flaeche —
Vollbild, schwarzer Grund, `cursor:none`. Schwarz ist dort kein Geschmack,
sondern die richtige Umgebung fuer Bild und Video: jeder andere Grund faerbt
die Ueberblendungen. Eine Marken-Regel fuer Bedienoberflaechen endet an der
Ausspielung.
"""
import re
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = (WURZEL / "static/style.css").read_text(encoding="utf-8")
MANAGER = (WURZEL / "station-manager/renderer/style.css").read_text(encoding="utf-8")


def token(css: str, name: str) -> str:
    treffer = re.search(rf"{name}:\s*([^;]+);", css)
    return treffer.group(1).strip() if treffer else ""


class WebOberflaeche(unittest.TestCase):
    def test_palette(self):
        self.assertEqual(token(WEB, "--bg"), "#132040", "Grund ist Deep Navy")
        self.assertEqual(token(WEB, "--surface"), "#1D324F", "Flaeche ist Zumpe Navy")
        self.assertEqual(token(WEB, "--text"), "#E1ECEF", "Fliesstext ist Eisblau")
        self.assertEqual(token(WEB, "--text-dim"), "#8C9CB3", "Gedaempft ist Stahlblau")

    def test_akzent_ist_die_aktionsflaeche(self):
        self.assertEqual(token(WEB, "--accent"), "#F6F5F0")
        self.assertEqual(token(WEB, "--accent-text"), "#132040", "darauf steht Navy")

    def test_status_ist_nicht_signal(self):
        self.assertEqual(token(WEB, "--danger"), "#B04A3F")
        self.assertEqual(token(WEB, "--warning"), "#C8892B")
        self.assertEqual(token(WEB, "--signal"), "#D6402E")
        self.assertNotEqual(token(WEB, "--danger"), token(WEB, "--signal"))

    def test_naeherung_folgt_den_status_toenen(self):
        # --near/--far sind ein Zustand, keine Schmuckfarben: jemand steht
        # davor oder nicht.
        self.assertEqual(token(WEB, "--near"), "#2F7D5C")
        self.assertEqual(token(WEB, "--far"), "#8C9CB3")

    def test_fokusring_ist_das_signal(self):
        self.assertIn("outline: 2px solid var(--signal)", WEB)
        self.assertIn("outline-offset: 3px", WEB)


class StationManager(unittest.TestCase):
    def test_dieselbe_palette(self):
        self.assertEqual(token(MANAGER, "--bg"), "#132040")
        self.assertEqual(token(MANAGER, "--card"), "#1D324F")
        self.assertEqual(token(MANAGER, "--accent"), "#F6F5F0")
        self.assertEqual(token(MANAGER, "--signal"), "#D6402E")


class Form(unittest.TestCase):
    def test_keine_rundungen(self):
        for name, css in (("web", WEB), ("manager", MANAGER)):
            rest = re.findall(r"border-radius:\s*(50%|[1-9][^;]*)", css)
            self.assertEqual(rest, [], f"{name}: harte Radien {rest}")

    def test_keine_schatten(self):
        for name, css in (("web", WEB), ("manager", MANAGER)):
            rest = re.findall(r"box-shadow:(?!\s*none\s*;)[^;]+;", css)
            self.assertEqual(rest, [], f"{name}: Schatten {rest}")

    def test_keine_verlaeufe(self):
        for name, css in (("web", WEB), ("manager", MANAGER)):
            self.assertNotIn("linear-gradient", css, name)
            self.assertNotIn("radial-gradient", css, name)

    def test_keine_schwarze_schrift_auf_der_aktionsflaeche(self):
        # Reines Schwarz gehoert nicht in die Palette; auf Off-White steht
        # Navy.
        rest = [z.strip() for z in WEB.split("\n")
                if "var(--accent)" in z and re.search(r"color:\s*#000", z)]
        self.assertEqual(rest, [], f"Schwarz auf Off-White: {rest}")


class Marke(unittest.TestCase):
    """Name, Icon und Signet stehen auf jeder Oberflaeche, die Menschen sehen."""

    def test_jede_seite_hat_das_favicon(self):
        for seite in ("templates/admin.html", "templates/display.html", "templates/launch.html"):
            html = (WURZEL / seite).read_text(encoding="utf-8")
            self.assertIn('href="/static/brand/favicon.svg"', html, seite)
        self.assertIn('href="brand/favicon.svg"',
                      (WURZEL / "station-manager/renderer/index.html").read_text(encoding="utf-8"))

    def test_markendateien_liegen_bereit(self):
        for datei in ("static/brand/favicon.svg", "static/brand/icon-512.png",
                      "static/brand/lzm_signet_offwhite_tally.svg",
                      "static/brand/lzm_hauptlogo_offwhite.svg",
                      "station-manager/build/icon.png", "station-manager/build/icon.ico",
                      "station-manager/renderer/brand/icon-512.png"):
            self.assertTrue((WURZEL / datei).is_file(), datei)

    def test_signet_weicht_unter_640_px(self):
        self.assertIn("@media (max-width: 639px)", WEB)
        self.assertIn("@media (max-width: 639px)", MANAGER)

    def test_anzeigename(self):
        self.assertIn("<h1>LZ Media Station", (WURZEL / "templates/admin.html").read_text(encoding="utf-8"))
        self.assertTrue((WURZEL / "README.md").read_text(encoding="utf-8").startswith("# LZ Media Station"))


if __name__ == "__main__":
    unittest.main()

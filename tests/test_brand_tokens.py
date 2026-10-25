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
    """Seit Oktober 2026 folgt die WEB-Oberflaeche dem lzm-web-Skill: NEUTRAL
    traegt, BLAU akzentuiert, hell UND dunkel. Die alten Print-Werte (Navy als
    Flaeche) gelten hier nicht mehr — der Skill hebt sie fuer Oberflaechen
    ausdruecklich auf. Was BLEIBT, ist die Marke: Navy als Akzent (hell),
    Off-White darauf, Tally-Rot als Signal, und das Signet-Lockup in Navy."""

    def test_neutrale_flaeche_kein_navy_grund(self):
        # Grund und Karten sind neutral (Fast-Weiss / Weiss), nicht Navy.
        self.assertEqual(token(WEB, "--bg"), "#F2F1EC")
        self.assertEqual(token(WEB, "--surface"), "#FFFFFF")
        self.assertEqual(token(WEB, "--text"), "#202329", "Anthrazit, nicht Eisblau")

    def test_akzent_ist_markenblau(self):
        # Hell: Akzent = Zumpe Navy, darauf Off-White.
        self.assertEqual(token(WEB, "--accent"), "#1D324F")
        self.assertEqual(token(WEB, "--accent-text"), "#F6F5F0")

    def test_signet_lockup_bleibt_navy(self):
        # Das Signet steht weiter Off-White auf Navy — eigenes Token, nie an
        # --accent gekoppelt.
        self.assertEqual(token(WEB, "--logo"), "#1D324F")
        self.assertEqual(token(WEB, "--logo-ink"), "#F6F5F0")

    def test_status_ist_nicht_signal(self):
        self.assertEqual(token(WEB, "--danger"), "#B04A3F")
        self.assertEqual(token(WEB, "--warning"), "#C8892B")
        self.assertEqual(token(WEB, "--signal"), "#D6402E")
        self.assertNotEqual(token(WEB, "--danger"), token(WEB, "--signal"))

    def test_naeherung_folgt_den_status_toenen(self):
        self.assertEqual(token(WEB, "--near"), "#2F7D5C")
        self.assertEqual(token(WEB, "--far"), "#8C9CB3")

    def test_hat_hell_und_dunkel(self):
        # Beide Modi und ein Dunkel-Grund in Anthrazit (nicht Schwarz/Navy).
        self.assertIn('prefers-color-scheme: dark', WEB)
        self.assertIn('[data-theme="dark"]', WEB)
        self.assertIn('[data-theme="light"]', WEB)

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
    """Die Print-Form-Regeln (keine Rundungen/Schatten/Verlaeufe) gelten noch
    fuer den Electron-MANAGER — der ist nicht auf lzm-web umgestellt. Die
    WEB-Oberflaeche darf seit der Umstellung weiche Rundungen, ruhige Schatten
    und sehr dezente Verlaeufe tragen (lzm-web)."""

    def test_manager_bleibt_ohne_rundungen(self):
        rest = re.findall(r"border-radius:\s*(50%|[1-9][^;]*)", MANAGER)
        self.assertEqual(rest, [], f"manager: harte Radien {rest}")

    def test_manager_bleibt_ohne_schatten(self):
        rest = re.findall(r"box-shadow:(?!\s*none\s*;)[^;]+;", MANAGER)
        self.assertEqual(rest, [], f"manager: Schatten {rest}")

    def test_web_nutzt_rundungs_tokens(self):
        # Weiche Rundungen kommen aus Tokens, nicht als Streuwerte.
        self.assertIn("--radius-l:", WEB)
        self.assertIn("--radius-m:", WEB)

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


    def test_keine_emoji_in_der_oberflaeche(self):
        # Symbole sind Text oder eigene Inline-SVGs, kein fremdes Icon-Set.
        muster = re.compile(r"[\u2190-\u21FF\u2300-\u23FF\u2600-\u27BF\U0001F000-\U0001FAFF]"
                            r"|&#(?:x(?:2[1-7]|1F)[0-9a-fA-F]{2,3}|(?:8[4-9]|9[0-9]|10[0-2])[0-9]{2}|1[2-3][0-9]{4});")
        for datei in ("templates/admin.html", "templates/launch.html", "templates/display.html",
                      "static/app.js", "static/display.js",
                      "station-manager/renderer/index.html", "station-manager/renderer/app.js"):
            for nr, zeile in enumerate((WURZEL / datei).read_text(encoding="utf-8").splitlines(), 1):
                if zeile.strip().startswith(("//", "*", "/*", "<!--")):
                    continue
                self.assertIsNone(muster.search(zeile), f"{datei}:{nr}: {zeile.strip()[:80]}")


if __name__ == "__main__":
    unittest.main()

"""Waechter: stimmt die Dokumentation noch mit dem Code ueberein?

WARUM ES DAS GIBT. Am 2026-09-16 stand in der API-Uebersicht des README ein
Endpunkt `POST /api/zone`, den es **nie gegeben hat** — und zehn Endpunkte, die
es gibt, fehlten. Dazu ein Modul `media_player.py` in der Architektur-Liste,
das nicht existiert (die Wiedergabe laeuft im Browser).

Eine Doku, die Dinge verspricht, die es nicht gibt, ist schlimmer als keine:
wer `POST /api/zone` aufruft, sucht den Fehler bei sich.

Doku laesst sich nicht auf Richtigkeit pruefen — aber auf **Vollstaendigkeit
und Nichterfundenheit**, und genau das ist hier moeglich, weil Routen und
Modulnamen maschinenlesbar sind.

Lauf: `python3 -m unittest discover -s tests -v`
"""
import re
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
README = (WURZEL / "README.md").read_text(encoding="utf-8")
README_DE = (WURZEL / "README.de.md").read_text(encoding="utf-8")
#: Routen stehen in `web_ui.py` UND in den Erweiterungen `api_*.py` (3.0).
ROUTEN_QUELLEN = [WURZEL / "web_ui.py"] + sorted(WURZEL.glob("api_*.py"))
WEB_UI = "\n".join(p.read_text(encoding="utf-8") for p in ROUTEN_QUELLEN)

#: Seiten, keine Schnittstelle — sie stehen im README als Text, nicht als Pfad.
KEINE_API = {"/", "/admin", "/display", "/login"}


def platzhalter_vereinheitlichen(pfad):
    """`/api/media/<media_type>` und `/api/media/<type>` sind derselbe Pfad.

    Der Name des Platzhalters ist eine Frage des Codes, nicht der Doku — wer
    ihn umbenennt, soll nicht die Doku rot machen.
    """
    return re.sub(r"<[^>]+>", "<>", pfad)


def routen_aus_code():
    # `@app.route` in web_ui.py, `@bp.route` in den Blueprints.
    roh = re.findall(r'@\w+\.route\("([^"]+)"', WEB_UI)
    return {platzhalter_vereinheitlichen(p) for p in roh if p not in KEINE_API}


def pfade_aus_readme(text=None):
    """Alle Pfade, die das README in Backticks als KONKRETEN Endpunkt nennt.

    Sammelbegriffe mit `*` (etwa „Flask-Routen `/api/*`") sind Prosa und kein
    Versprechen auf einen Endpunkt — sie zaehlen hier nicht mit. Ein Waechter,
    der bei einer voellig richtigen Formulierung rot wird, wird beim naechsten
    Mal angepasst statt gelesen.
    """
    # `/widgets/…` (3.0): die Dateien eigener Widgets sind ebenfalls Routen.
    treffer = re.findall(r"`(/(?:api|media|widgets)[^`]*)`", README if text is None else text)
    return {platzhalter_vereinheitlichen(p.strip())
            for p in treffer if "*" not in p}


class DieApiUebersichtStimmt(unittest.TestCase):
    def test_kein_endpunkt_fehlt(self):
        fehlen = sorted(routen_aus_code() - pfade_aus_readme())
        self.assertEqual(
            fehlen, [],
            f"Endpunkte gibt es, stehen aber nicht im README: {fehlen}")

    def test_kein_erfundener_endpunkt(self):
        # Der eigentliche Befund: `POST /api/zone` stand jahrelang in der
        # Tabelle und existierte nie.
        erfunden = sorted(pfade_aus_readme() - routen_aus_code())
        self.assertEqual(
            erfunden, [],
            f"README nennt Endpunkte, die es nicht gibt: {erfunden}")


class DieModulliste_stimmt(unittest.TestCase):
    def test_jedes_genannte_modul_gibt_es(self):
        # `media_player.py` stand hier und existierte nicht.
        genannt = set(re.findall(r"`([a-z_]+\.py)`", README))
        fehlend = sorted(n for n in genannt if not (WURZEL / n).is_file())
        self.assertEqual(
            fehlend, [],
            f"README nennt Dateien, die es nicht gibt: {fehlend}")

    def test_jedes_modul_wird_genannt(self):
        # Ein neues Modul ohne Eintrag in der Architektur-Liste faellt sonst
        # niemandem auf.
        vorhanden = {p.name for p in WURZEL.glob("*.py")}
        genannt = set(re.findall(r"`([a-z_]+\.py)`", README))
        fehlen = sorted(vorhanden - genannt)
        self.assertEqual(
            fehlen, [],
            f"Module ohne Eintrag in der Architektur-Liste: {fehlen}")


class DasDeutscheReadmeLaeuftMit(unittest.TestCase):
    """`README.de.md` ist die Uebersetzung — kein Test hielt es bisher auf
    dem Stand des englischen. Endpunkte und Module muessen in beiden
    stehen, sonst verspricht eine Sprache etwas, das die andere nicht kennt."""

    def test_dieselben_endpunkte(self):
        en, de = pfade_aus_readme(), pfade_aus_readme(README_DE)
        self.assertEqual(sorted(en - de), [], "nur im englischen README")
        self.assertEqual(sorted(de - en), [], "nur im deutschen README")

    def test_dieselben_module(self):
        en = set(re.findall(r"`([a-z_]+\.py)`", README))
        de = set(re.findall(r"`([a-z_]+\.py)`", README_DE))
        self.assertEqual(sorted(en ^ de), [], "Modulliste weicht ab")

    def test_dieselben_dokumente(self):
        docs = {p.name for p in (WURZEL / "docs").glob("*.md")} - {"README.md"}
        fehlen = sorted(d for d in docs if d not in README_DE)
        self.assertEqual(fehlen, [], f"nicht im deutschen README verlinkt: {fehlen}")


class DieDokuIstVerlinkt(unittest.TestCase):
    def dokumente(self):
        return {p.name for p in (WURZEL / "docs").glob("*.md")} - {"README.md"}

    def test_jedes_dokument_ist_im_index(self):
        index = (WURZEL / "docs/README.md").read_text(encoding="utf-8")
        fehlen = sorted(d for d in self.dokumente() if d not in index)
        self.assertEqual(fehlen, [], f"nicht im Doku-Index: {fehlen}")

    def test_jedes_dokument_ist_im_readme(self):
        fehlen = sorted(d for d in self.dokumente() if d not in README)
        self.assertEqual(fehlen, [], f"nicht im README verlinkt: {fehlen}")

    def test_kein_toter_link_ins_docs_verzeichnis(self):
        ziele = re.findall(r"\]\((docs/[^)]+)\)", README)
        tot = sorted(z for z in set(ziele) if not (WURZEL / z).exists())
        self.assertEqual(tot, [], f"tote Links im README: {tot}")


if __name__ == "__main__":
    unittest.main()

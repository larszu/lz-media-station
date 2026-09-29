"""Oberflaechensprache: Deutsch ist Quelle, Englisch kommt aus dem Woerterbuch.

Was hier geprueft wird, ist das, was sonst still verrottet: ein neuer Text im
Template ohne englischen Eintrag, eine umformulierte Server-Meldung, zu der
kein Muster mehr passt, und zwei Kopien des Kerns, die auseinanderlaufen.
"""

import json
import os
import re
import sys
import unittest
from html.parser import HTMLParser

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

import gesundheit  # noqa: E402
import medien_check  # noqa: E402

# Texte, die auf Englisch genauso heissen — Namen, Einheiten, Fachwoerter.
GLEICH = {
    "LZ Media Station – Admin", "LZ Media Station", "LZ Station Manager", "Station",
    "m", "s", "%", "0%", "▶ Start", "◼ Stop", "■ Stop", "⟲ Reboot", "🎬 Videos",
    "📹 Videos", "🎵 Audio", "Video:", "Audio:", "GPIO Trigger", "GPIO Echo",
    "Gateway", "Version", "Lars Zumpe Medienproduktion", "Config-Push",
    "IP / Hostname", "Port", "EN", "LZ Station 1", "de, en", "192.168.1.1",
    "1.1.1.1,8.8.8.8", "192.168.1.50", "Auto-Start in",
    # Layouts (3.0): Fachwoerter, die im Englischen genauso heissen.
    "Layout", "Layouts", "Ticker", "Region",
    # Monitor und Zugang (3.0)
    "Monitor", "System", "Topic", "Webhook (JSON)", "ntfy", "https://ntfy.sh", "PIN", "Zone",
    # Station Manager (3.0)
    "Text", "Tag",
}


def datei(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as f:
        return f.read()


def woerterbuch(pfad):
    return json.loads(datei(pfad).split("/*JSON*/")[1])


def zusatz_woerterbuecher():
    """`static/i18n/*.en.js` — die Woerterbuecher der Erweiterungen (3.0)."""
    ordner = os.path.join(WURZEL, "static", "i18n")
    return sorted(os.path.join("static", "i18n", n) for n in os.listdir(ordner)
                  if n.endswith(".en.js")) if os.path.isdir(ordner) else []


def web_woerterbuch():
    """Kern plus Zusaetze — so, wie `zusammen()` in i18n.js es zusammenfuehrt:
    spaetere Texte gewinnen, Muster werden angehaengt."""
    w = {"texte": {}, "muster": [], "html": {}}
    for pfad in ["static/i18n-en.js"] + zusatz_woerterbuecher():
        t = woerterbuch(pfad)
        w["texte"].update(t.get("texte", {}))
        w["muster"] += t.get("muster", [])
        w["html"].update(t.get("html", {}))
    return w


def alle_templates():
    """Jede Datei unter templates/ — seit 3.0 sind die Karten des Admins
    Includes (templates/admin/), und Erweiterungen legen dort weitere ab."""
    heraus = []
    for wurzel, _ordner, dateien in os.walk(os.path.join(WURZEL, "templates")):
        for n in dateien:
            if n.endswith(".html"):
                heraus.append(os.path.relpath(os.path.join(wurzel, n), WURZEL))
    return sorted(heraus)


def ohne_jinja(html):
    """`{% include %}`, `{{ … }}` und `{# … #}` sind kein sichtbarer Text."""
    return re.sub(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", "", html, flags=re.S)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


class Texte(HTMLParser):
    """Sichtbare Texte und uebersetzbare Attribute eines Templates.

    Ueberspringt, was i18n.js auch ueberspringt: script, style, code und
    alles innerhalb von data-i18n (das steht als Ganzes in `html`).
    """

    def __init__(self):
        super().__init__()
        self.stapel, self.texte, self.schluessel = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        leer = tag in ("input", "img", "meta", "link", "br")
        if "data-i18n" in a:
            self.schluessel.append(a["data-i18n"])
        if not self._still():
            for name in ("placeholder", "title", "alt", "aria-label"):
                if a.get(name):
                    self.texte.append(norm(a[name]))
        if not leer:
            self.stapel.append((tag, "data-i18n" in a))

    def handle_endtag(self, tag):
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i][0] == tag:
                del self.stapel[i:]
                break

    def _still(self):
        return any(t in ("script", "style", "code", "title") or i18n for t, i18n in self.stapel)

    def handle_data(self, data):
        if not self._still() and re.search(r"[A-Za-zÄÖÜäöüß]", data):
            self.texte.append(norm(data))


def lies(pfad):
    p = Texte()
    p.feed(ohne_jinja(datei(pfad)))
    return p


def uebersetze(wb, kern, tiefe=0):
    """Dasselbe wie `uebersetze` in i18n.js: exakt, sonst erstes Muster,
    dessen Gruppen rekursiv uebersetzt werden. None = nichts gefunden."""
    if kern in wb["texte"]:
        return wb["texte"][kern]
    if tiefe > 3:
        return None
    for muster, ersatz in wb["muster"]:
        m = re.match(muster, kern)
        if m:
            def gruppe(g):
                roh = m.group(int(g.group(1))) or ""
                u = uebersetze(wb, norm(roh), tiefe + 1)
                return roh if u is None else u
            return re.sub(r"\{(\d)\}", gruppe, ersatz)
    return None


def uebersetzt(wb, text):
    """Wirklich uebersetzt — ein Muster, das nur die Gruppen wieder
    zusammensetzt (z. B. „Datei: Hinweis"), zaehlt nicht, wenn darin nichts
    Englisches entsteht."""
    en = uebersetze(wb, text)
    return en is not None and en != text


class KernGleich(unittest.TestCase):
    def test_web_und_manager_haben_denselben_kern(self):
        a = datei("static/i18n.js")
        b = datei("station-manager/renderer/i18n.js")
        self.assertEqual(a, b, "station-manager/renderer/i18n.js ist eine Kopie von static/i18n.js")


class Vollstaendig(unittest.TestCase):
    def pruefe(self, template, wb, wbpfad):
        p = lies(template)
        fehlt = sorted({t for t in p.texte if t not in GLEICH and not uebersetzt(wb, t)})
        self.assertEqual(fehlt, [], f"{template}: ohne englischen Eintrag in {wbpfad}")
        ohne_html = [k for k in p.schluessel if k not in wb["html"]]
        self.assertEqual(ohne_html, [], f"{template}: data-i18n ohne Eintrag in `html`")

    def test_alle_templates_der_station(self):
        # Jede Datei unter templates/ — auch die Includes und was
        # Erweiterungen unter templates/admin/zusatz/ ablegen.
        wb = web_woerterbuch()
        templates = alle_templates()
        self.assertIn("templates/admin.html", templates)
        self.assertIn("templates/admin/_zonen.html", templates)
        for t in templates:
            with self.subTest(template=t):
                self.pruefe(t, wb, "static/i18n-en.js oder static/i18n/*.en.js")

    def test_station_manager(self):
        self.pruefe("station-manager/renderer/index.html",
                    woerterbuch("station-manager/renderer/i18n-en.js"),
                    "station-manager/renderer/i18n-en.js")

    def test_muster_sind_gueltig(self):
        for pfad in ["static/i18n-en.js", "station-manager/renderer/i18n-en.js"] + zusatz_woerterbuecher():
            for m in woerterbuch(pfad)["muster"]:
                re.compile(m[0])

    def test_zusatz_woerterbuecher_haben_die_form_des_kerns(self):
        # `(window.LZ_I18N_EN_EXTRA = …).push(/*JSON*/{…}/*JSON*/);` — der
        # Block dazwischen ist reines JSON mit texte/muster/html.
        for pfad in zusatz_woerterbuecher():
            with self.subTest(datei=pfad):
                self.assertIn("LZ_I18N_EN_EXTRA", datei(pfad))
                wb = woerterbuch(pfad)
                self.assertEqual(set(wb) <= {"texte", "muster", "html"}, True, pfad)
                # `muster` ist eine LISTE von Paaren [Regex, Ersatz]. Ein Objekt
                # `{}` sieht harmlos aus, legt aber im Browser (`concat`) ein
                # Nicht-Paar in die Liste: `new RegExp(undefined)` passt auf
                # jeden Text, der Ersatz fehlt, und die Uebersetzung der ganzen
                # Verwaltung bricht mit einem TypeError ab. So geschehen am
                # 2026-09-29 mit einem neuen Zusatzwoerterbuch.
                m = wb.get("muster", [])
                self.assertIsInstance(m, list, f"{pfad}: muster muss eine Liste sein")
                for paar in m:
                    self.assertTrue(isinstance(paar, list) and len(paar) == 2
                                    and all(isinstance(x, str) for x in paar),
                                    f"{pfad}: Muster {paar!r} ist kein Paar [Regex, Ersatz]")


class ServerMeldungen(unittest.TestCase):
    """Die Meldungen entstehen im Python-Kern — hier echt erzeugt, damit ein
    umformulierter Satz auffaellt, statt still deutsch zu bleiben."""

    def setUp(self):
        self.wb = web_woerterbuch()

    def test_befunde_der_zustandspruefung(self):
        config = {"near": {"videos": ["a.mp4"]}, "far": {}}
        befunde = gesundheit.pruefe(
            config=config, sensor_ok=False, sensor_status="kein Sensor: gpiozero nicht installiert",
            freier_platz_b=10 * 1024 * 1024, vorhandene={"videos": set()}, aktiv=False,
            geschlossen=False, sync_ok=None, sync_status="")
        self.assertTrue(befunde)
        for b in befunde:
            self.assertTrue(uebersetzt(self.wb, norm(b["text"])), b["text"])

    def test_hinweise_des_medien_checks(self):
        for h in medien_check.beurteile(breite=3840, hoehe=2160, codec="hevc",
                                        bildrate=60, bitrate=80_000_000):
            self.assertTrue(uebersetzt(self.wb, norm(h)), h)


if __name__ == "__main__":
    unittest.main()

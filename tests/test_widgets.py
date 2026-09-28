"""Widgets (3.0, Welle 2): Parser, Proxys, Zwischenspeicher, Katalog, QR.

WARUM. Ein Widget auf einem Schirm im Foyer hat niemanden, der hinsieht.
Drei Dinge gehen dort still schief, und jedes davon steht hier als Test:

1. **Der Feed sieht anders aus als gedacht.** Ein Atom-Feed statt RSS, ein
   Kalender mit gefalteten Zeilen, ein Termin ueber Mitternacht, eine RRULE —
   der Parser darf daran nicht zerbrechen und nichts erfinden.
2. **Das Netz ist weg.** Der Zwischenspeicher muss das Alte liefern (und es
   als alt kennzeichnen), und der Proxy darf kein Tor ins Dateisystem sein.
3. **Der QR-Code stimmt nicht.** Ein Code, der aussieht wie ein QR-Code und
   nicht scannt, faellt erst auf, wenn der erste Besucher es probiert. Der
   Eigenbau wird deshalb Modul fuer Modul gegen eine Referenz gehalten
   (`tests/fixtures/qr_referenz.json`, erzeugt mit der Bibliothek `qrcode`,
   die dafuer NICHT in requirements steht — die Fixture ist eingecheckt).

Lauf: `python3 -m unittest discover -s tests -v`
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

import main  # noqa: E402
import widgets as W  # noqa: E402
from web_ui import create_app  # noqa: E402

WIDGETS_JS = (WURZEL / "static/anzeige/widgets.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def frische_config():
    return json.loads(json.dumps(main.DEFAULT_CONFIG))


# --------------------------------------------------------------------------
# RSS / Atom
# --------------------------------------------------------------------------

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Museum aktuell</title>
<item><title>Neue Ausstellung &amp; Fest</title><link>https://m.example/a</link>
  <pubDate>Mon, 21 Sep 2026 10:00:00 +0200</pubDate><description>&lt;p&gt;Es gibt &lt;b&gt;Kuchen&lt;/b&gt;.&lt;/p&gt;</description></item>
<item><title>Aelter</title><link>https://m.example/b</link><pubDate>Sun, 20 Sep 2026 08:00:00 +0200</pubDate></item>
<item><title>Neuer</title><link>https://m.example/c</link><pubDate>Tue, 22 Sep 2026 09:00:00 +0200</pubDate></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Erster</title><link rel="alternate" href="https://b.example/1"/><updated>2026-09-01T12:00:00Z</updated>
  <summary>Hallo</summary></entry>
<entry><title>Zweiter</title><link href="https://b.example/2"/><published>2026-09-02T12:00:00Z</published></entry>
</feed>"""


class RssUndAtom(unittest.TestCase):
    def test_rss_neueste_zuerst_und_ohne_html(self):
        f = W.parse_rss(RSS)
        self.assertEqual(f["titel"], "Museum aktuell")
        self.assertEqual([e["titel"] for e in f["eintraege"]], ["Neuer", "Neue Ausstellung & Fest", "Aelter"])
        self.assertEqual(f["eintraege"][1]["text"], "Es gibt Kuchen.")
        self.assertEqual(f["eintraege"][1]["quelle"], "Museum aktuell")
        self.assertTrue(f["eintraege"][0]["zeit"].startswith("2026-09-22T09:00:00"))

    def test_atom_wird_verstanden(self):
        f = W.parse_rss(ATOM)
        self.assertEqual(f["titel"], "Blog")
        self.assertEqual([e["titel"] for e in f["eintraege"]], ["Zweiter", "Erster"])
        self.assertEqual(f["eintraege"][1]["link"], "https://b.example/1")

    def test_anzahl_begrenzt(self):
        self.assertEqual(len(W.parse_rss(RSS, anzahl=2)["eintraege"]), 2)

    def test_kein_feed_wird_benannt_statt_geraten(self):
        with self.assertRaises(W.Abrufsfehler):
            W.parse_rss("<html><body>Keine Berechtigung</body></html>")
        with self.assertRaises(W.Abrufsfehler):
            W.parse_rss("das ist kein XML <")


# --------------------------------------------------------------------------
# ICS
# --------------------------------------------------------------------------

ICS = "\r\n".join([
    "BEGIN:VCALENDAR", "VERSION:2.0", "X-WR-CALNAME:Veranstaltungen",
    "BEGIN:VEVENT", "UID:1", "SUMMARY:Lange Nacht der Museen\\, mit Musik",
    "DTSTART;TZID=Europe/Berlin:20260918T220000", "DTEND;TZID=Europe/Berlin:20260919T020000", "END:VEVENT",
    # Gefaltet nach RFC 5545: der Umbruch steht mitten im Wort-Zwischenraum, das
    # Leerzeichen am Zeilenanfang gehoert zur Faltung und faellt weg.
    "BEGIN:VEVENT", "UID:2", "SUMMARY:Fuehrung mit einem sehr langen Titel der ueber ",
    " zwei Zeilen gefaltet ist", "DTSTART:20260921T110000", "DURATION:PT1H30M",
    "RRULE:FREQ=WEEKLY;BYDAY=MO,TH;COUNT=4", "END:VEVENT",
    "BEGIN:VEVENT", "UID:3", "SUMMARY:Feiertag", "DTSTART;VALUE=DATE:20261003", "END:VEVENT",
    "BEGIN:VEVENT", "UID:4", "SUMMARY:Taeglich", "DTSTART:20260920T090000", "DTEND:20260920T093000",
    "RRULE:FREQ=DAILY;UNTIL=20260922T235959", "END:VEVENT",
    "END:VCALENDAR", ""])


class Kalender(unittest.TestCase):
    def setUp(self):
        self.von = datetime(2026, 9, 17)
        self.bis = datetime(2026, 10, 10)
        self.k = W.parse_ics(ICS, self.von, self.bis)

    def titel(self, t):
        return [x for x in self.k["termine"] if x["titel"].startswith(t)]

    def test_kalendername_und_escapes(self):
        self.assertEqual(self.k["name"], "Veranstaltungen")
        self.assertEqual(self.titel("Lange Nacht")[0]["titel"], "Lange Nacht der Museen, mit Musik")

    def test_termin_ueber_mitternacht_behaelt_beide_zeiten(self):
        t = self.titel("Lange Nacht")[0]
        self.assertEqual(t["start"], "2026-09-18T22:00")
        self.assertEqual(t["ende"], "2026-09-19T02:00")
        self.assertFalse(t["ganztags"])

    def test_gefaltete_zeile_wird_zusammengesetzt(self):
        self.assertTrue(self.titel("Fuehrung mit einem sehr langen Titel der ueber zwei Zeilen"))

    def test_rrule_weekly_byday_count(self):
        starts = [t["start"] for t in self.titel("Fuehrung")]
        # Mo 21.9., Do 24.9., Mo 28.9., Do 1.10. — COUNT=4, Uhrzeit bleibt, Dauer 1:30
        self.assertEqual(starts, ["2026-09-21T11:00", "2026-09-24T11:00", "2026-09-28T11:00", "2026-10-01T11:00"])
        self.assertEqual(self.titel("Fuehrung")[0]["ende"], "2026-09-21T12:30")

    def test_rrule_daily_until(self):
        starts = [t["start"] for t in self.titel("Taeglich")]
        self.assertEqual(starts, ["2026-09-20T09:00", "2026-09-21T09:00", "2026-09-22T09:00"])

    def test_ganztaegiger_termin(self):
        t = self.titel("Feiertag")[0]
        self.assertTrue(t["ganztags"])
        self.assertEqual((t["start"], t["ende"]), ("2026-10-03T00:00", "2026-10-04T00:00"))

    def test_fenster_grenzt_ein(self):
        k = W.parse_ics(ICS, datetime(2026, 9, 25), datetime(2026, 9, 30))
        self.assertEqual([t["titel"][:8] for t in k["termine"]], ["Fuehrung"])
        self.assertEqual(k["termine"][0]["start"], "2026-09-28T11:00")

    def test_sortiert(self):
        starts = [t["start"] for t in self.k["termine"]]
        self.assertEqual(starts, sorted(starts))

    def test_kein_kalender_wird_benannt(self):
        with self.assertRaises(W.Abrufsfehler):
            W.parse_ics("<html>Login</html>")


# --------------------------------------------------------------------------
# Wetter
# --------------------------------------------------------------------------

class Wetter(unittest.TestCase):
    def test_umformen_liefert_klartext_je_code(self):
        roh = {"current": {"temperature_2m": 17.6, "weather_code": 61, "time": "2026-09-28T12:00"},
               "current_units": {"temperature_2m": "°C"},
               "daily": {"time": ["2026-09-28", "2026-09-29"], "weather_code": [61, 0],
                         "temperature_2m_max": [18.2, 21.0], "temperature_2m_min": [9.1, 8.0]}}
        w = W.wetter_umformen(roh)
        self.assertEqual(w["aktuell"]["text"], "leichter Regen")
        self.assertEqual(w["tage"][1]["text"], "klar")
        self.assertEqual(w["einheit"], "°C")

    def test_koordinaten_werden_geprueft(self):
        self.assertEqual(W.pruefe_koordinaten("52.52", "13.405"), (52.52, 13.405))
        with self.assertRaises(W.Abrufsfehler):
            W.pruefe_koordinaten("abc", 1)
        with self.assertRaises(W.Abrufsfehler):
            W.pruefe_koordinaten(95, 0)


# --------------------------------------------------------------------------
# Zwischenspeicher und Abruf
# --------------------------------------------------------------------------

class Zwischenspeicher(unittest.TestCase):
    def test_bei_fehler_kommt_das_alte_als_veraltet(self):
        uhr = [0.0]
        c = W.Cache(uhr=lambda: uhr[0])
        stand = {"n": 0}

        def lader():
            stand["n"] += 1
            if stand["n"] > 1:
                raise W.Abrufsfehler("Netz weg")
            return {"wert": "erster"}
        a = c.hole("k", lader, ttl=10)
        self.assertEqual((a["wert"], a["veraltet"], a["aus_cache"]), ("erster", False, False))
        uhr[0] = 5
        b = c.hole("k", lader, ttl=10)          # noch frisch: Lader wird nicht gerufen
        self.assertEqual((b["aus_cache"], stand["n"]), (True, 1))
        uhr[0] = 20
        d = c.hole("k", lader, ttl=10)          # abgelaufen, Lader scheitert -> das Alte, als veraltet
        self.assertEqual((d["wert"], d["veraltet"], d["fehler"]), ("erster", True, "Netz weg"))

    def test_ohne_altes_wird_der_fehler_weitergereicht(self):
        c = W.Cache()

        def lader():
            raise W.Abrufsfehler("Netz weg")
        with self.assertRaises(W.Abrufsfehler):
            c.hole("x", lader)

    def test_nur_http_und_https(self):
        for schlecht in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)", "", None, "http://"):
            with self.subTest(url=schlecht):
                with self.assertRaises(W.Abrufsfehler):
                    W.pruefe_url(schlecht)
        self.assertEqual(W.pruefe_url(" https://a.example/feed.xml "), "https://a.example/feed.xml")


# --------------------------------------------------------------------------
# Die Schnittstelle
# --------------------------------------------------------------------------

class UeberDieApi(unittest.TestCase):
    def setUp(self):
        self.controller = main.Controller(frische_config())
        self.controller.save_config = lambda: None
        self.app = create_app(self.controller)
        W.CACHE.leeren()

    def test_proxy_lehnt_dateisystem_ab(self):
        with self.app.test_client() as c:
            r = c.get("/api/widgets/rss?url=file:///etc/passwd")
            self.assertEqual(r.status_code, 400)
            self.assertIn("http", r.get_json()["fehler"])
            self.assertEqual(c.get("/api/widgets/ics").status_code, 400)
            self.assertEqual(c.get("/api/widgets/wetter?lat=x&lon=1").status_code, 400)
            self.assertEqual(c.get("/api/widgets/einbettbar?url=gopher://x").status_code, 400)

    def test_proxy_meldet_502_wenn_die_gegenseite_nicht_liefert(self):
        def kaputt(*a, **k):
            raise W.Abrufsfehler("nicht erreichbar (Test)")
        with unittest.mock.patch.object(W, "hole_url", kaputt):
            with self.app.test_client() as c:
                r = c.get("/api/widgets/rss?url=https://a.example/feed")
                self.assertEqual(r.status_code, 502)
                self.assertIn("nicht erreichbar", r.get_json()["fehler"])

    def test_proxy_liefert_geparsten_feed(self):
        with unittest.mock.patch.object(W, "hole_url", lambda *a, **k: (RSS.encode(), {"content-type": "application/rss+xml"})):
            with self.app.test_client() as c:
                r = c.get("/api/widgets/rss?url=https://a.example/feed&anzahl=2")
                self.assertEqual(r.status_code, 200)
                d = r.get_json()
                self.assertEqual(len(d["eintraege"]), 2)
                self.assertFalse(d["veraltet"])

    def test_einbettbar_liest_die_kopfzeilen(self):
        with unittest.mock.patch.object(W, "hole_url", lambda *a, **k: (b"", {"x-frame-options": "DENY"})):
            with self.app.test_client() as c:
                d = c.get("/api/widgets/einbettbar?url=https://a.example/").get_json()
                self.assertFalse(d["einbettbar"])
                self.assertIn("DENY", d["grund"])

    def test_eigene_widgets_werden_gelistet_und_ausgeliefert(self):
        with self.app.test_client() as c:
            namen = [w["name"] for w in c.get("/api/widgets/eigene").get_json()["widgets"]]
            self.assertIn("beispiel", namen)
            r = c.get("/widgets/beispiel/index.html")
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"LZ_WIDGET_EINSTELLUNGEN", r.data)
            self.assertEqual(c.get("/widgets/beispiel/").status_code, 200)

    def test_kein_weg_aus_dem_widget_ordner(self):
        with self.app.test_client() as c:
            for pfad in ("/widgets/beispiel/../../config_schema.py", "/widgets/beispiel/..%2F..%2Fmain.py",
                         "/widgets/../main.py", "/widgets/Beispiel/index.html", "/widgets/gibtsnicht/index.html"):
                with self.subTest(pfad=pfad):
                    r = c.get(pfad)
                    self.assertIn(r.status_code, (400, 404), pfad)
                    self.assertNotIn(b"DEFAULT_CONFIG", r.data)

    def test_eigene_widgets_ohne_ordner_ist_leer(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(W.eigene_widgets(os.path.join(d, "gibtsnicht")), [])
            os.makedirs(os.path.join(d, "ok"))
            os.makedirs(os.path.join(d, "Ohne.Index"))
            Path(d, "ok", "index.html").write_text("<title>Mein Widget</title>", encoding="utf-8")
            self.assertEqual(W.eigene_widgets(d), [{"name": "ok", "titel": "Mein Widget"}])


# --------------------------------------------------------------------------
# widgets.js: Katalog-Vertrag und QR-Referenz
# --------------------------------------------------------------------------

class DerKatalogVertrag(unittest.TestCase):
    """Jedes Widget ist ein Eintrag in `WIDGETS` mit name, beschreibung,
    felder und render — der Katalog leitet sich daraus ab. Der Test haelt
    fest, was ein neues Widget mitbringen muss, und dass die Doku es kennt."""

    def typen(self):
        return re.findall(r"^\s{4}WIDGETS\.([a-z]+) = \{", WIDGETS_JS, re.M)

    def test_jedes_widget_hat_name_beschreibung_felder_und_render(self):
        typen = self.typen()
        self.assertGreaterEqual(len(typen), 10, typen)
        for typ in typen:
            block = WIDGETS_JS.split(f"WIDGETS.{typ} = {{", 1)[1].split("\n    WIDGETS.", 1)[0]
            for pflicht in ("name:", "beschreibung:", "felder:", "render:"):
                self.assertIn(pflicht, block, f"{typ} ohne {pflicht}")

    def test_die_doku_kennt_jedes_widget(self):
        doku = (WURZEL / "docs/widgets.md").read_text(encoding="utf-8")
        for typ in self.typen():
            self.assertIn(f"### `{typ}`", doku, f"docs/widgets.md ohne Abschnitt fuer {typ}")

    def test_die_geforderten_widgets_gibt_es(self):
        self.assertEqual(set(self.typen()) >= {"uhr", "text", "ticker", "wetter", "rss", "kalender", "qr", "webseite", "html", "zaehler"}, True)

    def test_kein_alert_kein_confirm(self):
        # Ein Dialog haelt den Kiosk an — auf einem Schirm ohne Tastatur fuer immer.
        self.assertNotRegex(WIDGETS_JS, r"\b(alert|confirm|prompt)\(")

    def test_keine_konsolenfehler_als_fehlerweg(self):
        # Fehler werden auf dem Schirm dezent gesagt, nicht in die Konsole geworfen.
        self.assertNotIn("console.error", WIDGETS_JS)
        self.assertNotRegex(WIDGETS_JS, r"^\s*throw ", )

    def test_sichtbare_katalogtexte_sind_uebersetzt(self):
        wb = json.loads((WURZEL / "static/i18n/widgets.en.js").read_text(encoding="utf-8").split("/*JSON*/")[1])
        gleich = {"↖", "↗", "↘", "↙", "°C", "°F", "Zoom (%)"}
        texte = set(re.findall(r"label: '([^']+)'", WIDGETS_JS)) | set(re.findall(r"name: '([^']+)'", WIDGETS_JS)) \
            | set(re.findall(r"beschreibung: '([^']+)'", WIDGETS_JS))
        fehlt = sorted(t for t in texte if t not in gleich and t not in wb["texte"])
        self.assertEqual(fehlt, [], f"Katalogtexte ohne englischen Eintrag: {fehlt}")


@unittest.skipUnless(NODE, "node fehlt — der QR-Vergleich laeuft nur mit Node")
class QrGegenReferenz(unittest.TestCase):
    """Die Referenzmatrizen stammen aus `qrcode` (Python), Byte-Modus, Level M,
    erzwungene Maske. Der Eigenbau muss Modul fuer Modul dasselbe liefern —
    sonst scannt der Code auf dem Schirm nicht, und niemand merkt es."""

    def lauf(self):
        skript = r"""
            const W = require(process.argv[1]);
            const fix = require(process.argv[2]);
            const out = fix.map(f => {
                const q = W.qr.matrix(f.text, f.auto ? undefined : { maske: f.maske });
                const m = q.module.map(z => z.map(c => c ? '1' : '0').join(''));
                const selbst = W.qr.matrix(f.text, { maske: q.maske }).module.map(z => z.map(c => c ? '1' : '0').join(''));
                return { auto: f.auto, version: q.version, maske: q.maske, gleich: JSON.stringify(m) === JSON.stringify(f.matrix),
                         selbstkonsistent: JSON.stringify(m) === JSON.stringify(selbst) };
            });
            console.log(JSON.stringify(out));
        """
        r = subprocess.run([NODE, "-e", skript, str(WURZEL / "static/anzeige/widgets.js"),
                            str(WURZEL / "tests/fixtures/qr_referenz.json")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout), json.loads((WURZEL / "tests/fixtures/qr_referenz.json").read_text(encoding="utf-8"))

    def test_erzwungene_maske_liefert_dieselbe_matrix(self):
        ergebnis, fix = self.lauf()
        for e, f in zip(ergebnis, fix):
            if f["auto"]:
                continue
            with self.subTest(text=f["text"][:24], maske=f["maske"]):
                self.assertEqual(e["version"], f["version"])
                self.assertTrue(e["gleich"], "Matrix weicht von der Referenz ab")

    def test_automatische_maske_ist_gueltig_und_versionsgleich(self):
        # Die Bewertung der Masken unterscheidet sich zwischen Bibliotheken
        # (ISO 2000 vs. 2015) — geprueft wird deshalb die Version und dass der
        # gewaehlte Code dem entspricht, der mit dieser Maske entsteht.
        ergebnis, fix = self.lauf()
        for e, f in zip(ergebnis, fix):
            if not f["auto"]:
                continue
            with self.subTest(text=f["text"][:24]):
                self.assertEqual(e["version"], f["version"])
                self.assertIn(e["maske"], range(8))
                self.assertTrue(e["selbstkonsistent"])

    def test_zu_lang_liefert_null_statt_muell(self):
        r = subprocess.run([NODE, "-e", "const W=require(process.argv[1]);console.log(JSON.stringify([W.qr.matrix('a'.repeat(213))!==null, W.qr.matrix('a'.repeat(214)), W.qr.svg('x').startsWith('<svg')]))",
                            str(WURZEL / "static/anzeige/widgets.js")], capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout), [True, None, True], r.stderr)

    def test_katalog_unter_node(self):
        r = subprocess.run([NODE, "-e", "const W=require(process.argv[1]);const k=W.katalog();console.log(JSON.stringify(k.map(w=>[w.typ,w.felder.length])))",
                            str(WURZEL / "static/anzeige/widgets.js")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        katalog = dict(json.loads(r.stdout))
        self.assertIn("uhr", katalog)
        self.assertTrue(all(n > 0 for n in katalog.values()))


import unittest.mock  # noqa: E402  (nach den Klassen, damit oben nichts im Weg steht)


if __name__ == "__main__":
    unittest.main()

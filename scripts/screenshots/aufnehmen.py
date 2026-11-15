#!/usr/bin/env python3
"""Die README-Screenshots neu aufnehmen (DE und EN).

Startet drei Demo-Stationen aus dem Arbeitsstand dieses Repos (je eine
Kopie in einem Temp-Ordner, damit `config.json` und Medien des Repos
unberuehrt bleiben), befuellt sie mit Layouts, Wochenprogramm und
Ausloesern und fotografiert sie mit Headless Chromium (Playwright).

    python3 -m venv /tmp/lz-shots && /tmp/lz-shots/bin/pip install flask playwright
    /tmp/lz-shots/bin/python -m playwright install chromium-headless-shell
    /tmp/lz-shots/bin/python scripts/screenshots/aufnehmen.py

Ergebnis: docs/screenshot-*.png. Immer im hellen Schema — Headless Chrome
meldet sonst je nach System dunkel.
"""

import base64
import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO, "docs")
HIER = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# Drei echte Stationen; die vierte Kachel im Station Manager ist offline.
STATIONEN = [
    {"name": "Foyer Nord", "port": 5101, "gruppe": "Foyer", "tags": ["EG", "Eingang"],
     "nah": "foyer-l-form", "fern": "foyer-l-form"},
    {"name": "Café Theke", "port": 5102, "gruppe": "Café", "tags": ["EG"],
     "nah": "cafe-plakat", "fern": "cafe-plakat"},
    {"name": "Saal 1 Bühne", "port": 5103, "gruppe": "Saal", "tags": ["OG"],
     "nah": "saal-plakat", "fern": "saal-plakat"},
]
OFFLINE = {"name": "Foyer Süd", "host": "192.168.10.23", "port": 5000,
           "gruppe": "Foyer", "tags": ["Eingang"]}


# ── Demo-Inhalte ─────────────────────────────────────────────────────────────

def region(rid, name, x, y, w, h, typ="medien", z=0, playlist=None, widget=None):
    return {"id": rid, "name": name, "x": x, "y": y, "w": w, "h": h, "z": z,
            "typ": typ, "ton": typ == "medien", "playlist": playlist or [],
            "shuffle": False, "einmal": False, "uebergang": "blende",
            "widget": widget or {}}


def bild(name, dauer=None):
    return {"typ": "image", "name": name, "dauer_s": dauer, "von": None, "bis": None}


TICKER = ("Café im Erdgeschoss geöffnet bis 18 Uhr  •  Führung um 15 Uhr am Infotresen"
          "  •  Willkommen im Haus der Medien")


def layouts(stationsname):
    return {
        "foyer-l-form": {
            "name": "Foyer – L-Form", "vorlage": "l-form", "hintergrund": "#132040",
            "regionen": [
                region("hauptbild", "Hauptbild", 0, 0, 75, 85, playlist=[
                    bild("ausstellung-licht-und-raum.png", 30),
                    bild("fuehrung-15-uhr.png", 10),
                    bild("willkommen.png", 8)]),
                region("seitenleiste", "Seitenleiste", 75, 0, 25, 85, typ="widget", z=1,
                       widget={"typ": "uhr", "stil": "digital", "datum": True}),
                region("ticker", "Laufschrift", 0, 85, 100, 15, typ="widget", z=2,
                       widget={"typ": "ticker", "text": TICKER, "geschwindigkeit": 90}),
            ],
        },
        "willkommen": {
            "name": "Willkommen", "vorlage": "frei", "hintergrund": "#132040",
            "regionen": [
                region("text", "Begrüßung", 0, 0, 70, 100, typ="widget",
                       widget={"typ": "text", "vorlage": "willkommen",
                               "ueberschrift": "Willkommen",
                               "text": stationsname, "fusszeile": "Haus der Medien"}),
                region("qr", "QR-Code", 70, 25, 30, 50, typ="widget", z=1,
                       widget={"typ": "qr", "inhalt": "https://example.org/programm",
                               "beschriftung": "Programm aufs Handy"}),
            ],
        },
        # Vollbild-Plakate: die Vorschau im Station Manager zeigt Bilder, keine Widgets.
        "cafe-plakat": {
            "name": "Café – Plakat", "vorlage": "vollbild", "hintergrund": "#132040",
            "regionen": [region("haupt", "Hauptbild", 0, 0, 100, 100, playlist=[
                bild("willkommen.png", 20), bild("fuehrung-15-uhr.png", 10)])],
        },
        "saal-plakat": {
            "name": "Saal – Abendprogramm", "vorlage": "vollbild", "hintergrund": "#132040",
            "regionen": [region("haupt", "Hauptbild", 0, 0, 100, 100, playlist=[
                bild("fuehrung-15-uhr.png", 20), bild("ausstellung-licht-und-raum.png", 10)])],
        },
        "speisekarte": {
            "name": "Speisekarte", "vorlage": "frei", "hintergrund": "#132040",
            "regionen": [
                region("karte", "Karte", 0, 0, 100, 100, typ="widget",
                       widget={"typ": "text", "vorlage": "menuekarte",
                               "ueberschrift": "Mittagstisch",
                               "text": "Tagessuppe | 4,50 €\nOfengemüse mit Feta | 9,80 €\n"
                                       "Hausgemachter Kuchen | 3,20 €\nCappuccino | 2,90 €",
                               "fusszeile": "Täglich 11:30–14:00"}),
            ],
        },
    }


def programm(heute):
    montag = heute - dt.timedelta(days=heute.weekday())
    werktage = ["mo", "di", "mi", "do", "fr"]
    return {
        "eintraege": [
            {"id": "mittagstisch", "name": "Mittagstisch", "layout_id": "speisekarte",
             "zonen": [], "tage": werktage, "von": "11:30", "bis": "14:00",
             "prioritaet": 6, "aktiv": True},
            {"id": "abendprogramm", "name": "Abendprogramm", "layout_id": "foyer-l-form",
             "zonen": [], "tage": werktage, "von": "17:00", "bis": "22:00",
             "prioritaet": 5, "aktiv": True},
            {"id": "vernissage", "name": "Vernissage", "layout_id": "willkommen",
             "zonen": [], "tage": ["do"], "von": "19:00", "bis": "23:00",
             "prioritaet": 8, "aktiv": True},
            {"id": "wochenende", "name": "Wochenende", "layout_id": "willkommen",
             "zonen": [], "tage": ["sa", "so"], "von": "09:00", "bis": "20:00",
             "prioritaet": 5, "aktiv": True},
        ],
        "ausnahmen": [
            {"datum": (montag + dt.timedelta(days=2)).isoformat(),
             "layout_id": "willkommen", "name": "Tag der offenen Tür"},
        ],
    }


AUSLOESER = [
    {"id": "einlass", "name": "Einlass beginnt", "aktiv": True,
     "quelle": {"typ": "webhook", "token": "einlass-saal-1"},
     "aktion": {"typ": "meldung", "text": "Einlass in Saal 1", "untertext": "Bitte Plätze einnehmen",
                "farbe": "#B04A3F", "textfarbe": "#FFFFFF", "dauer_s": 120, "ton": True}},
    {"id": "morgens-an", "name": "Morgens einschalten", "aktiv": True,
     "quelle": {"typ": "zeit", "tage": ["mo", "di", "mi", "do", "fr"], "zeit": "08:30"},
     "aktion": {"typ": "start"}},
    {"id": "naehe-plakat", "name": "Besucher nah → Plakat", "aktiv": True,
     "quelle": {"typ": "zone", "zone": "near"},
     "aktion": {"typ": "zeige_layout", "layout_id": "foyer-l-form", "dauer_s": 60}},
]


def config(station, heute):
    zone = {"videos": [], "images": [], "audio": [], "shuffle": False,
            "einmal": False, "bildzeiten": {}}
    return {
        "system_name": station["name"],
        "zonen_stufen": 2,
        "near": dict(zone, layout=station["nah"]),
        "far": dict(zone, layout=station["fern"]),
        "layouts": layouts(station["name"]),
        # Programm und Ausloeser nur im Foyer: sonst schaltet das Programm
        # tagsueber alle drei Stationen auf dasselbe Layout.
        "programm": programm(heute) if station is STATIONEN[0] else {"eintraege": [], "ausnahmen": []},
        "ausloeser": AUSLOESER if station is STATIONEN[0] else [],
    }


# ── Plakate (als HTML gesetzt, mit Chromium gerendert) ───────────────────────

PLAKATE = {
    "ausstellung-licht-und-raum.png": ("Sonderausstellung", "Licht<br>und Raum",
                                       "12. September – 30. November 2026", "#132040", "#C8A86B"),
    "fuehrung-15-uhr.png": ("Heute", "Führung<br>15 Uhr", "Treffpunkt Infotresen", "#1E4D3A", "#F6F5F0"),
    "willkommen.png": ("Haus der Medien", "Will&shy;kommen", "Erdgeschoss · Eintritt frei", "#2A2F45", "#F6F5F0"),
}


def plakate_rendern(browser, ziel):
    seite = browser.new_page(viewport={"width": 1440, "height": 1224})
    for datei, (dach, titel, unten, grund, akzent) in PLAKATE.items():
        seite.set_content(f"""<html><body style="margin:0;width:1440px;height:1224px;
            background:radial-gradient(circle at 78% 30%, {akzent}33, transparent 55%), {grund};
            color:#F6F5F0;font-family:'Helvetica Neue',Arial,sans-serif;display:flex;
            flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box">
            <div style="letter-spacing:.3em;text-transform:uppercase;font-size:34px;color:{akzent}">{dach}</div>
            <div style="font-size:190px;font-weight:700;line-height:.95;margin:30px 0 50px">{titel}</div>
            <div style="font-size:44px;opacity:.85">{unten}</div></body></html>""")
        seite.screenshot(path=os.path.join(ziel, datei))
    seite.close()


# ── Stationen ────────────────────────────────────────────────────────────────

def kopie_anlegen(ziel):
    dateien = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, check=True,
                             capture_output=True).stdout.decode().split("\0")
    for rel in filter(None, dateien):
        quelle = os.path.join(REPO, rel)
        if not os.path.isfile(quelle):
            continue
        os.makedirs(os.path.dirname(os.path.join(ziel, rel)), exist_ok=True)
        shutil.copy2(quelle, os.path.join(ziel, rel))


def warte_auf(port, sekunden=30):
    ende = time.time() + sekunden
    while time.time() < ende:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    raise RuntimeError(f"Station auf Port {port} kommt nicht hoch")


def http(port, pfad, methode="GET", daten=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{pfad}", method=methode,
                                 data=json.dumps(daten).encode() if daten is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"null")


# ── Station Manager: Renderer im Browser, Preload nachgebildet ───────────────

def manager_vorbereiten(seite, stationen):
    """`window.station` aus preload.js gegen die echten Demo-Stationen."""
    def holen(url, methode="GET", koerper=None, roh=False):
        try:
            req = urllib.request.Request(url, method=methode,
                                         data=json.dumps(koerper).encode() if koerper is not None else None,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                daten = r.read()
                if roh:
                    return {"status": r.status, "typ": r.headers.get("content-type"),
                            "b64": base64.b64encode(daten).decode(), "zeit": r.headers.get("x-lz-zeit")}
                return {"status": r.status, "body": json.loads(daten or b"null")}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "body": None}
        except Exception as e:  # offline
            return {"status": 0, "error": str(e)}

    seite.expose_function("lzHolen", holen)
    with open(os.path.join(REPO, "station-manager", "package.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    seite.add_init_script("window.__LZ_STATIONEN = " + json.dumps(stationen) + ";\n"
                          + "window.__LZ_VERSION = " + json.dumps(version) + ";\n"
                          + open(os.path.join(HIER, "manager-preload.js"), encoding="utf-8").read())


# ── Aufnahme ─────────────────────────────────────────────────────────────────

# Die Startseite nennt die LAN-Adresse des Rechners; ins Repo gehoert eine
# Beispieladresse, nicht die des Netzes, in dem aufgenommen wurde.
BEISPIEL_IP = "192.168.1.50"


def beispieladresse(ctx):
    def umschreiben(route):
        antwort = route.fetch()
        daten = antwort.json()
        daten["host_ip"], daten["web_port"] = BEISPIEL_IP, 5000
        for feld in ("remote_url", "display_url"):
            daten.pop(feld, None)
        route.fulfill(response=antwort, json=daten)
    ctx.route("**/api/status", umschreiben)


def ohne_vorschau(ctx):
    """Vorschau-iframes der Verwaltung nicht laden: sie meldeten sich sonst
    beim Monitor als weitere Anzeigen."""
    ctx.route("**/display?*vorschau=1*", lambda route: route.abort())

def admin(browser, port, sprache, breite=1280, hoehe=2600, dpr=1, mobil=False, vorbereiten=None):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              device_scale_factor=dpr, is_mobile=mobil, has_touch=mobil,
                              color_scheme="light",
                              locale="en-US" if sprache == "en" else "de-DE")
    if vorbereiten:
        vorbereiten(ctx)
    seite = ctx.new_page()
    seite.goto(f"http://127.0.0.1:{port}/admin?lang={sprache}")
    seite.wait_for_load_state("networkidle")
    return ctx, seite


def ansicht(seite, name):
    seite.click(f'.view-tab[data-view="{name}"]')
    seite.wait_for_timeout(800)


def karte(seite, selektor, datei, bis=None, vorher=None):
    """Eine Karte fotografieren; mit `bis` nur bis zur Unterkante dieses Elements."""
    el = seite.locator(selektor)
    # Die Karte steckt in einer der Ansichten (Reiter); diese zuerst zeigen.
    name = el.evaluate("e => (e.closest('.view') || {}).dataset?.view || ''")
    if name:
        ansicht(seite, name)
    el.scroll_into_view_if_needed()
    if vorher:
        vorher()
    seite.wait_for_timeout(600)
    if bis:
        k = el.bounding_box()
        unten = seite.locator(bis).bounding_box()
        seite.screenshot(path=os.path.join(DOCS, datei), clip={
            "x": k["x"], "y": k["y"], "width": k["width"],
            "height": unten["y"] + unten["height"] - k["y"] + 10})
    else:
        el.screenshot(path=os.path.join(DOCS, datei))
    print("  ", datei)


def main():
    heute = dt.date.today()
    tmp = tempfile.mkdtemp(prefix="lz-shots-")
    prozesse = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            plakat_ordner = os.path.join(tmp, "plakate")
            os.makedirs(plakat_ordner)
            plakate_rendern(browser, plakat_ordner)

            for i, st in enumerate(STATIONEN):
                ordner = os.path.join(tmp, f"station{i}")
                kopie_anlegen(ordner)
                for f in os.listdir(plakat_ordner):
                    shutil.copy(os.path.join(plakat_ordner, f), os.path.join(ordner, "images", f))
                with open(os.path.join(ordner, "config.json"), "w", encoding="utf-8") as f:
                    json.dump(config(st, heute), f, ensure_ascii=False, indent=2)
                log = open(os.path.join(tmp, f"station{i}.log"), "w")
                prozesse.append(subprocess.Popen(
                    [PYTHON, "main.py", "--host", "127.0.0.1", "--port", str(st["port"])],
                    cwd=ordner, stdout=log, stderr=subprocess.STDOUT))
            for st in STATIONEN:
                warte_auf(st["port"])

            # Anzeigen verbinden: je Station eine (Foyer zwei), damit Monitor,
            # Proof-of-Play und die Manager-Kacheln echte Bilder haben.
            anzeigen = browser.new_context(viewport={"width": 1920, "height": 1080}, color_scheme="light")
            for st, anzahl in zip(STATIONEN, (2, 1, 1)):
                for _ in range(anzahl):
                    anzeigen.new_page().goto(f"http://127.0.0.1:{st['port']}/display")
            for st in STATIONEN:
                try:
                    http(st["port"], "/api/start", "POST", {})
                except Exception:
                    pass
            time.sleep(12)
            for st in STATIONEN:
                try:
                    http(st["port"], "/api/anzeige/screenshot/anfordern", "POST", {})
                except Exception as e:
                    print("  Vorschau", st["name"], e)

            port = STATIONEN[0]["port"]

            # Proof-of-Play zaehlt Starts: erst nach dem ersten Wechsel im
            # Hauptbild (30 s) steht dort etwas.
            time.sleep(35)

            # Monitor zuerst: Vorschau-Seiten (Aufmacher, Layout-Editor)
            # meldeten sich sonst als weitere Anzeigen.
            for sprache in ("de", "en"):
                ctx, s = admin(browser, port, sprache, vorbereiten=ohne_vorschau)
                karte(s, "#card-monitor", "screenshot-monitor" + ("-en" if sprache == "en" else "") + ".png",
                      bis="#pop-tabelle", vorher=lambda: (
                          s.locator('#card-monitor button[onclick="ladeWiedergabe()"]').click(),
                          s.wait_for_timeout(2500)))
                ctx.close()

            # Aufmacher: das L-Layout so, wie es auf dem Schirm laeuft.
            p = anzeigen.new_page()
            p.goto(f"http://127.0.0.1:{port}/display?vorschau=1&layout=foyer-l-form")
            p.wait_for_timeout(4000)
            p.screenshot(path=os.path.join(DOCS, "screenshot-widgets.png"))
            print("   screenshot-widgets.png")
            p.close()

            for sprache in ("de", "en"):
                endung = "-en" if sprache == "en" else ""
                print(f"[{sprache}]")

                # Startseite
                ctx = browser.new_context(viewport={"width": 1280, "height": 720}, color_scheme="light",
                                          locale="en-US" if sprache == "en" else "de-DE")
                beispieladresse(ctx)
                s = ctx.new_page()
                s.goto(f"http://127.0.0.1:{port}/?lang={sprache}")
                s.wait_for_load_state("networkidle")
                s.wait_for_timeout(500)
                s.screenshot(path=os.path.join(DOCS, f"screenshot-start{endung}.png"))
                print(f"   screenshot-start{endung}.png")
                ctx.close()

                # Verwaltung am Handy
                ctx, s = admin(browser, port, sprache, 390, 844, 2, mobil=True)
                s.wait_for_timeout(800)
                s.screenshot(path=os.path.join(DOCS, f"screenshot-handy{endung}.png"))
                print(f"   screenshot-handy{endung}.png")
                ctx.close()

                ctx, s = admin(browser, port, sprache)
                ansicht(s, "zonen")
                s.select_option("#le-wahl", "foyer-l-form")
                s.wait_for_timeout(1500)
                karte(s, "#card-layouts", f"screenshot-layout-editor{endung}.png")
                karte(s, "#card-programm", f"screenshot-programm{endung}.png")
                karte(s, "#card-ausloeser", f"screenshot-ausloeser{endung}.png")
                ctx.close()

                # Station Manager
                ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light",
                                          locale="en-US" if sprache == "en" else "de-DE")
                s = ctx.new_page()
                liste = [dict(st, host="127.0.0.1") for st in STATIONEN] + [OFFLINE]
                manager_vorbereiten(s, liste)
                s.goto("file://" + os.path.join(REPO, "station-manager", "renderer", "index.html")
                       + f"?lang={sprache}")
                s.wait_for_timeout(9000)
                s.screenshot(path=os.path.join(DOCS, f"screenshot-manager{endung}.png"))
                print(f"   screenshot-manager{endung}.png")
                ctx.close()

            browser.close()
    finally:
        for p in prozesse:
            p.terminate()
        for p in prozesse:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        if os.environ.get("LZ_SHOTS_BEHALTEN"):
            print("Temp-Ordner:", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

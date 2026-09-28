#!/usr/bin/env python3
"""Layouts, Regionen und Playlists — das Bild auf dem Schirm.

WARUM ES DAS GIBT. Bis 3.0 kannte eine Zone drei Listen (Videos, Bilder,
Audio) und spielte sie im Vollbild: Videos vor Bildern, nie beides. Fuer eine
Ausstellungs-Station reicht das; fuer einen Schirm im Foyer, der links einen
Film, rechts das Programm und unten eine Laufschrift zeigen soll, nicht.

Ein **Layout** teilt den Schirm in **Regionen** (Prozent-Rechtecke). Jede
Medien-Region hat eine eigene **Playlist** aus gemischten Eintraegen (Video,
Bild, Webseite, Audio) mit optionaler Standzeit und Gueltigkeit (von/bis).
Eine Widget-Region ueberlaesst die Flaeche einem Widget (Uhr, Laufschrift —
kommt mit Welle 2). Jede Zone spielt genau ein Layout.

DAS MODUL IST REIN: kein Flask, keine Platte, keine Uhr. `heile_*` repariert
(Ladeweg), `pruefe_*` lehnt ab und nennt das Feld (Schreibweg) — dieselben
zwei Politiken wie in `config_schema`.

RUECKWAERTSKOMPATIBILITAET. Die alten Zonenfelder (`videos`, `images`,
`shuffle`, `einmal`, `bildzeiten`) BLEIBEN in der Zone stehen — als
**Spiegel** der Hauptregion des Zonen-Layouts, den `spiegle_zone` nach jedem
Schreibzugriff neu setzt. Die Wahrheit steht im Layout. Der Spiegel ist fuer
alte Displays, alte Manager-Fassungen (die `{"near": {"videos": [...]}}`
schicken) und alte Sicherungen da — und fuer alles im Code, das die Zone noch
so liest. Beim ersten Start mit einer alten `config.json` wandern die Listen
einmalig ins Layout `zone-<zone>` (Migration).
"""
import copy
import re

#: Kennungen fuer Layouts und Regionen: klein, Ziffern, Bindestrich, 1..40.
KENNUNG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FARBE = re.compile(r"^#[0-9a-fA-F]{6}$")
DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://\S+$")

MAX_LAYOUTS = 60
MAX_REGIONEN = 12
NAME_MAX = 64
DAUER_MIN_S = 1.0
DAUER_MAX_S = 86400.0

VORLAGEN = ("vollbild", "geteilt", "l-form", "ticker", "frei")
REGION_TYPEN = ("medien", "widget")
ITEM_TYPEN = ("video", "image", "audio", "web")
UEBERGAENGE = ("blende", "keiner")

#: Welche Medienart (Verzeichnis) zu welchem Item-Typ gehoert.
ART_ZU_TYP = {"videos": "video", "images": "image", "audio": "audio"}

#: Das Standard-Layout je Zone. `zone["layout"] == ""` heisst: dieses.
ZONEN = ("near", "mid", "far")
ZONEN_LAYOUT = {"near": "zone-near", "mid": "zone-mid", "far": "zone-far"}
ZONEN_LAYOUT_NAMEN = {"near": "Nah – Vollbild", "mid": "Mitte – Vollbild",
                      "far": "Fern – Vollbild"}

VORLAGEN_INFO = {
    "vollbild": "Eine Region ueber den ganzen Schirm.",
    "geteilt": "Zwei Regionen nebeneinander, je die halbe Breite.",
    "l-form": "Hauptbild links oben, Seitenleiste rechts, Laufschrift unten.",
    "ticker": "Vollbild mit Laufschrift am unteren Rand.",
    "frei": "Ohne Regionen — selbst anlegen.",
}


# ── Bausteine ────────────────────────────────────────────────────────────────

def standard_region(rid, name, x=0, y=0, w=100, h=100, typ="medien", ton=True,
                    z=0, widget=None):
    return {
        "id": rid, "name": name,
        "x": float(x), "y": float(y), "w": float(w), "h": float(h),
        "z": int(z), "typ": typ, "ton": bool(ton),
        "playlist": [], "shuffle": False, "einmal": False,
        "uebergang": "blende",
        "widget": dict(widget or {}),
    }


def vorlage_regionen(vorlage):
    """Die Regionen, die eine Vorlage vorbelegt."""
    if vorlage == "geteilt":
        return [standard_region("links", "Links", 0, 0, 50, 100, ton=True),
                standard_region("rechts", "Rechts", 50, 0, 50, 100, ton=False)]
    if vorlage == "l-form":
        return [standard_region("haupt", "Hauptbild", 0, 0, 70, 80, ton=True),
                standard_region("seite", "Seitenleiste", 70, 0, 30, 80, ton=False),
                standard_region("ticker", "Laufschrift", 0, 80, 100, 20,
                                typ="widget", ton=False, z=1,
                                widget={"typ": "ticker", "text": ""})]
    if vorlage == "ticker":
        return [standard_region("haupt", "Hauptbild", 0, 0, 100, 85, ton=True),
                standard_region("ticker", "Laufschrift", 0, 85, 100, 15,
                                typ="widget", ton=False, z=1,
                                widget={"typ": "ticker", "text": ""})]
    if vorlage == "frei":
        return []
    return [standard_region("haupt", "Hauptbild", 0, 0, 100, 100, ton=True)]


def standard_layout(name, vorlage="vollbild"):
    if vorlage not in VORLAGEN:
        vorlage = "vollbild"
    return {"name": name, "vorlage": vorlage, "hintergrund": "#000000",
            "regionen": vorlage_regionen(vorlage)}


def standard_layouts():
    """Die drei Zonen-Layouts einer frischen Station — leer, Vollbild."""
    return {ZONEN_LAYOUT[z]: standard_layout(ZONEN_LAYOUT_NAMEN[z]) for z in ZONEN}


def kennung_aus_name(name, vergeben=()):
    """Eine Kennung aus einem Anzeigenamen — und eindeutig gegen `vergeben`."""
    s = (name or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40].strip("-")
    if not s or not KENNUNG.match(s):
        s = "layout"
    basis, n = s, 2
    while s in vergeben:
        s = (basis[:36] + "-" + str(n)).strip("-")
        n += 1
    return s


# ── Items ────────────────────────────────────────────────────────────────────

def _dauer(roh):
    """None (allgemeine Standzeit) oder eine Zahl im erlaubten Bereich.
    Wirft bei Unsinn."""
    if roh is None or roh == "":
        return None
    if isinstance(roh, bool):
        raise ValueError("dauer_s: muss eine Zahl sein")
    wert = float(roh)
    if not (DAUER_MIN_S <= wert <= DAUER_MAX_S):
        raise ValueError(f"dauer_s: {wert} liegt ausserhalb von "
                         f"{DAUER_MIN_S:.0f}..{DAUER_MAX_S:.0f} s")
    return wert


def _datum(roh, feld):
    if roh is None or roh == "":
        return None
    if not isinstance(roh, str) or not DATUM.match(roh):
        raise ValueError(f"{feld}: muss JJJJ-MM-TT sein")
    return roh


def pruefe_item(roh):
    """Schreibweg: ein Playlist-Eintrag, oder ValueError mit Feldnamen."""
    if not isinstance(roh, dict):
        raise ValueError("Eintrag muss ein Objekt sein")
    typ = roh.get("typ")
    if typ not in ITEM_TYPEN:
        raise ValueError(f"typ: {typ!r} ist keins von {'|'.join(ITEM_TYPEN)}")
    item = {"typ": typ}
    if typ == "web":
        url = roh.get("url")
        if not isinstance(url, str) or not URL.match(url):
            raise ValueError("url: muss mit http:// oder https:// beginnen")
        item["url"] = url
    else:
        name = roh.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name: Dateiname fehlt")
        item["name"] = name.strip()
    item["dauer_s"] = _dauer(roh.get("dauer_s"))
    item["von"] = _datum(roh.get("von"), "von")
    item["bis"] = _datum(roh.get("bis"), "bis")
    if item["von"] and item["bis"] and item["von"] > item["bis"]:
        raise ValueError("von/bis: das Ende liegt vor dem Anfang")
    return item


def heile_item(roh):
    """Ladeweg: reparieren, was geht — None, wenn nichts zu retten ist."""
    if not isinstance(roh, dict):
        return None
    typ = roh.get("typ")
    if typ not in ITEM_TYPEN:
        return None
    item = {"typ": typ}
    if typ == "web":
        url = roh.get("url")
        if not isinstance(url, str) or not URL.match(url):
            return None
        item["url"] = url
    else:
        name = roh.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        item["name"] = name.strip()
    try:
        item["dauer_s"] = _dauer(roh.get("dauer_s"))
    except (TypeError, ValueError):
        item["dauer_s"] = None
    for feld in ("von", "bis"):
        try:
            item[feld] = _datum(roh.get(feld), feld)
        except ValueError:
            item[feld] = None
    if item["von"] and item["bis"] and item["von"] > item["bis"]:
        item["von"] = item["bis"] = None
    return item


def item_gilt(item, heute):
    """Gilt der Eintrag an diesem Tag? `heute` ist ein ISO-Datum (String)."""
    von, bis = item.get("von"), item.get("bis")
    if von and heute < von:
        return False
    if bis and heute > bis:
        return False
    return True


# ── Regionen ─────────────────────────────────────────────────────────────────

def _prozent(roh, feld, mindestens=0.0):
    if isinstance(roh, bool):
        raise ValueError(f"{feld}: muss eine Zahl sein")
    wert = float(roh)
    if not (mindestens <= wert <= 100.0):
        raise ValueError(f"{feld}: {wert} liegt ausserhalb von {mindestens:g}..100 %")
    return wert


def pruefe_region(roh):
    if not isinstance(roh, dict):
        raise ValueError("Region muss ein Objekt sein")
    rid = roh.get("id")
    if not isinstance(rid, str) or not KENNUNG.match(rid):
        raise ValueError(f"id: {rid!r} — erlaubt sind a-z, 0-9 und '-', 1..40 Zeichen")
    name = roh.get("name", rid)
    if not isinstance(name, str) or not (0 < len(name) <= NAME_MAX):
        raise ValueError(f"{rid}.name: 1..{NAME_MAX} Zeichen")
    region = standard_region(rid, name)
    try:
        region["x"] = _prozent(roh.get("x", 0), "x")
        region["y"] = _prozent(roh.get("y", 0), "y")
        region["w"] = _prozent(roh.get("w", 100), "w", mindestens=1.0)
        region["h"] = _prozent(roh.get("h", 100), "h", mindestens=1.0)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{rid}.{e}") from None
    if region["x"] + region["w"] > 100.0001 or region["y"] + region["h"] > 100.0001:
        raise ValueError(f"{rid}: die Region ragt ueber den Schirm hinaus")
    z = roh.get("z", 0)
    if isinstance(z, bool) or not isinstance(z, (int, float)):
        raise ValueError(f"{rid}.z: muss eine ganze Zahl sein")
    region["z"] = int(z)
    typ = roh.get("typ", "medien")
    if typ not in REGION_TYPEN:
        raise ValueError(f"{rid}.typ: {typ!r} ist keins von {'|'.join(REGION_TYPEN)}")
    region["typ"] = typ
    for schalter in ("ton", "shuffle", "einmal"):
        if schalter in roh:
            if not isinstance(roh[schalter], bool):
                raise ValueError(f"{rid}.{schalter}: muss true oder false sein")
            region[schalter] = roh[schalter]
    ueb = roh.get("uebergang", "blende")
    if ueb not in UEBERGAENGE:
        raise ValueError(f"{rid}.uebergang: {ueb!r} ist keins von {'|'.join(UEBERGAENGE)}")
    region["uebergang"] = ueb
    playlist = roh.get("playlist", [])
    if not isinstance(playlist, list):
        raise ValueError(f"{rid}.playlist: muss eine Liste sein")
    items = []
    for i, eintrag in enumerate(playlist):
        try:
            items.append(pruefe_item(eintrag))
        except ValueError as e:
            raise ValueError(f"{rid}.playlist[{i}].{e}") from None
    region["playlist"] = items
    widget = roh.get("widget", {})
    if widget is None:
        widget = {}
    if not isinstance(widget, dict):
        raise ValueError(f"{rid}.widget: muss ein Objekt sein")
    if "typ" in widget and not isinstance(widget["typ"], str):
        raise ValueError(f"{rid}.widget.typ: muss ein Text sein")
    region["widget"] = copy.deepcopy(widget)
    return region


def heile_region(roh, ersatz_id):
    if not isinstance(roh, dict):
        return None
    rid = roh.get("id")
    if not isinstance(rid, str) or not KENNUNG.match(rid):
        rid = ersatz_id
    name = roh.get("name")
    if not isinstance(name, str) or not (0 < len(name) <= NAME_MAX):
        name = rid
    region = standard_region(rid, name)
    for feld, vorgabe, mindestens in (("x", 0.0, 0.0), ("y", 0.0, 0.0),
                                      ("w", 100.0, 1.0), ("h", 100.0, 1.0)):
        try:
            region[feld] = _prozent(roh.get(feld, vorgabe), feld, mindestens)
        except (TypeError, ValueError):
            region[feld] = vorgabe
    # Ragt sie hinaus, wird sie eingekuerzt statt weggeworfen: eine Region,
    # die 2 % ueber den Rand steht, ist ein Tippfehler, kein Defekt.
    region["w"] = min(region["w"], 100.0 - region["x"]) or 1.0
    region["h"] = min(region["h"], 100.0 - region["y"]) or 1.0
    try:
        z = roh.get("z", 0)
        region["z"] = 0 if isinstance(z, bool) else int(z)
    except (TypeError, ValueError):
        region["z"] = 0
    region["typ"] = roh.get("typ") if roh.get("typ") in REGION_TYPEN else "medien"
    for schalter, vorgabe in (("ton", True), ("shuffle", False), ("einmal", False)):
        region[schalter] = bool(roh.get(schalter, vorgabe))
    region["uebergang"] = roh.get("uebergang") if roh.get("uebergang") in UEBERGAENGE else "blende"
    playlist = roh.get("playlist")
    if isinstance(playlist, list):
        region["playlist"] = [i for i in (heile_item(e) for e in playlist) if i]
    widget = roh.get("widget")
    if isinstance(widget, dict):
        region["widget"] = copy.deepcopy(widget)
        if "typ" in region["widget"] and not isinstance(region["widget"]["typ"], str):
            del region["widget"]["typ"]
    return region


# ── Layouts ──────────────────────────────────────────────────────────────────

def pruefe_layout(roh):
    """Schreibweg fuer EIN Layout (ohne Kennung — die steht im Pfad)."""
    if not isinstance(roh, dict):
        raise ValueError("Layout muss ein Objekt sein")
    name = roh.get("name")
    if not isinstance(name, str) or not (0 < len(name.strip()) <= NAME_MAX):
        raise ValueError(f"name: 1..{NAME_MAX} Zeichen")
    vorlage = roh.get("vorlage", "frei")
    if vorlage not in VORLAGEN:
        raise ValueError(f"vorlage: {vorlage!r} ist keins von {'|'.join(VORLAGEN)}")
    farbe = roh.get("hintergrund", "#000000")
    if not isinstance(farbe, str) or not FARBE.match(farbe):
        raise ValueError("hintergrund: Farbe als #rrggbb")
    regionen = roh.get("regionen", [])
    if not isinstance(regionen, list):
        raise ValueError("regionen: muss eine Liste sein")
    if len(regionen) > MAX_REGIONEN:
        raise ValueError(f"regionen: hoechstens {MAX_REGIONEN}")
    geprueft, ids = [], set()
    for i, r in enumerate(regionen):
        try:
            region = pruefe_region(r)
        except ValueError as e:
            raise ValueError(f"regionen[{i}].{e}") from None
        if region["id"] in ids:
            raise ValueError(f"regionen: Kennung {region['id']!r} ist doppelt")
        ids.add(region["id"])
        geprueft.append(region)
    return {"name": name.strip(), "vorlage": vorlage, "hintergrund": farbe.lower(),
            "regionen": geprueft}


def heile_layout(roh, ersatz_name="Layout"):
    if not isinstance(roh, dict):
        return standard_layout(ersatz_name, "frei")
    name = roh.get("name")
    if not isinstance(name, str) or not (0 < len(name.strip()) <= NAME_MAX):
        name = ersatz_name
    vorlage = roh.get("vorlage") if roh.get("vorlage") in VORLAGEN else "frei"
    farbe = roh.get("hintergrund")
    if not isinstance(farbe, str) or not FARBE.match(farbe):
        farbe = "#000000"
    regionen, ids = [], set()
    roh_regionen = roh.get("regionen")
    if isinstance(roh_regionen, list):
        for i, r in enumerate(roh_regionen[:MAX_REGIONEN]):
            region = heile_region(r, f"region-{i + 1}")
            if region is None or region["id"] in ids:
                continue
            ids.add(region["id"])
            regionen.append(region)
    return {"name": name.strip(), "vorlage": vorlage, "hintergrund": farbe.lower(),
            "regionen": regionen}


def heile_layouts(roh):
    """Ladeweg fuer die ganze Tabelle: Unbrauchbares weglassen, sagen."""
    if not isinstance(roh, dict):
        return {}
    heraus = {}
    for lid, layout in roh.items():
        if not isinstance(lid, str) or not KENNUNG.match(lid):
            print(f"[Layouts] Kennung {lid!r} unbrauchbar — Layout weggelassen")
            continue
        if len(heraus) >= MAX_LAYOUTS:
            print(f"[Layouts] mehr als {MAX_LAYOUTS} Layouts — {lid!r} weggelassen")
            continue
        heraus[lid] = heile_layout(layout, ersatz_name=lid)
    return heraus


# ── Zonen und ihr Layout ─────────────────────────────────────────────────────

def layout_id_der_zone(cfg, zone):
    """Die Kennung des Layouts, das diese Zone spielt (leer = Standard)."""
    zonendaten = cfg.get(zone) if isinstance(cfg.get(zone), dict) else {}
    lid = zonendaten.get("layout") or ""
    return lid if lid else ZONEN_LAYOUT.get(zone, "zone-" + zone)


def layout_der_zone(cfg, zone):
    return (cfg.get("layouts") or {}).get(layout_id_der_zone(cfg, zone))


def zonen_mit_layout(cfg, lid):
    """Welche Zonen spielen dieses Layout? (Auch die unausgesprochene Vorgabe.)"""
    return [z for z in ZONEN if layout_id_der_zone(cfg, z) == lid]


def hauptregion(layout, anlegen=False):
    """Die erste Medien-Region — dort landen die alten Zonenlisten.

    `anlegen`: gibt es keine, wird eine Vollbild-Region angelegt. Auf dem
    Schreibweg ist das richtig (die Zuweisung soll ankommen), auf dem
    Leseweg nicht (ein Layout nur aus Widgets hat eben keine Medien).
    """
    for region in layout.get("regionen", []):
        if region.get("typ") == "medien":
            return region
    if not anlegen:
        return None
    if len(layout.get("regionen", [])) >= MAX_REGIONEN:
        return None
    region = standard_region("haupt", "Hauptbild")
    layout.setdefault("regionen", []).insert(0, region)
    return region


def playlist_aus_listen(videos, images, bildzeiten, alt=None):
    """Alte Zonenlisten zu einer Playlist — Videos zuerst, dann Bilder (so
    spielte die Zone bis 3.0: Videos vor Bildern).

    `alt` sind die bisherigen Eintraege der Region: was dort zu einem Namen
    schon steht (Gueltigkeit, Standzeit einer Webseite), bleibt erhalten,
    und Eintraege anderer Art (Web, Audio) haengen hinten dran.
    """
    bisher = {}
    for item in (alt or []):
        bisher[(item.get("typ"), item.get("name") or item.get("url"))] = item
    neu = []
    for name in videos:
        item = dict(bisher.get(("video", name)) or
                    {"typ": "video", "name": name, "dauer_s": None, "von": None, "bis": None})
        neu.append(item)
    for name in images:
        item = dict(bisher.get(("image", name)) or
                    {"typ": "image", "name": name, "dauer_s": None, "von": None, "bis": None})
        zeit = (bildzeiten or {}).get(name)
        item["dauer_s"] = float(zeit) if zeit else None
        neu.append(item)
    for item in (alt or []):
        if item.get("typ") in ("web", "audio"):
            neu.append(dict(item))
    return neu


def uebernimm_spiegel(zonendaten, region):
    """Steht in der Zone eine Liste, die im (leeren) Layout fehlt, gehoert sie
    ins Layout — nicht weggespiegelt.

    Das ist die Migrationsregel, angewandt vor jedem Schreibzugriff: sie
    faengt alles auf, was die alten Felder direkt beschreibt (ein Skript,
    ein Test, ein von Hand editiertes config.json). Nur in eine LEERE
    Hauptregion — steht dort etwas, ist das Layout die Wahrheit.
    """
    if region.get("playlist"):
        return False
    videos = zonendaten.get("videos") or []
    images = zonendaten.get("images") or []
    if not videos and not images:
        return False
    region["playlist"] = playlist_aus_listen(videos, images, zonendaten.get("bildzeiten") or {})
    region["shuffle"] = bool(zonendaten.get("shuffle", region.get("shuffle")))
    region["einmal"] = bool(zonendaten.get("einmal", region.get("einmal")))
    return True


def spiegle_zone(cfg, zone):
    """Die alten Zonenfelder aus der Hauptregion des Layouts neu setzen.

    Wahrheit ist das Layout; die Zone traegt den Spiegel fuer alles, was sie
    noch so liest. Nach JEDEM Schreibzugriff aufrufen.
    """
    zonendaten = cfg.get(zone)
    if not isinstance(zonendaten, dict):
        return
    layout = layout_der_zone(cfg, zone)
    region = hauptregion(layout) if layout else None
    playlist = (region or {}).get("playlist") or []
    zonendaten["videos"] = [i["name"] for i in playlist if i.get("typ") == "video"]
    zonendaten["images"] = [i["name"] for i in playlist if i.get("typ") == "image"]
    zonendaten["bildzeiten"] = {i["name"]: i["dauer_s"] for i in playlist
                                if i.get("typ") == "image" and i.get("dauer_s")}
    zonendaten["shuffle"] = bool((region or {}).get("shuffle", False))
    zonendaten["einmal"] = bool((region or {}).get("einmal", False))
    if not isinstance(zonendaten.get("audio"), list):
        zonendaten["audio"] = []


def heile_layouts_und_zonen(cfg, heile_zone):
    """Ladeweg fuer Layouts UND die Zuordnung der Zonen — mit Migration.

    `heile_zone` ist `config_schema.heile_zone` (hereingereicht, damit dieses
    Modul nichts aus `config_schema` importieren muss — das importiert dieses).

    Reihenfolge, und warum:
      1. Layouts heilen.
      2. Je Zone: zeigt sie auf ein Layout, das es nicht gibt, zurueck auf die
         Vorgabe. Fehlt das Vorgabe-Layout `zone-<zone>`, wird es angelegt —
         und zwar AUS den alten Listen der Zone. Das ist die Migration: sie
         passiert genau einmal, beim ersten Start mit einer Konfiguration
         aus der Zeit vor den Layouts.
      3. Je Zone den Spiegel setzen. Danach stimmt beides ueberein.
    """
    layouts = heile_layouts(cfg.get("layouts"))
    for zone in ZONEN:
        cfg[zone] = heile_zone(cfg.get(zone))
        lid = cfg[zone].get("layout") or ""
        if lid and lid not in layouts:
            print(f"[Layouts] Zone {zone} zeigt auf unbekanntes Layout {lid!r} — "
                  "nehme das Zonen-Layout")
            cfg[zone]["layout"] = ""
        vorgabe = ZONEN_LAYOUT[zone]
        if vorgabe not in layouts:
            if len(layouts) >= MAX_LAYOUTS:
                # Platz schaffen: das Zonen-Layout ist unverzichtbar.
                layouts.pop(next(k for k in layouts if k not in ZONEN_LAYOUT.values()))
            layouts[vorgabe] = standard_layout(ZONEN_LAYOUT_NAMEN[zone])
        # Migration: traegt die Zone noch Listen, die im Layout nicht stehen,
        # wandern sie in dessen Hauptregion. Das trifft die alte config.json
        # (kein `layouts`-Schluessel) ebenso wie eine von Hand ergaenzte Liste.
        # Nur in eine LEERE Hauptregion: steht dort schon etwas, ist das
        # Layout die Wahrheit und der Spiegel veraltet.
        region = hauptregion(layouts[vorgabe], anlegen=True)
        if region is not None and uebernimm_spiegel(cfg[zone], region):
            print(f"[Layouts] Zone {zone}: {len(region['playlist'])} Eintraege "
                  f"ins Layout {vorgabe!r} uebernommen")
    cfg["layouts"] = layouts
    for zone in ZONEN:
        spiegle_zone(cfg, zone)
    return cfg


def schreibe_zonen_teil(cfg, zone, teil):
    """Schreibweg fuer einen geprueften Zonen-Patch (`pruefe_zone`).

    Alte Listen (`videos`, `images`, `bildzeiten`, `shuffle`, `einmal`)
    landen in der Hauptregion des Zonen-Layouts; `audio` und `layout` in der
    Zone. Das haelt den Manager und alte Skripte am Leben, die weiterhin
    `{"near": {"videos": [...]}}` schicken.
    """
    zonendaten = cfg.setdefault(zone, {})
    if "layout" in teil:
        zonendaten["layout"] = teil["layout"]
    if "audio" in teil:
        zonendaten["audio"] = list(teil["audio"])
    layout = layout_der_zone(cfg, zone)
    if layout is None:
        layout = cfg.setdefault("layouts", {})[layout_id_der_zone(cfg, zone)] = \
            standard_layout(ZONEN_LAYOUT_NAMEN.get(zone, zone))
    region = hauptregion(layout, anlegen=True)
    if region is not None:
        uebernimm_spiegel(zonendaten, region)
        if "videos" in teil or "images" in teil or "bildzeiten" in teil:
            spiegle_zone(cfg, zone)   # den Stand vor dem Patch als Basis
            videos = teil.get("videos", zonendaten.get("videos") or [])
            images = teil.get("images", zonendaten.get("images") or [])
            zeiten = teil.get("bildzeiten", zonendaten.get("bildzeiten") or {})
            region["playlist"] = playlist_aus_listen(videos, images, zeiten,
                                                     alt=region.get("playlist"))
        for schalter in ("shuffle", "einmal"):
            if schalter in teil:
                region[schalter] = bool(teil[schalter])
    spiegle_zone(cfg, zone)


def entferne_datei(cfg, media_type, name):
    """Eine Datei aus ALLEN Layouts und Zonen austragen. Loescht nichts."""
    typ = ART_ZU_TYP.get(media_type)
    entfernt = False
    for layout in (cfg.get("layouts") or {}).values():
        for region in layout.get("regionen", []):
            vorher = len(region.get("playlist", []))
            region["playlist"] = [i for i in region.get("playlist", [])
                                  if not (i.get("typ") == typ and i.get("name") == name)]
            entfernt = entfernt or len(region["playlist"]) != vorher
    if media_type == "audio":
        for zone in ZONEN:
            zonendaten = cfg.get(zone)
            if isinstance(zonendaten, dict) and name in (zonendaten.get("audio") or []):
                zonendaten["audio"] = [a for a in zonendaten["audio"] if a != name]
                entfernt = True
    for zone in ZONEN:
        spiegle_zone(cfg, zone)
    return entfernt


def filtere_layout(layout, heute):
    """Eine Kopie des Layouts ohne die Eintraege, die heute nicht gelten."""
    kopie = copy.deepcopy(layout)
    for region in kopie.get("regionen", []):
        region["playlist"] = [i for i in region.get("playlist", []) if item_gilt(i, heute)]
    return kopie


def dateien_im_layout(layout):
    """{"videos": {...}, "images": {...}, "audio": {...}} — was das Layout braucht."""
    heraus = {"videos": set(), "images": set(), "audio": set()}
    typ_zu_art = {v: k for k, v in ART_ZU_TYP.items()}
    for region in layout.get("regionen", []):
        for item in region.get("playlist", []):
            art = typ_zu_art.get(item.get("typ"))
            if art and item.get("name"):
                heraus[art].add(item["name"])
    return heraus


def hat_inhalt(layout):
    """Spielt das Layout irgendetwas — Medien oder ein Widget?"""
    for region in layout.get("regionen", []):
        if region.get("typ") == "widget":
            return True
        if region.get("playlist"):
            return True
    return False

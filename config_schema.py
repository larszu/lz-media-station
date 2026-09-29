#!/usr/bin/env python3
"""Konfigurations-Schema der LZ Media Station.

Hier stehen die Vorgaben UND die Grenzen. Beides an einer Stelle, weil beides
dieselbe Frage beantwortet: was ist ein gueltiger Wert fuer dieses Feld.

Eigenes Modul, damit `main.py` (Ladeweg) und `web_ui.py` (Schreibweg) es
teilen koennen — `main` importiert `web_ui`, ein Import zurueck waere ein
Kreis.
"""
import re

import ausloeser as ausloeser_modul
import layouts as layouts_modul
import programm as programm_modul
from zeitplan import heile_zeitplan, standard_zeitplan

#: ALLE moeglichen Zonen, von nah nach fern. "mid" ist optional und wird nur
#: benutzt, wenn `zonen_stufen` auf 3 steht — siehe `aktive_zonen`.
ZONEN = ("near", "mid", "far")

#: Klartext je Zone fuer Meldungen und Oberflaeche.
ZONEN_NAMEN = {"near": "Nah", "mid": "Mitte", "far": "Fern"}
MEDIENARTEN = ("videos", "images", "audio")

#: Sprachcodes, die als Untertitelspur erlaubt sind (ISO 639-1, zwei Buchstaben).
#: Keine Liste erlaubter Sprachen: wer Raetoromanisch braucht, soll es eintragen
#: koennen. Geprueft wird die FORM, nicht die Auswahl.
SPRACHCODE = re.compile(r"^[a-z]{2}$")

#: Grenzen fuer eine eigene Standzeit je Bild.
BILDZEIT_MIN_S = 1.0
BILDZEIT_MAX_S = 3600.0


def standard_zone():
    """Eine leere Zone mit allen Wiedergabe-Optionen.

    `shuffle`  — zufaellige Reihenfolge statt der Listenreihenfolge
    `einmal`   — einmal durchspielen statt endlos zu wiederholen
    `bildzeiten` — {Dateiname: Sekunden} fuer Bilder, die laenger oder kuerzer
                 stehen sollen als der allgemeine Bildwechsel
    `layout`   — Kennung des Layouts, das diese Zone spielt; leer = das
                 Zonen-Layout `zone-<zone>` (siehe layouts.py)

    Seit 3.0 sind `videos`, `images`, `shuffle`, `einmal` und `bildzeiten`
    ein SPIEGEL der Hauptregion dieses Layouts (`layouts.spiegle_zone`). Die
    Wahrheit steht im Layout; die Felder bleiben fuer alte Displays, alte
    Manager-Fassungen und alte Sicherungen — und werden nach jedem
    Schreibzugriff neu gesetzt. `audio` gehoert weiterhin der Zone.
    """
    return {"videos": [], "images": [], "audio": [],
            "shuffle": False, "einmal": False, "bildzeiten": {}, "layout": ""}


def heile_zone(roh):
    """Ladeweg fuer EINE Zone: reparieren statt abbrechen.

    Eine Stelle fuer beide Zonen und beide Wege. Vorher stand die
    Zonen-Normalisierung in `main.load_config` und kannte nur die drei
    Medienlisten — jede neue Option haette dort nachgezogen werden muessen,
    und ein Vergessen faellt erst auf, wenn eine gespeicherte Einstellung
    nach dem Neustart weg ist.
    """
    zone = standard_zone()
    if not isinstance(roh, dict):
        return zone
    for art in MEDIENARTEN:
        wert = roh.get(art)
        if isinstance(wert, list):
            zone[art] = [x for x in wert if isinstance(x, str) and x]
    zone["shuffle"] = bool(roh.get("shuffle", False))
    zone["einmal"] = bool(roh.get("einmal", False))
    rohzeiten = roh.get("bildzeiten")
    if isinstance(rohzeiten, dict):
        sauber = {}
        for name, sekunden in rohzeiten.items():
            if not isinstance(name, str):
                continue
            try:
                wert = float(sekunden)
            except (TypeError, ValueError):
                continue
            if BILDZEIT_MIN_S <= wert <= BILDZEIT_MAX_S:
                sauber[name] = wert
        zone["bildzeiten"] = sauber
    lid = roh.get("layout")
    if isinstance(lid, str) and (lid == "" or layouts_modul.KENNUNG.match(lid)):
        zone["layout"] = lid
    return zone


def pruefe_zone(roh):
    """Schreibweg fuer EINE Zone: ablehnen statt heilen, mit Feldnamen."""
    if not isinstance(roh, dict):
        raise ValueError("Zone muss ein Objekt sein")
    heraus = {}
    for art in MEDIENARTEN:
        if art in roh:
            if not isinstance(roh[art], list):
                raise ValueError(f"{art}: muss eine Liste sein")
            heraus[art] = [x for x in roh[art] if isinstance(x, str) and x]
    for schalter in ("shuffle", "einmal"):
        if schalter in roh:
            if not isinstance(roh[schalter], bool):
                raise ValueError(f"{schalter}: muss true oder false sein")
            heraus[schalter] = roh[schalter]
    if "bildzeiten" in roh:
        if not isinstance(roh["bildzeiten"], dict):
            raise ValueError("bildzeiten: muss ein Objekt sein")
        zeiten = {}
        for name, sekunden in roh["bildzeiten"].items():
            try:
                wert = float(sekunden)
            except (TypeError, ValueError):
                raise ValueError(f"bildzeiten.{name}: muss eine Zahl sein") from None
            if not (BILDZEIT_MIN_S <= wert <= BILDZEIT_MAX_S):
                raise ValueError(
                    f"bildzeiten.{name}: {wert} liegt ausserhalb von "
                    f"{BILDZEIT_MIN_S:.0f}..{BILDZEIT_MAX_S:.0f} s")
            zeiten[name] = wert
        heraus["bildzeiten"] = zeiten
    if "layout" in roh:
        lid = roh["layout"]
        if lid is None:
            lid = ""
        if not isinstance(lid, str) or (lid != "" and not layouts_modul.KENNUNG.match(lid)):
            raise ValueError("layout: Kennung aus a-z, 0-9 und '-' (leer = Zonen-Layout)")
        heraus["layout"] = lid
    return heraus


DEFAULT_CONFIG = {
    "system_name": "LZ Station 1",
    "threshold_m": 1.0,
    # Drei Stufen statt zwei: fern -> mitte -> nah. Vorgabe bleibt 2, damit
    # sich eine bestehende Installation exakt wie vorher verhaelt.
    "zonen_stufen": 2,
    # Obere Grenze der Mitte (nur bei drei Stufen). Muss groesser sein als
    # `threshold_m` — sonst gaebe es die Mitte rechnerisch nicht.
    "threshold_mid_m": 2.5,
    "delay_s": 1.5,
    # Welche Abstandsquelle die Station benutzt: "auto" (Vorgabe seit Issue
    # #13 — HC-SR04 am GPIO, und wenn es den nicht gibt, die Kamera),
    # "ultrasonic" (nur der HC-SR04), "camera" (Webcam + Gesichtserkennung,
    # laeuft auch auf Mac/Windows) oder "button" (GPIO-Taster: der Besucher
    # drueckt, statt dass gemessen wird). Details in docs/sensoren.md.
    #
    # "ultrasonic" bleibt und ist nicht dasselbe wie "auto": es ist die Ansage
    # „an dieser Station gehoert ein Sensor hin". Faellt er aus, soll sie
    # schweigen und es melden, statt still mit einer anderen Reichweite und
    # einem anderen Blickfeld weiterzulaufen.
    "sensor_type": "auto",
    "gpio_trigger": 23,
    "gpio_echo": 24,
    # Kamera-Quelle: welcher Kamera-Index und die kalibrierte Brennweite in
    # Pixeln (bezogen auf die interne Erkennungsbreite, siehe camera_sensor.py).
    "camera_index": 0,
    "camera_focal_px": 700.0,
    # Taster-Quelle: Pin und wie lange ein Druck als „nah" gilt.
    "button_pin": 17,
    "button_haltezeit_s": 30.0,
    "web_port": 5000,
    "image_interval_s": 5,
    "master_volume": 100,
    "video_volume": 100,
    "audio_volume": 80,
    "video_resume": False,
    # Zeitsteuerung (Wochenplan). `aktiv` ist in der Vorgabe False, damit sich
    # eine bestehende Installation exakt wie vorher verhaelt. Siehe zeitplan.py.
    "zeitplan": standard_zeitplan(),
    # Ausserhalb der Oeffnungszeiten zusaetzlich den Fernseher per HDMI-CEC
    # abschalten. Braucht `cec-client` auf dem Geraet; fehlt es, passiert
    # nichts ausser einer Zeile im Log.
    "cec_aktiv": False,
    "display_ip": "",
    # Untertitel. `sprachen` sind die am Display anwaehlbaren Codes (leer =
    # keine Umschaltung), `untertitel` ordnet je Video und Sprache eine
    # .vtt-Datei zu: {"film.mp4": {"de": "film-de.vtt"}}.
    "sprachen": [],
    "untertitel": {},
    # Gleichtakt mehrerer Stationen. "aus" (Vorgabe) wertet den eigenen Sensor
    # aus; "follower" uebernimmt die Zone von `sync_master`. Eine „master"-
    # Rolle gibt es NICHT: jede Station beantwortet /api/sync ohnehin.
    "sync_rolle": "aus",
    "sync_master": "",
    "sync_port": 5000,
    "near": standard_zone(),
    "mid": standard_zone(),
    "far": standard_zone(),
    # Layouts (seit 3.0): Regionen mit eigenen Playlists, siehe layouts.py
    # und docs/architektur-v3.md. Eine frische Station hat je Zone ein leeres
    # Vollbild-Layout — und verhaelt sich damit exakt wie vor 3.0.
    "layouts": layouts_modul.standard_layouts(),
    # Wochenprogramm, Sofortmeldung und Ausloeser (Welle 2). Alle drei sind in
    # der Vorgabe leer bzw. aus — eine Station von vor 3.0 verhaelt sich
    # exakt wie vorher. Schema: programm.py, ausloeser.py.
    "programm": programm_modul.standard_programm(),
    "meldung": programm_modul.standard_meldung(),
    "ausloeser": ausloeser_modul.standard_ausloeser(),
}


def aktive_zonen(config):
    """Die Zonen, die diese Station wirklich benutzt — von nah nach fern.

    Bei zwei Stufen ist `mid` zwar in der Konfiguration vorhanden (damit die
    Medien-Zuweisung beim Umschalten nicht verloren geht), zaehlt aber
    nirgends mit: nicht in der Zustandsmaschine und nicht in der
    Zustandspruefung. Sonst meldete eine gewoehnliche Station dauerhaft
    „Zone Mitte hat keine Medien".
    """
    if int(config.get("zonen_stufen", 2)) >= 3:
        return ("near", "mid", "far")
    return ("near", "far")


# ───────────────────────────────────────────────────────────────────────────
# Was ein Feld BEDEUTET, nicht nur wie es heisst.
#
# BEFUND (Defektformen-Sweep, Form `vertrag-nur-feldnamen`, gemessen
# 2026-09-07). `web_ui.api_config` hatte einen Vertrag — eine Tabelle aus
# FELDNAME -> Typ:
#
#     simple = { "system_name": str, "threshold_m": float, "delay_s": float,
#                "gpio_trigger": int, "gpio_echo": int, "web_port": int, ... }
#     for key, cast in simple.items():
#         if key in data:
#             try: controller.config[key] = cast(data[key])
#             except (ValueError, TypeError): pass
#
# Der Name stimmte, der Typ stimmte, und damit war die Pruefung zu Ende. Was
# durchging:
#
#   gpio_trigger: 99      -> gibt es am Pi nicht; beim naechsten Start wirft
#                            gpiozero, die Station laeuft ohne Sensor weiter
#                            und bleibt fuer immer in der Fern-Szene
#   gpio_echo == gpio_trigger -> derselbe Pin fuer Senden und Empfangen; misst
#                            nie etwas, und kein Feld fuer sich ist falsch
#   threshold_m: -5       -> `dist <= -5` ist nie wahr, die Nah-Szene ist tot
#   delay_s: -1           -> die Hysterese schaltet sofort, das Flackern, das
#                            sie verhindern soll, ist wieder da
#   web_port: 0           -> beim naechsten Start ist die Oberflaeche weg,
#                            und zwar auf einem Geraet ohne Tastatur
#   image_interval_s: 0   -> Diashow ohne Wechselpause
#   master_volume: 500    -> der Regler zeigt Unsinn an
#
# Die Station steht unbeaufsichtigt in einer Ausstellung. Jeder dieser Werte
# faellt erst beim naechsten Start auf, und dann ist niemand da.
#
# GRENZEN ist deshalb die eine Tabelle, und sie sagt beides: Typ UND Bereich.
# Sie wird an zwei Stellen mit VERSCHIEDENER Politik benutzt, und das ist
# Absicht:
#
#   * `pruefe_patch` (Schreibweg, `POST /api/config`) LEHNT AB und sagt, welches
#     Feld. Wer einen Wert setzt, soll erfahren, dass er nicht angekommen ist.
#   * `heile_config` (Ladeweg, `load_config`) REPARIERT auf die Vorgabe und
#     sagt es im Log. Eine von Hand verhunzte `config.json` darf den Start
#     nicht verhindern — ein Geraet ohne Tastatur, das nicht hochkommt, ist
#     schlimmer als eines mit einer Vorgabe.
# ───────────────────────────────────────────────────────────────────────────

#: BCM-Nummern, die am 40-poligen Pi-Header als GPIO nutzbar sind.
NUTZBARE_BCM = tuple(range(2, 28))

#: Feld -> (Typ, Pruefung, Klartext fuer die Meldung).
GRENZEN = {
    "system_name": (str, lambda v: 0 < len(v) <= 64, "1..64 Zeichen"),
    "display_ip": (str, lambda v: len(v) <= 64 and all(c.isalnum() or c in ".-" for c in v),
                   "Hostname oder IP, max. 64 Zeichen"),
    "threshold_m": (float, lambda v: 0.05 <= v <= 20.0, "0.05..20.0 m"),
    "threshold_mid_m": (float, lambda v: 0.05 <= v <= 20.0, "0.05..20.0 m"),
    "zonen_stufen": (int, lambda v: v in (2, 3), "2 oder 3"),
    "delay_s": (float, lambda v: 0.0 <= v <= 60.0, "0..60 s"),
    "sensor_type": (str, lambda v: v in ("auto", "ultrasonic", "camera", "button"),
                    "auto|ultrasonic|camera|button"),
    "gpio_trigger": (int, lambda v: v in NUTZBARE_BCM, f"BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}"),
    "gpio_echo": (int, lambda v: v in NUTZBARE_BCM, f"BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}"),
    "camera_index": (int, lambda v: 0 <= v <= 16, "0..16"),
    "camera_focal_px": (float, lambda v: 1.0 <= v <= 100000.0, "1..100000 px"),
    "button_pin": (int, lambda v: v in NUTZBARE_BCM, f"BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}"),
    "button_haltezeit_s": (float, lambda v: 1.0 <= v <= 600.0, "1..600 s"),
    "web_port": (int, lambda v: 1 <= v <= 65535, "1..65535"),
    "image_interval_s": (float, lambda v: 1.0 <= v <= 3600.0, "1..3600 s"),
    "master_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "video_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "audio_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "video_resume": (bool, lambda v: True, "true/false"),
    "cec_aktiv": (bool, lambda v: True, "true/false"),
    "sync_rolle": (str, lambda v: v in ("aus", "follower"), "aus|follower"),
    "sync_master": (str, lambda v: len(v) <= 64 and all(c.isalnum() or c in ".-" for c in v),
                    "Hostname oder IP, max. 64 Zeichen"),
    "sync_port": (int, lambda v: 1 <= v <= 65535, "1..65535"),
}


def _umwandeln(feld, roh):
    """Rohwert in den Typ des Feldes bringen. Wirft bei Unsinn."""
    typ = GRENZEN[feld][0]
    if typ is bool:
        if not isinstance(roh, bool):
            raise ValueError("muss true oder false sein")
        return roh
    if typ is not str and isinstance(roh, bool):
        # `True` ist in Python eine 1. Ein Schalter ist aber keine Portnummer.
        raise ValueError("muss eine Zahl sein")
    return typ(roh)


def pruefe_patch(daten):
    """Schreibweg: die geprueften Felder zurueck, oder ValueError mit Feldnamen.

    Geprueft wird auch das, was kein Feld fuer sich sagen kann: Trigger und
    Echo duerfen nicht derselbe Pin sein. Genau solche Bedingungen fallen
    durch, wenn ein Vertrag nur Feldnamen kennt.
    """
    if not isinstance(daten, dict):
        raise ValueError("Konfiguration muss ein Objekt sein")
    heraus = {}
    for feld, (_typ, erlaubt, klartext) in GRENZEN.items():
        if feld not in daten:
            continue
        try:
            wert = _umwandeln(feld, daten[feld])
        except (ValueError, TypeError) as e:
            raise ValueError(f"{feld}: {e}") from None
        if not erlaubt(wert):
            raise ValueError(f"{feld}: {wert!r} liegt ausserhalb von {klartext}")
        heraus[feld] = wert
    return heraus


def pruefe_pins(config, patch):
    """Trigger und Echo duerfen nicht derselbe Pin sein — auch nicht ueber
    zwei getrennte Anfragen hinweg. Deshalb gegen den ZUSAMMENGEFUEHRTEN
    Stand, nicht gegen den Patch allein."""
    trig = patch.get("gpio_trigger", config.get("gpio_trigger"))
    echo = patch.get("gpio_echo", config.get("gpio_echo"))
    if trig is not None and trig == echo:
        raise ValueError(
            f"gpio_trigger und gpio_echo sind beide BCM {trig} — "
            "derselbe Pin kann nicht senden und empfangen")
    # Und in die andere Richtung: ein Sensor-Pin darf nicht auf einen Pin
    # wandern, an dem schon ein Taster-Ausloeser haengt. Die Ausloeser-Seite
    # prueft das beim Anlegen des Tasters — hier wird es beim Verschieben des
    # Sensors geprueft, sonst verliert der Taster beim naechsten Start still.
    zusammen = dict(config or {})
    zusammen.update(patch or {})
    belegt = ausloeser_modul.belegte_pins(zusammen)
    for e in zusammen.get("ausloeser") or []:
        q = (e.get("quelle") or {}) if isinstance(e, dict) else {}
        if q.get("typ") == "taster" and q.get("pin") in belegt:
            raise ValueError(
                f"{belegt[q['pin']]}: BCM {q['pin']} gehoert schon dem "
                f"Taster-Ausloeser {e.get('id')!r}")


def pruefe_schwellen(config, patch):
    """Die Mitte muss weiter weg sein als die Nah-Schwelle.

    Wieder eine Bedingung, die KEIN Feld fuer sich sieht: `threshold_m: 3.0`
    ist gueltig, `threshold_mid_m: 2.0` ist gueltig — zusammen gibt es die
    Mitte rechnerisch nicht, und die Station spraenge von fern direkt auf nah,
    ohne dass ein Wert falsch aussieht. Geprueft wird deshalb gegen den
    ZUSAMMENGEFUEHRTEN Stand, nicht gegen den Patch allein (sonst rutscht es
    ueber zwei getrennte Anfragen durch).
    """
    stufen = int(patch.get("zonen_stufen", config.get("zonen_stufen", 2)) or 2)
    if stufen < 3:
        return
    nah = float(patch.get("threshold_m", config.get("threshold_m", 1.0)))
    mitte = float(patch.get("threshold_mid_m", config.get("threshold_mid_m", 2.5)))
    if mitte <= nah:
        raise ValueError(
            f"threshold_mid_m: {mitte} muss groesser sein als threshold_m "
            f"({nah}) — sonst gibt es die Mitte nicht")


def heile_config(cfg):
    """Ladeweg: unbrauchbare Werte auf die Vorgabe zuruecksetzen und sagen.

    KEIN Abbruch. Ein Geraet ohne Tastatur, das wegen einer verhunzten
    Konfiguration nicht hochkommt, ist schlimmer als eines, das mit der
    Vorgabe laeuft und es ins Log schreibt.
    """
    for feld, (_typ, erlaubt, klartext) in GRENZEN.items():
        if feld not in cfg:
            continue
        try:
            wert = _umwandeln(feld, cfg[feld])
            if not erlaubt(wert):
                raise ValueError(f"ausserhalb von {klartext}")
        except (ValueError, TypeError) as e:
            print(f"[Config] {feld}={cfg[feld]!r} unbrauchbar ({e}) — "
                  f"nehme Vorgabe {DEFAULT_CONFIG[feld]!r}")
            cfg[feld] = DEFAULT_CONFIG[feld]
            continue
        cfg[feld] = wert
    if cfg.get("gpio_trigger") == cfg.get("gpio_echo"):
        print(f"[Config] gpio_trigger und gpio_echo sind beide "
              f"{cfg.get('gpio_trigger')!r} — nehme die Vorgaben")
        cfg["gpio_trigger"] = DEFAULT_CONFIG["gpio_trigger"]
        cfg["gpio_echo"] = DEFAULT_CONFIG["gpio_echo"]
    # Der Zeitplan ist verschachtelt und passt nicht in die flache
    # GRENZEN-Tabelle — eigene Heilung, gleiche Politik (reparieren statt
    # abbrechen), genau wie bei den Zonen in `load_config`.
    cfg["zeitplan"] = heile_zeitplan(cfg.get("zeitplan"))
    cfg["sprachen"] = heile_sprachen(cfg.get("sprachen"))
    cfg["untertitel"] = heile_untertitel(cfg.get("untertitel"))
    # Und die Kreuzbedingung der Schwellen: liegt die Mitte nicht weiter weg
    # als die Nah-Schwelle, gibt es sie rechnerisch nicht. Beim Laden wird das
    # repariert statt abgebrochen (Politik wie oben).
    try:
        pruefe_schwellen(cfg, {})
    except ValueError as e:
        print(f"[Config] {e} — nehme die Vorgaben fuer beide Schwellen")
        cfg["threshold_m"] = DEFAULT_CONFIG["threshold_m"]
        cfg["threshold_mid_m"] = DEFAULT_CONFIG["threshold_mid_m"]
    # Layouts und die Zuordnung der Zonen — samt der einmaligen Migration
    # alter Zonenlisten ins Zonen-Layout. Danach stimmen Layout und Spiegel
    # ueberein.
    layouts_modul.heile_layouts_und_zonen(cfg, heile_zone)
    # Wochenprogramm, Sofortmeldung, Ausloeser: eintragsweise heilen (Welle 2).
    cfg["programm"] = programm_modul.heile_programm(cfg.get("programm"))
    cfg["meldung"] = programm_modul.heile_meldung(cfg.get("meldung"))
    cfg["ausloeser"] = ausloeser_modul.heile_ausloeser(cfg.get("ausloeser"), cfg)
    return cfg


def pruefe_sprachen(roh):
    """Schreibweg: die Liste der am Display anwaehlbaren Sprachcodes.

    Geprueft wird die FORM (zwei Kleinbuchstaben, ISO 639-1), nicht eine
    Auswahl erlaubter Sprachen — wer Raetoromanisch braucht, soll es eintragen
    koennen, ohne dass jemand die Liste pflegen muss.
    """
    if not isinstance(roh, list):
        raise ValueError("sprachen: muss eine Liste sein")
    heraus = []
    for code in roh:
        if not isinstance(code, str) or not SPRACHCODE.match(code):
            raise ValueError(
                f"sprachen: {code!r} ist kein Sprachcode aus zwei "
                "Kleinbuchstaben (z. B. 'de', 'en')")
        if code not in heraus:      # doppelte Knoepfe waeren nur verwirrend
            heraus.append(code)
    return heraus


def heile_sprachen(roh):
    """Ladeweg: alles Unbrauchbare stillschweigend weglassen."""
    if not isinstance(roh, list):
        return []
    heraus = []
    for code in roh:
        if isinstance(code, str) and SPRACHCODE.match(code) and code not in heraus:
            heraus.append(code)
    return heraus


def pruefe_untertitel(roh):
    """Schreibweg: {Video: {Sprachcode: .vtt-Datei}}.

    Ein leerer Dateiname loescht die Zuordnung — sonst gaebe es keinen Weg,
    eine falsch gesetzte Spur wieder zu entfernen.
    """
    if not isinstance(roh, dict):
        raise ValueError("untertitel: muss ein Objekt sein")
    heraus = {}
    for video, spuren in roh.items():
        if not isinstance(video, str) or not video:
            raise ValueError("untertitel: Videoname fehlt")
        if not isinstance(spuren, dict):
            raise ValueError(f"untertitel.{video}: muss ein Objekt sein")
        sauber = {}
        for code, datei in spuren.items():
            if not isinstance(code, str) or not SPRACHCODE.match(code):
                raise ValueError(f"untertitel.{video}: {code!r} ist kein Sprachcode")
            if not datei:
                continue
            if not isinstance(datei, str) or not datei.lower().endswith(".vtt"):
                raise ValueError(
                    f"untertitel.{video}.{code}: Browser spielen nur WebVTT "
                    "(.vtt) ab")
            sauber[code] = datei
        if sauber:
            heraus[video] = sauber
    return heraus


def heile_untertitel(roh):
    """Ladeweg: reparieren statt abbrechen — und zwar EINTRAGSWEISE.

    Nicht ueber `pruefe_untertitel` mit einem try/except drumherum: dann
    wuerfe ein einziger falscher Eintrag alle anderen mit weg. Wer zehn Videos
    untertitelt hat und bei einem eine `.srt` erwischt, soll neun behalten.
    (Dieselbe Politik wie bei den Bildzeiten in `heile_zone`.)
    """
    if not isinstance(roh, dict):
        return {}
    heraus = {}
    for video, spuren in roh.items():
        if not isinstance(video, str) or not video or not isinstance(spuren, dict):
            continue
        sauber = {}
        for code, datei in spuren.items():
            if (isinstance(code, str) and SPRACHCODE.match(code)
                    and isinstance(datei, str) and datei.lower().endswith(".vtt")):
                sauber[code] = datei
        if sauber:
            heraus[video] = sauber
    return heraus

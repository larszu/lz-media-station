#!/usr/bin/env python3
"""Konfigurations-Schema der LZ Media Station.

Hier stehen die Vorgaben UND die Grenzen. Beides an einer Stelle, weil beides
dieselbe Frage beantwortet: was ist ein gueltiger Wert fuer dieses Feld.

Eigenes Modul, damit `main.py` (Ladeweg) und `web_ui.py` (Schreibweg) es
teilen koennen — `main` importiert `web_ui`, ein Import zurueck waere ein
Kreis.
"""
from zeitplan import heile_zeitplan, standard_zeitplan

#: Die beiden Zonen und die Medienarten darin.
ZONEN = ("near", "far")
MEDIENARTEN = ("videos", "images", "audio")

#: Grenzen fuer eine eigene Standzeit je Bild.
BILDZEIT_MIN_S = 1.0
BILDZEIT_MAX_S = 3600.0


def standard_zone():
    """Eine leere Zone mit allen Wiedergabe-Optionen.

    `shuffle`  — zufaellige Reihenfolge statt der Listenreihenfolge
    `einmal`   — einmal durchspielen statt endlos zu wiederholen
    `bildzeiten` — {Dateiname: Sekunden} fuer Bilder, die laenger oder kuerzer
                 stehen sollen als der allgemeine Bildwechsel
    """
    return {"videos": [], "images": [], "audio": [],
            "shuffle": False, "einmal": False, "bildzeiten": {}}


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
    return heraus


DEFAULT_CONFIG = {
    "system_name": "LZ Station 1",
    "threshold_m": 1.0,
    "delay_s": 1.5,
    # Welche Abstandsquelle die Station benutzt: "ultrasonic" (HC-SR04 am GPIO,
    # Vorgabe) oder "camera" (Webcam + Gesichtserkennung, laeuft auch auf
    # Mac/Windows). Details in docs/sensoren.md.
    "sensor_type": "ultrasonic",
    "gpio_trigger": 23,
    "gpio_echo": 24,
    # Kamera-Quelle: welcher Kamera-Index und die kalibrierte Brennweite in
    # Pixeln (bezogen auf die interne Erkennungsbreite, siehe camera_sensor.py).
    "camera_index": 0,
    "camera_focal_px": 700.0,
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
    "near": standard_zone(),
    "far": standard_zone(),
}


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
    "delay_s": (float, lambda v: 0.0 <= v <= 60.0, "0..60 s"),
    "sensor_type": (str, lambda v: v in ("ultrasonic", "camera"), "ultrasonic|camera"),
    "gpio_trigger": (int, lambda v: v in NUTZBARE_BCM, f"BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}"),
    "gpio_echo": (int, lambda v: v in NUTZBARE_BCM, f"BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}"),
    "camera_index": (int, lambda v: 0 <= v <= 16, "0..16"),
    "camera_focal_px": (float, lambda v: 1.0 <= v <= 100000.0, "1..100000 px"),
    "web_port": (int, lambda v: 1 <= v <= 65535, "1..65535"),
    "image_interval_s": (float, lambda v: 1.0 <= v <= 3600.0, "1..3600 s"),
    "master_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "video_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "audio_volume": (int, lambda v: 0 <= v <= 100, "0..100 %"),
    "video_resume": (bool, lambda v: True, "true/false"),
    "cec_aktiv": (bool, lambda v: True, "true/false"),
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
    return cfg

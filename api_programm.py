#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer Wochenprogramm und Sofortmeldung.

`/api/programm`           GET/PUT  das ganze Programm (Eintraege + Ausnahmen)
`/api/programm/jetzt`     GET      je Zone: welches Layout, woher
`/api/programm/vorschau`  GET      ?von=&bis=[&zone=][&raster=] — Abschnitte
`/api/meldung`            GET/POST/DELETE  die Sofortmeldung

Ein `api_*.py`-Modul (siehe api_layouts.py). Beim Registrieren haengt es sich
in den Kern: die Programm-Regel in `controller.layout_regeln` (welches Layout
die Zone jetzt spielt) und die Meldung in `controller.szene_zusatz` (die
Anzeige bekommt sie mit jeder Szene). `web_ui.py` und `main.py` kennen dieses
Modul nicht.
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

import programm as P
from config_schema import aktive_zonen


def erzeuge_blueprint(controller):
    bp = Blueprint("programm", __name__)

    def config():
        return controller.config

    def layouts():
        return config().get("layouts") or {}

    # -- In den Kern einhaengen -------------------------------------------
    if hasattr(controller, "layout_regeln"):
        if not any(getattr(r, "__name__", "") == "programm" for r in controller.layout_regeln):
            controller.layout_regeln.append(P.regel(config))
    if hasattr(controller, "szene_zusatz"):
        def meldung_zusatz(jetzt):
            return {"meldung": P.meldung_fuer_szene(config().get("meldung"), jetzt)}
        meldung_zusatz.__name__ = "meldung"
        if not any(getattr(z, "__name__", "") == "meldung" for z in controller.szene_zusatz):
            controller.szene_zusatz.append(meldung_zusatz)

    def schreibe(aenderung):
        with controller.lock:
            ergebnis = aenderung()
            controller.save_config()
        if hasattr(controller, "melde_config"):
            controller.melde_config()
        return ergebnis

    # -- Programm ------------------------------------------------------------

    @bp.route("/api/programm")
    def api_programm():
        return jsonify(config().get("programm") or P.standard_programm())

    @bp.route("/api/programm", methods=["PUT"])
    def api_programm_setzen():
        """Das ganze Programm ersetzen. Lehnt ab und nennt das Feld — auch
        ein Layout, das es nicht gibt: ein Eintrag, der ins Leere zeigt,
        faellt sonst erst auf, wenn der Schirm zur geplanten Zeit schwarz
        bleibt."""
        try:
            neu = P.pruefe_programm(request.get_json(silent=True))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        for i, e in enumerate(neu["eintraege"]):
            if e["layout_id"] not in layouts():
                return jsonify({"error": f"programm.eintraege[{i}].layout_id: "
                                         f"Layout {e['layout_id']!r} gibt es nicht"}), 400
        for i, a in enumerate(neu["ausnahmen"]):
            if a["layout_id"] and a["layout_id"] not in layouts():
                return jsonify({"error": f"programm.ausnahmen[{i}].layout_id: "
                                         f"Layout {a['layout_id']!r} gibt es nicht"}), 400

        def setzen():
            config()["programm"] = neu
            return neu

        return jsonify({"ok": True, "programm": schreibe(setzen)})

    @bp.route("/api/programm/jetzt")
    def api_programm_jetzt():
        jetzt = datetime.now()
        heraus = {}
        for zone in aktive_zonen(config()):
            lid, quelle, eintrag = P.aufloesen(config().get("programm"), zone, jetzt)
            gespielt = controller.layout_fuer_zone(zone, jetzt) if hasattr(controller, "layout_fuer_zone") else lid
            heraus[zone] = {
                "layout_id": gespielt,
                "layout_name": (layouts().get(gespielt) or {}).get("name"),
                "quelle": quelle if (lid is None or lid in layouts()) else "zone",
                "eintrag": eintrag,
            }
        return jsonify({"zeit": jetzt.isoformat(timespec="minutes"), "zonen": heraus})

    @bp.route("/api/programm/vorschau")
    def api_programm_vorschau():
        """Aufloesung ueber einen Zeitraum, fuer die Kalenderansicht."""
        try:
            von = datetime.fromisoformat(request.args["von"]) if request.args.get("von") else None
            bis = datetime.fromisoformat(request.args["bis"]) if request.args.get("bis") else None
        except (ValueError, KeyError):
            return jsonify({"error": "von/bis: Zeitpunkt als JJJJ-MM-TTTHH:MM"}), 400
        jetzt = datetime.now()
        if von is None:
            von = datetime(jetzt.year, jetzt.month, jetzt.day) - timedelta(days=jetzt.weekday())
        if bis is None:
            bis = von + timedelta(days=7)
        zone = request.args.get("zone") or aktive_zonen(config())[0]
        if zone not in P.ZONEN:
            return jsonify({"error": f"zone: {'|'.join(P.ZONEN)}"}), 400
        try:
            schritt = int(request.args.get("raster", P.RASTER_MIN))
        except ValueError:
            return jsonify({"error": "raster: Minuten als ganze Zahl"}), 400
        if not (1 <= schritt <= 240):
            return jsonify({"error": "raster: 1..240 Minuten"}), 400
        return jsonify({"zone": zone, "von": von.isoformat(timespec="minutes"),
                        "bis": bis.isoformat(timespec="minutes"),
                        "abschnitte": P.raster(config().get("programm"), zone, von, bis, schritt)})

    # -- Sofortmeldung -------------------------------------------------------

    def meldung_setzen(daten, jetzt=None):
        """Setzen UND melden: Befehl an die Anzeigen (sofort, auch waehrend
        einer Ueberblendung) plus `config`/`scene`. Wird auch vom Modul
        `ausloeser` gerufen."""
        jetzt = jetzt or datetime.now()
        neu = P.pruefe_meldung(daten, jetzt)

        def setzen():
            config()["meldung"] = neu
            return neu

        schreibe(setzen)
        controller.bus.senden("befehl", dict({"typ": "meldung"}, **P.meldung_fuer_szene(neu, jetzt)))
        return neu

    controller.meldung_setzen = meldung_setzen

    @bp.route("/api/meldung")
    def api_meldung():
        return jsonify(P.meldung_fuer_szene(config().get("meldung"), datetime.now()))

    @bp.route("/api/meldung", methods=["POST"])
    def api_meldung_setzen():
        daten = request.get_json(silent=True)
        if not isinstance(daten, dict):
            return jsonify({"error": "meldung: muss ein Objekt sein"}), 400
        daten.setdefault("aktiv", True)
        try:
            neu = meldung_setzen(daten)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "meldung": neu, "empfaenger": controller.bus.anzahl})

    @bp.route("/api/meldung", methods=["DELETE"])
    def api_meldung_beenden():
        alt = dict(config().get("meldung") or P.standard_meldung())
        alt["aktiv"] = False
        alt["dauer_s"] = None
        alt["bis"] = None
        neu = meldung_setzen(alt)
        return jsonify({"ok": True, "meldung": neu})

    return bp

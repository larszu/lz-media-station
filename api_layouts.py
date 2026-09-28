#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer Layouts (`/api/layouts…`).

Ein `api_*.py`-Modul: `web_ui.create_app` findet es im Wurzelverzeichnis und
registriert `erzeuge_blueprint(controller)` von selbst — so kommt Welle 2 mit
weiteren Modulen dazu, ohne dass `web_ui.py` angefasst wird.

Politik wie ueberall: ABLEHNEN und das Feld nennen (`layouts.pruefe_*`); der
Ladeweg (`layouts.heile_*`) gehoert zu `config_schema.heile_config`. Nach jedem
Schreibzugriff werden die Zonen gespiegelt, gespeichert und die Ereignisse
`config` + `scene` geschickt — die Anzeige zeigt die Aenderung sofort.
"""
import copy

from flask import Blueprint, jsonify, request

import layouts as L


def erzeuge_blueprint(controller):
    bp = Blueprint("layouts", __name__)

    def tabelle():
        return controller.config.setdefault("layouts", {})

    def antwort_liste():
        return {
            "layouts": tabelle(),
            # Welche Zone spielt welches Layout — AUFGELOEST (leer = Zonen-Layout).
            "zonen": {z: L.layout_id_der_zone(controller.config, z) for z in L.ZONEN},
        }

    def schreibe(aenderung):
        """Eine Aenderung unter dem Schloss ausfuehren, spiegeln, speichern, melden."""
        with controller.lock:
            ergebnis = aenderung()
            for zone in L.ZONEN:
                L.spiegle_zone(controller.config, zone)
            controller.save_config()
        if hasattr(controller, "melde_config"):
            controller.melde_config()
        return ergebnis

    @bp.route("/api/layouts")
    def api_layouts_liste():
        return jsonify(antwort_liste())

    @bp.route("/api/layouts/vorlagen")
    def api_layouts_vorlagen():
        return jsonify([
            {"id": v, "beschreibung": L.VORLAGEN_INFO[v],
             "regionen": len(L.vorlage_regionen(v))}
            for v in L.VORLAGEN
        ])

    @bp.route("/api/layouts", methods=["POST"])
    def api_layouts_anlegen():
        """{name, vorlage?, id?} — die Kennung entsteht sonst aus dem Namen."""
        daten = request.get_json(silent=True) or {}
        name = daten.get("name")
        if not isinstance(name, str) or not (0 < len(name.strip()) <= L.NAME_MAX):
            return jsonify({"error": f"name: 1..{L.NAME_MAX} Zeichen"}), 400
        vorlage = daten.get("vorlage", "vollbild")
        if vorlage not in L.VORLAGEN:
            return jsonify({"error": f"vorlage: {'|'.join(L.VORLAGEN)}"}), 400
        if len(tabelle()) >= L.MAX_LAYOUTS:
            return jsonify({"error": f"Hoechstens {L.MAX_LAYOUTS} Layouts"}), 409
        lid = daten.get("id")
        if lid is not None:
            if not isinstance(lid, str) or not L.KENNUNG.match(lid):
                return jsonify({"error": "id: a-z, 0-9 und '-', 1..40 Zeichen"}), 400
            if lid in tabelle():
                return jsonify({"error": f"Layout {lid!r} gibt es schon"}), 409
        else:
            lid = L.kennung_aus_name(name, vergeben=tabelle())

        def anlegen():
            tabelle()[lid] = L.standard_layout(name.strip(), vorlage)
            return tabelle()[lid]

        layout = schreibe(anlegen)
        return jsonify({"ok": True, "id": lid, "layout": layout}), 201

    @bp.route("/api/layouts/<lid>")
    def api_layout(lid):
        layout = tabelle().get(lid)
        if layout is None:
            return jsonify({"error": f"Layout {lid!r} gibt es nicht"}), 404
        return jsonify({"id": lid, "layout": layout,
                        "zonen": L.zonen_mit_layout(controller.config, lid)})

    @bp.route("/api/layouts/<lid>", methods=["PUT"])
    def api_layout_ersetzen(lid):
        """Das ganze Layout ersetzen — Regionen, Playlists, Farbe, Name."""
        if lid not in tabelle():
            return jsonify({"error": f"Layout {lid!r} gibt es nicht"}), 404
        try:
            neu = L.pruefe_layout(request.get_json(silent=True))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        def ersetzen():
            tabelle()[lid] = neu
            return neu

        return jsonify({"ok": True, "id": lid, "layout": schreibe(ersetzen)})

    @bp.route("/api/layouts/<lid>", methods=["DELETE"])
    def api_layout_loeschen(lid):
        if lid not in tabelle():
            return jsonify({"error": f"Layout {lid!r} gibt es nicht"}), 404
        # Ein Layout, das eine Zone spielt, laesst sich nicht loeschen — auch
        # nicht das unausgesprochene Zonen-Layout. Erst die Zone umhaengen.
        nutzer = L.zonen_mit_layout(controller.config, lid)
        if nutzer:
            return jsonify({"error": f"Layout {lid!r} wird von Zone "
                                     f"{', '.join(nutzer)} gespielt",
                            "zonen": nutzer}), 409

        def loeschen():
            return tabelle().pop(lid)

        schreibe(loeschen)
        return jsonify({"ok": True, "id": lid})

    @bp.route("/api/layouts/<lid>/duplizieren", methods=["POST"])
    def api_layout_duplizieren(lid):
        """{name?, id?} — eine Kopie, standardmaessig „<Name> (Kopie)"."""
        quelle = tabelle().get(lid)
        if quelle is None:
            return jsonify({"error": f"Layout {lid!r} gibt es nicht"}), 404
        if len(tabelle()) >= L.MAX_LAYOUTS:
            return jsonify({"error": f"Hoechstens {L.MAX_LAYOUTS} Layouts"}), 409
        daten = request.get_json(silent=True) or {}
        name = daten.get("name") or (quelle["name"] + " (Kopie)")
        if not isinstance(name, str) or not (0 < len(name.strip()) <= L.NAME_MAX):
            return jsonify({"error": f"name: 1..{L.NAME_MAX} Zeichen"}), 400
        neu_id = daten.get("id")
        if neu_id is not None:
            if not isinstance(neu_id, str) or not L.KENNUNG.match(neu_id):
                return jsonify({"error": "id: a-z, 0-9 und '-', 1..40 Zeichen"}), 400
            if neu_id in tabelle():
                return jsonify({"error": f"Layout {neu_id!r} gibt es schon"}), 409
        else:
            neu_id = L.kennung_aus_name(name, vergeben=tabelle())

        def kopieren():
            kopie = copy.deepcopy(quelle)
            kopie["name"] = name.strip()[:L.NAME_MAX]
            tabelle()[neu_id] = kopie
            return kopie

        return jsonify({"ok": True, "id": neu_id, "layout": schreibe(kopieren)}), 201

    return bp

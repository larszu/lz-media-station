#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer Ausloeser.

`/api/ausloeser`             GET/PUT   die ganze Liste
`/api/ausloeser/protokoll`   GET       die letzten Ausloesungen (im Speicher)
`/api/ausloeser/<id>/test`   POST      von Hand ausloesen
`/api/trigger/<id>`          POST      der Webhook (Token per `X-LZ-Token`
                                       oder `?token=`), fuer Home Assistant,
                                       Node-RED, einen Taster mit WLAN …
`/api/trigger/_video_ende`   POST      {datei, region} — von der Anzeige

Ein `api_*.py`-Modul (siehe api_layouts.py). Beim Registrieren startet es die
Maschine (`ausloeser.Ausloeser`, eigener Faden fuer Zeit und Zonenwechsel) und
haengt `schwarz` und `ausloeser_video_ende` an die Szene — die Anzeige weiss
so, ob sie schwarz sein soll und ob sie Video-Enden melden muss.
"""
from flask import Blueprint, jsonify, request

import ausloeser as A


def erzeuge_blueprint(controller):
    bp = Blueprint("ausloeser", __name__)

    def config():
        return controller.config

    # Sofortmeldungen gehoeren dem Programm-Modul; ist es (noch) nicht
    # registriert, holt die Maschine die Funktion beim ersten Aufruf.
    def meldung_setzen(aktion):
        fn = getattr(controller, "meldung_setzen", None)
        if fn is None:
            raise RuntimeError("Sofortmeldung nicht verfuegbar (api_programm fehlt)")
        fn(dict(aktion, aktiv=True))

    maschine = A.Ausloeser(controller, meldung_setzen=meldung_setzen)
    controller.ausloeser = maschine
    if hasattr(controller, "szene_zusatz"):
        def zusatz(jetzt):
            return {"schwarz": maschine.schwarz,
                    "ausloeser_video_ende": maschine.hat_quelle("video_ende")}
        zusatz.__name__ = "ausloeser"
        if not any(getattr(z, "__name__", "") == "ausloeser" for z in controller.szene_zusatz):
            controller.szene_zusatz.append(zusatz)
    # Im Test (Flask-Testclient) laeuft kein Faden — `tick()` wird dort direkt
    # gerufen. Auf der Station startet `main()` die App und damit den Faden.
    if getattr(controller, "ausloeser_faden", True):
        maschine.start()

    def schreibe(aenderung):
        with controller.lock:
            ergebnis = aenderung()
            controller.save_config()
        maschine.synchronisiere_taster()
        if hasattr(controller, "melde_config"):
            controller.melde_config()
        return ergebnis

    def mit_status(liste):
        heraus = []
        for e in liste:
            e = dict(e)
            q = e.get("quelle") or {}
            if q.get("typ") == "taster":
                e["status"] = maschine.taster_status.get(q.get("pin"), "")
            heraus.append(e)
        return heraus

    @bp.route("/api/ausloeser")
    def api_ausloeser():
        return jsonify({"ausloeser": mit_status(maschine.liste()),
                        "belegte_pins": {str(k): v for k, v in A.belegte_pins(config()).items()},
                        "gpio": maschine._fabrik() is not None})

    @bp.route("/api/ausloeser", methods=["PUT"])
    def api_ausloeser_setzen():
        try:
            neu = A.pruefe_ausloeser(request.get_json(silent=True), config())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        layouts = config().get("layouts") or {}
        for i, e in enumerate(neu):
            a = e["aktion"]
            if a["typ"] == "zeige_layout" and a["layout_id"] not in layouts:
                return jsonify({"error": f"ausloeser[{i}].aktion.layout_id: "
                                         f"Layout {a['layout_id']!r} gibt es nicht"}), 400

        def setzen():
            config()["ausloeser"] = neu
            return neu

        return jsonify({"ok": True, "ausloeser": mit_status(schreibe(setzen))})

    @bp.route("/api/ausloeser/protokoll")
    def api_ausloeser_protokoll():
        return jsonify(maschine.protokoll())

    @bp.route("/api/ausloeser/<aid>/test", methods=["POST"])
    def api_ausloeser_test(aid):
        if maschine.eintrag(aid) is None:
            return jsonify({"error": f"Ausloeser {aid!r} gibt es nicht"}), 404
        return jsonify({"ok": True, "ergebnis": maschine.feuere(aid, "Test")})

    @bp.route("/api/trigger/<aid>", methods=["POST"])
    def api_trigger(aid):
        if aid == "_video_ende":
            daten = request.get_json(silent=True) or {}
            gefeuert = maschine.video_ende(str(daten.get("datei") or ""), str(daten.get("region") or ""))
            return jsonify({"ok": True, "ausgeloest": gefeuert})
        token = request.headers.get("X-LZ-Token") or request.args.get("token") or ""
        if not token:
            daten = request.get_json(silent=True) or {}
            token = str(daten.get("token") or "")
        status, meldung = maschine.webhook(aid, token)
        if status != 200:
            return jsonify({"error": meldung}), status
        return jsonify({"ok": True, "ergebnis": meldung})

    return bp

#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer den Multicast-Kanal (`/api/multicast…`).

Die Protokollarbeit steht in `multicast.py`. Vorgaben kommen aus dem
optionalen Config-Abschnitt `multicast` (gruppe, port, name, ttl, sap,
tsid, pid_video, pid_audio); der Body von `/start` schlaegt sie.
"""
import ipaddress
import os

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

import multicast
from api_cast import _aktuelle_datei
from web_ui import MEDIA_DIRS

VORGABE = {"gruppe": "239.10.10.211", "port": 1000, "name": "LZ Media Station",
           "ttl": 16, "sap": True, "tsid": 1234, "pid_video": 168, "pid_audio": 170}


def erzeuge_blueprint(controller):
    bp = Blueprint("multicast", __name__)
    zustand = {"kanal": None}

    @bp.route("/api/multicast/start", methods=["POST"])
    def mc_start():
        daten = request.get_json(silent=True) or {}
        cfg = {**VORGABE, **(controller.config.get("multicast") or {}), **daten}
        try:
            if not ipaddress.ip_address(cfg["gruppe"]).is_multicast:
                raise ValueError
        except ValueError:
            return jsonify({"error": "gruppe: Multicast-Adresse (224.0.0.0/4)"}), 400

        datei = daten.get("datei")
        media_type = "videos"
        if not datei:
            media_type, datei = _aktuelle_datei(controller.get_scene())
            if media_type != "videos" or not datei:
                return jsonify({"error": "Es laeuft kein Video und keine datei angegeben"}), 409
        pfad = os.path.join(MEDIA_DIRS["videos"], secure_filename(datei))

        if zustand["kanal"]:
            zustand["kanal"].stop()
        kanal = multicast.Kanal(
            pfad, cfg["gruppe"], int(cfg["port"]), str(cfg["name"]),
            ttl=int(cfg["ttl"]), sap=bool(cfg["sap"]), tsid=int(cfg["tsid"]),
            pid_video=int(cfg["pid_video"]), pid_audio=int(cfg["pid_audio"]))
        try:
            kanal.start()
        except (RuntimeError, FileNotFoundError) as e:
            return jsonify({"error": str(e)}), 502
        zustand["kanal"] = kanal
        return jsonify(kanal.status())

    @bp.route("/api/multicast/stop", methods=["POST"])
    def mc_stop():
        if zustand["kanal"]:
            zustand["kanal"].stop()
            zustand["kanal"] = None
        return jsonify({"ok": True})

    @bp.route("/api/multicast/status")
    def mc_status():
        k = zustand["kanal"]
        return jsonify(k.status() if k else {"laeuft": False})

    return bp

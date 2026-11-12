#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer den Multicast-Kanal (`/api/multicast…`).

Zwei Modi:
- `anzeige` (Vorgabe): die komplette Anzeige — Layouts, Wochenprogramm,
  Widgets, Speiseplan — wird gerendert und als Kanal gesendet (Linux).
- `datei`: ein Video unveraendert in Endlosschleife (wie die VLC-Zeile).

Die Protokollarbeit steht in `multicast.py`. Vorgaben kommen aus dem
optionalen Config-Abschnitt `multicast` (modus, gruppe, port, name, ttl,
sap, tsid, pid_video, pid_audio, breite, hoehe, fps, bitrate_k, sprache);
der Body von `/start` schlaegt sie.
"""
import os
import threading
import time

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

import multicast
from config_schema import DEFAULT_CONFIG, pruefe_multicast
from api_cast import _aktuelle_datei
from web_ui import MEDIA_DIRS

VORGABE = DEFAULT_CONFIG["multicast"]

#: So lange wartet der Autostart, bis der Webserver die Anzeige ausliefert.
AUTOSTART_S = 8


def erzeuge_blueprint(controller):
    bp = Blueprint("multicast", __name__)
    zustand = {"kanal": None}
    sperre = threading.Lock()

    def starte(daten):
        """Kanal (neu) starten -> (Antwort, HTTP-Code)."""
        datei = daten.pop("datei", None)
        try:
            cfg = pruefe_multicast({**VORGABE, **(controller.config.get("multicast") or {}), **daten})
        except ValueError as e:
            return {"error": str(e)}, 400

        gemeinsam = dict(ttl=cfg["ttl"], sap=cfg["sap"], tsid=cfg["tsid"],
                         pid_video=cfg["pid_video"], pid_audio=cfg["pid_audio"])
        if cfg["modus"] == "anzeige":
            port_web = controller.config.get("web_port", 5000)
            # `kanal=1`: puls.js meldet diesen Browser fest als Anzeige
            # `kanal` statt unter einer zufaelligen Tab-Kennung (#51).
            url = f"http://127.0.0.1:{port_web}/display?lang={cfg['sprache']}&kanal=1"
            kanal = multicast.AnzeigeKanal(
                url, cfg["gruppe"], cfg["port"], cfg["name"], breite=cfg["breite"],
                hoehe=cfg["hoehe"], fps=cfg["fps"], bitrate_k=cfg["bitrate_k"], **gemeinsam)
        else:
            if not datei:
                media_type, datei = _aktuelle_datei(controller.get_scene())
                if media_type != "videos" or not datei:
                    return {"error": "Es laeuft kein Video und keine Datei gewaehlt"}, 409
            pfad = os.path.join(MEDIA_DIRS["videos"], secure_filename(datei))
            kanal = multicast.Kanal(pfad, cfg["gruppe"], cfg["port"], cfg["name"], **gemeinsam)

        with sperre:
            if zustand["kanal"]:
                zustand["kanal"].stop()
                zustand["kanal"] = None
            try:
                kanal.start()
            except (RuntimeError, FileNotFoundError) as e:
                kanal.stop()
                return {"error": str(e)}, 502
            zustand["kanal"] = kanal
        return kanal.status(), 200

    def autostart():
        time.sleep(AUTOSTART_S)
        antwort, code = starte({})
        print(f"[Multicast] Autostart: {antwort.get('error') or antwort.get('url')}")

    if (controller.config.get("multicast") or {}).get("aktiv"):
        threading.Thread(target=autostart, daemon=True).start()

    @bp.route("/api/multicast/start", methods=["POST"])
    def mc_start():
        antwort, code = starte(dict(request.get_json(silent=True) or {}))
        return jsonify(antwort), code

    @bp.route("/api/multicast/stop", methods=["POST"])
    def mc_stop():
        with sperre:
            if zustand["kanal"]:
                zustand["kanal"].stop()
                zustand["kanal"] = None
        return jsonify({"ok": True})

    @bp.route("/api/multicast/status")
    def mc_status():
        k = zustand["kanal"]
        return jsonify(k.status() if k else {"laeuft": False})

    return bp

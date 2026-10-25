#!/usr/bin/env python3
"""HTTP-Schnittstelle fuer den Chromecast als Ausgabeziel (`/api/cast…`).

Spiegelt, was `/api/displays…` fuer lokale Schirme tut (siehe `displays.py`),
nur fuer einen Chromecast im Netz: suchen, die laufende Datei (oder die ganze
Anzeige-Seite) hinwerfen, stoppen. Die eigentliche Protokollarbeit steht in
`chromecast.py`; hier ist nur der Weg von der Oberflaeche dorthin.

WARUM „die laufende Datei" und nicht „die Anzeige-Seite" als Normalfall:
Der Standard-Empfaenger des Chromecast kann nur Medien, keine beliebige
Webseite. Ein Video/Bild geht also direkt. Die ganze `/display`-Seite braucht
einen eigenen, registrierten Web-Receiver (App-ID in `cast.app_id`); ist die
gesetzt, kann `modus="anzeige"` die Seite casten — sonst bleibt es bei Medien
und sagt das.

Registrierung erfolgt wie bei allen `api_*.py` automatisch (`web_ui`): dieses
Modul liefert `erzeuge_blueprint(controller)`, mehr braucht es nicht.
"""
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

import chromecast
from web_ui import lan_adresse


def _host(controller):
    """Die Adresse, unter der der Chromecast die Station erreicht.

    Dieselbe Logik wie `/api/status`: eine in der Config gesetzte
    `display_ip` schlaegt die Messung — fuer Aufbauten mit mehreren
    Schnittstellen, wo die automatische Wahl danebenliegen kann. NIE
    `127.0.0.1`: der Chromecast ist ein anderes Geraet und wuerde bei sich
    selbst anklopfen.
    """
    cfg_ip = (controller.config.get("display_ip") or "").strip()
    port = controller.config.get("web_port", 5000)
    return (cfg_ip or lan_adresse()), port


def _aktuelle_datei(scene):
    """Aus einer Szene die erste spielbare Datei ziehen: (media_type, name).

    Erst Videos (der Normalfall einer Station), dann Bilder. Sucht in der
    aktiven Zone — zuerst in deren alter `videos`/`images`-Liste, dann in den
    Playlists der Layout-Regionen. Gibt (None, None), wenn nichts da ist.
    """
    zone = scene.get("zone")
    zonendaten = scene.get(zone) if zone else None
    if isinstance(zonendaten, dict):
        for name in zonendaten.get("videos") or []:
            return "videos", name
    layout = scene.get("layout") or {}
    for region in layout.get("regionen", []):
        for item in region.get("playlist", []):
            if item.get("typ") == "video" and item.get("name"):
                return "videos", item["name"]
    if isinstance(zonendaten, dict):
        for name in zonendaten.get("images") or []:
            return "images", name
    for region in layout.get("regionen", []):
        for item in region.get("playlist", []):
            if item.get("typ") == "image" and item.get("name"):
                return "images", item["name"]
    return None, None


#: Datei-Endung -> MIME-Typ. Der Chromecast braucht einen passenden
#: contentType, sonst lehnt der Empfaenger ab. Klein gehalten auf das, was
#: die Station wirklich ausliefert.
_MIME = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
    ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".wav": "audio/wav",
}


def _mime(name):
    punkt = name.rfind(".")
    return _MIME.get(name[punkt:].lower(), "video/mp4") if punkt >= 0 else "video/mp4"


def erzeuge_blueprint(controller):
    bp = Blueprint("cast", __name__)

    @bp.route("/api/cast/geraete")
    def cast_geraete():
        """Chromecasts im Netz suchen. Immer 200 — eine leere Liste mit
        Hinweis ist kein Fehler, nur „nichts gefunden"."""
        liste, meldung = chromecast.finde_geraete()
        return jsonify({"geraete": liste, "meldung": meldung})

    @bp.route("/api/cast/play", methods=["POST"])
    def cast_play():
        """Auf einem Chromecast abspielen.

        Body (JSON), alles optional:
          ip       — Zielgeraet; fehlt sie, kommt sie aus `cast.geraet_ip`.
          datei    — Dateiname aus `videos/` oder `images/` erzwingen.
          media_type — „videos" (Vorgabe) oder „images" zu `datei`.
          url      — eine beliebige, vollstaendige Medien-URL (schlaegt datei).
          modus    — „medien" (Vorgabe) oder „anzeige" (ganze /display-Seite,
                     braucht `cast.app_id`).
        Ohne `datei`/`url`/`anzeige` wird gecastet, was GERADE laeuft.
        """
        daten = request.get_json(silent=True) or {}
        cast_cfg = controller.config.get("cast") or {}
        ip = (daten.get("ip") or cast_cfg.get("geraet_ip") or "").strip()
        if not ip:
            return jsonify({"error": "Keine Chromecast-IP — in cast.geraet_ip "
                                     "eintragen oder im Body mitschicken"}), 400

        host, port = _host(controller)
        basis = f"http://{host}:{port}"
        modus = daten.get("modus") or cast_cfg.get("modus") or "medien"

        if modus == "anzeige":
            app_id = (cast_cfg.get("app_id") or "").strip()
            if not app_id:
                return jsonify({"error": "modus=anzeige braucht einen eigenen "
                                "Web-Receiver: cast.app_id (in der Cast-Konsole "
                                "registrierte App-ID) ist leer"}), 400
            ok, meldung = chromecast.spiele(
                ip, f"{basis}/display", content_type="text/html",
                app_id=app_id, titel=controller.config.get("system_name") or None)
            return (jsonify({"ok": ok, "meldung": meldung, "url": f"{basis}/display"}),
                    200 if ok else 502)

        # --- Modus „medien": eine konkrete Datei/URL ---
        url = (daten.get("url") or "").strip()
        if not url:
            datei = daten.get("datei")
            media_type = daten.get("media_type", "videos")
            if not datei:
                media_type, datei = _aktuelle_datei(controller.get_scene())
                if not datei:
                    return jsonify({"error": "Es laeuft gerade nichts und keine "
                                    "datei/url angegeben"}), 409
            url = f"{basis}/media/{media_type}/{secure_filename(datei)}"
            content_type = _mime(datei)
        else:
            content_type = daten.get("content_type") or "video/mp4"

        ok, meldung = chromecast.spiele(
            ip, url, content_type=content_type,
            app_id=(cast_cfg.get("app_id") or chromecast.STANDARD_EMPFAENGER),
            titel=controller.config.get("system_name") or None)
        return jsonify({"ok": ok, "meldung": meldung, "url": url}), 200 if ok else 502

    @bp.route("/api/cast/stop", methods=["POST"])
    def cast_stop():
        daten = request.get_json(silent=True) or {}
        cast_cfg = controller.config.get("cast") or {}
        ip = (daten.get("ip") or cast_cfg.get("geraet_ip") or "").strip()
        if not ip:
            return jsonify({"error": "Keine Chromecast-IP angegeben"}), 400
        ok, meldung = chromecast.stoppe(ip)
        return jsonify({"ok": ok, "meldung": meldung}), 200 if ok else 502

    return bp

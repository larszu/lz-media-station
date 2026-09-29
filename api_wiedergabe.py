#!/usr/bin/env python3
"""HTTP-Schnittstelle des Proof-of-Play (`/api/wiedergabe…`).

Die Anzeigeseite schickt ihre Starts gesammelt (`POST`), die Verwaltung
fragt Zusammenfassungen (`GET …/zusammenfassung`) und laedt die Rohliste
als CSV. Die Datei liegt neben `config.json`; `DB_PFAD` ist ein Modulwert,
damit Tests sie in ein Temp-Verzeichnis legen koennen, statt das
Repository vollzuschreiben.
"""
import os
from datetime import datetime

from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

import wiedergabe_log

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PFAD = os.path.join(BASE_DIR, "wiedergabe.sqlite")

#: Wie oft hoechstens aufgeraeumt wird — beim Eintragen, nicht per Uhr.
AUFRAEUMEN_ALLE_N = 200


def _datum(roh):
    if not roh:
        return None
    try:
        return datetime.strptime(roh, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("von/bis: JJJJ-MM-TT erwartet") from None


def erzeuge_blueprint(controller):
    bp = Blueprint("wiedergabe", __name__)
    zaehler = {"n": 0}

    def log_holen():
        """Die Datei entsteht beim ERSTEN Zugriff, nicht beim Start: eine
        Test-App oder ein Kern ohne Anzeige soll keine leere Datenbank
        anlegen."""
        log = getattr(controller, "wiedergabe", None)
        if log is None:
            tage = controller.config.get("wiedergabe_aufbewahrung_tage", wiedergabe_log.AUFBEWAHRUNG_TAGE)
            log = controller.wiedergabe = wiedergabe_log.WiedergabeLog(DB_PFAD, tage)
        log.aufbewahrung_tage = controller.config.get("wiedergabe_aufbewahrung_tage", log.aufbewahrung_tage)
        return log

    @bp.route("/api/wiedergabe", methods=["POST"])
    def api_wiedergabe_melden():
        daten = request.get_json(silent=True)
        if not isinstance(daten, dict):
            return jsonify({"error": "Objekt {kennung, eintraege: [...]} erwartet"}), 400
        eintraege = daten.get("eintraege")
        if not isinstance(eintraege, list):
            return jsonify({"error": "eintraege: Liste erwartet"}), 400
        log = log_holen()
        neu = log.eintragen(daten.get("kennung"), eintraege)
        zaehler["n"] += 1
        if zaehler["n"] % AUFRAEUMEN_ALLE_N == 1:
            log.aufraeumen(datetime.now())
        return jsonify({"ok": True, "neu": neu})

    @bp.route("/api/wiedergabe/zusammenfassung")
    def api_wiedergabe_zusammenfassung():
        try:
            return jsonify(log_holen().zusammenfassung(
                von=_datum(request.args.get("von")),
                bis=_datum(request.args.get("bis")),
                gruppe=request.args.get("gruppe", "datei")))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @bp.route("/api/wiedergabe.csv")
    def api_wiedergabe_csv():
        try:
            von, bis = _datum(request.args.get("von")), _datum(request.args.get("bis"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        name = (controller.config.get("system_name") or "station").replace(" ", "_")
        return Response(
            log_holen().als_csv(von, bis),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     f'attachment; filename="{secure_filename(name)}-wiedergabe.csv"'})

    return bp

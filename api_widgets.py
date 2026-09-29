#!/usr/bin/env python3
"""HTTP-Schnittstelle der Widgets (`/api/widgets/…`, `/widgets/…`).

Ein `api_*.py`-Modul wie `api_layouts.py`: `web_ui.create_app` registriert
`erzeuge_blueprint(controller)` von selbst.

Was hier steht, sind PROXYS und eine Dateiauslieferung — keine Konfiguration.
Die Einstellungen eines Widgets liegen in der Region des Layouts
(`region.widget`), gespeichert ueber `/api/layouts`. Hier holt der Kern nur,
was die Anzeige aus dem Netz braucht, und liefert eigene HTML-Widgets aus.

Fehler kommen als JSON `{"fehler": "…"}`: 400, wenn die Anfrage nicht stimmt
(keine URL, falsches Schema), 502, wenn die Gegenseite nicht liefert. Die
Anzeige macht daraus eine dezente Zeile — kein Absturz, kein Umleiten.
"""
import os

from flask import Blueprint, jsonify, request, send_from_directory

import widgets as W


def erzeuge_blueprint(controller):
    bp = Blueprint("widgets", __name__)

    def fehler(e, status):
        return jsonify({"fehler": str(e)}), status

    def ganzzahl(name, vorgabe, kleinstes, groesstes):
        try:
            wert = int(request.args.get(name, vorgabe))
        except (TypeError, ValueError):
            wert = vorgabe
        return max(kleinstes, min(groesstes, wert))

    @bp.route("/api/widgets/rss")
    def api_widgets_rss():
        """`?url=&anzahl=` -> {titel, eintraege:[{titel, link, zeit, text, quelle}], veraltet}."""
        try:
            url = W.pruefe_url(request.args.get("url"))
        except W.Abrufsfehler as e:
            return fehler(e, 400)
        try:
            return jsonify(W.rss_laden(url, anzahl=ganzzahl("anzahl", 6, 1, 50)))
        except W.Abrufsfehler as e:
            return fehler(e, 502)

    @bp.route("/api/widgets/ics")
    def api_widgets_ics():
        """`?url=&tage=` -> {name, termine:[{start, ende, titel, ort, ganztags}], veraltet}."""
        try:
            url = W.pruefe_url(request.args.get("url"))
        except W.Abrufsfehler as e:
            return fehler(e, 400)
        try:
            return jsonify(W.ics_laden(url, tage=ganzzahl("tage", 14, 1, 60)))
        except W.Abrufsfehler as e:
            return fehler(e, 502)

    @bp.route("/api/widgets/wetter")
    def api_widgets_wetter():
        """`?lat=&lon=&einheit=c|f` -> {aktuell, tage[], einheit, veraltet} (Open-Meteo)."""
        try:
            lat, lon = W.pruefe_koordinaten(request.args.get("lat"), request.args.get("lon"))
        except W.Abrufsfehler as e:
            return fehler(e, 400)
        try:
            return jsonify(W.wetter_laden(lat, lon, request.args.get("einheit", "c")))
        except W.Abrufsfehler as e:
            return fehler(e, 502)

    @bp.route("/api/widgets/einbettbar")
    def api_widgets_einbettbar():
        """`?url=` -> {einbettbar, grund} — laesst sich die Seite in einen Rahmen legen?"""
        try:
            url = W.pruefe_url(request.args.get("url"))
        except W.Abrufsfehler as e:
            return fehler(e, 400)
        try:
            return jsonify(W.einbettbar(url))
        except W.Abrufsfehler as e:
            return fehler(e, 502)

    @bp.route("/api/widgets/eigene")
    def api_widgets_eigene():
        """Eigene HTML-Widgets: alle Ordner unter `widgets/` mit `index.html`."""
        return jsonify({"widgets": W.eigene_widgets()})

    def widget_datei(name, pfad):
        """Dateien eines eigenen Widgets — nur aus seinem Ordner.

        `send_from_directory` weist `..` und absolute Pfade ab (404); der
        Ordnername wird zusaetzlich geprueft, damit `/widgets/../x` gar
        nicht erst zu einem Verzeichnis wird.
        """
        if not W.WIDGET_NAME.match(name or ""):
            return fehler("Widget-Name: a-z, 0-9, '-' und '_'", 400)
        ordner = os.path.join(W.WIDGETS_DIR, name)
        if not os.path.isdir(ordner):
            return fehler(f"Widget '{name}' gibt es nicht", 404)
        antwort = send_from_directory(ordner, pfad)
        # Eigene Widgets sind Vertrauenssache des Betreibers, aber gecacht
        # werden sollen sie nicht — wer die Datei aendert, will das sehen.
        antwort.headers["Cache-Control"] = "no-store"
        return antwort

    # Zwei Routen, zwei Endpunkte — KEIN `defaults=`: Werkzeug leitet sonst
    # `/widgets/x/index.html` per 308 auf `/widgets/x/` um, und ein iframe,
    # der die Datei direkt nennt, laeuft in die Umleitung.
    @bp.route("/widgets/<name>/")
    def widgets_start(name):
        return widget_datei(name, "index.html")

    @bp.route("/widgets/<name>/<path:pfad>")
    def widgets_datei(name, pfad):
        return widget_datei(name, pfad)

    return bp

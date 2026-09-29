#!/usr/bin/env python3
"""HTTP-Seite des Zugangsschutzes: `/login`, `/api/zugang…` und der Tuersteher.

`init(app, controller)` haengt den Tuersteher (`before_request`) an die App
und setzt den Sitzungs-Schluessel. Die Entscheidung selbst steht in
`zugang.entscheide` — rein, ohne Flask, dort getestet.

Der Zustand (`zugang.json`, `geheim.key`) liegt neben `config.json`;
`ZUGANG_PFAD`/`GEHEIM_PFAD` sind Modulwerte, damit Tests sie umbiegen.
"""
import os
import secrets
import time

from flask import Blueprint, jsonify, redirect, render_template, request, session

import zugang as Z

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZUGANG_PFAD = os.path.join(BASE_DIR, "zugang.json")
GEHEIM_PFAD = os.path.join(BASE_DIR, "geheim.key")


def _zugang(controller):
    z = getattr(controller, "zugang", None)
    if z is None:
        z = controller.zugang = Z.Zugang(ZUGANG_PFAD)
    return z


def _anmelden(z):
    session["zugang_bis"] = time.time() + z.sitzungsdauer_h * 3600
    session["zugang_gen"] = z.generation
    session.permanent = True


def _angemeldet(z):
    return Z.sitzung_gilt(z, session.get("zugang_bis"), session.get("zugang_gen"), time.time())


def erzeuge_blueprint(controller):
    bp = Blueprint("zugang", __name__)
    z = _zugang(controller)

    @bp.route("/login")
    def login_seite():
        weiter = Z.sicherer_weiter(request.args.get("weiter"))
        if not z.gesetzt or _angemeldet(z):
            return redirect(weiter)
        from web_ui import erweiterungen  # spaet: web_ui laedt dieses Modul
        return render_template("login.html", weiter=weiter, **erweiterungen())

    @bp.route("/api/zugang")
    def api_zugang():
        return jsonify({
            "gesetzt": z.gesetzt,
            "angemeldet": _angemeldet(z),
            "lokal": Z.ist_lokal(request.remote_addr or ""),
            "sitzungsdauer_h": z.sitzungsdauer_h,
        })

    @bp.route("/api/zugang", methods=["POST"])
    def api_zugang_setzen():
        """PIN setzen oder aendern. Ist schon eine gesetzt, braucht es die alte
        (`alt`) — oder den Aufruf vom Pi selbst (127.0.0.1), fuer den Fall,
        dass sie vergessen wurde: dann per SSH `curl` an localhost."""
        daten = request.get_json(silent=True) or {}
        adresse = request.remote_addr or ""
        if z.gesetzt and not Z.ist_lokal(adresse) and not _angemeldet(z):
            if z.gesperrt(adresse):
                return jsonify({"error": "Zu viele Fehlversuche — eine Minute warten"}), 429
            if not z.stimmt(daten.get("alt")):
                z.fehlversuch(adresse)
                return jsonify({"error": "alt: die bisherige PIN stimmt nicht"}), 401
        try:
            z.setzen(daten.get("pin"), daten.get("sitzungsdauer_h"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except OSError as e:
            return jsonify({"error": f"zugang.json nicht schreibbar: {e}"}), 500
        # Ab jetzt gibt es Sitzungen — der Schluessel muss den Neustart ueberleben.
        from flask import current_app
        Z.schreibe_geheim(GEHEIM_PFAD, current_app.secret_key)
        z.erfolg(adresse)
        _anmelden(z)
        return jsonify({"ok": True, "gesetzt": True})

    @bp.route("/api/zugang", methods=["DELETE"])
    def api_zugang_aufheben():
        """Die PIN aufheben — mit Sitzung, PIN im Kopf, oder vom Pi selbst.
        Der Tuersteher hat das schon geprueft; hier nur noch tun."""
        try:
            z.aufheben()
        except OSError as e:
            return jsonify({"error": f"zugang.json nicht schreibbar: {e}"}), 500
        session.pop("zugang_bis", None)
        session.pop("zugang_gen", None)
        return jsonify({"ok": True, "gesetzt": False})

    @bp.route("/api/zugang/login", methods=["POST"])
    def api_zugang_login():
        daten = request.get_json(silent=True) or {}
        adresse = request.remote_addr or ""
        if not z.gesetzt:
            return jsonify({"ok": True, "gesetzt": False})
        if z.gesperrt(adresse):
            return jsonify({"error": "Zu viele Fehlversuche — eine Minute warten"}), 429
        if not z.stimmt(daten.get("pin")):
            z.fehlversuch(adresse)
            return jsonify({"error": "PIN stimmt nicht"}), 401
        z.erfolg(adresse)
        _anmelden(z)
        return jsonify({"ok": True, "gesetzt": True})

    @bp.route("/api/zugang/logout", methods=["POST"])
    def api_zugang_logout():
        session.pop("zugang_bis", None)
        session.pop("zugang_gen", None)
        return jsonify({"ok": True})

    return bp


def init(app, controller):
    """Sitzungs-Schluessel setzen und den Tuersteher anhaengen."""
    z = _zugang(controller)
    if not app.secret_key:
        # Aus der Datei, wenn es sie gibt; sonst zufaellig im Speicher — die
        # Datei entsteht erst mit der ersten PIN (`_geheim_sichern`).
        app.secret_key = Z.lade_geheim(GEHEIM_PFAD) or secrets.token_bytes(32)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    @app.before_request
    def tuersteher():
        grund = Z.entscheide(
            z, request.method, request.path, request.remote_addr or "",
            session.get("zugang_bis"), request.headers.get("X-LZ-Pin"), time.time(),
            sitzung_gen=session.get("zugang_gen"))
        if grund is None:
            return None
        if grund == "anmelden":
            return redirect("/login?weiter=" + request.path)
        if grund == "gesperrt":
            return jsonify({"error": "Zu viele Fehlversuche — eine Minute warten", "zugang": "gesperrt"}), 429
        if grund == "falsche_pin":
            return jsonify({"error": "PIN stimmt nicht", "zugang": "pin"}), 401
        return jsonify({"error": "Anmeldung erforderlich — PIN im Kopf X-LZ-Pin oder Sitzung",
                        "zugang": "pin"}), 401

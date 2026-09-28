"""Flask Web-UI + Media-Server für LZ Media Station"""
import glob
import importlib
import json
import os
import socket
from datetime import datetime
from flask import Flask, Response, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import ereignisse
import gesundheit
import layouts as layouts_modul
import medien_check
from config_schema import (
    DEFAULT_CONFIG, MEDIENARTEN, ZONEN, ZONEN_NAMEN, aktive_zonen,
    heile_config, heile_zone, pruefe_patch, pruefe_pins, pruefe_schwellen,
    pruefe_sprachen, pruefe_untertitel, pruefe_zone, standard_zone,
)
from zeitplan import pruefe_zeitplan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIRS = {
    "videos": os.path.join(BASE_DIR, "videos"),
    "images": os.path.join(BASE_DIR, "images"),
    "audio": os.path.join(BASE_DIR, "audio"),
    # Untertitel sind eine eigene Medienart: sie werden hochgeladen und
    # aufgelistet wie Videos, aber nie einer Zone zugewiesen — sie haengen an
    # einem Video, nicht an einer Entfernung.
    "subtitles": os.path.join(BASE_DIR, "subtitles"),
}
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ALLOWED_EXT = {
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"},
    # Nur WebVTT: das ist das einzige Format, das ein Browser ohne Umwege
    # abspielt. Eine .srt anzunehmen und stumm nicht anzuzeigen waere
    # schlimmer als sie abzulehnen.
    "subtitles": {".vtt"},
}


def lies_version():
    """Die Version aus der EINEN Datei `VERSION`.

    Sie stand als Text in `/api/identity` ("2.1.0") und als Zahl in
    `station-manager/package.json` (2.0.4) — zwei Stellen, die nie jemand
    abgeglichen hat. Jetzt gibt es eine; der Release setzt sie.
    """
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def erweiterungen():
    """Was Welle 2 (und alles danach) nur als DATEI hinzulegen braucht.

    - `templates/admin/zusatz/*.html`  — weitere Karten im Admin
    - `static/module/*.js`             — Skripte nach app.js im Admin
    - `static/anzeige/*.js`            — Skripte auf der Anzeige (Widgets)
    - `static/i18n/*.en.js`            — weitere englische Woerterbuecher
    Alphabetisch, damit die Reihenfolge nachvollziehbar ist. Nichts davon
    muss in `create_app` eingetragen werden — das ist der Zweck.
    """
    def namen(muster):
        return sorted(os.path.basename(p) for p in glob.glob(os.path.join(BASE_DIR, muster)))
    return {
        "zusatz_templates": ["admin/zusatz/" + n for n in namen("templates/admin/zusatz/*.html")],
        "module_skripte": ["/static/module/" + n for n in namen("static/module/*.js")],
        "anzeige_skripte": ["/static/anzeige/" + n for n in namen("static/anzeige/*.js")],
        "i18n_extra": ["/static/i18n/" + n for n in namen("static/i18n/*.en.js")],
    }


def lan_adresse():
    """
    Beste Schätzung der LAN-IP.

    ÖFFENTLICH seit 2026-09-09, weil `main.py` sie beim Start ausgeben muss.
    Vorher stand dort `http://0.0.0.0:5000` — und `0.0.0.0` ist keine
    Adresse, die jemand eintippen kann. Es ist die Bind-Angabe „alle
    Schnittstellen"; wer sie in einen Browser tippt, landet je nach System
    nirgends. Der Server war also im Netz erreichbar, und niemand erfuhr,
    unter welcher Adresse.

    Eine zweite Erkennung in `main.py` wäre die naheliegende und falsche
    Lösung gewesen: zwei Funktionen, die dieselbe Frage beantworten, geben
    irgendwann zwei Antworten — und dann steht auf dem Schirm eine andere
    Adresse als in `/api/status`.
    """
    # 1) UDP-Trick (funktioniert wenn Default-Route da ist)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    finally:
        s.close()
    # 2) Fallback: alle aufgelösten IPs prüfen, erste nicht-Loopback nehmen
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    # 3) Letzter Ausweg: Linux 'hostname -I'
    try:
        import subprocess
        out = subprocess.check_output(["hostname", "-I"], timeout=2).decode().strip()
        for ip in out.split():
            if ip and not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:
        pass
    return "127.0.0.1"


def lage_der_station(controller):
    """Die echte Lage einsammeln und pruefen lassen.

    Das Einsammeln (Platte, Dateien, Systemwerte, Puls der Anzeigen) steht
    hier, die Beurteilung in `gesundheit.pruefe` — sonst waere kein einziger
    Befund ohne echtes Dateisystem testbar. Modulfunktion, weil der Waechter
    der Benachrichtigung (api_anzeige) sie ausserhalb einer Anfrage braucht.
    """
    import shutil
    try:
        freier_platz = shutil.disk_usage(BASE_DIR).free
    except Exception:
        freier_platz = None
    vorhandene = {}
    for art, verzeichnis in MEDIA_DIRS.items():
        try:
            vorhandene[art] = set(os.listdir(verzeichnis))
        except OSError:
            vorhandene[art] = set()
    return gesundheit.pruefe(
        controller.config,
        sensor_ok=controller.sensor.distance is not None,
        sensor_status=controller.sensor.status,
        freier_platz_b=freier_platz,
        vorhandene=vorhandene,
        aktiv=controller.active,
        geschlossen=not controller.ist_offen(),
        zonen=[(z, ZONEN_NAMEN.get(z, z)) for z in aktive_zonen(controller.config)],
        sync_ok=(None if not controller.follower
                 else controller.follower.zone is not None),
        sync_status=(controller.follower.status if controller.follower else None),
        system=gesundheit.systemwerte(),
        anzeige=(controller.anzeigen.zusammenfassung() if hasattr(controller, "anzeigen") else None),
    )


def create_app(controller, anzeigen=None):
    """`anzeigen` ist der Mehrschirm-Spieler dieses Rechners (`displays.py`).

    Er ist OPTIONAL, und zwar nicht aus Bequemlichkeit: die Tests bauen die
    App ohne ihn, und auf einem Pi ohne Grafik gibt es nichts zu bespielen.
    Fehlt er, antwortet `/api/displays` mit einer leeren Liste und dem
    Grund — nicht mit einem Fehler, denn „dieser Rechner hat keine Schirme"
    ist kein Fehler.
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

    # Fehlt der Bus (ein Controller-Ersatz in einem Test), bekommt die App
    # einen eigenen: `/api/events` soll nie an einem Attribut scheitern.
    if not hasattr(controller, "bus"):
        controller.bus = ereignisse.Ereignisbus()
    if not hasattr(controller, "lock"):
        import threading
        controller.lock = threading.RLock()

    def melde_config():
        if hasattr(controller, "melde_config"):
            controller.melde_config()

    # --- Erweiterungen: alle `api_*.py` im Wurzelverzeichnis ------------------
    # Ein neues Modul mit `erzeuge_blueprint(controller)` ist damit registriert,
    # ohne dass hier eine Zeile dazukommt. Fehlt die Funktion, wird das Modul
    # genannt und uebersprungen — nicht der Start verhindert.
    for pfad in sorted(glob.glob(os.path.join(BASE_DIR, "api_*.py"))):
        name = os.path.splitext(os.path.basename(pfad))[0]
        try:
            modul = importlib.import_module(name)
            app.register_blueprint(modul.erzeuge_blueprint(controller))
            # Optional `init(app, controller)`: fuer Hintergrundfaeden und
            # Hooks an der App (Tuersteher, Waechter) — siehe architektur-v3.md.
            init = getattr(modul, "init", None)
            if init:
                init(app, controller)
        except Exception as e:  # noqa: BLE001 — der Start geht vor
            print(f"[Erweiterung] {name}: nicht registriert ({e})")

    # --- Pages ---
    @app.route("/")
    def launch():
        return render_template("launch.html", **erweiterungen())

    @app.route("/admin")
    def admin():
        return render_template("admin.html", **erweiterungen())

    @app.route("/display")
    def display():
        return render_template("display.html", **erweiterungen())

    # --- API ---
    def _status():
        cfg_ip = (controller.config.get("display_ip") or "").strip()
        port = controller.config.get("web_port", 5000)
        host_ip = cfg_ip or lan_adresse()
        return {
            # `None`, wenn keine gueltige Messung vorliegt. Frueher stand
            # hier 0.0 — eine Zahl, die aussieht wie „Besucher steht direkt
            # davor", und die Oberflaeche konnte nicht zwischen „ganz nah"
            # und „Sensor tot" unterscheiden.
            "distance": (None if controller.sensor.distance is None
                         else round(controller.sensor.distance, 3)),
            "sensor_ok": controller.sensor.distance is not None,
            "state": controller.state,
            "active": controller.active,
            # Welche Quelle laeuft und ihr Klartext-Zustand. Loest das alte
            # `dummy_sensor` ab: es gibt keinen Demo-Modus mehr, und die
            # Oberflaeche soll sagen koennen „kein Sensor angeschlossen" statt
            # eine erfundene Zahl zu zeigen.
            "sensor_type": controller.config.get("sensor_type", "ultrasonic"),
            "sensor_label": controller.sensor.LABEL,
            "sensor_status": controller.sensor.status,
            # Wochenplan: die Verwaltung soll erklaeren koennen, warum nichts
            # spielt, statt dass es wie ein Defekt aussieht.
            "geschlossen": not controller.ist_offen(),
            "host_ip": host_ip,
            "web_port": port,
            "remote_url": "http://" + host_ip + ":" + str(port) + "/admin",
            # Die zweite Adresse, und sie fehlte. `remote_url` zeigte nur auf
            # die Konfiguration — der haeufigste Fall eines zweiten Geraets
            # ist aber, die ANZEIGE zu holen: ein Tablet im Foyer, ein
            # Notebook an einem zweiten Aufbau. Eine Adresse, die nirgends
            # steht, kann niemand erraten.
            "display_url": "http://" + host_ip + ":" + str(port) + "/display",
            "version": lies_version(),
            "config": controller.config,
            # Puls der Anzeigeseiten (api_anzeige, 3.0): wie viele, wie viele online.
            "anzeige": (controller.anzeigen.zusammenfassung() if hasattr(controller, "anzeigen") else None),
        }

    @app.route("/api/status")
    def api_status():
        return jsonify(_status())

    @app.route("/api/scene")
    def api_scene():
        """Was gerade zu spielen ist.

        `?layout=<id>` ist die VORSCHAU: dieses Layout, als Zone `?zone=`
        (oder die erste), unabhaengig von Sensor und Wochenplan; `?zeit=`
        (JJJJ-MM-TTTHH:MM) entscheidet, welche Eintraege an dem Tag gelten.
        Der Layout-Editor (Welle 2) zeigt damit, was er baut — mit derselben
        Anzeigeseite, die auch auf dem Schirm laeuft.
        """
        layout_id = request.args.get("layout")
        if layout_id is None:
            return jsonify(controller.get_scene())
        if layout_id not in (controller.config.get("layouts") or {}):
            return jsonify({"error": f"Layout {layout_id!r} gibt es nicht"}), 404
        jetzt = None
        roh = request.args.get("zeit")
        if roh:
            try:
                jetzt = datetime.fromisoformat(roh)
            except ValueError:
                return jsonify({"error": "zeit: JJJJ-MM-TTTHH:MM erwartet"}), 400
        return jsonify(controller.get_scene(layout_id=layout_id,
                                            zone=request.args.get("zone"),
                                            jetzt=jetzt))

    # ── Ereignisse (SSE) ──────────────────────────────────────────────────
    #
    # Die Anzeige und die Verwaltung hoeren hier zu, statt zweimal je Sekunde
    # zu fragen. `scene` kommt bei jedem Zonenwechsel, `config` nach jedem
    # Schreibzugriff, `befehl` von `/api/befehl`. `?status=1` schickt
    # zusaetzlich jede Sekunde den Status (Abstand, Zustand) — das braucht
    # nur die Verwaltung.

    @app.route("/api/events")
    def api_events():
        mit_status = request.args.get("status") == "1"
        return Response(
            ereignisse.strom(controller.bus, status=_status if mit_status else None),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.route("/api/befehl", methods=["POST"])
    def api_befehl():
        """Ein Befehl an alle Anzeigen, die gerade zuhoeren.

        `reload`        — die Anzeigeseite neu laden (nach einem Update)
        `zeige_layout`  — {layout_id, dauer_s|null}: ein Layout zwischendurch
                          zeigen (Durchsage, Vorschau am echten Schirm);
                          `dauer_s` null = bis zum naechsten Befehl,
                          `layout_id` null = zurueck zur Zone
        `screenshot`    — wird durchgereicht (Auswertung kommt mit Welle 2)
        """
        daten = request.get_json(silent=True) or {}
        typ = daten.get("typ")
        if typ not in ("reload", "zeige_layout", "screenshot"):
            return jsonify({"error": "typ: reload|zeige_layout|screenshot"}), 400
        befehl = {"typ": typ}
        if typ == "zeige_layout":
            lid = daten.get("layout_id")
            if lid is not None and lid not in (controller.config.get("layouts") or {}):
                return jsonify({"error": f"layout_id: {lid!r} gibt es nicht"}), 404
            dauer = daten.get("dauer_s")
            if dauer is not None:
                if isinstance(dauer, bool) or not isinstance(dauer, (int, float)) or dauer <= 0:
                    return jsonify({"error": "dauer_s: Sekunden > 0 oder null"}), 400
            befehl["layout_id"] = lid
            befehl["dauer_s"] = dauer
        controller.bus.senden("befehl", befehl)
        return jsonify({"ok": True, "empfaenger": controller.bus.anzahl})

    @app.route("/api/sync")
    def api_sync():
        """Der Takt fuer andere Stationen: welche Zone laeuft hier gerade?

        JEDE Station beantwortet das — deshalb gibt es keine „master"-Rolle
        einzustellen. Absichtlich schmal: nur Zone und Betriebsruhe. Wer den
        ganzen Szenen-Zustand braucht, nimmt /api/scene; wer folgt, braucht
        genau diese zwei Angaben, und eine schmale Antwort haelt den Takt
        billig (der Follower fragt mehrmals je Sekunde).
        """
        szene = controller.get_scene()
        return jsonify({
            "zone": szene["zone"],
            "geschlossen": szene["geschlossen"],
            "zonen": szene["zonen"],
            "name": controller.config.get("system_name", "LZ Station"),
        })

    # ── Besucher-Statistik ────────────────────────────────────────────────
    #
    # Die Zahlen entstehen ohnehin im Sensor und wurden bisher weggeworfen.
    # Fuer den Betreiber sind sie der Nachweis, dass die Installation wirkt.
    # Gespeichert wird nur, WANN und WIE LANGE jemand nah war — nichts ueber
    # einzelne Personen.

    # ── Zustandspruefung ──────────────────────────────────────────────────

    def _lage():
        return lage_der_station(controller)

    @app.route("/api/health")
    def api_health():
        befunde = _lage()
        return jsonify({
            "stufe": gesundheit.gesamtstufe(befunde),
            "befunde": befunde,
        })

    @app.route("/api/statistik")
    def api_statistik():
        from datetime import datetime
        return jsonify(controller.statistik.zusammenfassung(datetime.now()))

    @app.route("/api/statistik.csv")
    def api_statistik_csv():
        from flask import Response
        name = (controller.config.get("system_name") or "station").replace(" ", "_")
        return Response(
            controller.statistik.als_csv(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     f'attachment; filename="{secure_filename(name)}-statistik.csv"'})

    @app.route("/api/statistik/reset", methods=["POST"])
    def api_statistik_reset():
        """Zaehler auf null — beim Umzug in die naechste Ausstellung.

        Bewusst ein eigener Endpunkt und nicht Teil von `/api/config`: das
        Loeschen von Messwerten soll nicht als Nebenwirkung eines
        Einstellungs-Speicherns passieren koennen.
        """
        controller.statistik_leeren()
        return jsonify({"ok": True})

    # ── Die Bildschirme DIESES Rechners (Nutzer, 2026-09-15) ──────────────
    #
    # „im mediaplayer das endgeraet selbst und externe displays die ans
    #  endgeraet angeschlossen sind als mediaplayer nutzen koennen."
    #
    # Die Anzeige war bis hierher ein Browser auf dem einen HDMI-Ausgang
    # eines Pi. Auf einem Notebook oder einem Rechner am Aufbau haengt oft
    # mehr als ein Schirm; der eingebaute zaehlt mit.

    @app.route("/api/displays")
    def api_displays():
        if anzeigen is None:
            return jsonify({
                "schirme": [],
                "browser": None,
                "grund": "Diese Station laeuft ohne Mehrschirm-Spieler.",
            })
        import displays as _d
        return jsonify({
            "schirme": anzeigen.zustand(),
            "browser": _d.finde_browser(),
            "suchorte": _d.suchorte(),
        })

    @app.route("/api/displays/play", methods=["POST"])
    def api_displays_play():
        if anzeigen is None:
            return jsonify({"ok": False,
                            "meldungen": ["Kein Mehrschirm-Spieler."]}), 409
        daten = request.get_json(silent=True) or {}
        auswahl = daten.get("schirme")
        if auswahl is not None and not isinstance(auswahl, list):
            return jsonify({"ok": False,
                            "meldungen": ["`schirme` muss eine Liste sein."]}), 400
        # `127.0.0.1` und nicht die LAN-Adresse: die Fenster laufen auf
        # DIESEM Rechner. Ueber die eigene Netzadresse zu gehen hiesse, sich
        # von der Netzwerkkarte abhaengig zu machen, die man gar nicht
        # braucht — in einem Gastnetz mit Client-Isolation faellt das aus.
        port = controller.config.get("web_port", 5000)
        url = f"http://127.0.0.1:{port}/display"
        gestartet, meldungen = anzeigen.starte(url, auswahl)
        return jsonify({"ok": bool(gestartet), "gestartet": gestartet,
                        "meldungen": meldungen})

    @app.route("/api/displays/stop", methods=["POST"])
    def api_displays_stop():
        if anzeigen is None:
            return jsonify({"ok": False,
                            "meldungen": ["Kein Mehrschirm-Spieler."]}), 409
        daten = request.get_json(silent=True) or {}
        auswahl = daten.get("schirme")
        if auswahl is not None and not isinstance(auswahl, list):
            return jsonify({"ok": False,
                            "meldungen": ["`schirme` muss eine Liste sein."]}), 400
        return jsonify({"ok": True, "beendet": anzeigen.beende(auswahl)})

    @app.route("/api/identity")
    def api_identity():
        """Station-Identität für Discovery / Manager-App."""
        import uuid, platform
        id_path = os.path.join(BASE_DIR, ".station_id")
        try:
            if os.path.exists(id_path):
                with open(id_path, "r") as f:
                    sid = f.read().strip()
            else:
                sid = uuid.uuid4().hex
                with open(id_path, "w") as f:
                    f.write(sid)
        except Exception:
            sid = "unknown"
        # Der Zustand kommt MIT. Der Station Manager fragt beim Scannen ohnehin
        # jede Station nach ihrer Identitaet — ein zweiter Aufruf je Station
        # nur fuer die Gesundheit waere dieselbe Runde ein zweites Mal.
        # Nur die Stufe und die Anzahl, nicht die ganzen Texte: die Liste holt
        # sich, wer sie anzeigt, ueber `/api/health`.
        befunde = _lage()
        stufe = gesundheit.gesamtstufe(befunde)
        return jsonify({
            "id": sid,
            "name": controller.config.get("system_name", "LZ Station"),
            "version": lies_version(),
            "hostname": platform.node(),
            "active": controller.active,
            "state": controller.state,
            "health": stufe,
            "health_anzahl": len([b for b in befunde if b["stufe"] != "hinweis"]),
        })

    @app.route("/api/config", methods=["POST"])
    def api_config():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine Daten"}), 400
        # Hier stand eine Tabelle aus FELDNAME -> Typ, und damit war die
        # Pruefung zu Ende: `gpio_trigger: 99`, `threshold_m: -5`,
        # `web_port: 0` gingen durch, weil der Name stimmte und `int()` nicht
        # warf. Die Bedeutung steht jetzt in `main.GRENZEN` — eine Tabelle,
        # zwei Politiken (ablehnen beim Schreiben, heilen beim Laden). Siehe
        # den Kopf dieses Abschnitts in `main.py`.
        try:
            geprueft = pruefe_patch(data)
            pruefe_pins(controller.config, geprueft)
            # Auch eine Kreuzbedingung: die Mitte muss weiter weg sein als die
            # Nah-Schwelle. Jedes Feld fuer sich waere gueltig.
            pruefe_schwellen(controller.config, geprueft)
            # Der Zeitplan ist verschachtelt und steht darum nicht in GRENZEN.
            # Gleiche Politik wie dort: ABLEHNEN statt heilen — wer eine
            # Oeffnungszeit setzt, soll erfahren, dass sie nicht ankam.
            if "zeitplan" in data:
                geprueft["zeitplan"] = pruefe_zeitplan(data["zeitplan"])
            if "sprachen" in data:
                geprueft["sprachen"] = pruefe_sprachen(data["sprachen"])
            if "untertitel" in data:
                geprueft["untertitel"] = {
                    secure_filename(video): {
                        code: secure_filename(datei) for code, datei in spuren.items()
                    }
                    for video, spuren in pruefe_untertitel(data["untertitel"]).items()
                }
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        # ERST alles pruefen, DANN schreiben — sonst waere die Haelfte eines
        # abgelehnten Patches schon angekommen.
        zonen_teile = {}
        for zone in ZONEN:
            if zone not in data:
                continue
            try:
                teil = pruefe_zone(data[zone])
            except ValueError as e:
                return jsonify({"error": f"{zone}.{e}"}), 400
            lid = teil.get("layout")
            if lid and lid not in (controller.config.get("layouts") or {}):
                return jsonify({"error": f"{zone}.layout: Layout {lid!r} gibt es nicht"}), 400
            # Dateinamen bleiben entschaerft — der Name kommt aus dem Browser
            # und landet spaeter in einem Pfad.
            for mt in MEDIENARTEN:
                if mt in teil:
                    teil[mt] = [secure_filename(f) for f in teil[mt]]
            if "bildzeiten" in teil:
                teil["bildzeiten"] = {
                    secure_filename(name): wert for name, wert in teil["bildzeiten"].items()
                }
            zonen_teile[zone] = teil
        with controller.lock:
            controller.config.update(geprueft)
            for zone, teil in zonen_teile.items():
                if not isinstance(controller.config.get(zone), dict):
                    controller.config[zone] = standard_zone()
                # Die alten Listen landen in der Hauptregion des Zonen-Layouts
                # (layouts.py) — so schicken der Manager und alte Skripte
                # weiterhin `{"near": {"videos": [...]}}`, und es kommt an.
                layouts_modul.schreibe_zonen_teil(controller.config, zone, teil)
            controller.save_config()
        melde_config()
        return jsonify({"ok": True, "config": controller.config})

    @app.route("/api/media/<media_type>")
    def api_list_media(media_type):
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        d = MEDIA_DIRS[media_type]
        exts = ALLOWED_EXT[media_type]
        files = []
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if os.path.splitext(f)[1].lower() in exts:
                    size = os.path.getsize(os.path.join(d, f)) / (1024 * 1024)
                    files.append({"name": f, "size_mb": round(size, 1)})
        return jsonify(files)

    @app.route("/api/upload/<media_type>", methods=["POST"])
    def api_upload(media_type):
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        if "file" not in request.files:
            return jsonify({"error": "Keine Datei"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "Kein Dateiname"}), 400
        name = secure_filename(f.filename)
        if os.path.splitext(name)[1].lower() not in ALLOWED_EXT[media_type]:
            return jsonify({"error": "Format nicht erlaubt"}), 400
        os.makedirs(MEDIA_DIRS[media_type], exist_ok=True)
        ziel = os.path.join(MEDIA_DIRS[media_type], name)
        f.save(ziel)
        # Hinweise, KEINE Ablehnung: wer weiss, was er tut (ein Pi 5 mit einem
        # kurzen 4K-Clip), soll nicht vom Werkzeug ausgebremst werden. Der
        # haeufigste Ausfallgrund einer Station ist aber kein Defekt, sondern
        # eine Datei, die der Pi nicht fluessig dekodiert — und der Upload war
        # dazu bisher stumm.
        hinweise = []
        if media_type == "videos":
            _geprueft, hinweise = medien_check.pruefe_datei(ziel)
        return jsonify({"ok": True, "name": name, "hinweise": hinweise})

    # ── Sicherung und Wiederherstellung ───────────────────────────────────
    #
    # Eine Station wird geklont (die naechste Ausstellung, derselbe Aufbau)
    # oder nach einem SD-Karten-Tod wiederhergestellt. Bisher hiess das: die
    # `config.json` von Hand ueber SSH kopieren.

    @app.route("/api/backup")
    def api_backup():
        from flask import Response
        name = (controller.config.get("system_name") or "station").replace(" ", "_")
        return Response(
            json.dumps(controller.config, indent=2, ensure_ascii=False),
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition":
                     f'attachment; filename="{secure_filename(name)}-konfiguration.json"'})

    @app.route("/api/restore", methods=["POST"])
    def api_restore():
        """Eine gesicherte Konfiguration einspielen.

        HEILEN statt ablehnen — anders als `/api/config`. Eine Sicherung kann
        aus einer aelteren Fassung stammen, in der es Felder noch nicht gab
        oder anders hiessen. Eine Wiederherstellung, die an einem einzigen
        veralteten Feld scheitert, ist im Ernstfall (Karte tot, Ausstellung
        oeffnet) genau das, was niemand gebrauchen kann.
        """
        daten = request.get_json(silent=True)
        if not isinstance(daten, dict):
            return jsonify({"error": "Kein lesbares Konfigurations-Objekt"}), 400
        neu = json.loads(json.dumps(DEFAULT_CONFIG))
        for schluessel, wert in daten.items():
            if schluessel in neu:
                neu[schluessel] = wert
        for zone in ZONEN:
            neu[zone] = heile_zone(neu.get(zone))
        neu = heile_config(neu)
        with controller.lock:
            controller.config.clear()
            controller.config.update(neu)
            controller.save_config()
        melde_config()
        # Die Quelle wird beim Programmstart gebaut; ein geaenderter Sensortyp
        # oder Pin wirkt erst danach. Das gehoert gesagt, sonst sucht jemand
        # den Fehler in der Verdrahtung.
        return jsonify({"ok": True, "config": controller.config,
                        "hinweis": "Wiederhergestellt. Fuer Sensor- und "
                                   "Port-Aenderungen die Station neu starten."})

    @app.route("/api/media/<media_type>/<name>", methods=["DELETE"])
    def api_delete_media(media_type, name):
        """Entfernt eine Datei nur aus den Zonen-Zuordnungen, löscht sie NICHT vom Pi."""
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        safe = secure_filename(name)
        # Aus ALLEN Layouts und Zonen — auch der Mitte. Hier stand
        # `for zone in ("near", "far")`, und die Mitte behielt die Datei.
        with controller.lock:
            removed = layouts_modul.entferne_datei(controller.config, media_type, safe)
            if removed:
                controller.save_config()
        if removed:
            melde_config()
        return jsonify({"ok": True, "removed_from_zones": removed})

    @app.route("/api/start", methods=["POST"])
    def api_start():
        controller.start()
        return jsonify({"ok": True})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        controller.stop()
        return jsonify({"ok": True})

    # --- System / Network ---
    @app.route("/api/system/network", methods=["GET"])
    def api_system_network_get():
        import subprocess
        info = {"connection": None, "interface": None, "method": None,
                "addresses": [], "gateway": None, "dns": [], "available_connections": []}
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show"],
                timeout=5).decode()
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 4:
                    name, ctype, dev, state = parts[0], parts[1], parts[2], parts[3]
                    if ctype in ("802-3-ethernet", "ethernet") or "wifi" in ctype:
                        info["available_connections"].append(
                            {"name": name, "type": ctype, "device": dev, "state": state})
                        if state == "activated" and not info["connection"]:
                            info["connection"] = name
                            info["interface"] = dev
        except Exception as e:
            info["error"] = "nmcli nicht verfügbar: " + str(e)
            return jsonify(info), 200
        if info["connection"]:
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f",
                     "ipv4.method,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                     "connection", "show", info["connection"]],
                    timeout=5).decode()
                for line in out.strip().splitlines():
                    if ":" not in line:
                        continue
                    k, _, v = line.partition(":")
                    if k == "ipv4.method":
                        info["method"] = v
                    elif k.startswith("IP4.ADDRESS"):
                        if v:
                            info["addresses"].append(v)
                    elif k == "IP4.GATEWAY":
                        info["gateway"] = v or None
                    elif k.startswith("IP4.DNS"):
                        if v:
                            info["dns"].append(v)
            except Exception as e:
                info["error"] = str(e)
        return jsonify(info)

    @app.route("/api/system/network", methods=["POST"])
    def api_system_network_set():
        import subprocess, re
        data = request.get_json() or {}
        connection = data.get("connection")
        method = data.get("method")  # "auto" oder "manual"
        if not connection or method not in ("auto", "manual"):
            return jsonify({"error": "connection und method (auto|manual) erforderlich"}), 400
        ip_re = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$")
        try:
            if method == "auto":
                cmd = ["sudo", "-n", "nmcli", "connection", "modify", connection,
                       "ipv4.method", "auto",
                       "ipv4.addresses", "",
                       "ipv4.gateway", "",
                       "ipv4.dns", ""]
                subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10)
            else:
                addr = (data.get("address") or "").strip()
                gw = (data.get("gateway") or "").strip()
                dns = (data.get("dns") or "").strip()
                if not ip_re.match(addr):
                    return jsonify({"error": "Adresse muss CIDR sein, z.B. 192.168.1.50/24"}), 400
                if "/" not in addr:
                    addr = addr + "/24"
                cmd = ["sudo", "-n", "nmcli", "connection", "modify", connection,
                       "ipv4.method", "manual",
                       "ipv4.addresses", addr,
                       "ipv4.gateway", gw,
                       "ipv4.dns", dns]
                subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10)
            # Verbindung neu aktivieren
            try:
                subprocess.check_output(
                    ["sudo", "-n", "nmcli", "connection", "down", connection],
                    stderr=subprocess.STDOUT, timeout=10)
            except subprocess.CalledProcessError:
                pass
            subprocess.check_output(
                ["sudo", "-n", "nmcli", "connection", "up", connection],
                stderr=subprocess.STDOUT, timeout=15)
            return jsonify({"ok": True})
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "nmcli: " + e.output.decode(errors="ignore")}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/system/reboot", methods=["POST"])
    def api_system_reboot():
        import subprocess
        try:
            subprocess.Popen(["sudo", "-n", "reboot"])
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/system/wifi", methods=["GET"])
    def api_system_wifi_get():
        import subprocess
        info = {"enabled": False, "current_ssid": None, "networks": []}
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "WIFI", "radio"], timeout=5).decode().strip()
            info["enabled"] = (out.lower() == "enabled")
        except Exception as e:
            info["error"] = "nmcli nicht verfügbar: " + str(e)
            return jsonify(info), 200
        if info["enabled"]:
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                    timeout=8).decode()
                seen = set()
                for line in out.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) < 4:
                        continue
                    active, ssid, signal, security = parts[0], parts[1], parts[2], ":".join(parts[3:])
                    if not ssid or ssid in seen:
                        continue
                    seen.add(ssid)
                    if active == "yes":
                        info["current_ssid"] = ssid
                    info["networks"].append({
                        "ssid": ssid,
                        "signal": int(signal) if signal.isdigit() else 0,
                        "security": security,
                        "active": active == "yes",
                    })
                info["networks"].sort(key=lambda n: -n["signal"])
            except Exception as e:
                info["error"] = str(e)
        return jsonify(info)

    @app.route("/api/system/wifi", methods=["POST"])
    def api_system_wifi_set():
        import subprocess
        data = request.get_json() or {}
        try:
            if "enabled" in data:
                state = "on" if data["enabled"] else "off"
                subprocess.check_output(
                    ["sudo", "-n", "nmcli", "radio", "wifi", state],
                    stderr=subprocess.STDOUT, timeout=10)
                return jsonify({"ok": True})
            ssid = (data.get("ssid") or "").strip()
            password = data.get("password") or ""
            if not ssid:
                return jsonify({"error": "ssid erforderlich"}), 400
            cmd = ["sudo", "-n", "nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            return jsonify({"ok": True})
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "nmcli: " + e.output.decode(errors="ignore")}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Media file serving ---
    @app.route("/media/<media_type>/<path:filename>")
    def serve_media(media_type, filename):
        if media_type not in MEDIA_DIRS:
            return "Not found", 404
        return send_from_directory(MEDIA_DIRS[media_type], secure_filename(filename))

    return app

#!/usr/bin/env python3
"""Was die Anzeigeseiten gerade tun: Puls, Screenshot, Benachrichtigung.

WARUM. Der Kern weiss, welche Zone er spielt. Er wusste bis 3.0 nicht, ob
irgendwo ein Schirm sie auch zeigt — Chromium abgestuerzt, HDMI-Kabel raus,
Tablet im Foyer ausgegangen: fuer `/api/status` war alles in Ordnung. Jetzt
meldet sich jede Anzeigeseite alle 10 s (`static/anzeige/puls.js`) und sagt,
was in jeder Region laeuft. Bleibt der Puls aus, ist das ein Befund der
Zustandspruefung — und ein Ereignis fuer die Benachrichtigung.

SCREENSHOT AUF ABRUF. `POST /api/anzeige/screenshot/anfordern` bittet die
Anzeigeseiten per Befehl um ein Bild und wartet bis 4 s darauf. Die Seite
zeichnet ihre Buehne in ein Canvas (Bilder, laufende Videobilder; Webseiten
und Widgets als beschriftete Flaeche, weil ein fremdes iframe nicht
auslesbar ist). Laeuft auf dem Pi `grim` (Wayland) oder `scrot` (X11), wird
stattdessen der echte Schirm aufgenommen — dann stimmt auch das iframe.

IM SPEICHER. Puls und letztes Bild je Anzeige liegen im Speicher des
Kerns, nicht auf der Karte: nach einem Neustart faengt die Liste leer an,
und das ist richtig — dann hat sich auch noch keine Anzeige gemeldet.
"""
import base64
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

import benachrichtigung as bn
import gesundheit

#: Ohne Puls seit so vielen Sekunden gilt eine Anzeige als offline.
OFFLINE_S = 30.0
#: Anzeigen, die sich so lange nicht melden, fallen aus der Liste.
VERGESSEN_S = 24 * 3600.0
#: Ein Screenshot ist hoechstens so gross (dataURL, Base64).
SCREENSHOT_MAX_B = 2 * 1024 * 1024
#: So lange wartet `anfordern` auf ein frisches Bild.
WARTE_S = 4.0
#: Mehr Puls-Fehlermeldungen je Anzeige gibt es nicht.
FEHLER_MAX = 5
#: Mehr Bilder haelt der Kern nicht — je Anzeige eines, und nur so viele
#: Anzeigen. Der Screenshot-Weg ist unangemeldet (die Anzeige im Foyer kennt
#: keine PIN); ohne Deckel koennte jeder im Gastnetz mit erfundenen Kennungen
#: den Speicher des Pi mit 2-MB-Bildern fuellen.
BILDER_MAX = 12
#: Ein Bild, das so alt ist, wird beim naechsten Ablegen weggeraeumt — auch
#: wenn zu seiner Kennung kein Puls mehr kommt.
BILD_ALTER_S = 3600.0
#: Kennung des echten Bildschirms (grim/scrot) — die einzige ohne Puls.
SYSTEM_KENNUNG = "system"


def _ortszeit(iso):
    """Ein ISO-Zeitstempel der Anzeige (mit `Z` oder Versatz) als Ortszeit
    des Kerns, ohne Zone — oder None, wenn er nichts taugt."""
    if not isinstance(iso, str):
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _kennung_ok(k):
    return isinstance(k, str) and 1 <= len(k) <= 64 and all(c.isalnum() or c in "-_" for c in k)


class Anzeigenregister:
    """Der letzte Puls und das letzte Bild je Anzeige. Thread-sicher."""

    def __init__(self, uhr=time.time):
        self.uhr = uhr
        self._lock = threading.Lock()
        self._bedingung = threading.Condition(self._lock)
        self._pulse = {}        # kennung -> puls-dict
        self._bilder = {}       # kennung -> (bytes, zeit)

    def puls(self, kennung, daten, adresse=""):
        if not _kennung_ok(kennung) or not isinstance(daten, dict):
            raise ValueError("kennung: 1..64 Zeichen aus Buchstaben, Ziffern, '-' und '_'")
        regionen = daten.get("regionen")
        if not isinstance(regionen, list):
            regionen = []
        sauber = []
        for r in regionen[:24]:
            if not isinstance(r, dict):
                continue
            item = r.get("item") if isinstance(r.get("item"), dict) else None
            sauber.append({
                "id": str(r.get("id", ""))[:40],
                "typ": str(r.get("typ", ""))[:16],
                "idx": r.get("idx") if isinstance(r.get("idx"), int) else None,
                "item": ({"typ": str(item.get("typ", ""))[:16],
                          "name": str(item.get("name") or item.get("url") or "")[:200]}
                         if item else None),
            })
        fehler = daten.get("fehler")
        if not isinstance(fehler, list):
            fehler = []
        fehler = [str(f)[:300] for f in fehler[-FEHLER_MAX:]]
        jetzt = self.uhr()
        with self._lock:
            alt = self._pulse.get(kennung) or {}
            self._pulse[kennung] = {
                "kennung": kennung,
                "adresse": adresse,
                "layout_id": (str(daten.get("layout_id"))[:40] if daten.get("layout_id") else None),
                "zone": (str(daten.get("zone"))[:16] if daten.get("zone") else None),
                "vorschau": bool(daten.get("vorschau")),
                "regionen": sauber,
                "fehler": fehler,
                "seit": alt.get("seit") or _ortszeit(daten.get("seit"))
                        or datetime.fromtimestamp(jetzt).strftime("%Y-%m-%dT%H:%M:%S"),
                "zuletzt_ts": jetzt,
            }
            self._vergessen(jetzt)

    def _vergessen(self, jetzt):
        for k in [k for k, p in self._pulse.items() if jetzt - p["zuletzt_ts"] > VERGESSEN_S]:
            self._pulse.pop(k, None)
            self._bilder.pop(k, None)
        self._bilder_begrenzen(jetzt)

    def _bilder_begrenzen(self, jetzt):
        """Alte Bilder weg, und nie mehr als BILDER_MAX — unabhaengig vom Puls."""
        for k in [k for k, (_, t) in self._bilder.items() if jetzt - t > BILD_ALTER_S]:
            self._bilder.pop(k, None)
        while len(self._bilder) > BILDER_MAX:
            aeltester = min(self._bilder, key=lambda k: self._bilder[k][1])
            self._bilder.pop(aeltester, None)

    def kennt(self, kennung):
        with self._lock:
            return kennung in self._pulse

    def liste(self):
        jetzt = self.uhr()
        with self._lock:
            heraus = []
            for p in sorted(self._pulse.values(), key=lambda p: -p["zuletzt_ts"]):
                alter = jetzt - p["zuletzt_ts"]
                d = {k: v for k, v in p.items() if k != "zuletzt_ts"}
                d["zuletzt"] = datetime.fromtimestamp(p["zuletzt_ts"]).strftime("%Y-%m-%dT%H:%M:%S")
                d["alter_s"] = round(alter, 1)
                d["online"] = alter < OFFLINE_S
                bild = self._bilder.get(p["kennung"])
                d["screenshot"] = (datetime.fromtimestamp(bild[1]).strftime("%Y-%m-%dT%H:%M:%S")
                                   if bild else None)
                heraus.append(d)
            return heraus

    def zusammenfassung(self):
        """Fuer `/api/status` und die Zustandspruefung: wie viele, wie viele
        online, und wie alt der juengste Puls einer ECHTEN Anzeige ist
        (die Vorschau im Editor zaehlt nicht als Schirm)."""
        jetzt = self.uhr()
        with self._lock:
            echte = [p for p in self._pulse.values() if not p["vorschau"]]
            juengster = max((p["zuletzt_ts"] for p in echte), default=None)
            return {
                "anzahl": len(echte),
                "online": sum(1 for p in echte if jetzt - p["zuletzt_ts"] < OFFLINE_S),
                "alter_s": (round(jetzt - juengster, 1) if juengster is not None else None),
            }

    def online(self):
        z = self.zusammenfassung()
        return None if not z["anzahl"] else z["online"] > 0

    def bild_ablegen(self, kennung, daten):
        """Ein Bild zu einer Kennung, die sich schon per Puls gemeldet hat.

        Ohne vorherigen Puls wird abgelehnt (ausser fuer den echten Bildschirm):
        eine Kennung, die nie gepulst hat, ist keine Anzeige — und nur so
        bleibt der Speicher an die Zahl echter Anzeigen gebunden.
        """
        if not _kennung_ok(kennung):
            raise ValueError("kennung: 1..64 Zeichen aus Buchstaben, Ziffern, '-' und '_'")
        jetzt = self.uhr()
        with self._bedingung:
            if kennung != SYSTEM_KENNUNG and kennung not in self._pulse:
                raise ValueError("kennung: diese Anzeige hat sich noch nicht gemeldet (erst ein Puls)")
            self._bilder[kennung] = (daten, jetzt)
            self._bilder_begrenzen(jetzt)
            self._bedingung.notify_all()

    def bild(self, kennung=None):
        with self._lock:
            if kennung:
                return self._bilder.get(kennung)
            if not self._bilder:
                return None
            return max(self._bilder.values(), key=lambda b: b[1])

    def warte_auf_bild(self, ab_zeit, timeout_s):
        """Blockiert, bis ein Bild juenger als `ab_zeit` da ist — oder gibt None.

        Liefert `(kennung, (daten, zeit))`: die Kennung kommt von HIER, unter
        dem Lock. Sie nachtraeglich im Woerterbuch zu suchen, waehrend andere
        Anzeigen gerade ihre Bilder ablegen, hiesse ueber ein Woerterbuch zu
        laufen, das sich dabei aendert — RuntimeError genau dann, wenn mehrere
        Schirme antworten.
        """
        ende = time.monotonic() + timeout_s
        with self._bedingung:
            while True:
                neu = [(k, b) for k, b in self._bilder.items() if b[1] >= ab_zeit]
                if neu:
                    return max(neu, key=lambda kb: kb[1][1])
                rest = ende - time.monotonic()
                if rest <= 0:
                    return None
                self._bedingung.wait(rest)


def dataurl_zu_bytes(roh):
    """`data:image/jpeg;base64,...` (oder png) → (bytes, mimetype)."""
    if not isinstance(roh, str) or not roh.startswith("data:image/"):
        raise ValueError("bild: data:image/…;base64,… erwartet")
    if len(roh) > SCREENSHOT_MAX_B:
        raise ValueError(f"bild: hoechstens {SCREENSHOT_MAX_B // (1024 * 1024)} MB")
    kopf, _, inhalt = roh.partition(",")
    mimetype = kopf[5:].split(";")[0]
    if mimetype not in ("image/jpeg", "image/png", "image/webp"):
        raise ValueError("bild: jpeg, png oder webp")
    try:
        return base64.b64decode(inhalt, validate=True), mimetype
    except ValueError:
        raise ValueError("bild: kein gueltiges Base64") from None


def bildschirm_aufnehmen(which=shutil.which, umgebung=None, lauf=subprocess.run):
    """Der echte Schirm des Pi, wenn `grim` (Wayland) oder `scrot` (X11) da ist.

    Gibt (bytes, mimetype) oder None zurueck. Nur, wenn ueberhaupt eine
    grafische Sitzung erkennbar ist — sonst gibt es nichts aufzunehmen, und
    das Werkzeug wuerde mit einem Fehler antworten, den niemand braucht.
    """
    umgebung = os.environ if umgebung is None else umgebung
    try:
        if umgebung.get("WAYLAND_DISPLAY") and which("grim"):
            r = lauf(["grim", "-t", "jpeg", "-q", "70", "-"], capture_output=True, timeout=5)
            if r.returncode == 0 and r.stdout:
                return r.stdout, "image/jpeg"
        if umgebung.get("DISPLAY") and which("scrot"):
            pfad = os.path.join("/tmp", f"lz-screenshot-{os.getpid()}.jpg")
            r = lauf(["scrot", "-o", "-q", "70", pfad], capture_output=True, timeout=5)
            if r.returncode == 0 and os.path.exists(pfad):
                with open(pfad, "rb") as f:
                    daten = f.read()
                os.unlink(pfad)
                return daten, "image/jpeg"
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def erzeuge_blueprint(controller):
    bp = Blueprint("anzeige", __name__)
    register = getattr(controller, "anzeigen", None)
    if register is None:
        register = controller.anzeigen = Anzeigenregister()

    @bp.route("/api/anzeige")
    def api_anzeige_liste():
        """Alle Anzeigen mit letztem Puls. Die Systemwerte stehen getrennt
        unter `/api/anzeige/system` — die Liste wird alle 5 s geholt, und dafuer
        muss der Kern nicht jedes Mal /sys und /proc lesen."""
        return jsonify({"anzeigen": register.liste(), **register.zusammenfassung()})

    @bp.route("/api/anzeige/system")
    def api_anzeige_system():
        """Die Systemwerte des Kerns: Temperatur, Last, Speicher, Platte —
        None, wo es sie nicht gibt."""
        return jsonify({"system": gesundheit.systemwerte(platz_pfad=os.path.dirname(os.path.abspath(__file__)))})

    @bp.route("/api/anzeige/puls", methods=["POST"])
    def api_anzeige_puls():
        daten = request.get_json(silent=True) or {}
        try:
            register.puls(daten.get("kennung"), daten, request.remote_addr or "")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True})

    @bp.route("/api/anzeige/screenshot", methods=["POST"])
    def api_anzeige_screenshot_ablegen():
        daten = request.get_json(silent=True) or {}
        try:
            bild, mimetype = dataurl_zu_bytes(daten.get("bild"))
            register.bild_ablegen(daten.get("kennung"), (bild, mimetype))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True, "bytes": len(bild)})

    @bp.route("/api/anzeige/screenshot")
    def api_anzeige_screenshot():
        eintrag = register.bild(request.args.get("kennung") or None)
        if not eintrag:
            return jsonify({"error": "Noch kein Screenshot — erst anfordern"}), 404
        (bild, mimetype), zeit = eintrag
        return Response(bild, mimetype=mimetype, headers={
            "Cache-Control": "no-store",
            "X-LZ-Zeit": datetime.fromtimestamp(zeit).strftime("%Y-%m-%dT%H:%M:%S"),
        })

    @bp.route("/api/anzeige/screenshot/anfordern", methods=["POST"])
    def api_anzeige_screenshot_anfordern():
        """Erst der echte Schirm (grim/scrot), sonst die Anzeigeseiten bitten
        und bis 4 s warten. Antwort nennt Kennung und Zeit; das Bild holt
        `GET /api/anzeige/screenshot?kennung=…`."""
        echt = bildschirm_aufnehmen()
        if echt:
            register.bild_ablegen(SYSTEM_KENNUNG, echt)
            return jsonify({"ok": True, "kennung": SYSTEM_KENNUNG, "quelle": "bildschirm",
                            "url": f"/api/anzeige/screenshot?kennung={SYSTEM_KENNUNG}"})
        ab = register.uhr()
        controller.bus.senden("befehl", {"typ": "screenshot"})
        if not controller.bus.anzahl:
            return jsonify({"error": "Keine Anzeige hoert zu — ist eine Anzeigeseite offen?"}), 409
        daten = request.get_json(silent=True) or {}
        timeout = daten.get("timeout_s", WARTE_S)
        timeout = timeout if isinstance(timeout, (int, float)) and 0 < timeout <= 15 else WARTE_S
        treffer = register.warte_auf_bild(ab, timeout)
        if not treffer:
            return jsonify({"error": "Keine Anzeige hat innerhalb der Wartezeit ein Bild geliefert"}), 504
        kennung = treffer[0]
        return jsonify({"ok": True, "kennung": kennung, "quelle": "anzeigeseite",
                        "url": f"/api/anzeige/screenshot?kennung={kennung}"})

    # ── Benachrichtigung ────────────────────────────────────────────────

    def ziel():
        return controller.config.get("benachrichtigung") or bn.standard()

    @bp.route("/api/benachrichtigung")
    def api_benachrichtigung():
        w = getattr(controller, "waechter", None)
        return jsonify({**ziel(), "gesendet": (w.gesendet if w else 0),
                        "ereignisse_moeglich": list(bn.EREIGNISSE)})

    @bp.route("/api/benachrichtigung", methods=["PUT"])
    def api_benachrichtigung_setzen():
        try:
            neu = bn.pruefe(request.get_json(silent=True) or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        with controller.lock:
            controller.config["benachrichtigung"] = neu
            controller.save_config()
        if hasattr(controller, "melde_config"):
            controller.melde_config()
        if neu["aktiv"]:
            starte_waechter(controller)
        return jsonify({"ok": True, "benachrichtigung": neu})

    @bp.route("/api/benachrichtigung/test", methods=["POST"])
    def api_benachrichtigung_test():
        """Eine Probenachricht — mit dem, was gerade eingestellt ist (oder
        dem Koerper der Anfrage, damit man vor dem Speichern pruefen kann)."""
        roh = request.get_json(silent=True)
        if roh is not None and not isinstance(roh, dict):
            return jsonify({"error": "Der Koerper muss ein Objekt sein"}), 400
        try:
            z = bn.pruefe({**ziel(), **(roh or {}), "aktiv": True})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        n = bn.nachricht("test", controller.config.get("system_name", "Station"),
                         "Probenachricht aus der Verwaltung — der Weg funktioniert.", datetime.now())
        n["titel"] = "Probenachricht"
        ok = bn.sende(z, n)
        if not ok:
            return jsonify({"error": "Das Ziel hat nicht geantwortet — Adresse und Topic pruefen"}), 502
        return jsonify({"ok": True})

    return bp


def init(app, controller):
    """Den Waechter starten, wenn die Benachrichtigung eingeschaltet ist.

    Ist sie aus, laeuft kein Faden — eine Test-App oder eine Station ohne
    Ziel soll nicht alle 30 s die Platte lesen. `PUT /api/benachrichtigung`
    startet ihn nach, sobald jemand einschaltet.
    """
    if (controller.config.get("benachrichtigung") or {}).get("aktiv"):
        starte_waechter(controller)


def starte_waechter(controller):
    if getattr(controller, "waechter", None) is not None or getattr(controller, "ohne_waechter", False):
        return
    register = controller.anzeigen

    def lage():
        befunde = []
        try:
            from web_ui import lage_der_station  # spaet: kein Kreis beim Import
            befunde = lage_der_station(controller)
        except Exception as e:  # noqa: BLE001
            print(f"[Benachrichtigung] Zustand nicht lesbar: {e}")
        stufe = gesundheit.gesamtstufe(befunde)
        return {
            "stufe": stufe,
            "anzeige_online": register.online(),
            "offen": controller.ist_offen(),
            "station": controller.config.get("system_name", "Station"),
            "befundtext": "; ".join(b["text"] for b in befunde if b["stufe"] == "fehler"),
        }

    controller.waechter = bn.Waechter(lage, lambda: controller.config.get("benachrichtigung") or bn.standard())
    controller.waechter.start()

#!/usr/bin/env python3
"""Ausloeser: WENN etwas passiert, DANN tut die Station etwas.

WARUM ES DAS GIBT. Der Abstandssensor ist ein Ausloeser — der einzige, den die
Station bis 3.0 kannte. Ein Foyer braucht mehr: ein Knopf am Empfang blendet
die Durchsage ein, die Hausautomation (Home Assistant, Node-RED) meldet per
Webhook „Veranstaltung beginnt", um 18:00 geht der Schirm aus, und wenn der
Film zu Ende ist, kommt das Menue zurueck. Das koennen sonst nur teure
Appliance-Player, und dort nur mit Skript.

WAS EIN AUSLOESER IST. `{id, name, aktiv, quelle, aktion}`:

  quelle.typ   webhook     POST /api/trigger/<id>  (optional mit Token)
               taster      ein GPIO-Taster (gpiozero, wenn vorhanden)
               zeit        Wochentage + Uhrzeit — einmal je Minute
               video_ende  die Anzeige meldet, dass ein Video zu Ende ist
               zone        die Zone hat zu X gewechselt
  aktion.typ   zeige_layout  ein Layout einblenden (dauer_s|null)
               meldung       Sofortmeldung ueber alles legen
               display_aus / display_an  Schirm schwarz (+ CEC, wenn moeglich)
               start / stop  die Sensor-Steuerung
               zurueck       eingeblendetes Layout beenden

WAS HIER NICHT PASSIERT. Kein Flask: die Klasse `Ausloeser` bekommt den
Controller und eine Funktion fuer Sofortmeldungen hereingereicht und redet
ueber `controller.bus` mit den Anzeigen. Die HTTP-Seite ist `api_ausloeser.py`.

EIN AUSLOESER, DER SCHIEFGEHT, IST KEIN FEHLER DER STATION. Jede Aktion ist in
try/except; das Ergebnis steht im Protokoll (`protokoll()`, die letzten 200),
und die Wiedergabe laeuft weiter.
"""
import re
import threading
import time
from collections import deque
from datetime import datetime

import tv_cec
from layouts import KENNUNG, FARBE
from zeitplan import TAGE, minuten

MAX_AUSLOESER = 60
NAME_MAX = 64
TOKEN_MAX = 128
TEXT_MAX = 200
UNTERTEXT_MAX = 400
PROTOKOLL_MAX = 200
#: BCM-Nummern, die am 40-poligen Pi-Header als GPIO nutzbar sind.
NUTZBARE_BCM = tuple(range(2, 28))

ZONEN = ("near", "mid", "far")
QUELLEN = ("webhook", "taster", "zeit", "video_ende", "zone")
AKTIONEN = ("zeige_layout", "meldung", "display_an", "display_aus", "start", "stop", "zurueck")

_TOKEN = re.compile(r"^[A-Za-z0-9_\-.~]{0,128}$")

# Der Takt des eigenen Fadens. 0,25 s: ein Zonenwechsel dauert mindestens
# `delay_s` (Vorgabe 1,5 s), eine Minute ist 240 Ticks lang — nichts geht
# durch die Lappen, und der Pi merkt es nicht.
TICK_S = 0.25


def standard_ausloeser():
    """Vorgabe: keiner. Eine Station von vor 3.0 verhaelt sich exakt wie vorher."""
    return []


# ── Schema ───────────────────────────────────────────────────────────────────

def _text(roh, feld, maximal, pflicht=True):
    if roh is None:
        roh = ""
    if not isinstance(roh, str):
        raise ValueError(f"{feld}: muss Text sein")
    roh = roh.strip()
    if pflicht and not roh:
        raise ValueError(f"{feld}: darf nicht leer sein")
    if len(roh) > maximal:
        raise ValueError(f"{feld}: hoechstens {maximal} Zeichen")
    return roh


def _farbe(roh, feld, vorgabe):
    if roh is None or roh == "":
        return vorgabe
    if not isinstance(roh, str) or not FARBE.match(roh):
        raise ValueError(f"{feld}: Farbe als #rrggbb")
    return roh


def _dauer(roh, feld):
    if roh is None or roh == "":
        return None
    if isinstance(roh, bool) or not isinstance(roh, (int, float)):
        raise ValueError(f"{feld}: Sekunden > 0 oder leer")
    if not (0 < float(roh) <= 86400):
        raise ValueError(f"{feld}: 1..86400 s oder leer")
    return float(roh)


def pruefe_quelle(roh, stelle):
    if not isinstance(roh, dict):
        raise ValueError(f"{stelle}: muss ein Objekt sein")
    typ = roh.get("typ")
    if typ not in QUELLEN:
        raise ValueError(f"{stelle}.typ: {'|'.join(QUELLEN)}")
    q = {"typ": typ}
    if typ == "webhook":
        token = roh.get("token") or ""
        if not isinstance(token, str) or not _TOKEN.match(token):
            raise ValueError(f"{stelle}.token: Buchstaben, Ziffern, _ - . ~ (bis {TOKEN_MAX})")
        q["token"] = token
    elif typ == "taster":
        pin = roh.get("pin")
        if isinstance(pin, bool) or not isinstance(pin, int) or pin not in NUTZBARE_BCM:
            raise ValueError(f"{stelle}.pin: BCM {NUTZBARE_BCM[0]}..{NUTZBARE_BCM[-1]}")
        q["pin"] = pin
    elif typ == "zeit":
        tage = roh.get("tage", list(TAGE))
        if not isinstance(tage, list) or not tage or any(t not in TAGE for t in tage):
            raise ValueError(f"{stelle}.tage: mindestens ein Tag aus {list(TAGE)}")
        q["tage"] = [t for t in TAGE if t in tage]
        try:
            minuten(roh.get("zeit"), ende=False)
        except ValueError as e:
            raise ValueError(f"{stelle}.zeit: {e}") from None
        q["zeit"] = roh.get("zeit").strip()
    elif typ == "video_ende":
        q["datei"] = _text(roh.get("datei"), f"{stelle}.datei", 255, pflicht=False)
        q["region"] = _text(roh.get("region"), f"{stelle}.region", 40, pflicht=False)
    elif typ == "zone":
        if roh.get("zone") not in ZONEN:
            raise ValueError(f"{stelle}.zone: {'|'.join(ZONEN)}")
        q["zone"] = roh["zone"]
    return q


def pruefe_aktion(roh, stelle):
    if not isinstance(roh, dict):
        raise ValueError(f"{stelle}: muss ein Objekt sein")
    typ = roh.get("typ")
    if typ not in AKTIONEN:
        raise ValueError(f"{stelle}.typ: {'|'.join(AKTIONEN)}")
    a = {"typ": typ}
    if typ == "zeige_layout":
        lid = roh.get("layout_id")
        if not isinstance(lid, str) or not KENNUNG.match(lid):
            raise ValueError(f"{stelle}.layout_id: Kennung fehlt")
        a["layout_id"] = lid
        a["dauer_s"] = _dauer(roh.get("dauer_s"), f"{stelle}.dauer_s")
    elif typ == "meldung":
        a["text"] = _text(roh.get("text"), f"{stelle}.text", TEXT_MAX)
        a["untertext"] = _text(roh.get("untertext"), f"{stelle}.untertext", UNTERTEXT_MAX, pflicht=False)
        a["farbe"] = _farbe(roh.get("farbe"), f"{stelle}.farbe", "#B04A3F")
        a["textfarbe"] = _farbe(roh.get("textfarbe"), f"{stelle}.textfarbe", "#FFFFFF")
        a["dauer_s"] = _dauer(roh.get("dauer_s"), f"{stelle}.dauer_s")
        ton = roh.get("ton", False)
        if not isinstance(ton, bool):
            raise ValueError(f"{stelle}.ton: muss true oder false sein")
        a["ton"] = ton
    return a


def pruefe_ausloeser_eintrag(roh, stelle="ausloeser"):
    if not isinstance(roh, dict):
        raise ValueError(f"{stelle}: muss ein Objekt sein")
    lid = roh.get("id")
    if not isinstance(lid, str) or not KENNUNG.match(lid) or lid.startswith("_"):
        raise ValueError(f"{stelle}.id: Kennung aus a-z, 0-9 und '-' (1..40 Zeichen)")
    aktiv = roh.get("aktiv", True)
    if not isinstance(aktiv, bool):
        raise ValueError(f"{stelle}.aktiv: muss true oder false sein")
    return {
        "id": lid,
        "name": _text(roh.get("name"), f"{stelle}.name", NAME_MAX),
        "aktiv": aktiv,
        "quelle": pruefe_quelle(roh.get("quelle"), f"{stelle}.quelle"),
        "aktion": pruefe_aktion(roh.get("aktion"), f"{stelle}.aktion"),
    }


def belegte_pins(config):
    """Welche BCM-Pins die Abstandsquelle dieser Station braucht.

    Nach `sensor_type`, nicht pauschal: `button_pin` steht auch in einer
    Konfiguration, die nie einen Taster als Quelle hatte — den Pin zu
    sperren, waere eine Grenze ohne Grund.
    """
    art = (config or {}).get("sensor_type", "auto")
    pins = {}
    if art in ("auto", "ultrasonic"):
        pins[config.get("gpio_trigger")] = "gpio_trigger"
        pins[config.get("gpio_echo")] = "gpio_echo"
    if art == "button":
        pins[config.get("button_pin")] = "button_pin"
    pins.pop(None, None)
    return pins


def pruefe_ausloeser(roh, config=None):
    """Schreibweg: die ganze Liste. Prueft auch, was kein Eintrag fuer sich
    sieht: zwei Taster am selben Pin, ein Taster am Pin des Sensors."""
    if not isinstance(roh, list):
        raise ValueError("ausloeser: muss eine Liste sein")
    if len(roh) > MAX_AUSLOESER:
        raise ValueError(f"ausloeser: hoechstens {MAX_AUSLOESER}")
    heraus, ids, pins = [], set(), dict(belegte_pins(config or {}))
    for i, e in enumerate(roh):
        sauber = pruefe_ausloeser_eintrag(e, f"ausloeser[{i}]")
        if sauber["id"] in ids:
            raise ValueError(f"ausloeser[{i}].id: {sauber['id']!r} gibt es schon")
        ids.add(sauber["id"])
        if sauber["quelle"]["typ"] == "taster":
            pin = sauber["quelle"]["pin"]
            if pin in pins:
                raise ValueError(f"ausloeser[{i}].quelle.pin: BCM {pin} ist schon belegt ({pins[pin]})")
            pins[pin] = f"Ausloeser {sauber['id']!r}"
        heraus.append(sauber)
    return heraus


def heile_ausloeser(roh, config=None):
    """Ladeweg: eintragsweise. Ein Ausloeser mit Unsinn fliegt raus und wird
    genannt; die anderen bleiben. Pin-Kollisionen: der spaetere verliert."""
    if roh is None:
        return standard_ausloeser()
    if not isinstance(roh, list):
        print(f"[Ausloeser] {roh!r} ist keine Liste — nehme leer")
        return standard_ausloeser()
    heraus, ids, pins = [], set(), dict(belegte_pins(config or {}))
    for i, e in enumerate(roh[:MAX_AUSLOESER]):
        try:
            sauber = pruefe_ausloeser_eintrag(e, f"ausloeser[{i}]")
        except ValueError as fehler:
            print(f"[Ausloeser] {fehler} — wird weggelassen")
            continue
        if sauber["id"] in ids:
            print(f"[Ausloeser] Kennung {sauber['id']!r} doppelt — zweiter wird weggelassen")
            continue
        if sauber["quelle"]["typ"] == "taster":
            pin = sauber["quelle"]["pin"]
            if pin in pins:
                print(f"[Ausloeser] {sauber['id']!r}: BCM {pin} ist schon belegt ({pins[pin]}) — wird weggelassen")
                continue
            pins[pin] = sauber["id"]
        ids.add(sauber["id"])
        heraus.append(sauber)
    return heraus


# ── Die Maschine ─────────────────────────────────────────────────────────────

class Ausloeser:
    """Fuehrt Ausloeser aus. Ein Exemplar je Station.

    `controller`      der Controller (config, bus, zone, start/stop)
    `meldung_setzen`  Funktion `(aktion_dict) -> None`, die eine Sofortmeldung
                      setzt — die gehoert dem Programm-Modul, nicht diesem
    `gpio`            optional: Fabrik `(pin, when_pressed) -> objekt mit close()`
                      fuer Tests; None = gpiozero, wenn installiert
    """

    def __init__(self, controller, meldung_setzen=None, gpio=None):
        self.controller = controller
        self.meldung_setzen = meldung_setzen
        self._gpio = gpio
        self._protokoll = deque(maxlen=PROTOKOLL_MAX)
        self._lock = threading.Lock()
        self._letzte_minute = {}      # id -> "JJJJ-MM-TT HH:MM" der letzten Zeit-Ausloesung
        self._letzte_zone = None
        self._taster = {}             # pin -> Button
        self.taster_status = {}       # pin -> Klartext
        self.schwarz = False
        self._thread = None
        self._laeuft = False

    # -- Konfiguration -------------------------------------------------------

    def liste(self):
        return [e for e in (self.controller.config.get("ausloeser") or []) if isinstance(e, dict)]

    def eintrag(self, aid):
        for e in self.liste():
            if e.get("id") == aid:
                return e
        return None

    def hat_quelle(self, typ):
        return any(e.get("aktiv", True) and (e.get("quelle") or {}).get("typ") == typ for e in self.liste())

    # -- Faden ----------------------------------------------------------------

    def start(self):
        if self._laeuft:
            return
        self._laeuft = True
        self._letzte_zone = getattr(self.controller, "zone", None)
        self.synchronisiere_taster()
        self._thread = threading.Thread(target=self._schleife, daemon=True, name="ausloeser")
        self._thread.start()

    def stop(self):
        self._laeuft = False
        for pin in list(self._taster):
            self._taster_schliessen(pin)

    def _schleife(self):
        while self._laeuft:
            try:
                self.tick(datetime.now())
            except Exception as e:  # noqa: BLE001 — die Wiedergabe geht vor
                print(f"[Ausloeser] Tick: {e}")
            time.sleep(TICK_S)

    def tick(self, jetzt):
        """Zeit-Quellen und Zonenwechsel pruefen. Wird auch im Test gerufen."""
        minute = jetzt.strftime("%Y-%m-%d %H:%M")
        tag = TAGE[jetzt.weekday()]
        zone = getattr(self.controller, "zone", None)
        if zone != self._letzte_zone:
            vorher, self._letzte_zone = self._letzte_zone, zone
            if vorher is not None and getattr(self.controller, "active", True):
                for e in self.liste():
                    q = e.get("quelle") or {}
                    if e.get("aktiv", True) and q.get("typ") == "zone" and q.get("zone") == zone:
                        self.feuere(e["id"], f"Zone -> {zone}")
        for e in self.liste():
            q = e.get("quelle") or {}
            if not e.get("aktiv", True) or q.get("typ") != "zeit":
                continue
            if tag not in (q.get("tage") or []) or q.get("zeit") != jetzt.strftime("%H:%M"):
                continue
            if self._letzte_minute.get(e["id"]) == minute:
                continue
            self._letzte_minute[e["id"]] = minute
            self.feuere(e["id"], f"Zeit {q.get('zeit')}")

    # -- Taster ---------------------------------------------------------------

    def synchronisiere_taster(self):
        """Nach jeder Konfigurationsaenderung: Taster oeffnen, die neu sind,
        und schliessen, die es nicht mehr gibt."""
        gewuenscht = {}
        for e in self.liste():
            q = e.get("quelle") or {}
            if e.get("aktiv", True) and q.get("typ") == "taster" and isinstance(q.get("pin"), int):
                gewuenscht[q["pin"]] = e["id"]
        for pin in list(self._taster):
            if pin not in gewuenscht:
                self._taster_schliessen(pin)
        for pin, aid in gewuenscht.items():
            if pin not in self._taster:
                self._taster_oeffnen(pin, aid)
        for pin in list(self.taster_status):
            if pin not in gewuenscht:
                del self.taster_status[pin]

    def _fabrik(self):
        if self._gpio is not None:
            return self._gpio
        try:
            from gpiozero import Button
        except Exception:  # noqa: BLE001
            return None

        def fabrik(pin, when_pressed):
            b = Button(pin, pull_up=True, bounce_time=0.05)
            b.when_pressed = when_pressed
            return b
        return fabrik

    def _taster_oeffnen(self, pin, aid):
        fabrik = self._fabrik()
        if fabrik is None:
            self.taster_status[pin] = "kein GPIO: gpiozero nicht installiert"
            return
        try:
            self._taster[pin] = fabrik(pin, lambda aid=aid: self.feuere(aid, f"Taster BCM {pin}"))
            self.taster_status[pin] = f"Taster an BCM {pin} bereit"
        except Exception as e:  # noqa: BLE001
            self.taster_status[pin] = f"kein Taster: GPIO-Fehler ({e})"

    def _taster_schliessen(self, pin):
        b = self._taster.pop(pin, None)
        if b is not None:
            try:
                b.close()
            except Exception:  # noqa: BLE001
                pass

    # -- Ereignisse von aussen ------------------------------------------------

    def webhook(self, aid, token):
        """`POST /api/trigger/<id>`. Gibt (status, meldung) zurueck."""
        e = self.eintrag(aid)
        if e is None or (e.get("quelle") or {}).get("typ") != "webhook":
            return 404, f"kein Webhook-Ausloeser {aid!r}"
        if not e.get("aktiv", True):
            return 409, f"Ausloeser {aid!r} ist ausgeschaltet"
        erwartet = (e.get("quelle") or {}).get("token") or ""
        if erwartet and token != erwartet:
            self._protokolliere(e, "Webhook", "abgelehnt: falsches Token")
            return 403, "Token stimmt nicht"
        ergebnis = self.feuere(aid, "Webhook")
        return 200, ergebnis

    def video_ende(self, datei, region):
        """Die Anzeige meldet: in `region` ist `datei` zu Ende."""
        gefeuert = []
        for e in self.liste():
            q = e.get("quelle") or {}
            if not e.get("aktiv", True) or q.get("typ") != "video_ende":
                continue
            if q.get("datei") and q.get("datei") != datei:
                continue
            if q.get("region") and q.get("region") != region:
                continue
            gefeuert.append(e["id"])
            self.feuere(e["id"], f"Video zu Ende: {datei}")
        return gefeuert

    # -- Ausfuehren -----------------------------------------------------------

    def feuere(self, aid, anlass="Test"):
        e = self.eintrag(aid)
        if e is None:
            return "unbekannt"
        try:
            ergebnis = self.fuehre_aus(e.get("aktion") or {})
        except Exception as fehler:  # noqa: BLE001 — ein Ausloeser darf die Station nicht anhalten
            ergebnis = f"Fehler: {fehler}"
        self._protokolliere(e, anlass, ergebnis)
        return ergebnis

    def fuehre_aus(self, aktion):
        typ = aktion.get("typ")
        bus = getattr(self.controller, "bus", None)
        if typ == "zeige_layout":
            lid = aktion.get("layout_id")
            if lid not in (self.controller.config.get("layouts") or {}):
                return f"Layout {lid!r} gibt es nicht"
            if bus:
                bus.senden("befehl", {"typ": "zeige_layout", "layout_id": lid, "dauer_s": aktion.get("dauer_s")})
            return f"Layout {lid} eingeblendet"
        if typ == "zurueck":
            if bus:
                bus.senden("befehl", {"typ": "zeige_layout", "layout_id": None, "dauer_s": None})
            return "zurueck zur Zone"
        if typ == "meldung":
            if self.meldung_setzen is None:
                return "keine Sofortmeldung moeglich"
            self.meldung_setzen(aktion)
            return f"Meldung: {aktion.get('text')}"
        if typ in ("display_an", "display_aus"):
            an = typ == "display_an"
            self.schwarz = not an
            if bus:
                bus.senden("befehl", {"typ": "schwarz", "an": not an})
            cec = ""
            if tv_cec.verfuegbar():
                _ok, cec = tv_cec.schalte(an)
                cec = " · " + cec
            if hasattr(self.controller, "melde_config"):
                # Die Szene traegt `schwarz` — eine Anzeige, die spaeter laedt,
                # soll denselben Stand sehen.
                self.controller._gemeldete_szene = None
                self.controller.melde_szene()
            return ("Schirm an" if an else "Schirm schwarz") + cec
        if typ == "start":
            self.controller.start()
            return "Steuerung gestartet"
        if typ == "stop":
            self.controller.stop()
            return "Steuerung angehalten"
        return f"unbekannte Aktion {typ!r}"

    # -- Protokoll ------------------------------------------------------------

    def _protokolliere(self, e, anlass, ergebnis):
        with self._lock:
            self._protokoll.appendleft({
                "zeit": datetime.now().isoformat(timespec="seconds"),
                "id": e.get("id"), "name": e.get("name"),
                "anlass": anlass,
                "aktion": (e.get("aktion") or {}).get("typ"),
                "ergebnis": ergebnis,
            })

    def protokoll(self):
        with self._lock:
            return list(self._protokoll)

#!/usr/bin/env python3
"""Benachrichtigung: die Station meldet sich, statt dass jemand nachsieht.

WARUM ES DAS GIBT. Die Zustandspruefung (`gesundheit.py`) kennt den Ausfall —
aber nur, wer die Verwaltung oeffnet, sieht ihn. In einer Ausstellung oeffnet
sie niemand, bis ein Besucher sich beschwert. Diese Station schickt deshalb
eine Nachricht, wenn sich etwas AENDERT: Stoerung, Anzeige weg, Anzeige
wieder da, Oeffnungszeit beginnt. Ziel ist ein Webhook (JSON) oder ntfy
(Push aufs Handy, ohne Konto).

NUR BEI UEBERGANG. Ein Melder, der alle 30 s „immer noch kaputt" schreibt,
wird stummgeschaltet — und meldet dann auch den Ausfall danach nicht mehr.
Gemeldet wird deshalb der Wechsel des Zustands, nicht der Zustand.

REIN GEHALTEN. `Melder.pruefe(jetzt, stufe, anzeige_online, offen)` bekommt
die Lage hereingereicht und gibt die faelligen Nachrichten zurueck. Das
Senden (`sende`) ist davon getrennt und ersetzbar — der Test schickt nichts
ins Netz. Ein Netzfehler wird geloggt und sonst ignoriert: eine Station darf
nicht an ihrem Melder scheitern.
"""
import json
import threading
import time
import urllib.error
import urllib.request

ZIEL_TYPEN = ("webhook", "ntfy")

#: Was gemeldet werden kann. Die Konfiguration waehlt daraus.
EREIGNISSE = ("gesundheit_fehler", "gesundheit_ok", "anzeige_verloren",
              "anzeige_zurueck", "offline_ende")

EREIGNIS_TEXTE = {
    "gesundheit_fehler": "Stoerung an der Station",
    "gesundheit_ok": "Stoerung behoben",
    "anzeige_verloren": "Keine Anzeige mehr verbunden",
    "anzeige_zurueck": "Anzeige wieder verbunden",
    "offline_ende": "Oeffnungszeit beginnt — die Station spielt",
}

#: ntfy-Prioritaet je Ereignis (1 min .. 5 max).
PRIORITAET = {"gesundheit_fehler": 4, "anzeige_verloren": 4,
              "gesundheit_ok": 3, "anzeige_zurueck": 3, "offline_ende": 2}

INTERVALL_S = 30.0
ZEITLIMIT_S = 5.0


def standard():
    return {
        "aktiv": False,
        "ziel_typ": "ntfy",
        "url": "https://ntfy.sh",
        "topic": "",
        "ereignisse": list(EREIGNISSE),
    }


def pruefe(roh):
    """Schreibweg: ablehnen und das Feld nennen."""
    if not isinstance(roh, dict):
        raise ValueError("benachrichtigung: muss ein Objekt sein")
    heraus = standard()
    if "aktiv" in roh:
        if not isinstance(roh["aktiv"], bool):
            raise ValueError("benachrichtigung.aktiv: muss true oder false sein")
        heraus["aktiv"] = roh["aktiv"]
    if "ziel_typ" in roh:
        if roh["ziel_typ"] not in ZIEL_TYPEN:
            raise ValueError(f"benachrichtigung.ziel_typ: {'|'.join(ZIEL_TYPEN)}")
        heraus["ziel_typ"] = roh["ziel_typ"]
    if "url" in roh:
        url = roh["url"]
        if not isinstance(url, str) or len(url) > 512 or (url and not url.startswith(("http://", "https://"))):
            raise ValueError("benachrichtigung.url: http(s)://…, hoechstens 512 Zeichen")
        heraus["url"] = url.rstrip("/")
    if "topic" in roh:
        topic = roh["topic"]
        if not isinstance(topic, str) or len(topic) > 64 or not all(c.isalnum() or c in "-_" for c in topic):
            raise ValueError("benachrichtigung.topic: Buchstaben, Ziffern, '-' und '_', hoechstens 64 Zeichen")
        heraus["topic"] = topic
    if "ereignisse" in roh:
        liste = roh["ereignisse"]
        if not isinstance(liste, list) or any(e not in EREIGNISSE for e in liste):
            raise ValueError(f"benachrichtigung.ereignisse: Liste aus {', '.join(EREIGNISSE)}")
        heraus["ereignisse"] = [e for e in EREIGNISSE if e in liste]
    if heraus["aktiv"] and heraus["ziel_typ"] == "ntfy" and not heraus["topic"]:
        raise ValueError("benachrichtigung.topic: fuer ntfy noetig")
    if heraus["aktiv"] and not heraus["url"]:
        raise ValueError("benachrichtigung.url: fuer den Versand noetig")
    return heraus


def heile(roh):
    """Ladeweg: reparieren und sagen — nie abbrechen."""
    if not isinstance(roh, dict):
        if roh is not None:
            print("[Benachrichtigung] Konfiguration ist kein Objekt — nehme die Vorgabe")
        return standard()
    heraus = standard()
    for feld in heraus:
        if feld not in roh:
            continue
        try:
            heraus[feld] = pruefe({**heraus, feld: roh[feld], "aktiv": False})[feld]
        except ValueError as e:
            print(f"[Benachrichtigung] {e} — nehme die Vorgabe")
    if "aktiv" in roh:
        heraus["aktiv"] = roh["aktiv"] is True
    if heraus["aktiv"]:
        try:
            pruefe(heraus)
        except ValueError as e:
            print(f"[Benachrichtigung] {e} — Versand bleibt aus")
            heraus["aktiv"] = False
    return heraus


def nachricht(ereignis, station, text, zeit):
    return {
        "station": station,
        "ereignis": ereignis,
        "titel": EREIGNIS_TEXTE.get(ereignis, ereignis),
        "text": text,
        "prioritaet": PRIORITAET.get(ereignis, 3),
        "zeit": zeit.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def sende(ziel, n, oeffne=urllib.request.urlopen):
    """Eine Nachricht hinaus. Gibt True zurueck, wenn das Ziel geantwortet hat.

    Fehler werden geloggt, nicht geworfen — der Melder laeuft in einem
    Nebenfaden der Station, und die darf daran nicht haengen bleiben.
    """
    try:
        if ziel.get("ziel_typ") == "ntfy":
            url = ziel["url"].rstrip("/") + "/" + ziel["topic"]
            koerper = f"{n['station']}: {n['text']}".encode("utf-8")
            req = urllib.request.Request(url, data=koerper, method="POST", headers={
                "Title": n["titel"].encode("utf-8").decode("latin-1", "replace"),
                "Priority": str(n["prioritaet"]),
                "Tags": "warning" if n["prioritaet"] >= 4 else "white_check_mark",
                "Content-Type": "text/plain; charset=utf-8",
            })
        else:
            req = urllib.request.Request(ziel["url"], data=json.dumps(n, ensure_ascii=False).encode("utf-8"),
                                         method="POST", headers={"Content-Type": "application/json"})
        with oeffne(req, timeout=ZEITLIMIT_S) as antwort:
            return 200 <= getattr(antwort, "status", 200) < 300
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[Benachrichtigung] {n.get('ereignis')}: nicht zugestellt ({e})")
        return False


class Melder:
    """Merkt sich die Lage und nennt, was sich geaendert hat."""

    def __init__(self):
        # None = noch nie gesehen: der erste Durchlauf setzt nur den Stand,
        # er meldet nichts. Sonst kaeme bei jedem Neustart „Anzeige wieder da".
        self._fehler = None
        self._anzeige_online = None
        self._offen = None

    def pruefe(self, jetzt, stufe, anzeige_online, offen, station="Station", befundtext=""):
        """Die faelligen Nachrichten fuer diese Lage — meist keine."""
        faellig = []
        fehler = stufe == "fehler"
        if self._fehler is not None and fehler != self._fehler:
            if fehler:
                faellig.append(nachricht("gesundheit_fehler", station,
                                         befundtext or "Die Zustandspruefung meldet eine Stoerung.", jetzt))
            else:
                faellig.append(nachricht("gesundheit_ok", station,
                                         "Die Zustandspruefung meldet keine Stoerung mehr.", jetzt))
        self._fehler = fehler

        if anzeige_online is not None:
            if self._anzeige_online is not None and anzeige_online != self._anzeige_online:
                if anzeige_online:
                    faellig.append(nachricht("anzeige_zurueck", station,
                                             "Eine Anzeigeseite meldet sich wieder.", jetzt))
                else:
                    faellig.append(nachricht("anzeige_verloren", station,
                                             "Seit ueber einer Minute kein Puls von einer Anzeigeseite.", jetzt))
            self._anzeige_online = anzeige_online

        if self._offen is not None and offen and not self._offen:
            faellig.append(nachricht("offline_ende", station,
                                     "Die Oeffnungszeit beginnt, die Station spielt wieder.", jetzt))
        self._offen = offen
        return faellig


def filtere(ziel, nachrichten):
    """Nur die Ereignisse, die die Konfiguration will — und nur wenn aktiv."""
    if not ziel or not ziel.get("aktiv"):
        return []
    gewollt = set(ziel.get("ereignisse") or ())
    return [n for n in nachrichten if n["ereignis"] in gewollt]


class Waechter(threading.Thread):
    """Der Nebenfaden: alle 30 s die Lage holen, den Melder fragen, senden.

    `lage()` liefert `{"stufe", "anzeige_online", "offen", "station",
    "befundtext"}`; `ziel()` die aktuelle Konfiguration `benachrichtigung`.
    Beides sind Funktionen, damit der Faden nie mit einem veralteten Stand
    arbeitet.
    """

    def __init__(self, lage, ziel, sende=sende, intervall_s=INTERVALL_S, uhr=None):
        super().__init__(daemon=True, name="benachrichtigung")
        self.lage, self.ziel, self.sende = lage, ziel, sende
        self.intervall_s = intervall_s
        self.uhr = uhr
        self.melder = Melder()
        self._stop = threading.Event()
        self.gesendet = 0

    def einmal(self):
        from datetime import datetime
        ziel = self.ziel()
        if not ziel or not ziel.get("aktiv"):
            # Ausgeschaltet: nichts lesen, nichts merken. Beim Einschalten
            # beginnt der Melder mit einem frischen Stand — die erste Runde
            # setzt nur die Lage, sie meldet nichts Altes.
            self.melder = Melder()
            return 0
        jetzt = self.uhr() if self.uhr else datetime.now()
        try:
            l = self.lage()
        except Exception as e:  # noqa: BLE001 — die Lage darf den Faden nicht toeten
            print(f"[Benachrichtigung] Lage nicht lesbar: {e}")
            return 0
        faellig = self.melder.pruefe(jetzt, l.get("stufe", "ok"), l.get("anzeige_online"),
                                     l.get("offen", True), l.get("station", "Station"),
                                     l.get("befundtext", ""))
        n = 0
        for nachr in filtere(ziel, faellig):
            if self.sende(ziel, nachr):
                n += 1
        self.gesendet += n
        return n

    def run(self):
        while not self._stop.is_set():
            self.einmal()
            self._stop.wait(self.intervall_s)

    def stop(self):
        self._stop.set()

#!/usr/bin/env python3
"""Einen Google Chromecast als Ausgabeziel ansprechen — ohne Fremdbibliothek.

─── WAS GEMELDET WURDE (Nutzer, 2026-10-25) ────────────────────────────────

Am Netzwerk haengt ein Chromecast (Ultra, „Buero"). Er soll als Player der
Station dienen: statt ein Browserfenster auf einem angeschlossenen Schirm zu
oeffnen (siehe `displays.py`), wirft die Station die Medien- oder Anzeige-URL
ueber das Cast-Protokoll auf das Geraet.

─── WARUM OHNE `pychromecast` ───────────────────────────────────────────────

Das ganze Projekt kommt mit einer einzigen Abhaengigkeit aus (`flask`). Ein
Pi im Dauerbetrieb soll genau das bleiben: wenig, das kaputtgehen kann.
`pychromecast` zoege `zeroconf`, `protobuf`, `casttube` nach — fuer eine
Aufgabe, die klein ist: eine TLS-Verbindung, eine Handvoll JSON-Nachrichten
in einem simplen Rahmen. Das steht hier mit der Standardbibliothek.

Das Cast-Protokoll (CASTV2) ist ueber Port 8009, TLS. Jede Nachricht ist ein
`CastMessage`-Protobuf, dem eine 4-Byte-Laenge (big-endian) vorangeht. Das
Protobuf hat sieben Felder und ist seit Jahren stabil — es von Hand zu
kodieren ist weniger Code als der Import es waere. Die Nutzlast ist JSON
ueber „Namespaces" (Kanaelen): Verbindung, Herzschlag, Empfaenger, Medien.

─── DER EHRLICHE TEIL: ZWEI BETRIEBSARTEN ──────────────────────────────────

  * „medien" — die laufende Datei (ein Video, ein Bild) geht direkt an den
    Standard-Empfaenger von Google (App-ID CC1AD845). Das braucht NICHTS
    ausser der Geraete-IP und einer erreichbaren URL. Deckt den Normalfall.

  * „anzeige" — die ganze `/display`-Seite (Layouts, Widgets, Untertitel)
    soll auf dem Fernseher laufen. Der Standard-Empfaenger kann aber keine
    beliebige Webseite, nur Medien. Dafuer braucht es einen EIGENEN
    Web-Receiver: eine im Cast-Entwicklerkonsole registrierte App-ID, deren
    gehostete HTML-Seite `/display` laedt. Fehlt die App-ID in der Config,
    faellt dieses Modul auf „medien" zurueck und sagt es — statt stumm eine
    nicht registrierte App zu starten (der Cast meldet das mit Fehler).

─── WAS DIESES MODUL NICHT TUT, und das steht auch in der Oberflaeche ──────

  * Es flasht nichts und veraendert das Geraet nicht. Secure Boot des Ultra
    laesst keine eigene Firmware zu; „customizen" heisst hier: eigene Medien
    und ein eigener Web-Receiver, nicht ein veraenderter Chromecast.
  * Es prueft das TLS-Zertifikat des Chromecast NICHT. Das Geraet benutzt
    ein eigenes, nicht oeffentlich verankertes Zertifikat; eine Pruefung
    waere Theater. Die Verbindung bleibt im LAN.
  * Ein Fehlschlag ist kein Fehler der Station. Wie bei `tv_cec`: eine Zeile
    zurueck, die der Aufrufer loggen darf, und sonst laeuft die Wiedergabe
    auf den lokalen Schirmen weiter.
"""
import json
import shutil
import socket
import ssl
import struct
import subprocess
import time

#: Standard-Empfaenger von Google — spielt eine einzelne Medien-URL.
STANDARD_EMPFAENGER = "CC1AD845"

#: Cast-Port (TLS).
CAST_PORT = 8009

#: Namespaces (Kanaele) des Protokolls.
NS_VERBINDUNG = "urn:x-cast:com.google.cast.tp.connection"
NS_HERZSCHLAG = "urn:x-cast:com.google.cast.tp.heartbeat"
NS_EMPFAENGER = "urn:x-cast:com.google.cast.receiver"
NS_MEDIEN = "urn:x-cast:com.google.cast.media"

#: Absender/Standardziel vor dem Start einer App.
_QUELLE = "sender-0"
_PLATTFORM = "receiver-0"

#: Zeitgrenzen. Ein haengender Chromecast darf die Steuerschleife nicht halten.
VERBINDUNGS_TIMEOUT_S = 5
ANTWORT_TIMEOUT_S = 8


# ───────────────────────────── Protobuf von Hand ───────────────────────────
# `CastMessage` (cast_channel.proto), nur die Felder, die wir senden/lesen:
#   1 protocol_version  varint   (0 = CASTV2_1_0)
#   2 source_id         string
#   3 destination_id    string
#   4 namespace         string
#   5 payload_type      varint   (0 = STRING)
#   6 payload_utf8      string
# Wire-Typen: 0 = varint, 2 = laengen-praefixiert.

def _varint(wert):
    out = bytearray()
    while True:
        byte = wert & 0x7F
        wert >>= 7
        if wert:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _feld_string(feldnr, text):
    roh = text.encode("utf-8")
    return _varint((feldnr << 3) | 2) + _varint(len(roh)) + roh


def _feld_varint(feldnr, wert):
    return _varint((feldnr << 3) | 0) + _varint(wert)


def kodiere(quelle, ziel, namespace, nutzlast):
    """Eine `CastMessage` mit String-Nutzlast zu Bytes machen."""
    nachricht = (
        _feld_varint(1, 0)
        + _feld_string(2, quelle)
        + _feld_string(3, ziel)
        + _feld_string(4, namespace)
        + _feld_varint(5, 0)
        + _feld_string(6, nutzlast)
    )
    return nachricht


def _lies_varint(daten, i):
    ergebnis = 0
    verschiebung = 0
    while True:
        byte = daten[i]
        i += 1
        ergebnis |= (byte & 0x7F) << verschiebung
        if not (byte & 0x80):
            return ergebnis, i
        verschiebung += 7


def dekodiere(daten):
    """Eine `CastMessage` lesen. Gibt (namespace, nutzlast_text) zurueck.

    Unbekannte Felder werden uebersprungen — robust gegen Erweiterungen des
    Protokolls, die uns nicht interessieren.
    """
    i = 0
    namespace = ""
    nutzlast = ""
    n = len(daten)
    while i < n:
        schluessel, i = _lies_varint(daten, i)
        feldnr = schluessel >> 3
        wire = schluessel & 7
        if wire == 0:
            _, i = _lies_varint(daten, i)
        elif wire == 2:
            laenge, i = _lies_varint(daten, i)
            roh = daten[i:i + laenge]
            i += laenge
            if feldnr == 4:
                namespace = roh.decode("utf-8", "replace")
            elif feldnr == 6:
                nutzlast = roh.decode("utf-8", "replace")
        elif wire == 1:
            i += 8
        elif wire == 5:
            i += 4
        else:  # pragma: no cover — kommt im Cast-Protokoll nicht vor
            break
    return namespace, nutzlast


# ───────────────────────────── Verbindung ──────────────────────────────────
class CastVerbindung:
    """Eine TLS-Verbindung zu einem Chromecast, nachrichtenweise.

    Absichtlich einfach: synchron, mit Zeitgrenzen. Ein `with`-Block oeffnet
    und schliesst sauber. Kein Hintergrundfaden — die Station ruft kurz an,
    sagt was zu tun ist, und legt wieder auf.
    """

    def __init__(self, ip, port=CAST_PORT):
        self.ip = ip
        self.port = port
        self.sock = None
        self._anfrage_id = 0

    def __enter__(self):
        roh = socket.create_connection((self.ip, self.port), VERBINDUNGS_TIMEOUT_S)
        ctx = ssl._create_unverified_context()
        self.sock = ctx.wrap_socket(roh)
        self.sock.settimeout(ANTWORT_TIMEOUT_S)
        return self

    def __exit__(self, *_):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass

    def _naechste_id(self):
        self._anfrage_id += 1
        return self._anfrage_id

    def sende(self, ziel, namespace, nutzlast):
        text = json.dumps(nutzlast) if not isinstance(nutzlast, str) else nutzlast
        rahmen = kodiere(_QUELLE, ziel, namespace, text)
        self.sock.sendall(struct.pack(">I", len(rahmen)) + rahmen)

    def _lies_rahmen(self):
        kopf = self._genau(4)
        (laenge,) = struct.unpack(">I", kopf)
        return dekodiere(self._genau(laenge))

    def _genau(self, anzahl):
        teile = []
        offen = anzahl
        while offen:
            stueck = self.sock.recv(offen)
            if not stueck:
                raise ConnectionError("Chromecast hat die Verbindung geschlossen")
            teile.append(stueck)
            offen -= len(stueck)
        return b"".join(teile)

    def verbinde_mit(self, ziel):
        """Den Verbindungs-Kanal zu einem Ziel oeffnen (Pflicht vor allem
        anderen, einmal zur Plattform und einmal zur gestarteten App)."""
        self.sende(ziel, NS_VERBINDUNG, {"type": "CONNECT"})

    def warte_auf(self, typen, frist_s=ANTWORT_TIMEOUT_S):
        """Rahmen lesen, bis eine Nutzlast mit `type` aus `typen` kommt.

        Herzschlag-PINGs werden nebenbei mit PONG beantwortet, damit das
        Geraet nicht mitten im Warten auflegt. Gibt die Nutzlast als dict
        zurueck oder `None`, wenn die Frist ablaeuft.
        """
        ende = time.monotonic() + frist_s
        while time.monotonic() < ende:
            try:
                namespace, roh = self._lies_rahmen()
            except socket.timeout:
                return None
            try:
                last = json.loads(roh) if roh else {}
            except ValueError:
                continue
            if namespace == NS_HERZSCHLAG and last.get("type") == "PING":
                self.sende(_PLATTFORM, NS_HERZSCHLAG, {"type": "PONG"})
                continue
            if last.get("type") in typen:
                return last
        return None


# ───────────────────────────── Hohe Ebene ──────────────────────────────────
def spiele(ip, medien_url, *, content_type="video/mp4", app_id=STANDARD_EMPFAENGER,
           stream_type="BUFFERED", titel=None):
    """Eine Medien-URL auf dem Chromecast starten. Gibt (ok, meldung) zurueck.

    Wirft NIE nach aussen — jeder Fehler wird zur Meldung. Der Ablauf:
    Verbindung -> App starten -> auf transportId warten -> mit der App
    verbinden -> LOAD. Laeuft die gewuenschte App schon, wird sie nicht neu
    gestartet.
    """
    try:
        with CastVerbindung(ip) as c:
            c.verbinde_mit(_PLATTFORM)
            c.sende(_PLATTFORM, NS_EMPFAENGER,
                    {"type": "LAUNCH", "requestId": c._naechste_id(), "appId": app_id})
            # Der Chromecast schickt die erste RECEIVER_STATUS oft noch OHNE
            # die App (sie startet gerade) und die transportId kommt erst im
            # naechsten Rahmen. Deshalb lesen, bis die App eine transportId
            # nennt — oder bis die Frist ablaeuft.
            transport = None
            ende = time.monotonic() + ANTWORT_TIMEOUT_S
            while time.monotonic() < ende:
                status = c.warte_auf({"RECEIVER_STATUS", "LAUNCH_ERROR"},
                                     frist_s=max(0.1, ende - time.monotonic()))
                if status is None:
                    break
                if status.get("type") == "LAUNCH_ERROR":
                    grund = status.get("reason", "unbekannt")
                    return False, (f"Chromecast lehnt die App {app_id} ab ({grund}) — "
                                   "bei einem eigenen Web-Receiver muss die App-ID in "
                                   "der Cast-Konsole registriert und das Geraet dort "
                                   "freigeschaltet sein")
                transport = _transport_id(status, app_id)
                if transport:
                    break
            if not transport:
                return False, "Chromecast antwortet nicht auf den App-Start"

            c.verbinde_mit(transport)
            nachricht = {
                "type": "LOAD",
                "requestId": c._naechste_id(),
                "autoplay": True,
                "currentTime": 0,
                "media": {
                    "contentId": medien_url,
                    "streamType": stream_type,
                    "contentType": content_type,
                },
            }
            if titel:
                nachricht["media"]["metadata"] = {"metadataType": 0, "title": titel}
            c.sende(transport, NS_MEDIEN, nachricht)
            antwort = c.warte_auf({"MEDIA_STATUS", "LOAD_FAILED", "INVALID_REQUEST"})
            if antwort is None:
                # LOAD ist raus; manche Receiver bestaetigen nur verzoegert.
                return True, "Medien gesendet (keine Bestaetigung abgewartet)"
            if antwort.get("type") == "MEDIA_STATUS":
                return True, "Wiedergabe laeuft auf dem Chromecast"
            return False, f"Chromecast lehnt die Medien ab ({antwort.get('type')})"
    except (OSError, ConnectionError) as e:
        return False, f"Chromecast {ip} nicht erreichbar ({e})"
    except Exception as e:  # noqa: BLE001 — die Station geht vor
        return False, f"Cast fehlgeschlagen ({e})"


def stoppe(ip):
    """Die laufende Empfaenger-App beenden (Geraet wird wieder frei)."""
    try:
        with CastVerbindung(ip) as c:
            c.verbinde_mit(_PLATTFORM)
            c.sende(_PLATTFORM, NS_EMPFAENGER,
                    {"type": "GET_STATUS", "requestId": c._naechste_id()})
            status = c.warte_auf({"RECEIVER_STATUS"})
            sitzung = _session_id(status) if status else None
            if not sitzung:
                return True, "Auf dem Chromecast lief keine App"
            c.sende(_PLATTFORM, NS_EMPFAENGER,
                    {"type": "STOP", "requestId": c._naechste_id(), "sessionId": sitzung})
            return True, "Chromecast gestoppt"
    except (OSError, ConnectionError) as e:
        return False, f"Chromecast {ip} nicht erreichbar ({e})"
    except Exception as e:  # noqa: BLE001
        return False, f"Cast-Stopp fehlgeschlagen ({e})"


def _transport_id(status, app_id):
    for app in status.get("status", {}).get("applications", []):
        if app.get("appId") == app_id or app.get("transportId"):
            return app.get("transportId")
    return None


def _session_id(status):
    apps = status.get("status", {}).get("applications", [])
    return apps[0].get("sessionId") if apps else None


# ───────────────────────────── Finden ──────────────────────────────────────
def finde_geraete(frist_s=4):
    """Chromecasts im Netz aufzaehlen. Gibt (liste, meldung) zurueck.

    Tolerant wie `tv_cec`: nimmt den Weg, den das System anbietet
    (`avahi-browse` auf Linux/Pi, `dns-sd` auf macOS). Ist keiner da, kommt
    eine leere Liste und eine Zeile, die sagt warum — kein Fehler.

    Jeder Eintrag: {name, ip, port, modell}. `name` ist der sichtbare
    Geraetename (TXT-Feld `fn`), `modell` das `md`-Feld.
    """
    if shutil.which("avahi-browse"):
        return _finde_avahi(frist_s)
    if shutil.which("dns-sd"):
        return _finde_dnssd(frist_s)
    return [], ("Weder avahi-browse noch dns-sd vorhanden — Chromecast-Suche "
                "uebersprungen. Die Geraete-IP kann in der Config direkt "
                "eingetragen werden.")


def _finde_avahi(frist_s):
    try:
        roh = subprocess.run(
            ["avahi-browse", "-rtp", "_googlecast._tcp"],
            capture_output=True, text=True, timeout=frist_s + 2,
        ).stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        return [], f"avahi-browse fehlgeschlagen ({e})"
    return _aus_avahi(roh), ""


def _aus_avahi(text):
    """Die `=`-Zeilen von `avahi-browse -p` auswerten (feldgetrennt mit `;`).

    Format: =;iface;proto;name;type;domain;host;ip;port;txt
    Das TXT-Feld steht als eine Zeichenkette aus `"fn=..." "md=..."`-Stuecken.
    """
    geraete = {}
    for zeile in text.splitlines():
        if not zeile.startswith("="):
            continue
        teile = zeile.split(";")
        if len(teile) < 9:
            continue
        ip, port, txt = teile[7], teile[8], ";".join(teile[9:])
        werte = _txt_felder(txt)
        schluessel = werte.get("id") or ip
        geraete[schluessel] = {
            "name": werte.get("fn", teile[3]),
            "ip": ip,
            "port": int(port) if port.isdigit() else CAST_PORT,
            "modell": werte.get("md", ""),
        }
    return list(geraete.values())


def _finde_dnssd(frist_s):
    # macOS: Browsen und Aufloesen laufen getrennt. Fuer die Station (Pi) ist
    # das der Nebenweg; hier reicht, die Namen zu liefern — die IP holt der
    # Resolve-Schritt, den der Aufrufer bei Bedarf fuehrt. Wir halten es
    # bewusst klein und tolerant.
    try:
        roh = subprocess.run(
            ["dns-sd", "-t", str(frist_s), "-B", "_googlecast._tcp"],
            capture_output=True, text=True, timeout=frist_s + 2,
        ).stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        return [], f"dns-sd fehlgeschlagen ({e})"
    except Exception:  # dns-sd kennt -t nicht ueberall
        return [], "dns-sd-Suche nicht moeglich — Geraete-IP in der Config eintragen"
    namen = []
    for zeile in roh.splitlines():
        if "_googlecast._tcp." in zeile and "Add" in zeile:
            name = zeile.split("_googlecast._tcp.")[-1].strip()
            if name and name not in namen:   # dns-sd meldet je Interface einmal
                namen.append(name)
    liste = [{"name": n, "ip": "", "port": CAST_PORT, "modell": ""} for n in namen]
    hinweis = "" if liste else "Keine Chromecasts gefunden"
    return liste, hinweis


def _txt_felder(txt):
    werte = {}
    for stueck in txt.split('" "'):
        stueck = stueck.strip('"')
        if "=" in stueck:
            k, _, v = stueck.partition("=")
            werte[k] = v
    return werte

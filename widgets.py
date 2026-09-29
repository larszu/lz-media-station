#!/usr/bin/env python3
"""Server-Seite der Widgets: Abruf, Parsen, Zwischenspeicher (3.0, Welle 2).

WARUM ES DAS GIBT. Die Widgets laufen im Browser der Anzeige
(`static/anzeige/widgets.js`). Drei von ihnen brauchen Daten aus dem Netz:
RSS, Kalender (ICS) und Wetter. Der Browser darf die nicht selbst holen —
fremde Server erlauben das selten (CORS), und ein Schirm im Foyer soll nicht
mit seinem Browser bei fremden Diensten anklopfen. Also holt der Kern, parst
und liefert ein kleines JSON, das die Anzeige ohne Nachdenken zeigen kann.

DREI REGELN, DIE HIER GELTEN:

* **Nur die Standardbibliothek.** Kein `feedparser`, kein `icalendar`, kein
  `requests`. `requirements.txt` hat einen Eintrag, und das soll so bleiben —
  ein Pi in einer Ausstellung hat keinen Paketmanager, den jemand pflegt.
* **Ohne Netz kein Absturz.** Jeder Abruf hat 5 s Zeit. Scheitert er, kommt
  das zuletzt Geholte (als `veraltet` markiert) — und wenn es das nicht gibt,
  eine Fehlerantwort, die das Widget in eine dezente Zeile verwandelt. Der
  Schirm bleibt an.
* **Nur GET, nur http(s), keine Cookies, hoechstens 1 MB.** Der Proxy ist
  kein offener Tunnel: `file://` und Co. werden abgewiesen, Antworten werden
  abgeschnitten, und wir geben nichts von uns weiter.

Die Parser (`parse_rss`, `parse_ics`) sind REIN — sie bekommen Text und
liefern Listen. Nur deshalb sind Feeds mit Eigenheiten (Atom, RRULE ueber
Mitternacht, gefaltete Zeilen) in der CI testbar, ohne ins Netz zu gehen.
"""
import http.client
import ipaddress
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

try:  # Zeitzonen aus dem ICS (TZID=Europe/Berlin) — ab Python 3.9 dabei
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#: Eigene HTML-Widgets: ein Ordner je Widget mit `index.html`.
WIDGETS_DIR = os.path.join(BASE_DIR, "widgets")

#: Wie lange eine Antwort gilt, bevor neu geholt wird. Ueberschreibbar per
#: Umgebung — ein Ticker mit Eilmeldungen will kuerzer, ein Pi im Museum laenger.
CACHE_TTL_S = float(os.environ.get("LZ_WIDGET_CACHE_S", "300") or 300)
ZEITGRENZE_S = 5.0
MAX_BYTES = 1_000_000
BENUTZER_AGENT = "LZ-Media-Station/3.0 (+https://github.com/larszu/lz-media-station)"

#: Ordnername eines eigenen Widgets: kein Punkt, kein Schraegstrich.
WIDGET_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")

#: Darf der Proxy Ziele im eigenen Netz holen (127.0.0.1, 192.168.x, fe80::)?
#: Vorgabe nein: die Anzeige soll ueber den Kern keine LAN-Geraete abfragen
#: koennen, die selbst keine Anmeldung verlangen. Wer einen Kalender vom
#: NAS im selben Netz zeigen will, setzt LZ_WIDGET_PRIVATE_ZIELE=1.
PRIVATE_ZIELE_ERLAUBT = os.environ.get("LZ_WIDGET_PRIVATE_ZIELE", "") in ("1", "ja", "true")

#: Mehr Eintraege haelt der Zwischenspeicher nicht — jede Adresse ist ein
#: Schluessel, und wer den Proxy mit immer neuen Adressen fuettert, darf
#: den Pi nicht in den Speichertod treiben.
CACHE_MAX_EINTRAEGE = 200


class Abrufsfehler(Exception):
    """Der Abruf ist gescheitert — Grund im Text, fuer die Antwort an das Widget."""


# --------------------------------------------------------------------------
# Abruf
# --------------------------------------------------------------------------

def pruefe_url(url):
    """Nur http(s) mit Host. Alles andere ist kein Feed, sondern ein Angriff
    (`file:///etc/passwd`) oder ein Tippfehler — beides wird benannt."""
    if not isinstance(url, str) or not url.strip():
        raise Abrufsfehler("url: fehlt")
    teile = urllib.parse.urlsplit(url.strip())
    if teile.scheme not in ("http", "https"):
        raise Abrufsfehler("url: nur http:// und https://")
    if not teile.netloc:
        raise Abrufsfehler("url: kein Host")
    return url.strip()


def _ist_privat(adresse):
    ip = ipaddress.ip_address(adresse)
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified)


def pruefe_ziel(url):
    """Zeigt der Host ins eigene Netz? Dann ist der Proxy kein Feed-Holer
    mehr, sondern ein Tor: `http://192.168.1.1/` waere der Router, `127.0.0.1`
    die Station selbst. Namen werden aufgeloest und jede Adresse geprueft;
    laesst sich ein Name nicht aufloesen, entscheidet der Abruf selbst."""
    if PRIVATE_ZIELE_ERLAUBT:
        return
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        adressen = [host] if ipaddress.ip_address(host) else []
    except ValueError:
        try:
            adressen = {a[4][0] for a in socket.getaddrinfo(host, None)}
        except (socket.gaierror, UnicodeError, OSError):
            return
    for a in adressen:
        try:
            if _ist_privat(a.split("%", 1)[0]):
                raise Abrufsfehler("url: Ziele im eigenen Netz holt der Proxy nicht")
        except ValueError:
            continue


def hole_url(url, max_bytes=MAX_BYTES, zeitgrenze=ZEITGRENZE_S, nur_kopf=False):
    """GET ohne Cookies; liefert (bytes, headers). Mehr als `max_bytes` gilt
    als Fehler — ein Feed von 50 MB ist keiner."""
    url = pruefe_url(url)
    pruefe_ziel(url)
    anfrage = urllib.request.Request(url, headers={
        "User-Agent": BENUTZER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, text/calendar, "
                  "application/json, text/xml, application/xml;q=0.9, */*;q=0.5",
    })
    try:
        with urllib.request.urlopen(anfrage, timeout=zeitgrenze) as antwort:
            kopf = {k.lower(): v for k, v in antwort.headers.items()}
            if nur_kopf:
                return b"", kopf
            daten = antwort.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise Abrufsfehler(f"Server antwortet mit {e.code}") from None
    except urllib.error.URLError as e:
        raise Abrufsfehler(f"nicht erreichbar ({e.reason})") from None
    except (TimeoutError, OSError) as e:
        raise Abrufsfehler(f"nicht erreichbar ({e})") from None
    except (http.client.HTTPException, ValueError) as e:
        # InvalidURL (Leerzeichen in der Adresse), IncompleteRead, LineTooLong:
        # alles Abruffehler, kein Grund fuer eine 500-Seite — und der
        # Zwischenspeicher soll das Alte liefern koennen.
        raise Abrufsfehler(f"Abruf gescheitert ({e.__class__.__name__}: {e})") from None
    if len(daten) > max_bytes:
        raise Abrufsfehler(f"Antwort groesser als {max_bytes // 1000} kB")
    return daten, kopf


def _text_aus(daten, kopf):
    """Bytes zu Text — Zeichensatz aus dem Header, sonst UTF-8, sonst latin-1.
    Ein Feed mit falschem Zeichensatz soll Sonderzeichen verlieren, nicht
    das ganze Widget."""
    typ = kopf.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", typ)
    for zeichensatz in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
        try:
            return daten.decode(zeichensatz)
        except (UnicodeDecodeError, LookupError):
            continue
    return daten.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Zwischenspeicher
# --------------------------------------------------------------------------

class Cache:
    """Ein Wert je Schluessel, mit Zeitstempel.

    `hole` ruft den Lader nur, wenn der Eintrag fehlt oder aelter als `ttl`
    ist. Scheitert der Lader, kommt der ALTE Wert zurueck — mit dem Vermerk
    `veraltet`, damit das Widget es sagen kann. Ohne alten Wert wird der
    Fehler weitergereicht: dann gab es diesen Feed nie, und eine leere Liste
    zu erfinden waere eine Luege auf dem Schirm.
    """

    def __init__(self, uhr=time.monotonic):
        self._werte = {}
        self._lock = threading.Lock()
        self._uhr = uhr

    def hole(self, schluessel, lader, ttl=None):
        ttl = CACHE_TTL_S if ttl is None else ttl
        jetzt = self._uhr()
        with self._lock:
            eintrag = self._werte.get(schluessel)
        if eintrag and jetzt - eintrag[0] < ttl:
            return dict(eintrag[1], veraltet=False, aus_cache=True)
        try:
            wert = lader()
        except Abrufsfehler as e:
            if eintrag:
                return dict(eintrag[1], veraltet=True, aus_cache=True, fehler=str(e))
            raise
        with self._lock:
            self._werte[schluessel] = (jetzt, wert)
            self._deckeln(jetzt, ttl)
        return dict(wert, veraltet=False, aus_cache=False)

    def _deckeln(self, jetzt, ttl):
        """Unter dem Lock: erst alles weg, was doppelt abgelaufen ist, dann
        die aeltesten, bis der Deckel wieder passt."""
        if len(self._werte) <= CACHE_MAX_EINTRAEGE:
            return
        for k in [k for k, (t, _) in self._werte.items() if jetzt - t > 2 * max(ttl, 1.0)]:
            del self._werte[k]
        while len(self._werte) > CACHE_MAX_EINTRAEGE:
            aeltester = min(self._werte, key=lambda k: self._werte[k][0])
            del self._werte[aeltester]

    def __len__(self):
        with self._lock:
            return len(self._werte)

    def leeren(self):
        with self._lock:
            self._werte.clear()


CACHE = Cache()


# --------------------------------------------------------------------------
# RSS / Atom
# --------------------------------------------------------------------------

def _lokal(tag):
    """`{http://www.w3.org/2005/Atom}entry` -> `entry`."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _kind_text(element, *namen):
    for kind in element:
        if _lokal(kind.tag) in namen and (kind.text or "").strip():
            return kind.text.strip()
    return ""


def _atom_link(element):
    for kind in element:
        if _lokal(kind.tag) == "link":
            if kind.get("rel", "alternate") == "alternate" and kind.get("href"):
                return kind.get("href")
    for kind in element:
        if _lokal(kind.tag) == "link" and kind.get("href"):
            return kind.get("href")
    return ""


def _zeit_aus_text(text):
    """RFC 822 (RSS) oder ISO 8601 (Atom) -> ISO mit Zeitzone; unlesbar -> None."""
    if not text:
        return None
    text = text.strip()
    try:
        return parsedate_to_datetime(text).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _entferne_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_rss(text, anzahl=20):
    """RSS 2.0 oder Atom -> {"titel", "eintraege": [{titel, link, zeit, quelle, text}]}.

    Neueste zuerst, wenn Zeiten da sind; sonst in Feed-Reihenfolge. Rein:
    kein Netz, kein Dateisystem.
    """
    try:
        wurzel = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        raise Abrufsfehler(f"kein lesbarer Feed ({e})") from None
    art = _lokal(wurzel.tag)
    eintraege = []
    if art == "rss" or art == "RDF":
        kanal = next((k for k in wurzel if _lokal(k.tag) == "channel"), wurzel)
        quelle = _kind_text(kanal, "title")
        # RSS 1.0 (RDF) haengt die <item> NEBEN den <channel>, nicht hinein —
        # deshalb von der Wurzel aus suchen, das findet beide Formen.
        items = [k for k in wurzel.iter() if _lokal(k.tag) == "item"]
        for item in items:
            eintraege.append({
                "titel": _entferne_html(_kind_text(item, "title")),
                "link": _kind_text(item, "link"),
                "zeit": _zeit_aus_text(_kind_text(item, "pubDate", "date")),
                "text": _entferne_html(_kind_text(item, "description"))[:300],
                "quelle": quelle,
            })
    elif art == "feed":
        quelle = _kind_text(wurzel, "title")
        for entry in (k for k in wurzel if _lokal(k.tag) == "entry"):
            eintraege.append({
                "titel": _entferne_html(_kind_text(entry, "title")),
                "link": _atom_link(entry),
                "zeit": _zeit_aus_text(_kind_text(entry, "updated", "published")),
                "text": _entferne_html(_kind_text(entry, "summary", "content"))[:300],
                "quelle": quelle,
            })
    else:
        raise Abrufsfehler(f"kein RSS- oder Atom-Feed (Wurzel <{art}>)")
    eintraege = [e for e in eintraege if e["titel"]]
    if all(e["zeit"] for e in eintraege):
        # Nicht am Text sortieren: "09:30+00:00" ist SPAETER als "10:00+02:00".
        eintraege.sort(key=lambda e: datetime.fromisoformat(e["zeit"]), reverse=True)
    return {"titel": quelle, "eintraege": eintraege[:max(1, int(anzahl))]}


def rss_laden(url, anzahl=20, ttl=None):
    def lader():
        daten, kopf = hole_url(url)
        return parse_rss(_text_aus(daten, kopf), anzahl=50)
    ergebnis = CACHE.hole(("rss", url), lader, ttl)
    ergebnis["eintraege"] = ergebnis["eintraege"][:max(1, int(anzahl))]
    return ergebnis


# --------------------------------------------------------------------------
# ICS (iCalendar)
# --------------------------------------------------------------------------

_ICS_WOCHENTAGE = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _ics_entfalten(text):
    """Gefaltete Zeilen (Fortsetzung beginnt mit Leerzeichen/Tab) zusammensetzen."""
    zeilen = []
    for zeile in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if zeile[:1] in (" ", "\t") and zeilen:
            zeilen[-1] += zeile[1:]
        else:
            zeilen.append(zeile)
    return zeilen


def _ics_eigenschaft(zeile):
    """`DTSTART;TZID=Europe/Berlin:20260601T090000` -> ("DTSTART", {"TZID": …}, wert)."""
    if ":" not in zeile:
        return None, {}, ""
    kopf, wert = zeile.split(":", 1)
    teile = kopf.split(";")
    name = teile[0].upper()
    params = {}
    for p in teile[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return name, params, wert


def _ics_unescape(text):
    return (text.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\")).strip()


def _ics_zeit(wert, params):
    """DATE oder DATE-TIME -> (datetime|date, ganztags)."""
    wert = wert.strip()
    if params.get("VALUE") == "DATE" or (len(wert) == 8 and wert.isdigit()):
        return datetime.strptime(wert, "%Y%m%d").date(), True
    utc = wert.endswith("Z")
    roh = wert.rstrip("Z")
    try:
        dt = datetime.strptime(roh, "%Y%m%dT%H%M%S")
    except ValueError:
        dt = datetime.strptime(roh, "%Y%m%dT%H%M")
    if utc:
        return dt.replace(tzinfo=timezone.utc), False
    tzid = params.get("TZID")
    if tzid and ZoneInfo is not None:
        try:
            return dt.replace(tzinfo=ZoneInfo(tzid)), False
        except Exception:  # unbekannte Zone: als Ortszeit der Station nehmen
            pass
    return dt, False


def _ics_dauer(wert):
    """`PT1H30M`, `P1D` -> timedelta (nur die gaengigen Formen)."""
    m = re.match(r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", wert.strip())
    if not m:
        return timedelta(0)
    vz, w, d, h, mi, s = m.groups()
    delta = timedelta(weeks=int(w or 0), days=int(d or 0), hours=int(h or 0),
                      minutes=int(mi or 0), seconds=int(s or 0))
    return -delta if vz == "-" else delta


#: Zeitzone, in der Termine auf dem Schirm stehen. None = Ortszeit des Rechners
#: (auf dem Pi die richtige). Tests setzen sie fest, damit der CI-Runner in UTC
#: dasselbe rechnet wie die Station in Berlin.
ANZEIGE_ZONE = None


def _vergleichbar(t):
    """Fuer Sortierung/Fenster: alles zu naiver Ortszeit, Datum zu Mitternacht."""
    if isinstance(t, datetime):
        if t.tzinfo is not None:
            t = t.astimezone(ANZEIGE_ZONE).replace(tzinfo=None)
        return t
    return datetime(t.year, t.month, t.day)


def _rrule_parsen(wert):
    regel = {}
    for teil in wert.split(";"):
        if "=" in teil:
            k, v = teil.split("=", 1)
            regel[k.upper()] = v
    return regel


def _wiederholungen(start, regel, von, bis):
    """Termine einer RRULE (FREQ=DAILY|WEEKLY) im Fenster [von, bis].

    Mehr als diese beiden Frequenzen kann kein Museums-Kalender brauchen, den
    ein Foyer-Schirm zeigt — und MONTHLY/YEARLY mit BYSETPOS & Co. richtig zu
    bauen ist eine eigene Bibliothek. Unbekanntes wird als Einzeltermin
    behandelt, nicht erfunden.
    """
    freq = regel.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY"):
        return [start]
    intervall = max(1, int(regel.get("INTERVAL", "1") or 1))
    anzahl = int(regel["COUNT"]) if regel.get("COUNT", "").isdigit() else None
    until = None
    if regel.get("UNTIL"):
        u, _ = _ics_zeit(regel["UNTIL"], {})
        until = _vergleichbar(u) if not isinstance(u, date) or isinstance(u, datetime) else datetime(u.year, u.month, u.day, 23, 59, 59)
    ist_datum = not isinstance(start, datetime)
    start_v = _vergleichbar(start)
    termine = []
    if freq == "DAILY":
        schritt = timedelta(days=intervall)
        t = start_v
        n = 0
        while t <= bis and (anzahl is None or n < anzahl) and (until is None or t <= until):
            if t >= von:
                termine.append(t)
            t += schritt
            n += 1
    else:
        tage = [_ICS_WOCHENTAGE[d] for d in regel.get("BYDAY", "").split(",")
                if d in _ICS_WOCHENTAGE] or [start_v.weekday()]
        wochenanfang = start_v - timedelta(days=start_v.weekday())
        woche = 0
        n = 0
        while True:
            basis = wochenanfang + timedelta(weeks=woche * intervall)
            if basis > bis + timedelta(days=7):
                break
            fertig = False
            for tag in sorted(tage):
                t = basis + timedelta(days=tag)
                if t < start_v:
                    continue
                if until is not None and t > until:
                    fertig = True
                    break
                if anzahl is not None and n >= anzahl:
                    fertig = True
                    break
                n += 1
                if von <= t <= bis:
                    termine.append(t)
            if fertig:
                break
            woche += 1
    if ist_datum:
        return [t.date() for t in termine]
    # `termine` sind schon Ortszeit der Anzeige (aus `start_v`). Sie auf den
    # Original-Start mit seiner Zeitzone zurueckzuschreiben, wuerde einen
    # UTC-Start (22:30Z = 00:30 Berlin) um einen Tag verschieben.
    return termine


def parse_ics(text, von=None, bis=None):
    """iCalendar-Text -> {"name", "termine": [{start, ende, titel, ort, ganztags}]}.

    `von`/`bis` (datetime, naiv = Ortszeit) begrenzen das Fenster, in dem
    Wiederholungen ausgerollt werden; ohne Angabe: gestern bis in 14 Tagen.
    Termine kommen sortiert, `start`/`ende` als ISO-Text.
    """
    jetzt = datetime.now()
    von = von or (jetzt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    bis = bis or (jetzt + timedelta(days=14))
    zeilen = _ics_entfalten(text)
    if not any(z.upper().startswith("BEGIN:VCALENDAR") for z in zeilen[:5]):
        raise Abrufsfehler("keine iCalendar-Datei (BEGIN:VCALENDAR fehlt)")
    name = ""
    ereignisse = []
    ereignis = None
    verschachtelt = 0  # VALARM & Co. IN einem VEVENT: ueberlesen, nicht uebernehmen
    for zeile in zeilen:
        eigenschaft, params, wert = _ics_eigenschaft(zeile)
        if ereignis is not None and verschachtelt:
            if eigenschaft == "BEGIN":
                verschachtelt += 1
            elif eigenschaft == "END":
                verschachtelt -= 1
            continue
        if eigenschaft == "BEGIN" and wert.upper() == "VEVENT":
            ereignis = {"EXDATE": []}
            continue
        if eigenschaft == "BEGIN" and ereignis is not None:
            verschachtelt = 1
            continue
        if eigenschaft == "END" and wert.upper() == "VEVENT" and ereignis is not None:
            ereignisse.append(ereignis)
            ereignis = None
            continue
        if ereignis is None:
            if eigenschaft in ("X-WR-CALNAME", "NAME") and not name:
                name = _ics_unescape(wert)
            continue
        if eigenschaft == "EXDATE":
            ereignis["EXDATE"].append((params, wert))
        elif eigenschaft in ("DTSTART", "DTEND", "DURATION", "SUMMARY", "LOCATION", "RRULE", "UID",
                             "RECURRENCE-ID", "STATUS"):
            ereignis[eigenschaft] = (params, wert)

    # Eine verschobene Einzelfolge (RECURRENCE-ID) ersetzt den Termin der
    # Reihe zu genau diesem Ursprungszeitpunkt — sonst stuende er doppelt.
    ersetzt = set()
    for e in ereignisse:
        if "RECURRENCE-ID" in e and "UID" in e:
            try:
                t, _ = _ics_zeit(e["RECURRENCE-ID"][1], e["RECURRENCE-ID"][0])
            except ValueError:
                continue
            ersetzt.add((e["UID"][1].strip(), _vergleichbar(t)))
    termine = []
    for e in ereignisse:
        status = e.get("STATUS", ({}, ""))[1].strip().upper()
        if status == "CANCELLED":
            continue
        termine.extend(_ereignis_ausrollen(e, von, bis, ersetzt))
    termine.sort(key=lambda t: t["start"])
    return {"name": name, "termine": termine}


def _ereignis_ausrollen(ereignis, von, bis, ersetzt=frozenset()):
    if "DTSTART" not in ereignis:
        return []
    params, wert = ereignis["DTSTART"]
    try:
        start, ganztags = _ics_zeit(wert, params)
    except ValueError:
        return []
    if "DTEND" in ereignis:
        try:
            ende, _ = _ics_zeit(ereignis["DTEND"][1], ereignis["DTEND"][0])
        except ValueError:
            ende = start
    elif "DURATION" in ereignis:
        ende = start + _ics_dauer(ereignis["DURATION"][1])
    else:
        ende = start + timedelta(days=1) if ganztags else start
    dauer = _vergleichbar(ende) - _vergleichbar(start)
    titel = _ics_unescape(ereignis.get("SUMMARY", ({}, ""))[1]) or "(ohne Titel)"
    ort = _ics_unescape(ereignis.get("LOCATION", ({}, ""))[1])
    if "RRULE" in ereignis:
        starts = _wiederholungen(start, _rrule_parsen(ereignis["RRULE"][1]), von, bis)
    else:
        starts = [start]
    # Ausnahmen der Reihe: EXDATE (geloescht) und RECURRENCE-ID (verschoben,
    # steht als eigener VEVENT im Kalender).
    ausgenommen = set()
    for params, wert in ereignis.get("EXDATE", []):
        for einzel in wert.split(","):
            try:
                t, _ = _ics_zeit(einzel, params)
                ausgenommen.add(_vergleichbar(t))
            except ValueError:
                continue
    uid = ereignis.get("UID", ({}, ""))[1].strip()
    if "RRULE" in ereignis and uid:
        ausgenommen |= {t for (u, t) in ersetzt if u == uid}
    ergebnis = []
    for s in starts:
        s_v = _vergleichbar(s)
        if s_v in ausgenommen or (ganztags and datetime(s_v.year, s_v.month, s_v.day) in ausgenommen):
            continue
        e_v = s_v + dauer
        # Ein Termin zaehlt, wenn er das Fenster beruehrt — auch der, der um
        # 22 Uhr begann und bis 2 Uhr geht.
        if e_v < von or s_v > bis:
            continue
        ergebnis.append({
            "start": s_v.isoformat(timespec="minutes"),
            "ende": e_v.isoformat(timespec="minutes"),
            "titel": titel, "ort": ort, "ganztags": ganztags,
        })
    return ergebnis


def ics_laden(url, tage=14, ttl=None):
    def lader():
        daten, kopf = hole_url(url)
        return parse_ics(_text_aus(daten, kopf),
                         bis=datetime.now() + timedelta(days=max(1, min(int(tage), 60))))
    return CACHE.hole(("ics", url, int(tage)), lader, ttl)


# --------------------------------------------------------------------------
# Wetter (Open-Meteo, ohne Schluessel)
# --------------------------------------------------------------------------

WETTER_URL = "https://api.open-meteo.com/v1/forecast"

#: WMO-Wettercode -> deutscher Klartext FUER DEN SCHIRM (deshalb mit Umlauten,
#: anders als Log-Meldungen). Die Anzeige uebersetzt ihn ueber das Woerterbuch;
#: das Symbol waehlt die Anzeige selbst.
WMO_TEXTE = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt",
    45: "Nebel", 48: "Reifnebel",
    51: "leichter Nieselregen", 53: "Nieselregen", 55: "starker Nieselregen",
    56: "gefrierender Nieselregen", 57: "gefrierender Nieselregen",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    66: "gefrierender Regen", 67: "gefrierender Regen",
    71: "leichter Schneefall", 73: "Schneefall", 75: "starker Schneefall", 77: "Schneegriesel",
    80: "leichte Schauer", 81: "Schauer", 82: "starke Schauer",
    85: "Schneeschauer", 86: "starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit Hagel",
}


def pruefe_koordinaten(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise Abrufsfehler("lat/lon: Zahlen erwartet") from None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise Abrufsfehler("lat/lon: ausserhalb der Erde")
    return round(lat, 4), round(lon, 4)


def wetter_laden(lat, lon, einheit="c", ttl=None):
    lat, lon = pruefe_koordinaten(lat, lon)
    einheit = "fahrenheit" if str(einheit).lower().startswith("f") else "celsius"
    abfrage = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 4,
        "temperature_unit": einheit,
        "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
    })

    def lader():
        daten, _ = hole_url(f"{WETTER_URL}?{abfrage}")
        try:
            roh = json.loads(daten.decode("utf-8"))
        except ValueError:
            raise Abrufsfehler("Wetterdienst antwortet nicht mit JSON") from None
        return wetter_umformen(roh)
    ttl = 900.0 if ttl is None else ttl  # Wetter aendert sich nicht im Minutentakt
    return CACHE.hole(("wetter", lat, lon, einheit), lader, ttl)


def wetter_umformen(roh):
    """Open-Meteo-JSON -> das, was die Anzeige braucht. Rein und testbar."""
    if not isinstance(roh, dict) or "current" not in roh:
        raise Abrufsfehler("Wetterdienst: unerwartete Antwort")
    akt = roh.get("current") or {}
    tag = roh.get("daily") or {}
    code = akt.get("weather_code")
    ergebnis = {
        "aktuell": {
            "temperatur": akt.get("temperature_2m"),
            "code": code, "text": WMO_TEXTE.get(code, "unbekannt"),
            "wind_kmh": akt.get("wind_speed_10m"),
            "feuchte": akt.get("relative_humidity_2m"),
            "zeit": akt.get("time"),
        },
        "tage": [],
        "einheit": (roh.get("current_units") or {}).get("temperature_2m", "°C"),
    }
    for i, datum in enumerate(tag.get("time") or []):
        c = (tag.get("weather_code") or [None] * 9)[i]
        ergebnis["tage"].append({
            "datum": datum, "code": c, "text": WMO_TEXTE.get(c, "unbekannt"),
            "max": (tag.get("temperature_2m_max") or [None] * 9)[i],
            "min": (tag.get("temperature_2m_min") or [None] * 9)[i],
        })
    return ergebnis


# --------------------------------------------------------------------------
# Einbettbarkeit einer Webseite
# --------------------------------------------------------------------------

def _frame_ancestors_offen(quellen):
    """Erlaubt die Quellenliste JEDEN Rahmen? Nur ein nacktes `*` oder ein
    reines Schema (`https:`) tut das — `https://*.partner.com` ist eine
    Wildcard fuer EINEN Anbieter und sperrt uns genauso aus wie 'self'."""
    for token in quellen.split():
        t = token.strip().strip("'").lower()
        if t in ("*", "http:", "https:"):
            return True
    return False


def einbettbar(url, ttl=None):
    """Sagt eine Seite per Header, dass sie sich nicht in einen Rahmen legen
    laesst? `onerror` eines iframes feuert dafuer nicht — der Browser zeigt
    still eine leere Flaeche. Also fragt der Kern die Kopfzeilen selbst."""
    def lader():
        _, kopf = hole_url(url, nur_kopf=True)
        xfo = (kopf.get("x-frame-options") or "").strip().upper()
        if xfo in ("DENY", "SAMEORIGIN") or xfo.startswith("ALLOW-FROM"):
            return {"einbettbar": False, "grund": f"X-Frame-Options: {xfo}"}
        csp = kopf.get("content-security-policy") or ""
        m = re.search(r"frame-ancestors\s+([^;]+)", csp, re.I)
        if m and not _frame_ancestors_offen(m.group(1)):
            return {"einbettbar": False, "grund": f"Content-Security-Policy: frame-ancestors {m.group(1).strip()}"}
        return {"einbettbar": True, "grund": ""}
    return CACHE.hole(("einbettbar", url), lader, 3600.0 if ttl is None else ttl)


# --------------------------------------------------------------------------
# Eigene HTML-Widgets
# --------------------------------------------------------------------------

def eigene_widgets(ordner=None):
    """Alle Ordner unter `widgets/` mit einer `index.html` — sortiert, mit
    dem Titel aus `<title>`, wenn es einen gibt."""
    ordner = ordner or WIDGETS_DIR
    if not os.path.isdir(ordner):
        return []
    ergebnis = []
    for name in sorted(os.listdir(ordner)):
        pfad = os.path.join(ordner, name, "index.html")
        if not WIDGET_NAME.match(name) or not os.path.isfile(pfad):
            continue
        titel = name
        try:
            with open(pfad, encoding="utf-8", errors="replace") as f:
                m = re.search(r"<title>([^<]{1,80})</title>", f.read(20000), re.I)
                if m:
                    titel = m.group(1).strip()
        except OSError:
            pass
        ergebnis.append({"name": name, "titel": titel})
    return ergebnis

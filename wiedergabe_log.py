#!/usr/bin/env python3
"""Proof-of-Play: was die Anzeige wann wirklich gespielt hat.

WARUM ES DAS GIBT. Die Besucher-Statistik sagt, wie oft jemand nah war. Sie
sagt nicht, welcher Film dabei lief. Wer eine Ausstellung im Auftrag
bespielt, muss genau das nachweisen koennen: „Der Sponsorenclip lief im
Juni 412-mal" — und bei einer Reklamation: „am 14. um 15:02 lief Datei X".
Die kommerziellen Systeme nennen das Proof-of-Play und verkaufen es als
Zusatzstufe. Hier ist es eine SQLite-Datei neben der Konfiguration.

WOHER DIE DATEN KOMMEN. Die Anzeigeseite (static/anzeige/puls.js) hoert
`lz-eintrag` — jeden Start eines Playlist-Eintrags — und schickt die Starts
gesammelt alle 30 s an `POST /api/wiedergabe`. Die Wahrheit liegt also im
Browser, der gespielt hat, nicht im Kern, der geglaubt hat zu spielen.

KEIN PERSONENBEZUG. Gespeichert wird Zeit, Region, Datei, Layout, Zone —
nichts ueber Menschen davor.

DEDUPLIZIERUNG. Ein Browser, der nach einem Netzabriss den Puffer erneut
schickt, darf keinen Eintrag doppelt zaehlen: Schluessel ist (Anzeige-
Kennung, Zeit, Region). Die Kennung ist je Tab zufaellig (sessionStorage).

REINE ZEIT. `aufraeumen(jetzt)` bekommt die Uhr hereingereicht — testbar.
"""
import csv
import io
import os
import sqlite3
import threading
from datetime import datetime, timedelta

#: So viele Tage werden aufgehoben, wenn die Konfiguration nichts anderes sagt.
#: Ein Geraet, das jahrelang steht, darf die Karte nicht vollschreiben.
AUFBEWAHRUNG_TAGE = 90

#: Hoechstens so viele Eintraege je Meldung — ein Browser mit 30 s Puffer
#: liefert einige Dutzend; Tausende sind ein Fehler oder Absicht.
MAX_JE_MELDUNG = 2000

TYPEN = ("video", "image", "web", "audio", "widget")

GRUPPEN = ("datei", "tag", "stunde", "layout", "zone")


def _iso(zeit):
    return zeit.strftime("%Y-%m-%dT%H:%M:%S")


def pruefe_eintrag(roh):
    """Ein Eintrag der Anzeige, geprueft — oder None, wenn er nichts taugt.

    Kein Werfen: die Anzeige schickt einen Puffer, und ein kaputter Eintrag
    darin darf die ordentlichen nicht mitreissen.
    """
    if not isinstance(roh, dict):
        return None
    zeit = roh.get("zeit")
    if not isinstance(zeit, str):
        return None
    try:
        zeit_dt = datetime.fromisoformat(zeit.replace("Z", "+00:00"))
        if zeit_dt.tzinfo is not None:
            zeit_dt = zeit_dt.astimezone().replace(tzinfo=None)
    except ValueError:
        return None
    typ = roh.get("typ")
    if typ not in TYPEN:
        return None
    name = roh.get("name") or roh.get("url") or ""
    if not isinstance(name, str) or not name or len(name) > 512:
        return None

    def text(feld, laenge=64):
        w = roh.get(feld)
        return w[:laenge] if isinstance(w, str) else ""

    return {
        "zeit": _iso(zeit_dt),
        "region": text("region") or "haupt",
        "typ": typ,
        "name": name,
        "layout_id": text("layout_id"),
        "zone": text("zone", 16),
    }


class WiedergabeLog:
    """Die SQLite-Datei mit den Starts. Thread-sicher ueber ein Schloss."""

    def __init__(self, pfad, aufbewahrung_tage=AUFBEWAHRUNG_TAGE):
        self.pfad = pfad
        self.aufbewahrung_tage = aufbewahrung_tage
        self._lock = threading.Lock()
        ordner = os.path.dirname(os.path.abspath(pfad))
        os.makedirs(ordner, exist_ok=True)
        self._db = sqlite3.connect(pfad, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS wiedergabe (
                kennung   TEXT NOT NULL,
                zeit      TEXT NOT NULL,
                region    TEXT NOT NULL,
                typ       TEXT NOT NULL,
                name      TEXT NOT NULL,
                layout_id TEXT NOT NULL DEFAULT '',
                zone      TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (kennung, zeit, region)
            )""")
        self._db.execute("CREATE INDEX IF NOT EXISTS wiedergabe_zeit ON wiedergabe (zeit)")
        self._db.commit()

    def schliessen(self):
        with self._lock:
            self._db.close()

    def eintragen(self, kennung, eintraege):
        """Eintraege einer Anzeige aufnehmen. Gibt zurueck, wie viele NEU waren."""
        if not isinstance(kennung, str) or not kennung or len(kennung) > 64:
            return 0
        sauber = [e for e in (pruefe_eintrag(r) for r in list(eintraege)[:MAX_JE_MELDUNG]) if e]
        if not sauber:
            return 0
        with self._lock:
            vorher = self._db.total_changes
            self._db.executemany(
                "INSERT OR IGNORE INTO wiedergabe (kennung, zeit, region, typ, name, layout_id, zone) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(kennung, e["zeit"], e["region"], e["typ"], e["name"], e["layout_id"], e["zone"])
                 for e in sauber])
            self._db.commit()
            return self._db.total_changes - vorher

    def anzahl(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM wiedergabe").fetchone()[0]

    def aufraeumen(self, jetzt):
        """Alles vor der Aufbewahrungsfrist loeschen. Gibt die Zahl zurueck."""
        grenze = _iso(jetzt - timedelta(days=self.aufbewahrung_tage))
        with self._lock:
            cur = self._db.execute("DELETE FROM wiedergabe WHERE zeit < ?", (grenze,))
            self._db.commit()
            return cur.rowcount

    def _bereich(self, von, bis):
        """`von`/`bis` als Kalendertage (JJJJ-MM-TT) — beide optional.
        `bis` schliesst den Tag ein."""
        wo, werte = [], []
        if von:
            wo.append("zeit >= ?")
            werte.append(f"{von}T00:00:00")
        if bis:
            wo.append("zeit <= ?")
            werte.append(f"{bis}T23:59:59")
        return (" WHERE " + " AND ".join(wo)) if wo else "", werte

    def zusammenfassung(self, von=None, bis=None, gruppe="datei", limit=500):
        """Starts gezaehlt nach `gruppe`: datei | tag | stunde | layout | zone."""
        if gruppe not in GRUPPEN:
            raise ValueError(f"gruppe: {'|'.join(GRUPPEN)}")
        spalte = {
            "datei": "name", "tag": "substr(zeit, 1, 10)",
            "stunde": "substr(zeit, 12, 2)", "layout": "layout_id", "zone": "zone",
        }[gruppe]
        wo, werte = self._bereich(von, bis)
        with self._lock:
            zeilen = self._db.execute(
                f"SELECT {spalte} AS schluessel, typ, COUNT(*) AS starts, "
                f"MIN(zeit) AS erster, MAX(zeit) AS letzter FROM wiedergabe{wo} "
                f"GROUP BY schluessel, typ ORDER BY starts DESC, schluessel LIMIT ?",
                werte + [limit]).fetchall()
            gesamt = self._db.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT kennung) FROM wiedergabe{wo}", werte).fetchone()
        return {
            "gruppe": gruppe, "von": von, "bis": bis,
            "starts_gesamt": gesamt[0], "anzeigen": gesamt[1],
            "zeilen": [{"schluessel": z[0], "typ": z[1], "starts": z[2],
                        "erster": z[3], "letzter": z[4]} for z in zeilen],
        }

    def als_csv(self, von=None, bis=None):
        """Jeder einzelne Start als Zeile — fuer die Tabellenkalkulation."""
        wo, werte = self._bereich(von, bis)
        puffer = io.StringIO()
        w = csv.writer(puffer, delimiter=";")
        w.writerow(["zeit", "typ", "name", "region", "layout", "zone", "anzeige"])
        with self._lock:
            for z in self._db.execute(
                    f"SELECT zeit, typ, name, region, layout_id, zone, kennung "
                    f"FROM wiedergabe{wo} ORDER BY zeit", werte):
                w.writerow(z)
        return puffer.getvalue()

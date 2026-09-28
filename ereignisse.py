#!/usr/bin/env python3
"""Ereignisbus: was sich aendert, wird gesagt — sofort, nicht beim naechsten Poll.

WARUM ES DAS GIBT. Die Anzeige fragte bis 3.0 zweimal je Sekunde `/api/scene`
ab, die Verwaltung ebenso oft `/api/status`. Das ist auf einem Pi Last ohne
Gegenwert — und trotzdem nicht sofort: eine Zuweisung im Admin erschien erst
beim naechsten Poll. Mit Server-Sent Events schickt der Kern die neue Szene
in dem Moment, in dem sie feststeht; die Seiten fragen nur noch als Rueckfall.

OHNE FLASK. Der Bus kennt nur Warteschlangen. Wer ihn an HTTP haengt
(`web_ui.py`, `GET /api/events`), formatiert die Eintraege mit `formatiere`
und laesst `strom` laufen. So bleibt er ohne Server testbar.
"""
import json
import queue
import threading
import time

#: Wie lange ein Abonnent hoechstens ohne Zeile bleibt — ein Kommentar haelt
#: die Verbindung durch Proxys und Browser-Zeitgrenzen hindurch offen.
HEARTBEAT_S = 15.0

#: Mehr als so viele ungelesene Ereignisse je Abonnent gibt es nicht: ein
#: Browser, der nicht mehr liest, soll den Kern nicht wachsen lassen.
WARTESCHLANGE = 100


class Ereignisbus:
    """Sendet Ereignisse an alle, die gerade zuhoeren. Thread-sicher."""

    def __init__(self):
        self._lock = threading.Lock()
        self._abos = []

    def abonnieren(self):
        q = queue.Queue(maxsize=WARTESCHLANGE)
        with self._lock:
            self._abos.append(q)
        return q

    def abmelden(self, q):
        with self._lock:
            if q in self._abos:
                self._abos.remove(q)

    @property
    def anzahl(self):
        with self._lock:
            return len(self._abos)

    def senden(self, typ, daten):
        """An alle Abonnenten. Wer nicht nachkommt, verliert das Ereignis —
        nicht der Kern seine Zeit."""
        with self._lock:
            abos = list(self._abos)
        for q in abos:
            try:
                q.put_nowait({"typ": typ, "daten": daten})
            except queue.Full:
                pass


def formatiere(typ, daten):
    """Ein Ereignis in der Form, die `EventSource` im Browser versteht."""
    return f"event: {typ}\ndata: {json.dumps(daten, ensure_ascii=False)}\n\n"


def strom(bus, status=None, intervall_s=1.0, heartbeat_s=HEARTBEAT_S, uhr=time.monotonic):
    """Generator fuer EINE Verbindung: Ereignisse, dazu optional den Status.

    `status` ist eine Funktion ohne Argumente. Ist sie gesetzt, wird ihr
    Ergebnis alle `intervall_s` als Ereignis `status` geschickt — die
    Verwaltung braucht den Abstand laufend, die Anzeige gar nicht, und wer
    ihn nicht braucht, bekommt ihn nicht.

    Das Abonnement endet, wenn der Aufrufer den Generator schliesst — bei
    Werkzeug in dem Moment, in dem der Browser die Verbindung trennt.
    """
    q = bus.abonnieren()
    try:
        yield ": verbunden\n\n"
        letzter_puls = uhr()
        while True:
            try:
                ereignis = q.get(timeout=intervall_s)
                yield formatiere(ereignis["typ"], ereignis["daten"])
                letzter_puls = uhr()
            except queue.Empty:
                if status is not None:
                    yield formatiere("status", status())
                    letzter_puls = uhr()
                elif uhr() - letzter_puls >= heartbeat_s:
                    yield ": puls\n\n"
                    letzter_puls = uhr()
    finally:
        bus.abmelden(q)

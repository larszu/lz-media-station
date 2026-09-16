"""Besucher-Statistik: wie oft und wie lange jemand vor der Station stand.

WARUM ES DAS GIBT. Die Zahlen entstehen ohnehin — der Sensor weiss jede
Zehntelsekunde, ob jemand in der Nah-Zone ist — und wurden bisher weggeworfen.
Fuer den Betreiber einer Ausstellung ist genau das der Nachweis, dass die
Installation wirkt: wie viele Besuche, wie lange, zu welcher Stunde.

WAS HIER NICHT PASSIERT: es wird nichts ueber einzelne Personen gespeichert.
Ein „Besuch" ist ein Zeitraum, in dem irgendjemand nah war — kein Bild, kein
Merkmal, keine Wiedererkennung. Auch bei der Kamera-Quelle nicht: die liefert
nur eine Entfernung.

REINE RECHNUNG. Die Uhrzeit wird hereingereicht, nie gelesen — sonst haengt
der Test an der Systemuhr. Das Schreiben auf die Platte ist davon getrennt
(`speichern`/`laden`), damit die Zaehlung ohne Dateisystem pruefbar ist.
"""
import json
import os
import tempfile

#: So viele Tage werden aufgehoben. Ohne Grenze waechst die Datei auf einem
#: Geraet, das jahrelang in einer Ausstellung steht, unbegrenzt.
MAX_TAGE = 90

#: Kuerzer als das ist kein Besuch, sondern jemand, der vorbeigeht. Ohne diese
#: Schwelle zaehlt jeder Durchgaenger mit und die Zahlen werden wertlos.
MINDESTDAUER_S = 1.0


def _tagesschluessel(zeitpunkt):
    return zeitpunkt.strftime("%Y-%m-%d")


class Statistik:
    """Zaehlt Besuche und ihre Dauer, aggregiert nach Tag und Stunde."""

    def __init__(self, tage=None):
        #: {"2026-09-16": {"besuche": int, "dauer_s": float, "stunden": {"9": int}}}
        self.tage = tage or {}
        self._beginn = None        # Zeitpunkt, seit dem jemand nah ist

    # -- Erfassung ---------------------------------------------------------

    def verfolge(self, ist_nah, jetzt):
        """Einmal je Schleifendurchlauf aufrufen. Erkennt die Wechsel selbst.

        Absichtlich EIN Eingang statt zwei (`beginnt`/`endet`) an verstreuten
        Stellen der Zustandsmaschine: dort haette jeder neue Pfad — etwa das
        Schliessen durch den Wochenplan — vergessen werden koennen, einen
        offenen Besuch zu beenden.

        Gibt die Dauer zurueck, wenn gerade ein Besuch endete, sonst None.
        """
        if ist_nah:
            if self._beginn is None:
                self._beginn = jetzt
            return None
        return self.abschliessen(jetzt)

    def abschliessen(self, jetzt):
        """Einen offenen Besuch beenden (Stopp, Herunterfahren, Zonenwechsel).

        Gibt die Dauer in Sekunden zurueck, oder None, wenn keiner offen war
        oder er zu kurz fuer einen Besuch war.
        """
        if self._beginn is None:
            return None
        beginn, self._beginn = self._beginn, None
        dauer = (jetzt - beginn).total_seconds()
        if dauer < MINDESTDAUER_S:
            return None
        tag = self.tage.setdefault(
            _tagesschluessel(beginn),
            {"besuche": 0, "dauer_s": 0.0, "stunden": {}})
        tag["besuche"] += 1
        tag["dauer_s"] = round(tag["dauer_s"] + dauer, 1)
        stunde = str(beginn.hour)
        tag["stunden"][stunde] = tag["stunden"].get(stunde, 0) + 1
        self._kuerzen()
        return dauer

    @property
    def laeuft_gerade(self):
        """Steht gerade jemand davor? (Fuer die Anzeige im Admin.)"""
        return self._beginn is not None

    def _kuerzen(self):
        if len(self.tage) <= MAX_TAGE:
            return
        for schluessel in sorted(self.tage)[:-MAX_TAGE]:
            del self.tage[schluessel]

    # -- Auswertung --------------------------------------------------------

    def zusammenfassung(self, heute, tage_zurueck=14):
        """Was die Oberflaeche zeigt: heute, die letzten Tage, Gesamtsumme."""
        schluessel = _tagesschluessel(heute)
        heute_daten = self.tage.get(schluessel, {"besuche": 0, "dauer_s": 0.0, "stunden": {}})
        letzte = []
        for tag in sorted(self.tage)[-tage_zurueck:]:
            d = self.tage[tag]
            letzte.append({
                "tag": tag,
                "besuche": d["besuche"],
                "dauer_s": round(d["dauer_s"], 1),
                "schnitt_s": round(d["dauer_s"] / d["besuche"], 1) if d["besuche"] else 0.0,
            })
        gesamt = sum(d["besuche"] for d in self.tage.values())
        gesamt_dauer = sum(d["dauer_s"] for d in self.tage.values())
        return {
            "heute": {
                "tag": schluessel,
                "besuche": heute_daten["besuche"],
                "dauer_s": round(heute_daten["dauer_s"], 1),
                "schnitt_s": (round(heute_daten["dauer_s"] / heute_daten["besuche"], 1)
                              if heute_daten["besuche"] else 0.0),
                # Alle 24 Stunden, auch die leeren — sonst muesste die
                # Oberflaeche die Luecken selbst auffuellen und die Kurve
                # haette je nach Tag eine andere Breite.
                "stunden": [heute_daten["stunden"].get(str(s), 0) for s in range(24)],
            },
            "letzte_tage": letzte,
            "gesamt_besuche": gesamt,
            "gesamt_dauer_s": round(gesamt_dauer, 1),
            "laeuft_gerade": self.laeuft_gerade,
        }

    def als_csv(self):
        """Tageswerte als CSV — zum Weiterreichen an den Auftraggeber.

        Semikolon als Trenner und Komma als Dezimalzeichen: so oeffnet eine
        deutsche Excel-Installation die Datei ohne Import-Dialog.
        """
        zeilen = ["Datum;Besuche;Gesamtdauer_s;Durchschnitt_s"]
        for tag in sorted(self.tage):
            d = self.tage[tag]
            schnitt = d["dauer_s"] / d["besuche"] if d["besuche"] else 0.0
            zeilen.append(
                f"{tag};{d['besuche']};"
                f"{d['dauer_s']:.1f};{schnitt:.1f}".replace(".", ","))
        return "\n".join(zeilen) + "\n"

    def leeren(self):
        self.tage = {}
        self._beginn = None


# -- Persistenz (getrennt von der Rechnung) --------------------------------

def laden(pfad):
    """Statistik von der Platte lesen. Faellt auf leer zurueck statt zu werfen."""
    if not os.path.isfile(pfad):
        return Statistik()
    try:
        with open(pfad, encoding="utf-8") as f:
            daten = json.load(f)
        tage = daten.get("tage")
        if not isinstance(tage, dict):
            raise ValueError("`tage` fehlt oder ist kein Objekt")
        # Jeden Tag pruefen: eine halb beschaedigte Datei darf nicht dazu
        # fuehren, dass die Auswertung spaeter mit einem TypeError aussteigt.
        sauber = {}
        for tag, d in tage.items():
            if not isinstance(d, dict):
                continue
            sauber[tag] = {
                "besuche": int(d.get("besuche", 0)),
                "dauer_s": float(d.get("dauer_s", 0.0)),
                "stunden": {str(k): int(v) for k, v in (d.get("stunden") or {}).items()},
            }
        return Statistik(sauber)
    except Exception as e:
        print(f"[Statistik] {pfad} unlesbar ({e}) — fange neu an")
        return Statistik()


def speichern(statistik, pfad):
    """Atomar schreiben: erst daneben, dann umbenennen.

    Die Station wird per Stecker ausgeschaltet. Ein direktes `write` kann
    genau dann auf eine halb geschriebene Datei treffen, und die naechste
    Lesung faende Schrott vor.
    """
    verzeichnis = os.path.dirname(os.path.abspath(pfad))
    try:
        os.makedirs(verzeichnis, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=verzeichnis,
                prefix=".statistik-", suffix=".tmp", delete=False) as f:
            json.dump({"version": 1, "tage": statistik.tage}, f, ensure_ascii=False)
            tmp = f.name
        os.replace(tmp, pfad)
        return True
    except Exception as e:
        print(f"[Statistik] Speicherfehler: {e}")
        return False

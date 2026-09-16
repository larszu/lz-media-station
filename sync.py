"""Mehrere Stationen im Gleichtakt: eine folgt der anderen.

WARUM ES DAS GIBT. Eine Videowand aus drei Schirmen, oder ein Exponat, bei dem
ein Sensor mehrere Aufbauten ausloesen soll. Bisher brauchte jeder Schirm eine
eigene Station MIT eigenem Sensor — und drei Sensoren nebeneinander schalten
nie gleichzeitig.

DAS MODELL IST BEWUSST EINFACH. Es gibt keine Rollenwahl, keine Wahl eines
Anfuehrers und keine Uhr-Synchronisation:

* JEDE Station beantwortet `/api/sync` mit ihrer aktuellen Zone. Damit ist
  jede Station potenziell ein Taktgeber — ohne dass man das irgendwo einstellt.
* Eine Station mit `sync_rolle = "follower"` fragt diese Adresse und uebernimmt
  die Zone, statt ihren eigenen Sensor auszuwerten.

Eine deklarative „master"-Rolle waere Zierde: sie wuerde nichts bewirken, weil
ohnehin jede Station antwortet. Konfiguration, die nichts tut, ist schlimmer
als keine — irgendwann verlaesst sich jemand darauf.

WAS NICHT SYNCHRONISIERT WIRD: die Position INNERHALB eines Videos. Dafuer
braeuchte es eine gemeinsame Zeitbasis und ein Nachregeln der Abspielrate; das
waere ein anderes Projekt. Synchron ist die ZONE — also welche Szene laeuft.
Bei einem Zonenwechsel starten die Follower ihre Szene neu, so wie sie es auch
mit eigenem Sensor taeten.

KEIN KONTAKT HEISST KEIN WERT — dieselbe Regel wie beim Sensor. `zone` gibt
`None` zurueck, wenn die letzte Antwort zu alt ist, statt die alte Zone
weiterzubehaupten. Ein abgerissenes Netzkabel darf nicht aussehen wie eine
Station, vor der gerade niemand steht.
"""
import json
import threading
import time
import urllib.error
import urllib.request

#: Wie oft der Taktgeber gefragt wird. Haeufiger waere fuer eine Zonen-Angabe
#: Verschwendung; seltener macht den Wechsel sichtbar traege.
INTERVALL_S = 0.4

#: Nach dieser Zeit ohne gueltige Antwort gilt die Zone als unbekannt.
#: Grosszuegiger als der Abfragetakt, damit ein einzelner Aussetzer im WLAN
#: nicht sofort die Szene abraeumt.
STALE_AFTER_S = 3.0

#: Laenger darf eine einzelne Anfrage nicht dauern — sonst blockiert ein
#: haengender Taktgeber den Thread ueber den Ablauf hinaus.
ZEITGRENZE_S = 2.0


class SyncFollower(threading.Thread):
    """Fragt eine andere Station nach ihrer Zone.

    Erfuellt bewusst dieselbe Form wie die Abstandsquellen: ein Thread, ein
    Wert mit Ablauf, ein Klartext-Zustand. Wer den Sensor verstanden hat,
    versteht auch das hier.
    """

    LABEL = "Sync-Follower"

    def __init__(self, host, port=5000):
        super().__init__(daemon=True)
        self.host = (host or "").strip()
        self.port = port
        self._zone = None
        self._geschlossen = False
        self._empfangen_at = None
        self._running = False
        self._lock = threading.Lock()
        self._status = "startet"

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/api/sync"

    @property
    def zone(self):
        """Die Zone des Taktgebers — oder `None`, wenn der Kontakt fehlt."""
        with self._lock:
            if self._empfangen_at is None:
                return None
            if time.monotonic() - self._empfangen_at > STALE_AFTER_S:
                return None
            return self._zone

    @property
    def geschlossen(self):
        """Hat der Taktgeber gerade Betriebsruhe (Wochenplan)?

        Der Follower uebernimmt auch das: sonst spielte eine Wand nachts zur
        Haelfte weiter, weil nur eine Station einen Zeitplan hat.
        """
        with self._lock:
            return self._geschlossen

    @property
    def status(self):
        return self._status

    def run(self):
        self._running = True
        if not self.host:
            self._setze_status("kein Taktgeber eingetragen")
            print(f"[Sync] {self._status} — es wird nicht gefolgt")
            return
        print(f"[Sync] folge {self.url}")
        while self._running:
            try:
                with urllib.request.urlopen(self.url, timeout=ZEITGRENZE_S) as antwort:
                    daten = json.loads(antwort.read().decode("utf-8"))
                with self._lock:
                    self._zone = daten.get("zone")
                    self._geschlossen = bool(daten.get("geschlossen"))
                    # Der Zeitstempel wird NUR hier fortgeschrieben — bei einem
                    # Fehler bleibt er stehen, damit der Wert von selbst
                    # veraltet.
                    self._empfangen_at = time.monotonic()
                self._setze_status(f"folgt {self.host}")
            except (urllib.error.URLError, OSError, ValueError) as e:
                self._setze_status(f"kein Kontakt zu {self.host} ({e})")
            time.sleep(INTERVALL_S)

    def _setze_status(self, text):
        self._status = text

    def stop(self):
        self._running = False

#!/usr/bin/env python3
"""LZ Media Station - Headless Pi mit Chromium-basierter Anzeige"""
import os
import sys
import json
import time
import signal
import threading
import argparse

from datetime import datetime

import displays
import ereignisse
import layouts as layouts_modul
import statistik as statistik_modul
import sync as sync_modul
import tv_cec
import zeitplan
from sensor import SensorThread
from button_sensor import ButtonSensorThread
from camera_sensor import CameraSensorThread
from auto_sensor import AutoAbstandsQuelle
from web_ui import create_app, lan_adresse, lies_version

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATISTIK_FILE = os.path.join(BASE_DIR, "statistik.json")

# Vorgaben und Grenzen stehen in `config_schema`; hier weiterhin unter ihrem
# alten Namen erreichbar, weil Tests und Aufrufer `main.DEFAULT_CONFIG` kennen.
from config_schema import (  # noqa: E402  (nach den Standard-Imports, absichtlich)
    DEFAULT_CONFIG, GRENZEN, NUTZBARE_BCM, ZONEN, ZONEN_NAMEN, aktive_zonen,
    pruefe_patch, pruefe_pins, pruefe_schwellen,
    heile_config, heile_zone, standard_zone,
)

__all__ = ["DEFAULT_CONFIG", "GRENZEN", "NUTZBARE_BCM", "ZONEN", "ZONEN_NAMEN",
           "aktive_zonen", "pruefe_patch", "pruefe_pins", "pruefe_schwellen",
           "heile_config", "heile_zone", "standard_zone",
           "erzeuge_abstandsquelle", "Controller", "load_config", "main"]


def erzeuge_abstandsquelle(config):
    """Die zur Konfiguration passende Abstandsquelle bauen.

    `sensor_type` entscheidet: „auto" -> Ultraschall mit Rueckfall auf die
    Kamera (Vorgabe, Issue #13), „camera" -> Webcam-Erkennung, „button" ->
    GPIO-Taster, „ultrasonic" -> nur der HC-SR04 am GPIO. Eine Stelle, an der
    die Wahl faellt — damit `main` und die Tests dieselbe Quelle bekommen.

    WARUM „ultrasonic" BLEIBT, obwohl „auto" es einschliesst: es ist die
    Ansage „an dieser Station gehoert ein Sensor hin". Faellt er aus, soll sie
    schweigen und es melden, statt still mit einem anderen Blickfeld und einer
    anderen Reichweite weiterzulaufen.
    """
    art = config.get("sensor_type")
    if art == "auto":
        return AutoAbstandsQuelle(
            trigger_pin=config["gpio_trigger"],
            echo_pin=config["gpio_echo"],
            camera_index=config.get("camera_index", 0),
            focal_px=config.get("camera_focal_px", 700.0),
        )
    if art == "camera":
        return CameraSensorThread(
            camera_index=config.get("camera_index", 0),
            focal_px=config.get("camera_focal_px", 700.0),
        )
    if art == "button":
        return ButtonSensorThread(
            pin=config.get("button_pin", 17),
            haltezeit_s=config.get("button_haltezeit_s", 30.0),
        )
    return SensorThread(
        trigger_pin=config["gpio_trigger"],
        echo_pin=config["gpio_echo"],
    )


class Controller:
    """Sensor → Zonen-Logik. Display wird vom Browser gehandhabt."""

    def __init__(self, config):
        self.config = config
        self.sensor = erzeuge_abstandsquelle(config)
        self.active = False
        #: Die BESTAETIGTE Zone. Getrennt vom Kandidaten, weil waehrend der
        #: Hysterese weiterhin die alte Zone spielt — sonst flackerte genau
        #: das, was die Verzoegerung verhindern soll.
        self.zone = "far"
        self._kandidat = None
        self._pending_since = None
        self._thread = None
        # Startwert True, damit der erste Ausfall gemeldet wird und nicht der
        # erste Erfolg.
        self._sensor_misst = True
        # `None` und nicht True/False: der erste Durchlauf soll die Lage
        # melden (und ggf. CEC schalten), egal ob offen oder geschlossen.
        self._war_offen = None
        # Besucher-Statistik. Wird beim Start von der Platte gelesen, damit ein
        # Neustart (oder ein Stromausfall) die Zahlen der Ausstellung nicht
        # zuruecksetzt.
        self.statistik = statistik_modul.laden(STATISTIK_FILE)
        # Gleichtakt: folgt diese Station einer anderen? `None` heisst „nein",
        # und dann bleibt alles wie bisher.
        self.follower = None
        if config.get("sync_rolle") == "follower":
            self.follower = sync_modul.SyncFollower(
                host=config.get("sync_master", ""),
                port=config.get("sync_port", 5000))
        # Ereignisse (SSE, seit 3.0): die Anzeige erfaehrt eine neue Szene in
        # dem Moment, in dem sie feststeht — nicht beim naechsten Poll.
        self.bus = ereignisse.Ereignisbus()
        # EIN Schloss um die Konfiguration. Flask bedient jede Anfrage in
        # einem eigenen Faden; zwei gleichzeitige Schreibzugriffe (Manager
        # und Handy) liefen sonst ungeordnet in dasselbe dict und dieselbe
        # Datei. Wiedereintrittsfaehig, weil `save_config` darin aufgerufen
        # wird und selbst sperrt.
        self.lock = threading.RLock()
        # Regeln, die das Zonen-Layout uebersteuern (siehe layout_fuer_zone)
        self.layout_regeln = []
        # Zusaetze zur Szene (Welle 2: Sofortmeldung, Schirm schwarz): jeder
        # Eintrag ist ein Aufruf `(jetzt) -> dict`, der in die Szene gemischt
        # wird. So bekommt die Anzeige alles mit EINER Antwort, und der Kern
        # muss die Erweiterung nicht kennen.
        self.szene_zusatz = []
        # Wer nach jeder Konfigurationsaenderung gerufen werden will (Welle 2:
        # Taster-Ausloeser oeffnen/schliessen). Aufrufe ohne Argument.
        self.config_beobachter = []
        self._gemeldete_szene = None

    @property
    def state(self):
        """Der Zustand als Text — die Form, die `/api/status` seit jeher nennt.

        Abgeleitet statt gespeichert: „nah", „auf dem Weg nach nah" und „welche
        Zone gerade spielt" sind drei Fragen an EINEN Zustand. Als drei Felder
        waeren sie irgendwann uneinig.
        """
        if not self.active:
            return "idle"
        if self._kandidat:
            return "pending_" + self._kandidat
        return self.zone

    def zonen(self):
        """Die aktiven Zonen dieser Station, von nah nach fern."""
        return aktive_zonen(self.config)

    def zone_fuer(self, dist):
        """Welche Zone gehoert zu diesem Abstand?

        `None` (keine Messung) ergibt „fern": ohne Messung wird nicht
        ausgeloest. Dieselbe Regel wie frueher — sie stand nur als
        `dist is not None and dist <= threshold` mitten in der Schleife.
        """
        if dist is None:
            return "far"
        if dist <= self.config.get("threshold_m", 1.0):
            return "near"
        if "mid" in self.zonen() and dist <= self.config.get("threshold_mid_m", 2.5):
            return "mid"
        return "far"

    def ist_offen(self, jetzt=None):
        """Spielt die Station gerade laut Wochenplan?

        Ein Follower uebernimmt die Betriebsruhe des Taktgebers — sonst
        spielte eine Wand nachts zur Haelfte weiter, weil nur eine der
        Stationen einen Zeitplan hat. Der EIGENE Plan gilt zusaetzlich: wer
        eine Station frueher schliessen will, kann das.

        Eine Stelle, die das beantwortet — die Steuerschleife und `get_scene`
        fragen dieselbe. Zwei Rechnungen wuerden bedeuten, dass der Schirm
        schwarz ist, waehrend die Zonenlogik noch schaltet.
        """
        if self.follower and self.follower.geschlossen:
            return False
        return zeitplan.ist_offen(self.config.get("zeitplan"),
                                  jetzt or datetime.now())

    def get_scene(self, layout_id=None, zone=None, jetzt=None):
        """Aktueller Zustand fuer die Display-Seite.

        `layout_id` schaltet in die VORSCHAU (Welle 2, Layout-Editor): die
        Szene zeigt dann dieses Layout, als waere es die Zone `zone` (oder
        die erste), unabhaengig von Sensor und Wochenplan. `jetzt` bestimmt,
        welche Eintraege heute gelten — die Vorschau kann so einen anderen Tag
        zeigen. Ohne Angabe: die Uhr.
        """
        jetzt = jetzt or datetime.now()
        heute = jetzt.date().isoformat()
        vorschau = layout_id is not None
        geschlossen = (not self.ist_offen(jetzt)) and not vorschau
        # Waehrend der Hysterese spielt die BESTAETIGTE Zone weiter — deshalb
        # `self.zone` und nicht der Kandidat.
        #
        # Ausserhalb der Oeffnungszeiten gibt es KEINE Zone. Das ist die
        # Absicherung an der Quelle: selbst wenn die Steuerschleife gerade
        # nicht laeuft (Controller gestoppt), bekommt die Anzeigeseite nichts
        # zu spielen — sie muss sich nicht darauf verlassen, das Flag zu
        # beachten.
        aktive_zone = self.zone if (self.active and not geschlossen) else None
        if vorschau:
            aktive_zone = zone if zone in self.zonen() else self.zonen()[0]
        szene = {
            "active": True if vorschau else self.active,
            "geschlossen": geschlossen,
            "zone": aktive_zone,
            "zonen": list(self.zonen()),
            "stationsname": self.config.get("system_name", ""),
            "image_interval_s": self.config.get("image_interval_s", 5),
            "master_volume": self.config.get("master_volume", 100),
            "video_volume": self.config.get("video_volume", 100),
            "audio_volume": self.config.get("audio_volume", 80),
            "video_resume": bool(self.config.get("video_resume", False)),
            # Untertitel: die Anzeigeseite baut daraus ihre <track>-Elemente
            # und die Sprachknoepfe. Leere Sprachliste = keine Umschaltung.
            "sprachen": list(self.config.get("sprachen") or []),
            "untertitel": dict(self.config.get("untertitel") or {}),
            "vorschau": vorschau,
        }
        # Die Zonen-Objekte je AKTIVER Zone, damit die Wiedergabe-Optionen
        # (shuffle/einmal/bildzeiten) mitkommen, ohne hier einzeln aufgezaehlt
        # zu werden — eine neue Option waere sonst im Kern da und auf dem
        # Schirm nicht. Eine neue Zone ebenso. `layout` ist dabei die
        # AUFGELOESTE Kennung (leer in der Konfiguration heisst Zonen-Layout).
        for name in self.zonen():
            zonendaten = dict(self.config.get(name) or standard_zone())
            zonendaten["layout"] = layouts_modul.layout_id_der_zone(self.config, name)
            szene[name] = zonendaten
        # Das Layout der aktiven Zone — vollstaendig, aber ohne die Eintraege,
        # die heute nicht gelten (von/bis). Gefiltert wird HIER, an der
        # Quelle: die Anzeige soll nichts kennen, was sie nicht zeigen darf.
        lid = None
        if vorschau:
            lid = layout_id
        elif aktive_zone:
            lid = self.layout_fuer_zone(aktive_zone, jetzt)
        layout = (self.config.get("layouts") or {}).get(lid) if lid else None
        szene["layout_id"] = lid if layout is not None else None
        szene["layout"] = layouts_modul.filtere_layout(layout, heute) if layout is not None else None
        for zusatz in list(self.szene_zusatz):
            try:
                szene.update(zusatz(jetzt) or {})
            except Exception as e:  # ein Zusatz darf die Szene nicht verhindern
                print(f"[Szene] Zusatz {getattr(zusatz, '__name__', zusatz)} gescheitert: {e}")
        return szene

    def layout_fuer_zone(self, zone, jetzt):
        """Welches Layout die Zone JETZT spielt.

        Andockpunkt fuer Regeln (Welle 2: Wochenprogramm, Ausloeser): jede
        Regel in `self.layout_regeln` ist ein Aufruf `(zone, jetzt, config)`
        und liefert eine Layout-Kennung oder None. Die erste Antwort gewinnt;
        eine Kennung, die es nicht gibt, zaehlt nicht. Ohne Treffer gilt das
        Layout der Zone aus der Konfiguration.
        """
        layouts = self.config.get("layouts") or {}
        for regel in list(self.layout_regeln):
            try:
                lid = regel(zone, jetzt, self.config)
            except Exception as e:  # eine kaputte Regel darf den Schirm nicht schwarz machen
                print(f"[Layout] Regel {getattr(regel, '__name__', regel)} gescheitert: {e}")
                continue
            if lid and lid in layouts:
                return lid
        return layouts_modul.layout_id_der_zone(self.config, zone)

    def melde_szene(self):
        """Die Szene an alle Anzeigen schicken — aber nur bei einem Wechsel.

        Die Steuerschleife ruft das zehnmal je Sekunde; die Szene selbst zu
        bauen und zu vergleichen waere dort zu teuer. Verglichen wird deshalb
        nur, woran die Szene haengt: laeuft sie, welche Zone, offen oder zu.
        Aendert sich die Konfiguration, setzt `melde_config` die Kennung
        zurueck — dann geht die Szene auch ohne Zonenwechsel hinaus.
        """
        # Seit Welle 2 zaehlt auch das AUFGELOESTE Layout der Zone: das
        # Wochenprogramm wechselt es zur vollen Stunde, ohne dass sich Zone
        # oder Oeffnung aendern — und die Anzeige soll das sofort erfahren.
        kennung = (self.active, self.zone, self.ist_offen(),
                   self.layout_fuer_zone(self.zone, datetime.now()) if self.active else None)
        if kennung == self._gemeldete_szene:
            return
        self._gemeldete_szene = kennung
        if self.bus.anzahl:
            self.bus.senden("scene", self.get_scene())

    def melde_config(self):
        """Nach jedem Schreibzugriff: Konfiguration UND Szene — die Anzeige
        braucht die Szene, die Verwaltung die Konfiguration."""
        self._gemeldete_szene = None
        for beobachter in list(self.config_beobachter):
            try:
                beobachter()
            except Exception as e:  # ein Beobachter darf die Meldung nicht verhindern
                print(f"[Config] Beobachter {getattr(beobachter, '__name__', beobachter)}: {e}")
        self.bus.senden("config", self.config)
        self.melde_szene()

    def start(self):
        if self.active:
            return
        self.active = True
        self.zone = "far"
        self._kandidat = None
        self._pending_since = None
        if self.follower and not self.follower.is_alive():
            self.follower.start()
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        print("[Controller] Gestartet")
        self.melde_szene()

    def stop(self):
        self.active = False
        self.zone = "far"
        self._kandidat = None
        self._pending_since = None
        # Einen laufenden Besuch abschliessen, sonst ginge er verloren —
        # gestoppt wird typischerweise am Ende eines Ausstellungstages.
        if self.statistik.abschliessen(datetime.now()) is not None:
            self.statistik_speichern()
        print("[Controller] Gestoppt")
        self.melde_szene()

    def _melde_sensorlage(self, dist):
        """Einmal melden, wenn die Messung ausfaellt — und einmal, wenn sie
        wiederkommt.

        Ohne diese Meldung ist ein toter Sensor am Verhalten nicht von einem
        leeren Raum zu unterscheiden: die Station spielt einfach die
        Fern-Szene weiter. Bei jedem Durchlauf zu melden waere das Gegenteil
        — zehn Zeilen je Sekunde liest niemand.
        """
        misst = dist is not None
        if misst == self._sensor_misst:
            return
        self._sensor_misst = misst
        print("[Sensor] Messung wieder da" if misst
              else "[Sensor] KEINE Messung — es wird nicht ausgeloest")

    def statistik_speichern(self):
        """Der EINE Ort, der den Statistik-Pfad kennt.

        `web_ui` soll ihn nicht kennen muessen — sonst stuenden zwei Module mit
        zwei Vorstellungen davon da, wo die Datei liegt.
        """
        return statistik_modul.speichern(self.statistik, STATISTIK_FILE)

    def statistik_leeren(self):
        self.statistik.leeren()
        return self.statistik_speichern()

    def _zaehle(self):
        """Die Statistik einmal je Durchlauf fortschreiben.

        Gespeichert wird NUR, wenn ein Besuch tatsaechlich endete — nicht
        zehnmal je Sekunde. Auf einer SD-Karte waere das der sichere Weg, sie
        in einer Ausstellungssaison durchzuschreiben.
        """
        beendet = self.statistik.verfolge(self.state == "near", datetime.now())
        if beendet is not None:
            self.statistik_speichern()
            print(f"[Statistik] Besuch beendet nach {beendet:.1f}s")

    def _melde_zeitlage(self, offen):
        """Einmal melden, wenn der Wochenplan zu- oder aufmacht.

        Bei jedem Durchlauf zu melden waere zehn Zeilen je Sekunde. Am Wechsel
        haengt ausserdem das optionale CEC-Schalten — auch das gehoert genau
        einmal getan und nicht zehnmal pro Sekunde.
        """
        if offen == self._war_offen:
            return
        self._war_offen = offen
        print("[Zeitplan] Oeffnungszeit — die Station spielt" if offen
              else "[Zeitplan] ausserhalb der Oeffnungszeit — Schirm bleibt schwarz")
        if self.config.get("cec_aktiv"):
            _ok, meldung = tv_cec.schalte(offen)
            print(f"[Zeitplan] {meldung}")

    def save_config(self):
        """Atomar: erst in eine Nachbardatei, dann umbenennen.

        Ein Stromausfall mitten im Schreiben liess vorher eine halbe
        `config.json` zurueck — und die Station kam mit den Vorgaben hoch,
        als haette nie jemand etwas eingestellt. `os.replace` ist auf
        derselben Platte unteilbar: entweder die alte oder die neue Datei.
        """
        with self.lock:
            tmp = CONFIG_FILE + ".tmp"
            try:
                with open(tmp, "w") as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, CONFIG_FILE)
            except Exception as e:
                print(f"[Config] Speicherfehler: {e}")
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _control_loop(self):
        """Zustandsmaschine mit Hysterese"""
        while self.active:
            # Der Wochenplan steht VOR dem Sensor. Ausserhalb der
            # Oeffnungszeit wird nicht ausgeloest — egal, wer davorsteht.
            # Der Zustand faellt dabei auf "far" zurueck, damit die Station
            # beim Aufmachen nicht mit einer alten Nah-Szene aufwacht.
            offen = self.ist_offen()
            self._melde_zeitlage(offen)
            if not offen:
                self.zone = "far"
                self._kandidat = None
                self._pending_since = None
                # Auch hier zaehlen: schliesst der Wochenplan, waehrend noch
                # jemand davorsteht, muss der laufende Besuch beendet werden.
                # Genau diesen Pfad haette ein `beginnt`/`endet`-Paar an den
                # Zustandsuebergaengen vergessen.
                self._zaehle()
                self.melde_szene()
                time.sleep(0.5)
                continue

            # Folgt diese Station einer anderen, wird der eigene Sensor gar
            # nicht ausgewertet — auch keine Hysterese: der Taktgeber hat sie
            # schon angewandt, ein zweites Mal warten hiesse, dass die Wand
            # sichtbar nacheinander umschaltet.
            if self.follower:
                fremde = self.follower.zone
                # Kein Kontakt heisst kein Wert (wie beim Sensor): dann faellt
                # die Station auf „fern" zurueck, statt die zuletzt empfangene
                # Zone weiterzubehaupten. Ein abgerissenes Netzkabel darf nicht
                # aussehen wie ein Besucher, der sich nicht vom Fleck ruehrt.
                self.zone = fremde or "far"
                self._kandidat = None
                self._pending_since = None
                self._zaehle()
                self.melde_szene()
                time.sleep(0.1)
                continue

            dist = self.sensor.distance
            delay = self.config.get("delay_s", 1.5)
            self._melde_sensorlage(dist)
            now = time.time()

            # EINE Maschine fuer zwei wie fuer drei Stufen: das Ziel ergibt
            # sich aus dem Abstand, und ein Wechsel gilt erst, wenn dasselbe
            # Ziel `delay_s` lang stabil war.
            #
            # Vorher standen die vier Faelle (far/near/pending_near/
            # pending_far) einzeln da. Mit einer dritten Stufe waeren daraus
            # neun geworden, und jede weitere Zone haette die Tabelle erneut
            # aufgeblaeht — bei gleichbleibender Regel. `None` (keine Messung)
            # ergibt „fern": ohne Messung wird nicht ausgeloest.
            ziel = self.zone_fuer(dist)
            if ziel == self.zone:
                # Zurueck zum Ausgangspunkt: ein angefangener Wechsel verfaellt.
                self._kandidat = None
                self._pending_since = None
            elif self._kandidat != ziel:
                self._kandidat = ziel
                self._pending_since = now
            elif now - self._pending_since >= delay:
                self.zone = ziel
                self._kandidat = None
                self._pending_since = None
                wo = "?" if dist is None else f"{dist:.2f}m"
                print(f"[Controller] → {ZONEN_NAMEN.get(ziel, ziel).upper()} ({wo})")

            self._zaehle()
            self.melde_szene()
            time.sleep(0.1)


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            # Eine Stelle heilt die Zonen (`config_schema.heile_zone`). Vorher
            # stand die Normalisierung hier und kannte nur die drei
            # Medienlisten — jede neue Wiedergabe-Option haette nachgezogen
            # werden muessen, und ein Vergessen faellt erst auf, wenn eine
            # gespeicherte Einstellung nach dem Neustart verschwunden ist.
            for zone in ZONEN:
                cfg[zone] = heile_zone(cfg.get(zone))
            return heile_config(cfg)
        except Exception as e:
            print(f"[Config] Lesefehler: {e}")
    return json.loads(json.dumps(DEFAULT_CONFIG))


def main():
    parser = argparse.ArgumentParser(description="LZ Media Station")
    # EINE Quelle fuer die Version: die Datei VERSION. Sie stand als Text in
    # `/api/identity` ("2.1.0", waehrend die App 2.0.4 hiess) — zwei Zahlen,
    # die nie jemand abgeglichen hat.
    parser.add_argument("--version", action="version",
                        version=f"LZ Media Station {lies_version()}")
    parser.add_argument("--port", type=int, help="Web-UI Port (Standard: 5000)")
    # Die Bind-Adresse war fest auf 0.0.0.0 verdrahtet — also auf ALLEN
    # Schnittstellen, ohne dass es eine Moeglichkeit gab, das zu lassen. Auf
    # einem Rechner in einem fremden Netz (Hotel-WLAN, Messe, Kundennetz)
    # steht damit die Verwaltungsoberflaeche offen, und niemand hat es
    # entschieden. Die Vorgabe bleibt 0.0.0.0, weil genau das der Zweck der
    # Station ist — aber jetzt ist es eine Entscheidung und keine
    # Unvermeidbarkeit.
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind-Adresse. Vorgabe 0.0.0.0 = im ganzen "
                             "Netz erreichbar; 127.0.0.1 = nur dieser Rechner.")
    # DIESER RECHNER IST AUCH EIN MEDIENSPIELER (Nutzer, 2026-09-15: „im
    # mediaplayer das endgeraet selbst und externe displays die ans endgeraet
    # angeschlossen sind als mediaplayer nutzen koennen. mac und windows").
    #
    # Die Anzeige ist seit jeher eine Browser-Seite; auf dem Pi oeffnet sie
    # ein Chromium auf dem einen HDMI-Ausgang. Auf einem Notebook oder einem
    # Rechner am Aufbau haengt oft mehr als ein Schirm, und der eingebaute
    # zaehlt mit — davon konnte die Station nichts nutzen.
    parser.add_argument("--play-on", default="", metavar="all|0,1",
                        help="die Anzeige auf den Bildschirmen DIESES "
                             "Rechners oeffnen: `all` fuer alle, sonst die "
                             "Nummern aus --list-displays (0-basiert).")
    parser.add_argument("--list-displays", action="store_true",
                        help="die gefundenen Bildschirme nennen und beenden")
    args = parser.parse_args()

    if args.list_displays:
        gefunden = displays.schirme()
        if not gefunden:
            print("Keine Bildschirme gefunden.")
            print(f"  System: {sys.platform}")
            print("  Ein Rechner ohne Grafik (ein Pi ohne X, ein Server) hat "
                  "keine — die Station laeuft dort weiter, sie bespielt nur "
                  "nichts vor Ort.")
            return 0
        for i, s in enumerate(gefunden):
            marke = " (Hauptschirm)" if s.get("haupt") else ""
            print(f"  {i}: {s['name']}  {s['breite']}x{s['hoehe']} "
                  f"bei {s['x']},{s['y']}{marke}")
        browser = displays.finde_browser()
        print()
        print(f"  Browser: {browser or 'KEINER GEFUNDEN'}")
        if not browser:
            for ort in displays.suchorte():
                print(f"    gesucht: {ort}")
        return 0

    config = load_config()
    port = args.port or config.get("web_port", 5000)

    for d in ("videos", "images", "audio", "subtitles"):
        os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

    controller = Controller(config)
    controller.ausloeser_faden = True   # der Ausloeser-Faden (api_ausloeser) laeuft nur auf der Station
    # Ein Follower wertet den eigenen Sensor nicht aus — dann ist auch kein
    # Grund, GPIO oder eine Kamera zu belegen. Auf einem Rechner, der nur
    # einen zweiten Schirm bespielt, ist oft gar keine Hardware angeschlossen.
    if not controller.follower:
        controller.sensor.start()

    if not os.path.isfile(CONFIG_FILE):
        controller.save_config()

    anzeigen = displays.Anzeigen()
    app = create_app(controller, anzeigen)

    # Controller automatisch starten (Kiosk-Betrieb)
    controller.start()

    # DIE ADRESSEN, DIE MAN WIRKLICH EINTIPPEN KANN.
    #
    # Hier stand `http://0.0.0.0:5000`. Das ist keine Adresse, sondern die
    # Bind-Angabe „alle Schnittstellen" — in einen Browser getippt landet sie
    # je nach System nirgends. Der Server war also die ganze Zeit im Netz
    # erreichbar und niemand erfuhr, unter welcher Adresse.
    #
    # Und die drei Ansichten werden benannt, weil sie unterschiedliche Leute
    # brauchen: die Anzeige gehoert auf den Schirm am Aufbau, die Verwaltung
    # auf das Geraet in der Hand, und beide koennen gleichzeitig offen sein.
    lan = lan_adresse()
    print()
    print("  LZ Media Station")
    print(f"    hier:            http://127.0.0.1:{port}/")
    if args.host == "0.0.0.0" and lan and not lan.startswith("127."):
        print(f"    im selben Netz:  http://{lan}:{port}/")
        print()
        print("    Anzeige (Schirm am Aufbau):   " f"http://{lan}:{port}/display")
        print("    Verwaltung (Handy/Notebook):  " f"http://{lan}:{port}/admin")
    elif args.host != "0.0.0.0":
        print(f"    gebunden an {args.host} — andere Geraete kommen NICHT dran.")
    else:
        print("    kein Netz gefunden — nur dieser Rechner kommt dran.")
    print()
    # `status` fuellt sich erst, wenn der Quellen-Thread seinen ersten
    # Durchlauf hatte; deshalb der Kurzname der Quelle als sofort sichtbare
    # Angabe und der Status daneben, sobald er da ist.
    if controller.follower:
        print(f"    Takt:   folgt {controller.config.get('sync_master')} "
              f"(eigener Sensor bleibt aus)")
    else:
        print(f"    Sensor: {controller.sensor.LABEL} — {controller.sensor.status}")
    print()

    def shutdown(sig, frame):
        # Die selbst geoeffneten Anzeige-Fenster gehen mit. Ohne das bleiben
        # sie als Vollbild auf den Schirmen stehen, nachdem die Station weg
        # ist — und der Aufbau zeigt ein totes Bild statt eines schwarzen.
        anzeigen.beende()
        controller.stop()
        controller.sensor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.play_on:
        # ERST DER SERVER, DANN DIE FENSTER. `app.run` blockiert, also wird
        # der Start in einen Faden gelegt, der kurz wartet: ein Browser, der
        # vor dem Server da ist, zeigt „nicht erreichbar" und laedt nicht von
        # selbst nach.
        #
        # Und `127.0.0.1` und nicht die LAN-Adresse: die Fenster laufen auf
        # DIESEM Rechner. Ueber die eigene Netzadresse zu gehen hiesse, sich
        # von der Netzwerkkarte abhaengig zu machen, die man gar nicht
        # braucht — in einem Gastnetz mit Client-Isolation faellt das aus.
        url = f"http://127.0.0.1:{port}/display"
        auswahl = None
        if args.play_on.strip().lower() != "all":
            try:
                auswahl = [int(t) for t in args.play_on.replace(" ", "").split(",") if t]
            except ValueError:
                print(f"[Anzeige] --play-on {args.play_on!r} ist keine "
                      "Liste von Nummern. `all` oder z. B. `0,2`.")
                auswahl = []

        def anzeigen_oeffnen():
            time.sleep(1.5)
            gestartet, meldungen = anzeigen.starte(url, auswahl)
            if gestartet:
                print(f"[Anzeige] geoeffnet auf Schirm: "
                      f"{', '.join(str(i) for i in gestartet)}")
            for m in meldungen:
                print(f"[Anzeige] {m}")
            if not gestartet and not meldungen:
                print("[Anzeige] nichts geoeffnet.")

        threading.Thread(target=anzeigen_oeffnen, daemon=True).start()

    app.run(host=args.host, port=port, threaded=True)


if __name__ == "__main__":
    main()

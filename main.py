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
import statistik as statistik_modul
import tv_cec
import zeitplan
from sensor import SensorThread
from button_sensor import ButtonSensorThread
from camera_sensor import CameraSensorThread
from web_ui import create_app, lan_adresse

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

    `sensor_type` entscheidet: „camera" -> Webcam-Erkennung, „button" ->
    GPIO-Taster, sonst der HC-SR04 am GPIO (Vorgabe). Eine Stelle, an der die Wahl faellt — damit
    `main` und die Tests dieselbe Quelle bekommen.
    """
    art = config.get("sensor_type")
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

        Eine Stelle, die das beantwortet — die Steuerschleife und `get_scene`
        fragen dieselbe. Zwei Rechnungen wuerden bedeuten, dass der Schirm
        schwarz ist, waehrend die Zonenlogik noch schaltet.
        """
        return zeitplan.ist_offen(self.config.get("zeitplan"),
                                  jetzt or datetime.now())

    def get_scene(self):
        """Aktueller Zustand für die Display-Seite"""
        geschlossen = not self.ist_offen()
        # Waehrend der Hysterese spielt die BESTAETIGTE Zone weiter — deshalb
        # `self.zone` und nicht der Kandidat.
        #
        # Ausserhalb der Oeffnungszeiten gibt es KEINE Zone. Das ist die
        # Absicherung an der Quelle: selbst wenn die Steuerschleife gerade
        # nicht laeuft (Controller gestoppt), bekommt die Anzeigeseite nichts
        # zu spielen — sie muss sich nicht darauf verlassen, das Flag zu
        # beachten.
        szene = {
            "active": self.active,
            "geschlossen": geschlossen,
            "zone": self.zone if (self.active and not geschlossen) else None,
            "zonen": list(self.zonen()),
            "image_interval_s": self.config.get("image_interval_s", 5),
            "master_volume": self.config.get("master_volume", 100),
            "video_volume": self.config.get("video_volume", 100),
            "audio_volume": self.config.get("audio_volume", 80),
            "video_resume": bool(self.config.get("video_resume", False)),
        }
        # Die Zonen-Objekte je AKTIVER Zone, damit die Wiedergabe-Optionen
        # (shuffle/einmal/bildzeiten) mitkommen, ohne hier einzeln aufgezaehlt
        # zu werden — eine neue Option waere sonst im Kern da und auf dem
        # Schirm nicht. Eine neue Zone ebenso.
        for name in self.zonen():
            szene[name] = self.config.get(name) or standard_zone()
        return szene

    def start(self):
        if self.active:
            return
        self.active = True
        self.zone = "far"
        self._kandidat = None
        self._pending_since = None
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        print("[Controller] Gestartet")

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
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Speicherfehler: {e}")

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
                time.sleep(0.5)
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

    for d in ("videos", "images", "audio"):
        os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

    controller = Controller(config)
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

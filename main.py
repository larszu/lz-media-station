#!/usr/bin/env python3
"""LZ Media Station - Headless Pi mit Chromium-basierter Anzeige"""
import os
import sys
import json
import time
import signal
import threading
import argparse

from sensor import SensorThread
from camera_sensor import CameraSensorThread
from web_ui import create_app, lan_adresse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Vorgaben und Grenzen stehen in `config_schema`; hier weiterhin unter ihrem
# alten Namen erreichbar, weil Tests und Aufrufer `main.DEFAULT_CONFIG` kennen.
from config_schema import (  # noqa: E402  (nach den Standard-Imports, absichtlich)
    DEFAULT_CONFIG, GRENZEN, NUTZBARE_BCM,
    pruefe_patch, pruefe_pins, heile_config,
)

__all__ = ["DEFAULT_CONFIG", "GRENZEN", "NUTZBARE_BCM",
           "pruefe_patch", "pruefe_pins", "heile_config",
           "erzeuge_abstandsquelle", "Controller", "load_config", "main"]


def erzeuge_abstandsquelle(config):
    """Die zur Konfiguration passende Abstandsquelle bauen.

    `sensor_type` entscheidet: „camera" -> Webcam-Erkennung, sonst der
    HC-SR04 am GPIO (Vorgabe). Eine Stelle, an der die Wahl faellt — damit
    `main` und die Tests dieselbe Quelle bekommen.
    """
    if config.get("sensor_type") == "camera":
        return CameraSensorThread(
            camera_index=config.get("camera_index", 0),
            focal_px=config.get("camera_focal_px", 700.0),
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
        self.state = "idle"
        self._pending_since = None
        self._thread = None
        # Startwert True, damit der erste Ausfall gemeldet wird und nicht der
        # erste Erfolg.
        self._sensor_misst = True

    def get_scene(self):
        """Aktueller Zustand für die Display-Seite"""
        zone = None
        if self.active:
            if self.state in ("near", "pending_far"):
                zone = "near"
            elif self.state in ("far", "pending_near"):
                zone = "far"
        return {
            "active": self.active,
            "zone": zone,
            "near": self.config.get("near", {"videos": [], "images": [], "audio": []}),
            "far": self.config.get("far", {"videos": [], "images": [], "audio": []}),
            "image_interval_s": self.config.get("image_interval_s", 5),
            "master_volume": self.config.get("master_volume", 100),
            "video_volume": self.config.get("video_volume", 100),
            "audio_volume": self.config.get("audio_volume", 80),
            "video_resume": bool(self.config.get("video_resume", False)),
        }

    def start(self):
        if self.active:
            return
        self.active = True
        self.state = "far"
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        print("[Controller] Gestartet")

    def stop(self):
        self.active = False
        self.state = "idle"
        self._pending_since = None
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

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Speicherfehler: {e}")

    def _control_loop(self):
        """Zustandsmaschine mit Hysterese"""
        while self.active:
            dist = self.sensor.distance
            threshold = self.config.get("threshold_m", 1.0)
            delay = self.config.get("delay_s", 1.5)
            # `None` heisst „kein gueltiger Messwert" — noch nie gemessen oder
            # der Sensor antwortet nicht mehr. Das ist KEIN „jemand steht
            # davor": ohne Messung wird nicht ausgeloest.
            #
            # Frueher startete `distance` bei 0.0, und `0.0 <= threshold` ist
            # wahr. Die Station ging deshalb beim Start in die Nah-Szene, ohne
            # dass jemand da war — und blieb dauerhaft dort, wenn der Sensor
            # gar nicht erst antwortete.
            is_near = dist is not None and dist <= threshold
            self._melde_sensorlage(dist)
            now = time.time()

            if self.state == "far":
                if is_near:
                    self.state = "pending_near"
                    self._pending_since = now
            elif self.state == "near":
                if not is_near:
                    self.state = "pending_far"
                    self._pending_since = now
            elif self.state == "pending_near":
                if not is_near:
                    self.state = "far"
                    self._pending_since = None
                elif now - self._pending_since >= delay:
                    self.state = "near"
                    self._pending_since = None
                    print(f"[Controller] → NAH ({dist:.2f}m)")
            elif self.state == "pending_far":
                if is_near:
                    self.state = "near"
                    self._pending_since = None
                elif now - self._pending_since >= delay:
                    self.state = "far"
                    self._pending_since = None
                    print(f"[Controller] → FERN ({dist:.2f}m)")

            time.sleep(0.1)


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            for zone in ("near", "far"):
                if not isinstance(cfg.get(zone), dict):
                    cfg[zone] = {"videos": [], "images": [], "audio": []}
                for key in ("videos", "images", "audio"):
                    cfg[zone].setdefault(key, [])
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
    args = parser.parse_args()

    config = load_config()
    port = args.port or config.get("web_port", 5000)

    for d in ("videos", "images", "audio"):
        os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

    controller = Controller(config)
    controller.sensor.start()

    if not os.path.isfile(CONFIG_FILE):
        controller.save_config()

    app = create_app(controller)

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
        controller.stop()
        controller.sensor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(host=args.host, port=port, threaded=True)


if __name__ == "__main__":
    main()

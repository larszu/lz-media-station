#!/usr/bin/env python3
"""FACES Media Station - Headless Pi mit Chromium-basierter Anzeige"""
import os
import sys
import json
import time
import signal
import threading
import argparse

from sensor import SensorThread
from web_ui import create_app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "system_name": "FACES Station 1",
    "threshold_m": 1.0,
    "delay_s": 1.5,
    "gpio_trigger": 23,
    "gpio_echo": 24,
    "web_port": 5000,
    "image_interval_s": 5,
    "master_volume": 100,
    "video_volume": 100,
    "audio_volume": 80,
    "near": {"videos": [], "images": [], "audio": []},
    "far": {"videos": [], "images": [], "audio": []},
}


class Controller:
    """Sensor → Zonen-Logik. Display wird vom Browser gehandhabt."""

    def __init__(self, config, use_dummy=False):
        self.config = config
        self.sensor = SensorThread(
            trigger_pin=config["gpio_trigger"],
            echo_pin=config["gpio_echo"],
            use_dummy=use_dummy,
        )
        self.active = False
        self.state = "idle"
        self._pending_since = None
        self._thread = None

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
            is_near = dist <= threshold
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
            return cfg
        except Exception as e:
            print(f"[Config] Lesefehler: {e}")
    return json.loads(json.dumps(DEFAULT_CONFIG))


def main():
    parser = argparse.ArgumentParser(description="FACES Media Station")
    parser.add_argument("--dummy", action="store_true", help="Dummy-Sensor (kein GPIO)")
    parser.add_argument("--port", type=int, help="Web-UI Port (Standard: 5000)")
    args = parser.parse_args()

    config = load_config()
    port = args.port or config.get("web_port", 5000)

    for d in ("videos", "images", "audio"):
        os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

    controller = Controller(config, use_dummy=args.dummy)
    controller.sensor.start()

    if not os.path.isfile(CONFIG_FILE):
        controller.save_config()

    app = create_app(controller)

    print(f"\n  FACES Media Station")
    print(f"  http://0.0.0.0:{port}")
    print(f"  Sensor: {'Dummy' if controller.sensor.use_dummy else 'HC-SR04'}\n")

    def shutdown(sig, frame):
        controller.stop()
        controller.sensor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()

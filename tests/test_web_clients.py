"""
Kommt ein anderes Geraet im selben Netz an die Station?

─── DIE MELDUNG DAHINTER (Nutzer, 2026-09-09) ──────────────────────────────

„Ebenso die Medien Station [muss man lokal starten koennen]. Man muss bei
 Medien Station auch Web Clients haben. Also Server lokal und andere Geraete
 koennen drauf zu greifen wenn im gleichen Netzwerk."

─── WAS GEMESSEN WIRD, UND WARUM GERADE DAS ────────────────────────────────

Der Server band schon immer an `0.0.0.0`. Technisch war die Station also im
Netz erreichbar — und trotzdem stimmte die Meldung, denn beim Start stand da:

    http://0.0.0.0:5000

`0.0.0.0` ist keine Adresse, die jemand eintippen kann. Es ist die
Bind-Angabe „alle Schnittstellen"; in einen Browser getippt landet sie je
nach System nirgends. Wer die Station aufbaute, bekam also nie zu sehen,
was er der Crew sagen soll.

Dieser Test fragt deshalb DREI getrennte Dinge, und keines folgt aus einem
anderen:

  1. Kommt eine Anfrage von einer ANDEREN Adresse als 127.0.0.1 durch?
     (Gebunden wird an 0.0.0.0, angefragt wird ueber die LAN-Adresse
     dieses Rechners — das ist derselbe Weg, den ein Handy nimmt.)
  2. Nennt die Station diese Adresse auch? Ein erreichbarer Server, dessen
     Adresse niemand kennt, ist fuer die Crew nicht erreichbar.
  3. Bindet `--host 127.0.0.1` wirklich nur lokal? Ohne diese Gegenprobe
     waere der Schalter eine Beschriftung ohne Wirkung — und die
     Verwaltungsoberflaeche staende in jedem fremden Netz offen, ohne dass
     es jemand entschieden haette.
"""

import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web_ui import lan_adresse  # noqa: E402


def freier_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def hole(url: str, timeout: float = 1.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


class Station:
    """Die Station starten und wieder abraeumen — mit echten HTTP-Anfragen."""

    def __init__(self, *args: str):
        self.port = freier_port()
        umgebung = dict(os.environ)
        umgebung["PYTHONUNBUFFERED"] = "1"
        self.p = subprocess.Popen(
            [sys.executable, str(ROOT / "main.py"),
             "--dummy", "--port", str(self.port), *args],
            cwd=str(ROOT), env=umgebung,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def warte(self, host: str = "127.0.0.1") -> bool:
        for _ in range(120):
            if self.p.poll() is not None:
                return False
            try:
                hole(f"http://{host}:{self.port}/api/status")
                return True
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        return False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.p.terminate()
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()


class AndereGeraeteKommenDran(unittest.TestCase):
    def test_anfrage_ueber_die_lan_adresse_kommt_durch(self):
        lan = lan_adresse()
        if not lan or lan.startswith("127."):
            self.fail(
                "Dieser Rechner hat keine LAN-Adresse — die Frage laesst sich "
                "hier nicht stellen. Das ist ein Grund, den Test zu MELDEN, "
                "nicht ihn zu ueberspringen: uebersprungen saehe er gruen aus.")
        with Station() as s:
            self.assertTrue(s.warte(), "Station ist nicht hochgekommen")
            # DER eigentliche Beweis: nicht ueber localhost, sondern ueber die
            # Adresse, die ein Handy im selben Netz benutzen wuerde.
            status, _ = hole(f"http://{lan}:{s.port}/api/status", timeout=3)
            self.assertEqual(status, 200)
            for pfad in ("/", "/display", "/admin"):
                st, _ = hole(f"http://{lan}:{s.port}{pfad}", timeout=3)
                self.assertEqual(st, 200, f"{pfad} ist von aussen nicht da")

    def test_die_station_nennt_ihre_adresse(self):
        # Ein erreichbarer Server, dessen Adresse niemand kennt, ist fuer die
        # Crew nicht erreichbar. Genau das war der Zustand: `0.0.0.0`.
        with Station() as s:
            self.assertTrue(s.warte(), "Station ist nicht hochgekommen")
            _, roh = hole(f"http://127.0.0.1:{s.port}/api/status")
            daten = json.loads(roh)
            self.assertNotEqual(daten.get("host_ip"), "0.0.0.0")
            self.assertTrue(daten.get("remote_url", "").startswith("http://"))
            self.assertNotIn("0.0.0.0", daten.get("remote_url", ""))

    def test_die_startausgabe_zeigt_keine_bindangabe_als_adresse(self):
        with Station() as s:
            self.assertTrue(s.warte(), "Station ist nicht hochgekommen")
            # Die Ausgabe steht schon im Puffer; sie wird nicht abgewartet,
            # sondern nach dem Beenden gelesen.
            s.p.terminate()
            try:
                ausgabe = s.p.communicate(timeout=10)[0] or ""
            except subprocess.TimeoutExpired:
                s.p.kill()
                ausgabe = s.p.communicate()[0] or ""
            self.assertNotIn("http://0.0.0.0", ausgabe,
                             "die Startausgabe nennt 0.0.0.0 als Adresse")
            self.assertIn("/display", ausgabe,
                          "die Anzeige-Ansicht wird nicht genannt")
            self.assertIn("/admin", ausgabe,
                          "die Verwaltungs-Ansicht wird nicht genannt")


class DerRiegelHaeltAuch(unittest.TestCase):
    def test_host_127_bindet_wirklich_nur_lokal(self):
        # Die Gegenprobe. Ohne sie waere `--host` eine Beschriftung ohne
        # Wirkung, und die Verwaltungsoberflaeche staende in jedem fremden
        # Netz offen, ohne dass es jemand entschieden haette.
        lan = lan_adresse()
        if not lan or lan.startswith("127."):
            self.fail("kein LAN auf diesem Rechner — die Gegenprobe braucht eine "
                      "zweite Adresse, um ueberhaupt etwas zu zeigen")
        with Station("--host", "127.0.0.1") as s:
            self.assertTrue(s.warte(), "Station ist nicht hochgekommen")
            with self.assertRaises((urllib.error.URLError, OSError)):
                hole(f"http://{lan}:{s.port}/api/status", timeout=2)


if __name__ == "__main__":
    unittest.main()

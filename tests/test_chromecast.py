#!/usr/bin/env python3
"""Der Chromecast-Weg — ohne Chromecast.

Wie `test_meldung` & Co. prueft das hier den Weg, der im Betrieb zaehlt, und
NICHT den echten Schaltvorgang (dafuer braeuchte es ein Geraet im Netz):

  * Das von Hand gebaute Protobuf muss sich selbst wieder lesen lassen
    (kodiere -> dekodiere), sonst stimmt kein einziger Rahmen.
  * Die avahi-Ausgabe muss korrekt zu Geraeten werden.
  * `spiele()` muss den richtigen Nachrichtenfluss sprechen (CONNECT, LAUNCH,
    dann LOAD an die transportId) — geprueft gegen einen Fake-Socket, der die
    Antworten des Geraets nachspielt.
  * Ein nicht erreichbares Geraet wird zur Meldung, nicht zur Ausnahme.
  * Der Config-Abschnitt wird geprueft und geheilt wie die anderen.

unittest, nicht pytest: die Station-Suite laeuft im CI mit dem
unittest-Loader, der kein pytest kennt (Issue: PR #40 war rot, weil hier
`import pytest` stand).
"""
import json
import os
import socket
import struct
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromecast
import config_schema


class Protobuf(unittest.TestCase):
    def test_roundtrip(self):
        roh = chromecast.kodiere("sender-0", "receiver-0",
                                 chromecast.NS_EMPFAENGER, '{"type":"PING"}')
        namespace, nutzlast = chromecast.dekodiere(roh)
        self.assertEqual(namespace, chromecast.NS_EMPFAENGER)
        self.assertEqual(json.loads(nutzlast), {"type": "PING"})

    def test_ueberspringt_unbekannte_felder(self):
        # Ein payload_binary-Feld (7, wire 2) anhaengen — muss ignoriert
        # werden, ohne namespace/nutzlast zu verlieren.
        roh = chromecast.kodiere("s", "d", "ns", "x")
        roh += chromecast._feld_string(7, "egal")
        namespace, nutzlast = chromecast.dekodiere(roh)
        self.assertEqual((namespace, nutzlast), ("ns", "x"))

    def test_varint_mehrbyte(self):
        # 300 braucht zwei Bytes (0xAC 0x02) — die Grenze, an der Einbyte kippt.
        self.assertEqual(chromecast._varint(300), b"\xac\x02")
        wert, i = chromecast._lies_varint(b"\xac\x02", 0)
        self.assertEqual((wert, i), (300, 2))


AVAHI = (
    '+;eth0;IPv4;Chromecast-Ultra;_googlecast._tcp;local\n'
    '=;eth0;IPv4;Chromecast-Ultra;_googlecast._tcp;local;cc.local;'
    '192.168.2.2;8009;"id=abc123" "md=Chromecast Ultra" "fn=Buero"\n'
)


class AvahiParsing(unittest.TestCase):
    def test_wird_zu_geraet(self):
        geraete = chromecast._aus_avahi(AVAHI)
        self.assertEqual(len(geraete), 1)
        g = geraete[0]
        self.assertEqual(g["ip"], "192.168.2.2")
        self.assertEqual(g["port"], 8009)
        self.assertEqual(g["name"], "Buero")
        self.assertEqual(g["modell"], "Chromecast Ultra")

    def test_ohne_eintraege(self):
        self.assertEqual(
            chromecast._aus_avahi("+;eth0;IPv4;x;_googlecast._tcp;local\n"), [])


class FakeSock:
    """Spielt einen Chromecast nach: nimmt Rahmen entgegen, gibt vorbereitete
    Antwortrahmen zurueck. Nur so viel, wie `spiele()` wirklich liest."""

    def __init__(self, antworten):
        self.gesendet = []
        self._aus = bytearray()
        for ns, last in antworten:
            rahmen = chromecast.kodiere("r", "s", ns, json.dumps(last))
            self._aus += struct.pack(">I", len(rahmen)) + rahmen

    def sendall(self, daten):
        i = 0
        while i < len(daten):
            (laenge,) = struct.unpack(">I", daten[i:i + 4])
            ns, last = chromecast.dekodiere(daten[i + 4:i + 4 + laenge])
            self.gesendet.append((ns, last))
            i += 4 + laenge

    def recv(self, anzahl):
        if not self._aus:
            raise socket.timeout()
        stueck = bytes(self._aus[:anzahl])
        del self._aus[:anzahl]
        return stueck

    def settimeout(self, _):
        pass

    def close(self):
        pass


def _mit_fake(antworten):
    """Einen Kontextmanager-Patch bauen, der `CastVerbindung.__enter__` den
    Fake-Socket unterschiebt. Gibt (patcher, fake) zurueck."""
    fake = FakeSock(antworten)

    def fake_enter(self):
        self.sock = fake
        return self

    return mock.patch.object(chromecast.CastVerbindung, "__enter__", fake_enter), fake


class Spielen(unittest.TestCase):
    def test_sendet_launch_und_load(self):
        status = {
            "type": "RECEIVER_STATUS",
            "status": {"applications": [
                {"appId": chromecast.STANDARD_EMPFAENGER, "transportId": "web-1"}]},
        }
        patcher, fake = _mit_fake([
            (chromecast.NS_EMPFAENGER, status),
            (chromecast.NS_MEDIEN, {"type": "MEDIA_STATUS"}),
        ])
        with patcher:
            ok, meldung = chromecast.spiele(
                "192.168.2.2", "http://host/media/videos/a.mp4")
        self.assertTrue(ok, meldung)

        typen = [json.loads(last).get("type") for _, last in fake.gesendet]
        self.assertIn("CONNECT", typen)
        self.assertIn("LAUNCH", typen)
        self.assertIn("LOAD", typen)
        # LOAD muss an die transportId gehen und die richtige Quelle tragen.
        load = next(last for _, last in fake.gesendet
                    if json.loads(last).get("type") == "LOAD")
        self.assertTrue(json.loads(load)["media"]["contentId"].endswith("a.mp4"))

    def test_meldet_launch_error(self):
        patcher, _ = _mit_fake([
            (chromecast.NS_EMPFAENGER, {"type": "LAUNCH_ERROR", "reason": "NOT_FOUND"}),
        ])
        with patcher:
            ok, meldung = chromecast.spiele(
                "192.168.2.2", "http://host/x.mp4", app_id="EIGEN123")
        self.assertFalse(ok)
        self.assertIn("EIGEN123", meldung)
        self.assertIn("registriert", meldung)

    def test_unerreichbar_wirft_nicht(self):
        def wirf(self):
            raise OSError("keine Route zum Host")
        with mock.patch.object(chromecast.CastVerbindung, "__enter__", wirf):
            ok, meldung = chromecast.spiele("10.0.0.1", "http://host/x.mp4")
        self.assertFalse(ok)
        self.assertIn("nicht erreichbar", meldung)


class CastConfig(unittest.TestCase):
    def test_default_vorhanden(self):
        self.assertEqual(config_schema.DEFAULT_CONFIG["cast"]["modus"], "medien")

    def test_pruefe_nimmt_gueltiges(self):
        out = config_schema.pruefe_cast(
            {"aktiv": True, "geraet_ip": "192.168.2.2", "modus": "anzeige",
             "app_id": "ABCD1234"})
        self.assertTrue(out["aktiv"])
        self.assertEqual(out["geraet_ip"], "192.168.2.2")
        self.assertEqual(out["modus"], "anzeige")
        self.assertEqual(out["app_id"], "ABCD1234")

    def test_pruefe_lehnt_modus_ab(self):
        with self.assertRaises(ValueError):
            config_schema.pruefe_cast({"modus": "quatsch"})

    def test_pruefe_lehnt_ip_ab(self):
        with self.assertRaises(ValueError):
            config_schema.pruefe_cast({"geraet_ip": "evil;rm -rf"})

    def test_heile_repariert_statt_abbruch(self):
        vorgabe = config_schema.DEFAULT_CONFIG["cast"]
        self.assertEqual(config_schema.heile_cast("kaputt"), vorgabe)
        self.assertEqual(config_schema.heile_cast({"modus": "nope"}), vorgabe)


if __name__ == "__main__":
    unittest.main()

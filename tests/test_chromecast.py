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
"""
import json
import socket
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromecast
import config_schema


# ───────────────────────────── Protobuf ────────────────────────────────────
def test_protobuf_roundtrip():
    roh = chromecast.kodiere("sender-0", "receiver-0",
                             chromecast.NS_EMPFAENGER, '{"type":"PING"}')
    namespace, nutzlast = chromecast.dekodiere(roh)
    assert namespace == chromecast.NS_EMPFAENGER
    assert json.loads(nutzlast) == {"type": "PING"}


def test_protobuf_ueberspringt_unbekannte_felder():
    # Ein payload_binary-Feld (7, wire 2) anhaengen — muss ignoriert werden,
    # ohne namespace/nutzlast zu verlieren.
    roh = chromecast.kodiere("s", "d", "ns", "x")
    roh += chromecast._feld_string(7, "egal")
    namespace, nutzlast = chromecast.dekodiere(roh)
    assert namespace == "ns" and nutzlast == "x"


def test_varint_mehrbyte():
    # 300 braucht zwei Bytes (0xAC 0x02) — die Grenze, an der Einbyte kippt.
    assert chromecast._varint(300) == b"\xac\x02"
    wert, i = chromecast._lies_varint(b"\xac\x02", 0)
    assert wert == 300 and i == 2


# ───────────────────────────── avahi-Parsing ───────────────────────────────
AVAHI = (
    '+;eth0;IPv4;Chromecast-Ultra;_googlecast._tcp;local\n'
    '=;eth0;IPv4;Chromecast-Ultra;_googlecast._tcp;local;cc.local;'
    '192.168.2.2;8009;"id=abc123" "md=Chromecast Ultra" "fn=Buero"\n'
)


def test_avahi_wird_zu_geraet():
    geraete = chromecast._aus_avahi(AVAHI)
    assert len(geraete) == 1
    g = geraete[0]
    assert g["ip"] == "192.168.2.2"
    assert g["port"] == 8009
    assert g["name"] == "Buero"
    assert g["modell"] == "Chromecast Ultra"


def test_avahi_ohne_eintraege():
    assert chromecast._aus_avahi("+;eth0;IPv4;x;_googlecast._tcp;local\n") == []


# ───────────────────────────── Fake-Socket ─────────────────────────────────
class FakeSock:
    """Spielt einen Chromecast nach: nimmt Rahmen entgegen, gibt vorbereitete
    Antwortrahmen zurueck. Nur so viel, wie `spiele()` wirklich liest."""

    def __init__(self, antworten):
        self._eingang = bytearray()
        self.gesendet = []
        self._aus = bytearray()
        for ziel, ns, last in antworten:
            rahmen = chromecast.kodiere("r", "s", ns, json.dumps(last))
            self._aus += struct.pack(">I", len(rahmen)) + rahmen

    def sendall(self, daten):
        # Rahmen zerlegen und als (namespace, nutzlast) merken.
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


def _verbindung_mit(monkeypatch, antworten):
    fake = FakeSock(antworten)

    def fake_enter(self):
        self.sock = fake
        return self

    monkeypatch.setattr(chromecast.CastVerbindung, "__enter__", fake_enter)
    return fake


def test_spiele_sendet_launch_und_load(monkeypatch):
    status = {
        "type": "RECEIVER_STATUS",
        "status": {"applications": [
            {"appId": chromecast.STANDARD_EMPFAENGER, "transportId": "web-1"}]},
    }
    fake = _verbindung_mit(monkeypatch, [
        (chromecast._PLATTFORM, chromecast.NS_EMPFAENGER, status),
        ("web-1", chromecast.NS_MEDIEN, {"type": "MEDIA_STATUS"}),
    ])

    ok, meldung = chromecast.spiele("192.168.2.2", "http://host/media/videos/a.mp4")
    assert ok, meldung

    typen = [json.loads(last).get("type") for _, last in fake.gesendet]
    assert "CONNECT" in typen
    assert "LAUNCH" in typen
    assert "LOAD" in typen
    # LOAD muss an die transportId gehen, nicht an die Plattform.
    load = next(last for ns, last in fake.gesendet if json.loads(last).get("type") == "LOAD")
    assert json.loads(load)["media"]["contentId"].endswith("a.mp4")


def test_spiele_meldet_launch_error(monkeypatch):
    _verbindung_mit(monkeypatch, [
        (chromecast._PLATTFORM, chromecast.NS_EMPFAENGER,
         {"type": "LAUNCH_ERROR", "reason": "NOT_FOUND"}),
    ])
    ok, meldung = chromecast.spiele("192.168.2.2", "http://host/x.mp4",
                                    app_id="EIGEN123")
    assert not ok
    assert "EIGEN123" in meldung and "registriert" in meldung


def test_spiele_unerreichbar_wirft_nicht(monkeypatch):
    def wirf(self):
        raise OSError("keine Route zum Host")
    monkeypatch.setattr(chromecast.CastVerbindung, "__enter__", wirf)
    ok, meldung = chromecast.spiele("10.0.0.1", "http://host/x.mp4")
    assert not ok
    assert "nicht erreichbar" in meldung


# ───────────────────────────── Config ──────────────────────────────────────
def test_cast_default_vorhanden():
    assert config_schema.DEFAULT_CONFIG["cast"]["modus"] == "medien"


def test_pruefe_cast_nimmt_gueltiges():
    out = config_schema.pruefe_cast(
        {"aktiv": True, "geraet_ip": "192.168.2.2", "modus": "anzeige",
         "app_id": "ABCD1234"})
    assert out["aktiv"] is True
    assert out["geraet_ip"] == "192.168.2.2"
    assert out["modus"] == "anzeige"
    assert out["app_id"] == "ABCD1234"


def test_pruefe_cast_lehnt_modus_ab():
    with pytest.raises(ValueError):
        config_schema.pruefe_cast({"modus": "quatsch"})


def test_pruefe_cast_lehnt_ip_ab():
    with pytest.raises(ValueError):
        config_schema.pruefe_cast({"geraet_ip": "evil;rm -rf"})


def test_heile_cast_repariert_statt_abbruch():
    # Unsinn -> Vorgabe, kein Wurf.
    assert config_schema.heile_cast("kaputt") == config_schema.DEFAULT_CONFIG["cast"]
    assert config_schema.heile_cast({"modus": "nope"}) == config_schema.DEFAULT_CONFIG["cast"]

import socket
import struct
import unittest
import zlib

import multicast
from config_schema import DEFAULT_CONFIG, heile_multicast, pruefe_multicast


class SapTest(unittest.TestCase):
    def test_sdp_beschreibt_kanal(self):
        t = multicast.sdp("BGHM", "239.10.10.211", 1000, "192.168.1.5")
        self.assertIn("s=BGHM\r\n", t)
        self.assertIn("c=IN IP4 239.10.10.211/16\r\n", t)
        self.assertIn("m=video 1000 RTP/AVP 33\r\n", t)
        self.assertTrue(t.startswith("v=0\r\n"))

    def test_sap_kopf(self):
        t = multicast.sdp("X", "239.1.1.1", 5004, "10.0.0.2")
        p = multicast.sap_paket(t, "10.0.0.2")
        erstes, auth, h, ip = struct.unpack("!BBH4s", p[:8])
        self.assertEqual(erstes, 0x20)
        self.assertEqual(auth, 0)
        self.assertEqual(h, zlib.crc32(t.encode()) & 0xFFFF)
        self.assertEqual(socket.inet_ntoa(ip), "10.0.0.2")
        self.assertEqual(p[8:24], b"application/sdp\x00")
        self.assertEqual(p[24:].decode(), t)

    def test_loeschpaket(self):
        p = multicast.sap_paket("v=0\r\n", "10.0.0.2", loeschen=True)
        self.assertEqual(p[0], 0x24)

    def test_ffmpeg_befehl(self):
        b = multicast.ffmpeg_befehl("a.mp4", "239.10.10.211", 1000)
        self.assertIn("-stream_loop", b)
        self.assertEqual(b[-1], "rtp://239.10.10.211:1000?ttl=16&pkt_size=1316")
        self.assertIn("0:168", b)
        self.assertIn("1:170", b)

    def test_anzeige_befehl(self):
        b = multicast.anzeige_befehl(":99", "lz_multicast.monitor", "239.1.1.1", 5000, fps=25)
        self.assertEqual(b[b.index("x11grab") - 1:b.index("x11grab") + 1], ["-f", "x11grab"])
        self.assertIn("lz_multicast.monitor", b)
        self.assertEqual(b[b.index("-g") + 1], "25")
        self.assertTrue(b[-1].startswith("rtp://239.1.1.1:5000"))

    def test_anzeige_ohne_ton_sendet_stille(self):
        b = multicast.anzeige_befehl(":99", None, "239.1.1.1", 5000)
        self.assertIn("anullsrc=r=48000:cl=stereo", b)


class EinstellungenTest(unittest.TestCase):
    def test_vorgabe_ist_gueltig(self):
        self.assertEqual(pruefe_multicast({}), DEFAULT_CONFIG["multicast"])

    def test_keine_multicast_adresse(self):
        with self.assertRaisesRegex(ValueError, "multicast.gruppe"):
            pruefe_multicast({"gruppe": "192.168.1.5"})

    def test_zahlengrenzen_und_typen(self):
        for feld, wert in (("port", 0), ("fps", 120), ("bitrate_k", "8000"), ("ttl", True)):
            with self.assertRaisesRegex(ValueError, f"multicast.{feld}"):
                pruefe_multicast({feld: wert})

    def test_gleiche_pids(self):
        with self.assertRaisesRegex(ValueError, "pid_audio"):
            pruefe_multicast({"pid_video": 200, "pid_audio": 200})

    def test_heilen_faellt_auf_vorgabe(self):
        self.assertEqual(heile_multicast({"modus": "quatsch"}), DEFAULT_CONFIG["multicast"])
        self.assertEqual(heile_multicast(None), DEFAULT_CONFIG["multicast"])


if __name__ == "__main__":
    unittest.main()

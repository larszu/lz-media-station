import socket
import struct
import unittest
import zlib

import multicast


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


if __name__ == "__main__":
    unittest.main()

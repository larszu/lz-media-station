#!/usr/bin/env python3
"""Multicast-Kanal als Ausgabeziel: eine Datei endlos als RTP/MPEG-TS ins
Netz senden und per SAP ankuendigen — der Weg, auf dem IPTV-Anlagen
(Hotel-TVs, Kopfstellen, VLC „Lokales Netzwerk") einen Kanal empfangen.

Entspricht der verbreiteten VLC-Zeile
    vlc datei.mp4 --repeat :sout=#transcode{scodec=none}:rtp{dst=239.x.x.x,
        port=1000,mux=ts{tsid=1234,pid-video=168,pid-audio=170},sap,name=…}
nur mit ffmpeg (Bild/Ton unveraendert kopiert, Untertitel weg) und einem
eigenen SAP-Sender, weil ffmpeg SAP nicht zusammen mit MPEG-TS kann.

SAP (RFC 2974): alle paar Sekunden ein UDP-Paket an 239.255.255.255:9875
mit einer SDP-Beschreibung (RFC 4566) des Kanals. Beim Stoppen ein
Loesch-Paket, damit der Kanal aus den Listen verschwindet.
"""
import os
import shutil
import socket
import struct
import subprocess
import threading
import zlib

SAP_GRUPPE = "239.255.255.255"
SAP_PORT = 9875
SAP_INTERVALL_S = 5


def sdp(name, gruppe, port, quelle_ip, ttl=16, sitzung_id=None):
    """SDP-Text fuer einen RTP/MPEG-TS-Kanal (Payload-Typ 33 = MP2T)."""
    sid = sitzung_id if sitzung_id is not None else zlib.crc32(
        f"{gruppe}:{port}".encode()) & 0x7FFFFFFF
    return ("v=0\r\n"
            f"o=- {sid} 1 IN IP4 {quelle_ip}\r\n"
            f"s={name}\r\n"
            f"c=IN IP4 {gruppe}/{ttl}\r\n"
            "t=0 0\r\n"
            "a=tool:lz-media-station\r\n"
            "a=type:broadcast\r\n"
            f"m=video {port} RTP/AVP 33\r\n"
            "a=rtpmap:33 MP2T/90000\r\n")


def sap_paket(sdp_text, quelle_ip, loeschen=False):
    """Ein SAP-Paket: 8 Byte Kopf, MIME-Typ, SDP.

    Kopf: V=1, IPv4, Typ Ankuendigung/Loeschung, keine Verschluesselung/
    Kompression, Auth-Laenge 0, 16-Bit-Hash aus dem SDP, Quell-IP.
    """
    erstes = 0x20 | (0x04 if loeschen else 0)
    hash16 = zlib.crc32(sdp_text.encode()) & 0xFFFF
    kopf = struct.pack("!BBH4s", erstes, 0, hash16, socket.inet_aton(quelle_ip))
    return kopf + b"application/sdp\x00" + sdp_text.encode()


def ffmpeg_befehl(datei, gruppe, port, *, ttl=16, tsid=1234,
                  pid_video=168, pid_audio=170, schleife=True):
    befehl = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re"]
    if schleife:
        befehl += ["-stream_loop", "-1"]
    befehl += ["-i", datei, "-map", "0:v:0?", "-map", "0:a:0?", "-sn",
               "-c", "copy",
               "-mpegts_transport_stream_id", str(tsid),
               "-streamid", f"0:{pid_video}", "-streamid", f"1:{pid_audio}",
               "-f", "rtp_mpegts", f"rtp://{gruppe}:{port}?ttl={ttl}&pkt_size=1316"]
    return befehl


def _quell_ip(gruppe):
    """Die eigene Adresse, ueber die Multicast hinausgeht."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((gruppe, 9))
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()


class Kanal:
    """Ein laufender Multicast-Kanal (ffmpeg + SAP-Thread)."""

    def __init__(self, datei, gruppe, port, name, *, ttl=16, sap=True, **ts):
        self.datei, self.gruppe, self.port, self.name = datei, gruppe, port, name
        self.ttl, self.sap, self.ts = ttl, sap, ts
        self.quelle = _quell_ip(gruppe)
        self._proc = None
        self._halt = threading.Event()
        self._thread = None

    def start(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg nicht gefunden")
        if not os.path.isfile(self.datei):
            raise FileNotFoundError(self.datei)
        self._proc = subprocess.Popen(
            ffmpeg_befehl(self.datei, self.gruppe, self.port, ttl=self.ttl, **self.ts),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)
        if self.sap:
            self._thread = threading.Thread(target=self._sap_schleife, daemon=True)
            self._thread.start()

    def _sap_sende(self, sock, loeschen=False):
        text = sdp(self.name, self.gruppe, self.port, self.quelle, self.ttl)
        sock.sendto(sap_paket(text, self.quelle, loeschen), (SAP_GRUPPE, SAP_PORT))

    def _sap_schleife(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
        try:
            while not self._halt.is_set():
                try:
                    self._sap_sende(sock)
                except OSError:
                    pass
                self._halt.wait(SAP_INTERVALL_S)
            try:
                self._sap_sende(sock, loeschen=True)
            except OSError:
                pass
        finally:
            sock.close()

    def laeuft(self):
        return self._proc is not None and self._proc.poll() is None

    def fehler(self):
        if self._proc and self._proc.poll() not in (None, 0) and self._proc.stderr:
            return self._proc.stderr.read().decode(errors="replace")[-500:]
        return ""

    def stop(self):
        self._halt.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._thread:
            self._thread.join(2)

    def status(self):
        return {"laeuft": self.laeuft(), "datei": os.path.basename(self.datei),
                "url": f"rtp://{self.gruppe}:{self.port}", "name": self.name,
                "sap": self.sap, "quelle": self.quelle, "fehler": self.fehler()}

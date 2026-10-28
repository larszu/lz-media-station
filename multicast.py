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
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
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


def _ausgang(gruppe, port, ttl, tsid, pid_video, pid_audio):
    return ["-mpegts_transport_stream_id", str(tsid),
            "-streamid", f"0:{pid_video}", "-streamid", f"1:{pid_audio}",
            "-f", "rtp_mpegts", f"rtp://{gruppe}:{port}?ttl={ttl}&pkt_size=1316"]


def ffmpeg_befehl(datei, gruppe, port, *, ttl=16, tsid=1234,
                  pid_video=168, pid_audio=170, schleife=True):
    befehl = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re"]
    if schleife:
        befehl += ["-stream_loop", "-1"]
    befehl += ["-i", datei, "-map", "0:v:0?", "-map", "0:a:0?", "-sn", "-c", "copy"]
    return befehl + _ausgang(gruppe, port, ttl, tsid, pid_video, pid_audio)


def anzeige_befehl(x_display, ton_quelle, gruppe, port, *, breite=1920, hoehe=1080,
                   fps=25, bitrate_k=8000, ttl=16, tsid=1234, pid_video=168,
                   pid_audio=170):
    """Den virtuellen Schirm (X11) samt Ton als H.264/AAC-Kanal kodieren.

    `ton_quelle` ist ein PulseAudio-Monitor oder None (dann Stille — viele
    IPTV-Empfaenger schalten ohne Tonspur nicht um). GOP = 1 s, damit ein
    Fernseher beim Umschalten schnell ein Bild hat.
    """
    befehl = ["ffmpeg", "-hide_banner", "-loglevel", "error",
              "-f", "x11grab", "-draw_mouse", "0", "-framerate", str(fps),
              "-video_size", f"{breite}x{hoehe}", "-i", x_display]
    if ton_quelle:
        befehl += ["-f", "pulse", "-i", ton_quelle]
    else:
        befehl += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    befehl += ["-map", "0:v", "-map", "1:a",
               "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
               "-pix_fmt", "yuv420p", "-g", str(fps), "-b:v", f"{bitrate_k}k",
               "-maxrate", f"{bitrate_k}k", "-bufsize", f"{bitrate_k * 2}k",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    return befehl + _ausgang(gruppe, port, ttl, tsid, pid_video, pid_audio)


def browser_bin():
    for name in ("chromium", "chromium-browser", "google-chrome"):
        pfad = shutil.which(name)
        if pfad:
            return pfad
    return "/usr/lib/chromium/chromium" if os.path.exists("/usr/lib/chromium/chromium") else None


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
        self._ffmpeg(ffmpeg_befehl(self.datei, self.gruppe, self.port, ttl=self.ttl, **self.ts))
        self._sap_start()

    def _ffmpeg(self, befehl):
        self._proc = subprocess.Popen(befehl, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def _sap_start(self):
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
        return {"laeuft": self.laeuft(), "modus": "datei", "datei": os.path.basename(self.datei),
                "url": f"rtp://{self.gruppe}:{self.port}", "name": self.name,
                "sap": self.sap, "quelle": self.quelle, "fehler": self.fehler()}


class AnzeigeKanal(Kanal):
    """Die ganze Anzeige (`/display` mit Layouts, Wochenprogramm, Widgets)
    als Kanal: ein unsichtbarer Browser auf einem virtuellen Schirm (Xvfb),
    sein Ton in einer eigenen PulseAudio-Senke, beides von ffmpeg kodiert.

    Unabhaengig vom HDMI-Ausgang: die Station kann gleichzeitig lokal
    zeigen und senden, und der Kanal hat immer die volle Aufloesung.
    Nur Linux (Xvfb, x11grab, PulseAudio/PipeWire-Pulse).
    """

    SENKE = "lz_multicast"

    def __init__(self, url, gruppe, port, name, *, breite=1920, hoehe=1080,
                 fps=25, bitrate_k=8000, x_nummer=99, **rest):
        super().__init__(url, gruppe, port, name, **rest)
        self.url, self.breite, self.hoehe = url, breite, hoehe
        self.fps, self.bitrate_k = fps, bitrate_k
        self.x_display = f":{x_nummer}"
        self._neben = []
        self._modul = None

    def _neben_start(self, befehl, **env):
        p = subprocess.Popen(befehl, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env={**os.environ, **env})
        self._neben.append(p)
        return p

    def _senke(self):
        """Eigene Null-Senke anlegen; ihr Monitor ist die Tonquelle. None ohne Pulse."""
        if not shutil.which("pactl"):
            return None
        try:
            r = subprocess.run(["pactl", "load-module", "module-null-sink",
                                f"sink_name={self.SENKE}",
                                f"sink_properties=device.description={self.SENKE}"],
                               capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if r.returncode != 0:
            return None
        self._modul = r.stdout.strip()
        return f"{self.SENKE}.monitor"

    def start(self):
        if not sys.platform.startswith("linux"):
            raise RuntimeError("Anzeige als Kanal geht nur auf Linux (Xvfb)")
        fehlt = [n for n in ("ffmpeg", "Xvfb") if not shutil.which(n)]
        browser = browser_bin()
        if not browser:
            fehlt.append("chromium")
        if fehlt:
            raise RuntimeError("Fehlt: " + ", ".join(fehlt) + " (sudo apt install xvfb ffmpeg chromium)")
        self._neben_start(["Xvfb", self.x_display, "-screen", "0",
                           f"{self.breite}x{self.hoehe}x24", "-nolisten", "tcp"])
        for _ in range(50):  # bis der Socket da ist
            if os.path.exists(f"/tmp/.X11-unix/X{self.x_display[1:]}"):
                break
            time.sleep(0.1)
        ton = self._senke()
        profil = tempfile.mkdtemp(prefix="lz-multicast-")
        # Kein Uebersetzungs-Angebot im Bild, auch ohne die Pi-Policy.
        os.makedirs(os.path.join(profil, "Default"))
        with open(os.path.join(profil, "Default", "Preferences"), "w") as f:
            json.dump({"translate": {"enabled": False},
                       "intl": {"accept_languages": "de-DE,de"}}, f)
        self._neben_start([browser, "--kiosk", "--no-first-run", "--no-default-browser-check",
                           "--noerrdialogs", "--disable-infobars", "--disable-translate",
                           "--disable-features=Translate,TranslateUI,MediaRouter",
                           "--autoplay-policy=no-user-gesture-required",
                           "--password-store=basic", f"--user-data-dir={profil}", "--lang=de-DE",
                           f"--window-size={self.breite},{self.hoehe}", "--window-position=0,0",
                           "--ozone-platform=x11", self.url]
                          + (["--no-sandbox"] if os.geteuid() == 0 else []),
                          DISPLAY=self.x_display, WAYLAND_DISPLAY="", LANGUAGE="de", LANG="de_DE.UTF-8",
                          **({"PULSE_SINK": self.SENKE} if ton else {}))
        self._ffmpeg(anzeige_befehl(self.x_display, ton, self.gruppe, self.port,
                                    breite=self.breite, hoehe=self.hoehe, fps=self.fps,
                                    bitrate_k=self.bitrate_k, ttl=self.ttl, **self.ts))
        self._sap_start()

    def stop(self):
        super().stop()
        for p in reversed(self._neben):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(3)
                except subprocess.TimeoutExpired:
                    p.kill()
        self._neben = []
        if self._modul:
            subprocess.run(["pactl", "unload-module", self._modul], capture_output=True)
            self._modul = None

    def status(self):
        s = super().status()
        s.update(modus="anzeige", datei=None, seite=self.url,
                 aufloesung=f"{self.breite}x{self.hoehe}@{self.fps}")
        return s

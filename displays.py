#!/usr/bin/env python3
"""
Die Bildschirme DIESES Rechners — finden und bespielen.

─── WAS GEMELDET WURDE (Nutzer, 2026-09-15) ────────────────────────────────

„im mediaplayer das endgeraet selbst und externe displays die ans endgeraet
angeschlossen sind als mediaplayer nutzen koennen. mac und windows"

─── WAS ES VORHER GAB ──────────────────────────────────────────────────────

Genau EINEN Schirm, und der war der HDMI-Ausgang eines Raspberry Pi. Die
Anzeige ist seit jeher eine Browser-Seite (`/display`) — auf dem Pi oeffnet
sie ein Chromium im Kiosk-Betrieb, und mehr Bildschirme hat ein Pi in
diesem Aufbau nicht.

Auf einem Notebook oder einem Rechner am Aufbau ist das anders: dort haengt
oft mehr als ein Schirm, und der eingebaute zaehlt mit. Die Station konnte
davon nichts nutzen. Wer zwei Schirme bespielen wollte, brauchte zwei
Rechner — oder er zog ein Browserfenster von Hand hinueber und drueckte F11.

─── WAS DIESES MODUL TUT ───────────────────────────────────────────────────

Zwei Dinge, und beide ohne neue Abhaengigkeit:

  1. ZAEHLT DIE BILDSCHIRME AUF, je System auf dem Weg, den das System
     selbst anbietet:

        Windows   ctypes -> user32.EnumDisplayMonitors  (Standardbibliothek)
        macOS     system_profiler SPDisplaysDataType -json
        Linux     xrandr --listmonitors

  2. OEFFNET DIE ANZEIGE-SEITE AUF EINEM BESTIMMTEN SCHIRM, als eigenes
     Browserfenster.

─── DER EHRLICHE TEIL: WARUM POSITION UND NICHT „SCHIRM NUMMER 2" ──────────

Es gibt keinen Weg, einem Browser zu sagen „geh auf Schirm 2 in den
Vollbildmodus". Was es gibt, ist ein Fenster an einer POSITION: jeder
Schirm hat im gemeinsamen Koordinatensystem des Systems eine Ecke, und ein
Fenster, das dort aufgeht, liegt auf diesem Schirm.

Genau das tun `--window-position` und `--window-size`; `--start-fullscreen`
macht daraus ein randloses Bild. Das ist die uebliche Loesung und sie hat
eine bekannte Grenze: verschiebt jemand die Schirme in den
Systemeinstellungen, waehrend ein Fenster offen ist, bleibt das Fenster, wo
es ist. Dieses Modul zaehlt beim OEFFNEN auf, nicht dauernd.

`--user-data-dir` je Schirm ist kein Schmuck: ohne ein eigenes Profil
faltet Chrome den zweiten Aufruf in das BESTEHENDE Fenster und der zweite
Schirm bleibt schwarz. Das ist der Fehler, den man dabei zuerst macht.

─── WAS DIESES MODUL NICHT KANN, und das steht auch in der Oberflaeche ─────

  * Es kann keinen Browser installieren. Findet es keinen, sagt es das
    samt der Stellen, an denen es gesucht hat — statt still nichts zu tun.
  * Es weiss nicht, was auf einem Schirm zu SEHEN ist. Es oeffnet ein
    Fenster an einer Stelle; ob dort ein Beamer, ein Fernseher oder nichts
    haengt, sagt ihm niemand.
  * Es raeumt nur auf, was es selbst gestartet hat. Ein von Hand
    geoeffnetes Fenster fasst es nicht an.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

#: Was ein Schirm ist: Ecke, Groesse, Name, und ob er der Hauptschirm ist.
#: `x`/`y` sind Koordinaten im gemeinsamen System — auf einem zweiten Schirm
#: links vom ersten ist `x` negativ, und das ist kein Fehler.


def _windows_schirme():
    """user32.EnumDisplayMonitors ueber ctypes — ohne Zusatzpaket.

    `GetMonitorInfoW` liefert `rcMonitor` (die ganze Flaeche) und
    `rcWork` (ohne Taskleiste). Genommen wird `rcMonitor`: eine
    Vollbild-Anzeige deckt die Taskleiste ab, das ist der Sinn.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()  # sonst sind alle Zahlen skaliert

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    MONITORINFOF_PRIMARY = 0x1
    gefunden = []

    PROTO = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                               ctypes.POINTER(RECT), ctypes.c_double)

    def rueckruf(hmon, _hdc, _rect, _data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            gefunden.append({
                "name": info.szDevice or f"Display {len(gefunden) + 1}",
                "x": r.left, "y": r.top,
                "breite": r.right - r.left, "hoehe": r.bottom - r.top,
                "haupt": bool(info.dwFlags & MONITORINFOF_PRIMARY),
            })
        return 1

    user32.EnumDisplayMonitors(0, 0, PROTO(rueckruf), 0)
    return gefunden


def _macos_schirme(ausgabe=None):
    """`system_profiler SPDisplaysDataType -json`.

    Die Ausgabe nennt Aufloesung und Hauptschirm, aber KEINE Koordinaten —
    macOS legt sie nicht dorthin. Die Ecken werden deshalb aus den Breiten
    aufgereiht: Hauptschirm bei 0/0, die uebrigen rechts daneben.

    DAS IST EINE ANNAHME UND SIE STEHT HIER, statt sich als Messung
    auszugeben: wer seine Schirme in den Systemeinstellungen uebereinander
    oder links legt, bekommt das Fenster an der falschen Stelle. Es geht
    dann trotzdem auf und laesst sich verschieben — das ist die Grenze
    dieses Weges, nicht ein Fehlschlag.
    """
    if ausgabe is None:
        ausgabe = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    daten = json.loads(ausgabe)

    roh = []
    for karte in daten.get("SPDisplaysDataType", []):
        for schirm in karte.get("spdisplays_ndrvs", []) or []:
            name = schirm.get("_name") or "Display"
            # `spdisplays_resolution` sieht aus wie „3840 x 2160 (2160p …)".
            text = (schirm.get("_spdisplays_resolution")
                    or schirm.get("spdisplays_resolution") or "")
            breite = hoehe = 0
            teile = text.replace("×", "x").split("x")
            if len(teile) >= 2:
                try:
                    breite = int("".join(c for c in teile[0] if c.isdigit()))
                    hoehe = int("".join(c for c in teile[1].split("(")[0] if c.isdigit()))
                except ValueError:
                    breite = hoehe = 0
            haupt = str(schirm.get("spdisplays_main", "")).lower() in (
                "spdisplays_yes", "yes", "true", "1")
            roh.append({"name": name, "breite": breite, "hoehe": hoehe, "haupt": haupt})

    if not roh:
        return []
    # Hauptschirm nach vorn, dann aufreihen.
    roh.sort(key=lambda s: not s["haupt"])
    x = 0
    for s in roh:
        s["x"], s["y"] = x, 0
        x += s["breite"] or 1920
    return roh


#: `1920/344x1080/193+0+0` — Breite/mm x Hoehe/mm +x +y, Vorzeichen erlaubt.
_XRANDR_GEOMETRIE = re.compile(
    r"^(\d+)(?:/\d+)?x(\d+)(?:/\d+)?([-+]\d+)([-+]\d+)$")


def _linux_schirme(ausgabe=None):
    """`xrandr --listmonitors` — eine Zeile je Schirm, mit Geometrie.

        0: +*eDP-1 1920/344x1080/193+0+0  eDP-1
                   ^Breite  ^Hoehe  ^x ^y

    Das `*` markiert den Hauptschirm, das `+` heisst „verbunden".
    """
    if ausgabe is None:
        if not shutil.which("xrandr"):
            return []
        ausgabe = subprocess.run(["xrandr", "--listmonitors"],
                                 capture_output=True, text=True, timeout=10).stdout
    schirme = []
    for zeile in ausgabe.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("Monitors:"):
            continue
        teile = zeile.split()
        if len(teile) < 3:
            continue
        marke, geometrie = teile[1], teile[2]
        # DIE ECKEN DUERFEN NEGATIV SEIN, und genau daran ist der erste
        # Anlauf gescheitert: er trennte an `+`, und ein Schirm LINKS vom
        # Hauptschirm steht bei `-1920+0`. Der Eintrag fiel dann still aus
        # der Liste — also ausgerechnet der zweite Schirm, um den es hier
        # geht. Ein Mustervergleich mit Vorzeichen trennt beides sauber.
        treffer = _XRANDR_GEOMETRIE.match(geometrie)
        if not treffer:
            continue
        breite, hoehe, x, y = (int(g) for g in treffer.groups())
        schirme.append({
            "name": marke.lstrip("+*"),
            "breite": breite, "hoehe": hoehe,
            "x": x, "y": y,
            "haupt": "*" in marke,
        })
    return schirme


def schirme():
    """Alle Bildschirme dieses Rechners. Leere Liste, wenn keiner zu finden ist.

    Wirft NICHT. Ein Rechner ohne Grafik (ein Pi ohne X, ein Server) ist
    kein Fehlerfall, sondern ein Rechner ohne Bildschirme — und die Station
    laeuft dort weiter, sie bespielt nur nichts vor Ort.
    """
    try:
        if sys.platform == "win32":
            return _windows_schirme()
        if sys.platform == "darwin":
            return _macos_schirme()
        return _linux_schirme()
    except Exception:
        return []


#: Wo ein Browser stehen koennte. Reihenfolge = Vorzug; Chrome/Chromium und
#: Edge koennen `--app` und `--window-position`, Firefox und Safari nicht —
#: deshalb stehen die beiden hier nicht drin. Ein Eintrag, der die noetigen
#: Schalter nicht kennt, waere kein Fund, sondern ein falsches Versprechen.
BROWSER_PFADE = {
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
    "linux": [],  # dort ueber `shutil.which`, siehe unten
}

LINUX_BROWSER = ["chromium", "chromium-browser", "google-chrome",
                 "google-chrome-stable", "microsoft-edge"]


def finde_browser():
    """Pfad zu einem Browser, der `--app` und `--window-position` kann.

    Gibt `None` zurueck, wenn keiner da ist — und der Aufrufer sagt dann,
    WO gesucht wurde. Ein „geht nicht" ohne Ort ist fuer den Nutzer dasselbe
    wie Schweigen.
    """
    if sys.platform in ("win32", "darwin"):
        for pfad in BROWSER_PFADE[sys.platform]:
            if os.path.exists(pfad):
                return pfad
        return None
    for name in LINUX_BROWSER:
        pfad = shutil.which(name)
        if pfad:
            return pfad
    return None


def suchorte():
    """Die Stellen, an denen `finde_browser` nachgesehen hat — fuer die Meldung."""
    if sys.platform in ("win32", "darwin"):
        return list(BROWSER_PFADE[sys.platform])
    return [f"PATH: {name}" for name in LINUX_BROWSER]


def _profil_verzeichnis(index):
    """Ein eigenes Profil je Schirm.

    OHNE DAS BLEIBT DER ZWEITE SCHIRM SCHWARZ: ein zweiter Chrome-Aufruf mit
    demselben Profil faltet sich in das bestehende Fenster, statt ein neues
    zu oeffnen. Das ist der Fehler, den man hier zuerst macht, und er sieht
    aus wie „der zweite Schirm geht nicht".
    """
    pfad = os.path.join(tempfile.gettempdir(), f"lz-media-display-{index}")
    os.makedirs(pfad, exist_ok=True)
    return pfad


def oeffne_auf_schirm(url, schirm, index, browser=None):
    """Die Anzeige-Seite als eigenes Fenster auf diesem Schirm.

    Gibt den Prozess zurueck, oder wirft `RuntimeError` mit einem Grund, den
    man lesen kann.
    """
    exe = browser or finde_browser()
    if not exe:
        orte = "\n  ".join(suchorte())
        raise RuntimeError(
            "Kein Chrome, Chromium oder Edge gefunden. Gesucht:\n  " + orte +
            "\n(Firefox und Safari koennen kein Fenster auf einem bestimmten "
            "Schirm oeffnen — deshalb stehen sie nicht in der Liste.)")

    argumente = [
        exe,
        f"--app={url}",
        f"--window-position={schirm['x']},{schirm['y']}",
        f"--window-size={schirm['breite']},{schirm['hoehe']}",
        "--start-fullscreen",
        "--new-window",
        f"--user-data-dir={_profil_verzeichnis(index)}",
        # Eine Anzeige am Aufbau soll nichts fragen und nichts anbieten.
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--autoplay-policy=no-user-gesture-required",
    ]
    return subprocess.Popen(argumente, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


class Anzeigen:
    """Die offenen Anzeige-Fenster — eines je Schirm.

    Haelt nur, was SIE gestartet hat. Ein von Hand geoeffnetes Fenster fasst
    sie nicht an, und sie behauptet auch nicht, es zu kennen.
    """

    def __init__(self):
        self._offen = {}

    def starte(self, url, auswahl=None):
        """Auf allen Schirmen oeffnen, oder auf den genannten (0-basiert).

        Gibt `(gestartet, meldungen)` zurueck — beides, weil ein Teilerfolg
        der Normalfall ist: drei Schirme, einer schon offen.
        """
        gefunden = schirme()
        if not gefunden:
            return [], ["Keine Bildschirme gefunden."]

        indizes = range(len(gefunden)) if auswahl is None else auswahl
        gestartet, meldungen = [], []
        for i in indizes:
            if i < 0 or i >= len(gefunden):
                meldungen.append(f"Schirm {i} gibt es nicht "
                                 f"({len(gefunden)} gefunden).")
                continue
            if i in self._offen and self._offen[i].poll() is None:
                meldungen.append(f"Schirm {i} zeigt schon.")
                continue
            try:
                self._offen[i] = oeffne_auf_schirm(url, gefunden[i], i)
                gestartet.append(i)
            except (RuntimeError, OSError) as e:
                meldungen.append(f"Schirm {i}: {e}")
        return gestartet, meldungen

    def beende(self, auswahl=None):
        """Schliesst die Fenster, die dieses Objekt geoeffnet hat."""
        beendet = []
        for i in list(self._offen):
            if auswahl is not None and i not in auswahl:
                continue
            p = self._offen.pop(i)
            try:
                p.terminate()
            except OSError:
                pass
            beendet.append(i)
        return beendet

    def zustand(self):
        """Je Schirm: gibt es ihn, und zeigt er gerade?"""
        gefunden = schirme()
        return [
            {
                **s,
                "index": i,
                "zeigt": i in self._offen and self._offen[i].poll() is None,
            }
            for i, s in enumerate(gefunden)
        ]

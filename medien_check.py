"""Prueft hochgeladene Videos darauf, ob ein Pi sie fluessig abspielt.

WARUM ES DAS GIBT. Der haeufigste Ausfallgrund einer Medienstation ist kein
Defekt, sondern eine Datei: ein 4K-Video mit 60 fps sieht auf dem Notebook
grossartig aus und ruckelt auf dem Pi zur Diashow. Bemerkt wird das
typischerweise beim Aufbau — oder in der Ausstellung.

Der Upload war bisher stumm: jede Datei mit erlaubter Endung galt als gut.

ZWEI TEILE, GETRENNT:

* `beurteile(...)` ist rein — sie bekommt Breite, Hoehe, Codec und Bitrate
  HEREINGEREICHT und entscheidet. Nur deshalb sind die interessanten Faelle
  ueberhaupt testbar: ein echtes 4K-Video in die CI zu legen, um eine Warnung
  auszuloesen, waere absurd.
* `pruefe_datei(...)` misst — sie ruft `ffprobe`. Fehlt es, gibt es KEINE
  Warnung und keinen Fehler, sondern die ehrliche Auskunft „nicht geprueft".
  Ein fehlendes Hilfsprogramm darf keinen Upload verhindern.

KEINE ABLEHNUNG. Es sind Hinweise, keine Sperren. Wer weiss, was er tut (ein
Pi 5 mit einem kurzen 4K-Clip), soll nicht vom Werkzeug ausgebremst werden.
"""
import json
import shutil
import subprocess

PROGRAMM = "ffprobe"
ZEITGRENZE_S = 20

#: Darueber wird es auf einem Pi eng. 1080p ist das, was die
#: Hardware-Dekodierung zuverlaessig schafft.
MAX_BREITE = 1920
MAX_HOEHE = 1080

#: Bildrate, ab der auch 1080p knapp wird.
MAX_BILDRATE = 31.0

#: Bitrate in Bit/s. Darueber limitiert eher die SD-Karte als der Dekoder.
MAX_BITRATE = 20_000_000

#: Was der Pi in Hardware dekodiert. Alles andere landet in der CPU.
GUTE_CODECS = ("h264",)


def beurteile(breite=None, hoehe=None, codec=None, bildrate=None, bitrate=None):
    """Hinweise zu einer Videodatei. Leere Liste heisst: unauffaellig.

    Rein und ohne Dateisystem — die unangenehmen Faelle (4K, 60 fps, exotischer
    Codec) lassen sich sonst in keiner CI herstellen.
    """
    hinweise = []
    if codec and codec.lower() not in GUTE_CODECS:
        hinweise.append(
            f"Codec {codec} wird auf dem Pi nicht in Hardware dekodiert — "
            "H.264 (MP4) laeuft dort deutlich fluessiger.")
    if breite and hoehe and (breite > MAX_BREITE or hoehe > MAX_HOEHE):
        hinweise.append(
            f"Aufloesung {breite}x{hoehe} liegt ueber {MAX_BREITE}x{MAX_HOEHE} — "
            "auf einem Pi ruckelt das erfahrungsgemaess.")
    if bildrate and bildrate > MAX_BILDRATE:
        hinweise.append(
            f"{bildrate:.0f} Bilder/s — 25 oder 30 reichen fuer eine "
            "Medienstation und entlasten den Dekoder.")
    if bitrate and bitrate > MAX_BITRATE:
        hinweise.append(
            f"Bitrate {bitrate / 1_000_000:.1f} Mbit/s ist sehr hoch — hier "
            "limitiert eher die SD-Karte als der Dekoder.")
    return hinweise


def _bildrate(text):
    """ffprobe liefert die Bildrate als Bruch ('30000/1001'). None bei Unsinn."""
    if not text or "/" not in str(text):
        return None
    zaehler, _, nenner = str(text).partition("/")
    try:
        z, n = float(zaehler), float(nenner)
        return z / n if n else None
    except ValueError:
        return None


def verfuegbar():
    return shutil.which(PROGRAMM) is not None


def pruefe_datei(pfad):
    """(geprueft, hinweise) fuer eine Videodatei.

    `geprueft=False` heisst „konnte nicht nachsehen" (kein ffprobe, kaputte
    Datei) — das ist ausdruecklich KEINE Entwarnung und wird auch nicht als
    solche gemeldet. Wirft nie.
    """
    if not verfuegbar():
        return False, []
    try:
        roh = subprocess.run(
            [PROGRAMM, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name,avg_frame_rate,bit_rate",
             "-show_entries", "format=bit_rate",
             "-of", "json", pfad],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=ZEITGRENZE_S, check=True).stdout
        daten = json.loads(roh)
    except Exception:
        return False, []

    spuren = daten.get("streams") or []
    if not spuren:
        return False, []
    spur = spuren[0]

    def zahl(wert):
        try:
            return float(wert)
        except (TypeError, ValueError):
            return None

    # Die Bitrate steht je nach Container in der Spur ODER im Format.
    bitrate = zahl(spur.get("bit_rate")) or zahl((daten.get("format") or {}).get("bit_rate"))
    return True, beurteile(
        breite=zahl(spur.get("width")),
        hoehe=zahl(spur.get("height")),
        codec=spur.get("codec_name"),
        bildrate=_bildrate(spur.get("avg_frame_rate")),
        bitrate=bitrate,
    )

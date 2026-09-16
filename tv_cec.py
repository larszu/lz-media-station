"""Fernseher per HDMI-CEC ein-/ausschalten — optional und ohne Eigengefahr.

Ausserhalb der Oeffnungszeiten wird der Schirm schwarz und der Ton aus. Das
spart aber keinen Strom und schont kein Panel: der Fernseher laeuft weiter.
Mit CEC laesst er sich ueber dasselbe HDMI-Kabel mit abschalten.

WARUM SO VORSICHTIG. `cec-client` ist ein externes Programm, das auf den
meisten Geraeten gar nicht installiert ist, und CEC ist zwischen Herstellern
notorisch unzuverlaessig. Deshalb gilt hier durchgehend: **ein Fehlschlag ist
kein Fehler der Station.** Es gibt eine Zeile im Log und sonst nichts — die
Medienwiedergabe darf davon nie abhaengen.

Absichtlich NICHT getestet: der tatsaechliche Schaltvorgang. Dafuer braeuchte
es einen Fernseher. Getestet wird der Weg, der im Betrieb wirklich zaehlt:
fehlt `cec-client`, sagt die Funktion das und wirft nicht.
"""
import shutil
import subprocess

#: Name des Programms. Als Konstante, damit der Test ihn ersetzen kann.
PROGRAMM = "cec-client"

#: Laenger als das darf ein Schaltversuch nicht dauern. Ein haengendes
#: `cec-client` wuerde sonst die Steuerschleife blockieren.
ZEITGRENZE_S = 10


def verfuegbar():
    """Ist `cec-client` auf diesem Geraet installiert?"""
    return shutil.which(PROGRAMM) is not None


def schalte(an):
    """Fernseher ein- (`an=True`) oder ausschalten. Gibt (ok, meldung) zurueck.

    Wirft NIE. Der Aufrufer soll den Rueckgabewert loggen duerfen und
    ansonsten weiterarbeiten.
    """
    if not verfuegbar():
        return False, f"{PROGRAMM} ist nicht installiert — CEC uebersprungen"
    # "on 0" / "standby 0" an das TV-Geraet (logische Adresse 0).
    befehl = "on 0" if an else "standby 0"
    try:
        subprocess.run(
            [PROGRAMM, "-s", "-d", "1"],
            input=befehl.encode(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ZEITGRENZE_S,
            check=True,
        )
        return True, f"CEC: {befehl}"
    except subprocess.TimeoutExpired:
        return False, f"CEC: {PROGRAMM} antwortet nicht (>{ZEITGRENZE_S}s)"
    except Exception as e:
        return False, f"CEC: {befehl} fehlgeschlagen ({e})"

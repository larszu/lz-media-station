"""Zustandspruefung: was an dieser Station gerade nicht stimmt.

WARUM ES DAS GIBT. Die Station steht unbeaufsichtigt in einer Ausstellung. Ein
toter Sensor, eine volle Platte oder eine Zone ohne Medien fielen bisher NUR
im Log auf — und das liest niemand, solange niemand einen Verdacht hat. Der
Ausfall wurde dadurch typischerweise vom Kunden gemeldet, nicht vom Betreiber
bemerkt.

Diese Pruefung buendelt die Befunde an EINER Stelle, damit die Verwaltung sie
zeigen und der Station Manager sie ueber `/api/identity` einsammeln kann, ohne
jede Station einzeln aufzurufen.

REINE FUNKTION. `pruefe` bekommt die Lage HEREINGEREICHT — Sensorzustand,
freier Platz, vorhandene Dateien — und sieht selbst weder auf die Platte noch
auf die Uhr. Sonst waere jeder Befund nur mit echtem Dateisystem testbar, und
genau die unangenehmen Faelle (Platte fast voll) liessen sich gar nicht
herstellen.
"""

#: Von harmlos nach schlimm. Die Reihenfolge entscheidet die Gesamtstufe.
STUFEN = ("ok", "hinweis", "warnung", "fehler")

#: Weniger freier Platz als das ist ein Fehler — ein Upload schlaegt dann fehl,
#: und auf einer vollen Platte kann auch die Statistik nicht mehr schreiben.
PLATZ_FEHLER_B = 200 * 1024 * 1024

#: Darunter wird es knapp. Frueh genug, um vor der naechsten Ausstellung noch
#: aufzuraeumen.
PLATZ_WARNUNG_B = 1024 * 1024 * 1024

MEDIENARTEN = ("videos", "images", "audio")


def _befund(stufe, thema, text):
    return {"stufe": stufe, "thema": thema, "text": text}


def gesamtstufe(befunde):
    """Die schlimmste vorkommende Stufe — oder "ok", wenn nichts anliegt."""
    schlimmste = "ok"
    for b in befunde:
        if STUFEN.index(b["stufe"]) > STUFEN.index(schlimmste):
            schlimmste = b["stufe"]
    return schlimmste


def pruefe(config, sensor_ok, sensor_status, freier_platz_b, vorhandene,
           aktiv, geschlossen):
    """Alle Befunde als Liste. Leer heisst: nichts zu melden.

    `vorhandene` ist {"videos": {...}, "images": {...}, "audio": {...}} mit den
    Dateinamen, die wirklich auf der Platte liegen.
    """
    befunde = []

    # --- Sensor -----------------------------------------------------------
    # Ausserhalb der Oeffnungszeiten ist „keine Messung" kein Befund: dann
    # soll gar nicht ausgeloest werden. Das sonst zu melden waere ein
    # Fehlalarm jede Nacht — und ein Melder, der jede Nacht anschlaegt, wird
    # abgeschaltet.
    if not sensor_ok and not geschlossen:
        befunde.append(_befund(
            "fehler", "sensor",
            f"Keine Messung — es wird nicht ausgeloest. ({sensor_status})"))

    # --- Platte -----------------------------------------------------------
    if freier_platz_b is not None:
        frei_mb = freier_platz_b / (1024 * 1024)
        if freier_platz_b < PLATZ_FEHLER_B:
            befunde.append(_befund(
                "fehler", "platte",
                f"Nur noch {frei_mb:.0f} MB frei — Uploads und die Statistik "
                "koennen nicht mehr schreiben."))
        elif freier_platz_b < PLATZ_WARNUNG_B:
            befunde.append(_befund(
                "warnung", "platte",
                f"Noch {frei_mb:.0f} MB frei — vor der naechsten Ausstellung aufraeumen."))

    # --- Medien je Zone ---------------------------------------------------
    for zone, name in (("near", "Nah"), ("far", "Fern")):
        zonendaten = config.get(zone) or {}
        zugewiesen = []
        for art in MEDIENARTEN:
            zugewiesen += list(zonendaten.get(art) or [])
        if not zugewiesen:
            befunde.append(_befund(
                "warnung", f"zone_{zone}",
                f"Zone {name} hat keine Medien — dort bleibt der Schirm leer."))
            continue
        # Zugewiesen, aber nicht mehr da: das passiert, wenn jemand Dateien
        # per SSH/USB entfernt. Die Zuweisung bleibt dabei bestehen, und die
        # Anzeige laeuft ins Leere.
        fehlend = []
        for art in MEDIENARTEN:
            for datei in (zonendaten.get(art) or []):
                if datei not in (vorhandene.get(art) or set()):
                    fehlend.append(datei)
        if fehlend:
            befunde.append(_befund(
                "fehler", f"medien_{zone}",
                f"Zone {name}: {len(fehlend)} zugewiesene Datei(en) fehlen auf "
                f"der Platte ({', '.join(sorted(fehlend)[:3])}"
                f"{' ...' if len(fehlend) > 3 else ''})."))

    # --- Betriebszustand --------------------------------------------------
    if not aktiv:
        befunde.append(_befund(
            "warnung", "gestoppt",
            "Die Sensor-Steuerung ist gestoppt — es wird nichts gespielt."))
    if geschlossen:
        # Ein Hinweis, KEIN Problem: das ist der Wochenplan, der seine Arbeit
        # tut. Als Warnung gemeldet waere es nachts ein Daueralarm.
        befunde.append(_befund(
            "hinweis", "zeitplan",
            "Ausserhalb der Oeffnungszeiten — Schirm schwarz, Ton aus."))

    return befunde

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

#: Ab hier drosselt ein Raspberry Pi den Takt (Soft-Limit 80 °C); das Bild
#: ruckelt dann, und niemand sieht, warum.
TEMP_FEHLER_C = 80.0
TEMP_WARNUNG_C = 70.0

#: Ohne Puls von einer Anzeigeseite laenger als das gilt: kein Schirm zeigt
#: etwas — egal, was der Kern glaubt zu spielen.
ANZEIGE_VERLOREN_S = 60.0


def systemwerte(thermal_glob="/sys/class/thermal/thermal_zone*/temp",
                meminfo="/proc/meminfo", platz_pfad=None):
    """Temperatur, Last, Speicher und Platte — oder None, wo es das nicht gibt.

    NICHTS ERFINDEN: auf einem Mac gibt es kein /sys/class/thermal, und dann
    steht da `None`, nicht 0 °C. Die Verwaltung zeigt eine Kachel nur, wenn
    ein Wert da ist.
    """
    import glob as _glob
    import os as _os
    werte = {"temp_c": None, "last_1m": None, "kerne": None,
             "ram_frei_mb": None, "ram_gesamt_mb": None, "platte_frei_mb": None}
    temps = []
    for pfad in _glob.glob(thermal_glob):
        try:
            with open(pfad) as f:
                temps.append(int(f.read().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    if temps:
        werte["temp_c"] = round(max(temps), 1)
    try:
        werte["last_1m"] = round(_os.getloadavg()[0], 2)
        werte["kerne"] = _os.cpu_count()
    except (OSError, AttributeError):
        pass
    try:
        with open(meminfo) as f:
            zeilen = dict(z.split(":", 1) for z in f if ":" in z)
        gesamt = int(zeilen["MemTotal"].split()[0])
        frei = int(zeilen["MemAvailable"].split()[0])
        werte["ram_gesamt_mb"] = gesamt // 1024
        werte["ram_frei_mb"] = frei // 1024
    except (OSError, KeyError, ValueError, IndexError):
        pass
    if platz_pfad:
        try:
            import shutil as _shutil
            werte["platte_frei_mb"] = _shutil.disk_usage(platz_pfad).free // (1024 * 1024)
        except OSError:
            pass
    return werte


def _befund(stufe, thema, text):
    return {"stufe": stufe, "thema": thema, "text": text}


def _inhalt_der_zone(config, zone, zonendaten):
    """Welche Dateien die Zone braucht — und ob sie ueberhaupt etwas zeigt.

    Seit 3.0 spielt eine Zone ein Layout (`layouts.py`): geprueft werden dann
    ALLE Regionen, nicht nur der Spiegel in der Zone — eine Seitenleiste mit
    einer fehlenden Datei ist genauso ein Loch im Bild wie das Hauptbild.
    Ohne Layout (alte Konfiguration, Tests) zaehlen die Zonenlisten.
    Ein Widget oder eine Webseite ist Inhalt, auch ohne Datei.
    """
    layouts = config.get("layouts") or {}
    lid = zonendaten.get("layout") or ("zone-" + zone)
    layout = layouts.get(lid) if isinstance(layouts, dict) else None
    gebraucht = {art: set(zonendaten.get(art) or []) for art in MEDIENARTEN}
    hat_inhalt = any(gebraucht.values())
    if isinstance(layout, dict):
        typ_zu_art = {"video": "videos", "image": "images", "audio": "audio"}
        for region in layout.get("regionen", []):
            if region.get("typ") == "widget":
                hat_inhalt = True
            for item in region.get("playlist", []):
                hat_inhalt = True
                art = typ_zu_art.get(item.get("typ"))
                if art and item.get("name"):
                    gebraucht[art].add(item["name"])
    return gebraucht, hat_inhalt


def gesamtstufe(befunde):
    """Die schlimmste vorkommende Stufe — oder "ok", wenn nichts anliegt."""
    schlimmste = "ok"
    for b in befunde:
        if STUFEN.index(b["stufe"]) > STUFEN.index(schlimmste):
            schlimmste = b["stufe"]
    return schlimmste


def pruefe(config, sensor_ok, sensor_status, freier_platz_b, vorhandene,
           aktiv, geschlossen, zonen=None, sync_status=None, sync_ok=None,
           system=None, anzeige=None):
    """Alle Befunde als Liste. Leer heisst: nichts zu melden.

    `vorhandene` ist {"videos": {...}, "images": {...}, "audio": {...}} mit den
    Dateinamen, die wirklich auf der Platte liegen.

    `sync_ok` ist None, wenn diese Station ihren EIGENEN Sensor auswertet —
    dann wird der Sensor geprueft. Ist sie ein Follower (True/False), zaehlt
    stattdessen der Kontakt zum Taktgeber: ihr eigener Sensor laeuft gar
    nicht, und ihn zu melden waere ein Dauerfehler ohne Ursache.

    `zonen` ist [(schluessel, klartext)] der AKTIVEN Zonen. Ohne Angabe die
    beiden Standardzonen. Wichtig, weil eine Station mit zwei Stufen die
    Mitte zwar in der Konfiguration traegt, aber nicht benutzt — sie zu
    pruefen hiesse, dauerhaft „Zone Mitte hat keine Medien" zu melden.

    `system` (3.0) ist das Ergebnis von `systemwerte()` — oder None, dann
    wird davon nichts geprueft. `anzeige` ist `{"anzahl", "online",
    "alter_s"}` aus dem Puls der Anzeigeseiten (api_anzeige) — oder None,
    wenn niemand Puls sammelt; auch dann kein Befund. Beide Vorgaben sind
    None, damit die Pruefung ohne diese Quellen genauso antwortet wie vor 3.0.
    """
    befunde = []

    # --- Anzeige (3.0) ----------------------------------------------------
    # Der Kern kann eine Zone spielen, ohne dass irgendwo ein Schirm sie
    # zeigt: Chromium abgestuerzt, Kabel raus, Tablet aus. Die Anzeigeseite
    # meldet sich alle 10 s; bleibt das aus, ist das ein Befund — aber nur,
    # wenn gerade etwas zu sehen sein SOLL (aktiv und offen).
    if anzeige is not None and aktiv and not geschlossen:
        alter = anzeige.get("alter_s")
        if not anzeige.get("anzahl"):
            befunde.append(_befund(
                "warnung", "anzeige",
                "Keine Anzeige verbunden — noch nie hat sich eine Anzeigeseite gemeldet."))
        elif alter is None or alter > ANZEIGE_VERLOREN_S:
            befunde.append(_befund(
                "warnung", "anzeige",
                f"Keine Anzeige verbunden — seit {int(alter or 0)} s kein Puls von einer Anzeigeseite."))

    # --- System (3.0) -----------------------------------------------------
    if system:
        temp = system.get("temp_c")
        if temp is not None:
            if temp >= TEMP_FEHLER_C:
                befunde.append(_befund(
                    "fehler", "temperatur",
                    f"CPU bei {temp:.0f} °C — der Pi drosselt, das Bild ruckelt. Lueftung pruefen."))
            elif temp >= TEMP_WARNUNG_C:
                befunde.append(_befund(
                    "warnung", "temperatur",
                    f"CPU bei {temp:.0f} °C — wird warm, Gehaeuse und Lueftung pruefen."))
        frei, gesamt = system.get("ram_frei_mb"), system.get("ram_gesamt_mb")
        if frei is not None and gesamt:
            if frei < gesamt * 0.1:
                befunde.append(_befund(
                    "warnung", "speicher",
                    f"Nur noch {frei} MB Arbeitsspeicher frei — Browser oder Kern koennten abstuerzen."))
        last, kerne = system.get("last_1m"), system.get("kerne")
        if last is not None and kerne:
            if last > kerne * 2:
                befunde.append(_befund(
                    "warnung", "last",
                    f"Systemlast {last:.1f} bei {kerne} Kernen — die Wiedergabe kann stocken."))

    # --- Gleichtakt ---------------------------------------------------------
    # Folgt diese Station einer anderen, ist der Kontakt zum Taktgeber ihr
    # Sensor. Reisst er ab, faellt sie auf „fern" zurueck und spielt still die
    # falsche Szene — das gehoert gemeldet.
    if sync_ok is False and not geschlossen:
        befunde.append(_befund(
            "fehler", "sync",
            f"Kein Kontakt zum Taktgeber — es wird die Fern-Szene gespielt. "
            f"({sync_status})"))

    # --- Sensor -----------------------------------------------------------
    # Ausserhalb der Oeffnungszeiten ist „keine Messung" kein Befund: dann
    # soll gar nicht ausgeloest werden. Das sonst zu melden waere ein
    # Fehlalarm jede Nacht — und ein Melder, der jede Nacht anschlaegt, wird
    # abgeschaltet.
    if not sensor_ok and not geschlossen and sync_ok is None:
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
    for zone, name in (zonen or (("near", "Nah"), ("far", "Fern"))):
        zonendaten = config.get(zone) or {}
        gebraucht, hat_inhalt = _inhalt_der_zone(config, zone, zonendaten)
        if not hat_inhalt:
            befunde.append(_befund(
                "warnung", f"zone_{zone}",
                f"Zone {name} hat keine Medien — dort bleibt der Schirm leer."))
            continue
        # Zugewiesen, aber nicht mehr da: das passiert, wenn jemand Dateien
        # per SSH/USB entfernt. Die Zuweisung bleibt dabei bestehen, und die
        # Anzeige laeuft ins Leere.
        fehlend = []
        for art in MEDIENARTEN:
            for datei in sorted(gebraucht.get(art) or ()):
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

#!/usr/bin/env python3
"""Speiseplan aus Excel (.xlsx), CSV oder Text lesen.

Die Kueche pflegt ihren Plan ohnehin in Excel oder schreibt ihn in eine
Textdatei; die Station soll genau diese Datei nehmen, ohne Abtippen.

ERKANNT WIRD (alles tolerant, Kopfzeile optional):
- Tabelle (xlsx/csv): erste Spalte = Tag (Montag, Mo, Mo. 03.11., 03.11.2026),
  weitere Spalten = Gericht(e); eine Zelle, die wie ein Preis aussieht
  (4,50 / 4.50 € / €4,50), wird dem Gericht links davon als Preis gegeben.
  Zeilen mit leerer Tagesspalte gehoeren zum Tag darueber.
- Text: eine Zeile, die mit einem Wochentag beginnt, eroeffnet den Tag;
  was nach dem Tag auf derselben Zeile steht (nach „:" oder „-") und jede
  folgende Zeile ist ein Gericht. Ein Preis am Zeilenende wird abgetrennt.

NUR STANDARDBIBLIOTHEK: .xlsx ist ein ZIP mit XML; openpyxl waere eine
Abhaengigkeit fuer zwanzig Zeilen.
"""
import csv
import datetime
import io
import re
import zipfile
import xml.etree.ElementTree as ET

ENDUNGEN = {".xlsx", ".csv", ".txt"}

_TAGE = [("mo", "Montag"), ("di", "Dienstag"), ("mi", "Mittwoch"),
         ("do", "Donnerstag"), ("fr", "Freitag"), ("sa", "Samstag"), ("so", "Sonntag")]
_TAG_RE = re.compile(r"^\s*(mo|di|mi|do|fr|sa|so)[a-zäöü]*\.?(?=$|[\s,:;\-–(\d])", re.I)
_DATUM_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?")
_PREIS_RE = re.compile(r"^\s*(?:€\s*)?(\d{1,3}(?:[.,]\d{2}))\s*(?:€|eur|euro)?\s*$", re.I)
_PREIS_ENDE_RE = re.compile(r"\s*[-–]?\s*((?:€\s*)?\d{1,3}[.,]\d{2}\s*(?:€|eur|euro)?)\s*$", re.I)


def _tag_aus(text, jahr=None):
    """'Mo 03.11.' -> ('mo', '2026-11-03' oder None); kein Tag -> (None, None)."""
    text = str(text or "").strip()
    m = _DATUM_RE.search(text)
    iso = None
    if m:
        j = m.group(3)
        j = int(j) + (2000 if j and len(j) == 2 else 0) if j else (jahr or datetime.date.today().year)
        try:
            iso = datetime.date(j, int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            iso = None
    t = _TAG_RE.match(text)
    if t:
        return t.group(1).lower(), iso
    if iso:
        return _TAGE[datetime.date.fromisoformat(iso).weekday()][0], iso
    return None, None


def _preis(text):
    m = _PREIS_RE.match(str(text or ""))
    return (m.group(1).replace(".", ",") + " €") if m else None


def _neuer_tag(kurz, iso):
    return {"tag": kurz, "name": dict(_TAGE)[kurz], "datum": iso, "gerichte": []}


def aus_zeilen(zeilen):
    """Tabellenzeilen (Listen von Zellen) -> Tage."""
    tage, aktuell = [], None
    for zeile in zeilen:
        zellen = [str(z).strip() if z is not None else "" for z in zeile]
        if not any(zellen):
            continue
        kurz, iso = _tag_aus(zellen[0])
        if kurz:
            aktuell = _neuer_tag(kurz, iso)
            tage.append(aktuell)
        elif zellen[0] or aktuell is None:
            continue  # Kopfzeile oder Text vor dem ersten Tag
        for zelle in zellen[1:]:
            if not zelle:
                continue
            p = _preis(zelle)
            if p and aktuell["gerichte"] and not aktuell["gerichte"][-1]["preis"]:
                aktuell["gerichte"][-1]["preis"] = p
            elif not p:
                aktuell["gerichte"].append({"name": zelle, "preis": None})
    return tage


def aus_text(text):
    tage, aktuell = [], None
    for roh in text.splitlines():
        zeile = roh.strip(" \t•*·-–")
        if not zeile:
            continue
        kurz, iso = _tag_aus(zeile)
        if kurz:
            aktuell = _neuer_tag(kurz, iso)
            tage.append(aktuell)
            rest = re.split(r"[:–\-]\s*", zeile, maxsplit=1)
            zeile = rest[1].strip() if len(rest) > 1 and not _DATUM_RE.fullmatch(rest[1].strip()) else ""
            if not zeile:
                continue
        if aktuell is None:
            continue
        preis = None
        m = _PREIS_ENDE_RE.search(zeile)
        if m and m.start() > 0:
            preis = _preis(m.group(1))
            zeile = zeile[:m.start()].rstrip(" -–:")
        aktuell["gerichte"].append({"name": zeile, "preis": preis})
    return tage


def _xlsx_zeilen(daten):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        geteilt = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                geteilt.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        blatt = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))[0]
        wurzel = ET.fromstring(z.read(blatt))
    zeilen = []
    for row in wurzel.iter(f"{{{ns['m']}}}row"):
        zellen = {}
        for c in row.findall("m:c", ns):
            spalte = 0
            for ch in re.match(r"[A-Z]+", c.get("r", "A")).group(0):
                spalte = spalte * 26 + ord(ch) - 64
            typ, v = c.get("t"), c.find("m:v", ns)
            if typ == "s" and v is not None:
                wert = geteilt[int(v.text)]
            elif typ == "inlineStr":
                wert = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            elif v is not None:
                wert = v.text or ""
                if re.fullmatch(r"\d+\.\d+", wert):
                    wert = f"{float(wert):.2f}"
                elif re.fullmatch(r"4\d{4}", wert) and spalte == 1:  # Excel-Datum
                    d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(wert))
                    wert = d.strftime("%d.%m.%Y")
            else:
                wert = ""
            zellen[spalte] = wert
        if zellen:
            zeilen.append([zellen.get(i, "") for i in range(1, max(zellen) + 1)])
    return zeilen


def _dekodiere(daten):
    for kod in ("utf-8-sig", "cp1252"):
        try:
            return daten.decode(kod)
        except UnicodeDecodeError:
            pass
    return daten.decode("latin-1")


def lies(daten, endung):
    """Bytes einer Datei -> {"tage": [...]}. Wirft ValueError bei Unlesbarem."""
    endung = endung.lower()
    try:
        if endung == ".xlsx":
            tage = aus_zeilen(_xlsx_zeilen(daten))
        elif endung == ".csv":
            text = _dekodiere(daten)
            try:
                dialekt = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
            except csv.Error:
                dialekt = csv.excel
            tage = aus_zeilen(csv.reader(io.StringIO(text), dialekt))
        elif endung == ".txt":
            tage = aus_text(_dekodiere(daten))
        else:
            raise ValueError(f"Format {endung} nicht unterstuetzt")
    except (zipfile.BadZipFile, ET.ParseError, IndexError, KeyError) as e:
        raise ValueError(f"Datei nicht lesbar: {e}") from e
    return {"tage": tage}

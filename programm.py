#!/usr/bin/env python3
"""Wochenprogramm: welches Layout eine Zone WANN spielt.

WARUM ES DAS GIBT. Der Wochenplan (`zeitplan.py`) sagt nur, ob die Station
ueberhaupt wach ist. Ein Schirm im Foyer soll aber morgens das Programm des
Tages zeigen, mittags die Speisekarte und abends den Film — ohne dass jemand
vorbeikommt und umschaltet. Das Programm ordnet Zeitfenstern ein Layout zu;
der Kern fragt es je Tick ueber `Controller.layout_regeln`.

REIN. Keine Uhr, keine Platte, kein Flask: `aufloesen` bekommt `jetzt`
hereingereicht. Ein Test, der um 23:59 anders ausgeht als um 00:01, macht eine
CI unglaubwuerdig (dieselbe Regel wie in `zeitplan.py`).

DIE REGELN, in dieser Reihenfolge:

1. Ein **Ausnahmetag** (Feiertag, Sondertag) gewinnt vor allem anderen. Sein
   `layout_id` gilt fuer alle Zonen den ganzen Tag; `null` heisst „das
   Layout der Zone" — also ausdruecklich KEIN Programm an diesem Tag.
2. Von den **Eintraegen**, die jetzt passen (aktiv, Zone, Wochentag, Fenster,
   Gueltigkeit), gewinnt die hoechste Prioritaet; bei Gleichstand der, der
   spaeter begonnen hat — wer eine Sonderschicht ueber ein Dauerprogramm legt,
   erwartet, dass sie sichtbar ist, ohne die Prioritaet anfassen zu muessen.
3. Passt nichts, spielt die Zone ihr Layout aus der Konfiguration.

UEBER MITTERNACHT wie im Wochenplan: ein Fenster `20:00`–`02:00` gehoert zum
Eintrag des Tages, an dem es beginnt. Deshalb wird auch der Eintrag von
GESTERN gefragt.

ZWEI POLITIKEN wie ueberall: `pruefe_programm` lehnt ab und nennt das Feld
(Schreibweg), `heile_programm` repariert eintragsweise und sagt es im Log
(Ladeweg). Ein einzelner kaputter Eintrag wirft nicht das ganze Programm weg.
"""
import re
from datetime import date, datetime, timedelta

from layouts import FARBE, KENNUNG, ZONEN
from zeitplan import TAGE, TAG_NAMEN, minuten

#: Grenzen. Grosszuegig, aber endlich — eine Oberflaeche, die 10.000
#: Eintraege zeichnet, ist keine Oberflaeche mehr.
MAX_EINTRAEGE = 100
MAX_AUSNAHMEN = 200
NAME_MAX = 64
PRIORITAET_MIN = 1
PRIORITAET_MAX = 9
PRIORITAET_STANDARD = 5

_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Raster der Kalender-Vorschau in Minuten.
RASTER_MIN = 15


def standard_programm():
    """Die Vorgabe: kein Eintrag, keine Ausnahme — jede Zone spielt ihr Layout.
    Eine Station von vor 3.0 verhaelt sich damit exakt wie vorher."""
    return {"eintraege": [], "ausnahmen": []}


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _datum(roh, feld):
    """`JJJJ-MM-TT` oder None. Wirft ValueError mit Feldnamen."""
    if roh is None or roh == "":
        return None
    if not isinstance(roh, str) or not _DATUM.match(roh):
        raise ValueError(f"{feld}: Datum als JJJJ-MM-TT erwartet")
    try:
        date.fromisoformat(roh)
    except ValueError:
        raise ValueError(f"{feld}: {roh!r} ist kein Kalendertag") from None
    return roh


def _kennung(roh, feld, leer_erlaubt=False):
    if roh is None or roh == "":
        if leer_erlaubt:
            return None
        raise ValueError(f"{feld}: Kennung fehlt")
    if not isinstance(roh, str) or not KENNUNG.match(roh):
        raise ValueError(f"{feld}: Kennung aus a-z, 0-9 und '-' (1..40 Zeichen)")
    return roh


def _text(roh, feld, maximal, pflicht=True):
    if roh is None:
        roh = ""
    if not isinstance(roh, str):
        raise ValueError(f"{feld}: muss Text sein")
    roh = roh.strip()
    if pflicht and not roh:
        raise ValueError(f"{feld}: darf nicht leer sein")
    if len(roh) > maximal:
        raise ValueError(f"{feld}: hoechstens {maximal} Zeichen")
    return roh


def _dauer(roh, feld):
    """Sekunden > 0 (bis ein Tag) oder None. Eine Stelle fuer Meldung UND
    Ausloeser — zwei Kopien dieser Grenze waren schon einmal auseinander."""
    if roh is None or roh == "":
        return None
    if isinstance(roh, bool) or not isinstance(roh, (int, float)):
        raise ValueError(f"{feld}: Sekunden > 0 oder leer")
    if not (0 < float(roh) <= 86400):
        raise ValueError(f"{feld}: 1..86400 s oder leer")
    return float(roh)


def kennung_aus_name(name, vergeben=(), vorgabe="eintrag"):
    """`Speisekarte mittags` -> `speisekarte-mittags`, eindeutig gemacht.

    Die Kennung entsteht HIER, nicht im Browser: eine zweite Fassung dieser
    Regel in JavaScript wuerde beim naechsten Sonderfall auseinanderlaufen."""
    grund = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:36] or vorgabe
    if grund[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
        grund = vorgabe[0] + "-" + grund
    kandidat, n = grund, 2
    while kandidat in vergeben:
        kandidat = f"{grund}-{n}"
        n += 1
    return kandidat


# ── Schreibweg: ablehnen ─────────────────────────────────────────────────────

def pruefe_eintrag(roh, stelle="eintrag"):
    """Einen Eintrag pruefen. Gibt die bereinigte Form zurueck oder wirft
    ValueError, der das Feld nennt."""
    if not isinstance(roh, dict):
        raise ValueError(f"{stelle}: muss ein Objekt sein")
    heraus = {
        "id": _kennung(roh.get("id"), f"{stelle}.id"),
        "name": _text(roh.get("name"), f"{stelle}.name", NAME_MAX),
        "layout_id": _kennung(roh.get("layout_id"), f"{stelle}.layout_id"),
    }
    zonen = roh.get("zonen", [])
    if zonen is None:
        zonen = []
    if not isinstance(zonen, list) or any(z not in ZONEN for z in zonen):
        raise ValueError(f"{stelle}.zonen: Liste aus {list(ZONEN)} (leer = alle)")
    heraus["zonen"] = [z for z in ZONEN if z in zonen]
    tage = roh.get("tage", list(TAGE))
    if not isinstance(tage, list) or not tage or any(t not in TAGE for t in tage):
        raise ValueError(f"{stelle}.tage: mindestens ein Tag aus {list(TAGE)}")
    heraus["tage"] = [t for t in TAGE if t in tage]
    try:
        von_m = minuten(roh.get("von", "00:00"), ende=False)
        bis_m = minuten(roh.get("bis", "24:00"), ende=True)
    except ValueError as e:
        raise ValueError(f"{stelle}: {e}") from None
    if von_m == bis_m:
        raise ValueError(f"{stelle}: Beginn und Ende sind gleich — das Fenster ist leer")
    heraus["von"] = roh.get("von", "00:00").strip()
    heraus["bis"] = roh.get("bis", "24:00").strip()
    prio = roh.get("prioritaet", PRIORITAET_STANDARD)
    if isinstance(prio, bool) or not isinstance(prio, int) or not (PRIORITAET_MIN <= prio <= PRIORITAET_MAX):
        raise ValueError(f"{stelle}.prioritaet: ganze Zahl {PRIORITAET_MIN}..{PRIORITAET_MAX}")
    heraus["prioritaet"] = prio
    heraus["gueltig_von"] = _datum(roh.get("gueltig_von"), f"{stelle}.gueltig_von")
    heraus["gueltig_bis"] = _datum(roh.get("gueltig_bis"), f"{stelle}.gueltig_bis")
    if heraus["gueltig_von"] and heraus["gueltig_bis"] and heraus["gueltig_von"] > heraus["gueltig_bis"]:
        raise ValueError(f"{stelle}.gueltig_bis: liegt vor gueltig_von")
    aktiv = roh.get("aktiv", True)
    if not isinstance(aktiv, bool):
        raise ValueError(f"{stelle}.aktiv: muss true oder false sein")
    heraus["aktiv"] = aktiv
    return heraus


def pruefe_ausnahme(roh, stelle="ausnahme"):
    if not isinstance(roh, dict):
        raise ValueError(f"{stelle}: muss ein Objekt sein")
    datum = _datum(roh.get("datum"), f"{stelle}.datum")
    if datum is None:
        raise ValueError(f"{stelle}.datum: fehlt")
    return {
        "datum": datum,
        "layout_id": _kennung(roh.get("layout_id"), f"{stelle}.layout_id", leer_erlaubt=True),
        "name": _text(roh.get("name"), f"{stelle}.name", NAME_MAX, pflicht=False),
    }


def pruefe_programm(roh):
    """Schreibweg: das ganze Programm. Doppelte Kennungen und doppelte
    Ausnahmetage werden abgelehnt — zwei Eintraege mit derselben Kennung
    liessen sich in der Oberflaeche nicht mehr auseinanderhalten."""
    if not isinstance(roh, dict):
        raise ValueError("programm: muss ein Objekt sein")
    eintraege = roh.get("eintraege", [])
    ausnahmen = roh.get("ausnahmen", [])
    if not isinstance(eintraege, list):
        raise ValueError("programm.eintraege: muss eine Liste sein")
    if not isinstance(ausnahmen, list):
        raise ValueError("programm.ausnahmen: muss eine Liste sein")
    if len(eintraege) > MAX_EINTRAEGE:
        raise ValueError(f"programm.eintraege: hoechstens {MAX_EINTRAEGE}")
    if len(ausnahmen) > MAX_AUSNAHMEN:
        raise ValueError(f"programm.ausnahmen: hoechstens {MAX_AUSNAHMEN}")
    heraus, ids = [], set()
    for i, e in enumerate(eintraege):
        if isinstance(e, dict) and not e.get("id"):
            e = dict(e, id=kennung_aus_name(e.get("name", ""), ids))
        sauber = pruefe_eintrag(e, f"programm.eintraege[{i}]")
        if sauber["id"] in ids:
            raise ValueError(f"programm.eintraege[{i}].id: {sauber['id']!r} gibt es schon")
        ids.add(sauber["id"])
        heraus.append(sauber)
    tage_gesehen, aus = set(), []
    for i, a in enumerate(ausnahmen):
        sauber = pruefe_ausnahme(a, f"programm.ausnahmen[{i}]")
        if sauber["datum"] in tage_gesehen:
            raise ValueError(f"programm.ausnahmen[{i}].datum: {sauber['datum']} steht schon drin")
        tage_gesehen.add(sauber["datum"])
        aus.append(sauber)
    aus.sort(key=lambda a: a["datum"])
    return {"eintraege": heraus, "ausnahmen": aus}


# ── Ladeweg: heilen ──────────────────────────────────────────────────────────

def heile_programm(roh):
    """Ladeweg: EINTRAGSWEISE reparieren. Ein Eintrag mit einer Uhrzeit
    `25:00` fliegt raus und wird genannt; die anderen bleiben."""
    if roh is None:
        return standard_programm()
    if not isinstance(roh, dict):
        print(f"[Programm] {roh!r} ist kein Objekt — nehme die Vorgabe")
        return standard_programm()
    heraus, ids = [], set()
    eintraege = roh.get("eintraege")
    if not isinstance(eintraege, list):
        if eintraege is not None:
            print("[Programm] eintraege ist keine Liste — nehme leer")
        eintraege = []
    for i, e in enumerate(eintraege[:MAX_EINTRAEGE]):
        try:
            if isinstance(e, dict) and not e.get("id"):
                e = dict(e, id=kennung_aus_name(e.get("name", ""), ids))
            sauber = pruefe_eintrag(e, f"eintraege[{i}]")
        except ValueError as fehler:
            print(f"[Programm] {fehler} — Eintrag wird weggelassen")
            continue
        if sauber["id"] in ids:
            print(f"[Programm] eintraege[{i}]: Kennung {sauber['id']!r} doppelt — zweiter wird weggelassen")
            continue
        ids.add(sauber["id"])
        heraus.append(sauber)
    aus, tage = [], set()
    ausnahmen = roh.get("ausnahmen")
    if not isinstance(ausnahmen, list):
        if ausnahmen is not None:
            print("[Programm] ausnahmen ist keine Liste — nehme leer")
        ausnahmen = []
    for i, a in enumerate(ausnahmen[:MAX_AUSNAHMEN]):
        try:
            sauber = pruefe_ausnahme(a, f"ausnahmen[{i}]")
        except ValueError as fehler:
            print(f"[Programm] {fehler} — Ausnahme wird weggelassen")
            continue
        if sauber["datum"] in tage:
            continue
        tage.add(sauber["datum"])
        aus.append(sauber)
    aus.sort(key=lambda a: a["datum"])
    return {"eintraege": heraus, "ausnahmen": aus}


# ── Aufloesung ───────────────────────────────────────────────────────────────

def _gilt_am(eintrag, tag):
    """Gueltigkeitszeitraum (Kalendertage) — `tag` ist ein `date`."""
    t = tag.isoformat()
    von, bis = eintrag.get("gueltig_von"), eintrag.get("gueltig_bis")
    if von and t < von:
        return False
    if bis and t > bis:
        return False
    return True


def _beginn(eintrag, jetzt):
    """Wann hat das Fenster begonnen, in dem `jetzt` liegt? None, wenn es
    jetzt nicht offen ist. Rechnet heute UND gestern (ueber Mitternacht)."""
    try:
        von_m = minuten(eintrag.get("von"), ende=False)
        bis_m = minuten(eintrag.get("bis"), ende=True)
    except ValueError:
        return None
    if von_m == bis_m:
        return None
    jetzt_m = jetzt.hour * 60 + jetzt.minute
    heute = jetzt.date()
    gestern = heute - timedelta(days=1)
    tage = eintrag.get("tage") or ()
    if TAGE[heute.weekday()] in tage and _gilt_am(eintrag, heute):
        if von_m < bis_m and von_m <= jetzt_m < bis_m:
            return datetime(heute.year, heute.month, heute.day) + timedelta(minutes=von_m)
        if von_m > bis_m and jetzt_m >= von_m:
            return datetime(heute.year, heute.month, heute.day) + timedelta(minutes=von_m)
    if von_m > bis_m and TAGE[gestern.weekday()] in tage and _gilt_am(eintrag, gestern):
        if jetzt_m < bis_m:
            return datetime(gestern.year, gestern.month, gestern.day) + timedelta(minutes=von_m)
    return None


def ausnahme_am(programm, tag):
    """Die Ausnahme fuer diesen Kalendertag (`date`) oder None."""
    t = tag.isoformat()
    for a in (programm or {}).get("ausnahmen") or []:
        if isinstance(a, dict) and a.get("datum") == t:
            return a
    return None


def aufloesen(programm, zone, jetzt):
    """Was spielt die Zone jetzt laut Programm?

    Gibt `(layout_id, quelle, eintrag)` zurueck:
      - `("durchsage", "programm", <eintrag>)`  — ein Eintrag passt
      - `("feiertag", "ausnahme", <ausnahme>)`  — ein Ausnahmetag
      - `(None, "ausnahme", <ausnahme>)`        — Ausnahmetag „Standard": das
                                                  Programm gilt heute nicht
      - `(None, "zone", None)`                  — nichts passt, Zonen-Layout
    """
    if not isinstance(programm, dict):
        return None, "zone", None
    ausnahme = ausnahme_am(programm, jetzt.date())
    if ausnahme is not None:
        return ausnahme.get("layout_id") or None, "ausnahme", ausnahme
    bester, bester_schluessel = None, None
    for e in programm.get("eintraege") or []:
        if not isinstance(e, dict) or not e.get("aktiv", True):
            continue
        zonen = e.get("zonen") or []
        if zonen and zone not in zonen:
            continue
        beginn = _beginn(e, jetzt)
        if beginn is None:
            continue
        schluessel = (int(e.get("prioritaet", PRIORITAET_STANDARD)), beginn)
        if bester_schluessel is None or schluessel > bester_schluessel:
            bester, bester_schluessel = e, schluessel
    if bester is None:
        return None, "zone", None
    return bester.get("layout_id"), "programm", bester


def layout_jetzt(programm, zone, jetzt):
    """Nur die Kennung — die Form, die `Controller.layout_regeln` erwartet."""
    return aufloesen(programm, zone, jetzt)[0]


def regel(config_holen):
    """Eine Layout-Regel fuer `Controller.layout_regeln` bauen.

    `config_holen` ist eine Funktion ohne Argumente, die die aktuelle
    Konfiguration liefert — die Regel darf sie sich nicht merken, weil
    `/api/restore` das ganze dict austauscht.
    """
    def programm_regel(zone, jetzt, config):
        return layout_jetzt((config or config_holen()).get("programm"), zone, jetzt)
    programm_regel.__name__ = "programm"
    return programm_regel


def raster(programm, zone, von, bis, schritt_min=RASTER_MIN):
    """Die Aufloesung ueber einen Zeitraum, als zusammengefasste Abschnitte.

    Fuer die Kalenderansicht: `[{von, bis, layout_id, quelle, eintrag_id}]`,
    benachbarte gleiche Abschnitte verschmolzen. Hoechstens eine Woche, sonst
    zeichnet die Oberflaeche Tausende Kaestchen.
    """
    if bis <= von:
        return []
    if bis - von > timedelta(days=8):
        bis = von + timedelta(days=8)
    schritt = timedelta(minutes=max(1, int(schritt_min)))
    heraus = []
    t = von
    while t < bis:
        lid, quelle, e = aufloesen(programm, zone, t)
        eid = None
        if quelle == "programm" and e:
            eid = e.get("id")
        elif quelle == "ausnahme" and e:
            eid = "ausnahme:" + str(e.get("datum"))
        ende = min(t + schritt, bis)
        if heraus and heraus[-1]["layout_id"] == lid and heraus[-1]["quelle"] == quelle \
                and heraus[-1]["eintrag_id"] == eid and heraus[-1]["bis"] == t.isoformat(timespec="minutes"):
            heraus[-1]["bis"] = ende.isoformat(timespec="minutes")
        else:
            heraus.append({"von": t.isoformat(timespec="minutes"),
                           "bis": ende.isoformat(timespec="minutes"),
                           "layout_id": lid, "quelle": quelle, "eintrag_id": eid})
        t = ende
    return heraus


def beschreibe_eintrag(eintrag):
    """Klartext fuer Log und Oberflaeche: „Mo, Di 09:00–12:00 (Prio 5)"."""
    tage = ", ".join(TAG_NAMEN[t][:2] for t in eintrag.get("tage") or [])
    return f"{tage} {eintrag.get('von')}–{eintrag.get('bis')} (Prio {eintrag.get('prioritaet')})"


# ── Sofortmeldung ────────────────────────────────────────────────────────────
#
# Eine Zeile ueber allem: Raeumung, „Beginn in 5 Minuten", „Pause bis 14:00".
# Sie gehoert zum Programm, weil sie dieselbe Frage beantwortet — was zeigt
# der Schirm JETZT — nur von Hand statt nach Plan. Gespeichert wird sie in der
# Konfiguration, damit eine Anzeige, die neu laedt, sie wieder zeigt; `bis`
# begrenzt sie, und der Ladeweg raeumt eine abgelaufene Meldung weg.

TEXT_MAX = 200
UNTERTEXT_MAX = 400
MELDUNG_FARBE = "#B04A3F"
MELDUNG_TEXTFARBE = "#FFFFFF"


def standard_meldung():
    return {"aktiv": False, "text": "", "untertext": "", "farbe": MELDUNG_FARBE,
            "textfarbe": MELDUNG_TEXTFARBE, "dauer_s": None, "bis": None, "ton": False}


def _farbe(roh, feld, vorgabe):
    if roh is None or roh == "":
        return vorgabe
    if not isinstance(roh, str) or not FARBE.match(roh):
        raise ValueError(f"{feld}: Farbe als #rrggbb")
    return roh


def _zeitpunkt(roh, feld):
    if roh is None or roh == "":
        return None
    if not isinstance(roh, str):
        raise ValueError(f"{feld}: Zeitpunkt als ISO-Text erwartet")
    try:
        t = datetime.fromisoformat(roh)
    except ValueError:
        raise ValueError(f"{feld}: {roh!r} ist kein Zeitpunkt") from None
    # Immer als ORTSZEIT ohne Zone ablegen. `bis` wird spaeter mit
    # `datetime.now()` verglichen, und Python vergleicht zonenbehaftet mit
    # zonenlos nicht — der Vergleich wuerfe TypeError, und zwar erst nach
    # dem Speichern, bei jedem Laden.
    if t.tzinfo is not None:
        t = t.astimezone().replace(tzinfo=None)
    return t.isoformat(timespec="seconds")


def pruefe_meldung(roh, jetzt=None):
    """Schreibweg. `dauer_s` rechnet `bis` aus — der Aufrufer muss keine Uhr
    kennen. Ohne beides gilt die Meldung bis zum Beenden."""
    if not isinstance(roh, dict):
        raise ValueError("meldung: muss ein Objekt sein")
    jetzt = jetzt or datetime.now()
    aktiv = roh.get("aktiv", True)
    if not isinstance(aktiv, bool):
        raise ValueError("meldung.aktiv: muss true oder false sein")
    m = standard_meldung()
    m["aktiv"] = aktiv
    m["text"] = _text(roh.get("text"), "meldung.text", TEXT_MAX, pflicht=aktiv)
    m["untertext"] = _text(roh.get("untertext"), "meldung.untertext", UNTERTEXT_MAX, pflicht=False)
    m["farbe"] = _farbe(roh.get("farbe"), "meldung.farbe", MELDUNG_FARBE)
    m["textfarbe"] = _farbe(roh.get("textfarbe"), "meldung.textfarbe", MELDUNG_TEXTFARBE)
    ton = roh.get("ton", False)
    if not isinstance(ton, bool):
        raise ValueError("meldung.ton: muss true oder false sein")
    m["ton"] = ton
    dauer = _dauer(roh.get("dauer_s"), "meldung.dauer_s")
    if dauer is not None:
        m["dauer_s"] = dauer
        m["bis"] = (jetzt + timedelta(seconds=dauer)).isoformat(timespec="seconds")
    else:
        m["bis"] = _zeitpunkt(roh.get("bis"), "meldung.bis")
    return m


def heile_meldung(roh, jetzt=None):
    """Ladeweg: Unsinn -> aus. Eine abgelaufene Meldung ist beim Start aus —
    sonst staende nach einem Neustart eine Raeumung von gestern auf dem Schirm."""
    jetzt = jetzt or datetime.now()
    if not isinstance(roh, dict):
        return standard_meldung()
    try:
        m = pruefe_meldung(dict(roh, dauer_s=None), jetzt)
    except (ValueError, TypeError) as e:
        print(f"[Meldung] {e} — Meldung aus")
        return standard_meldung()
    if not meldung_gilt(m, jetzt):
        m["aktiv"] = False
    return m


def meldung_gilt(m, jetzt):
    """Aktiv UND nicht abgelaufen."""
    if not isinstance(m, dict) or not m.get("aktiv"):
        return False
    bis = m.get("bis")
    if not bis:
        return True
    try:
        t = datetime.fromisoformat(bis)
        if t.tzinfo is not None:
            t = t.astimezone().replace(tzinfo=None)
        return t > jetzt
    except (ValueError, TypeError):
        return False


def meldung_fuer_szene(m, jetzt):
    """Die Form, die die Anzeige bekommt: `aktiv` schon gegen `bis` gerechnet."""
    m = dict(m or standard_meldung())
    m["aktiv"] = meldung_gilt(m, jetzt)
    return m

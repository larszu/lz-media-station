"""Zeitsteuerung: wann die Station ueberhaupt spielt.

WARUM ES DAS GIBT. Die Station steht unbeaufsichtigt in einer Ausstellung und
lief bisher 24/7: nachts spielt sie vor einem leeren Raum, der Ton laeuft, das
Panel altert. Ein Wochenplan sagt, wann sie wach ist; ausserhalb bleibt der
Schirm schwarz, der Ton aus, und es wird nicht ausgeloest.

RUECKWAERTSKOMPATIBEL: `aktiv` ist in der Vorgabe **False**. Eine bestehende
Installation verhaelt sich also exakt wie vorher, bis jemand den Plan
einschaltet. `ist_offen` gibt bei ausgeschalteter Zeitsteuerung immer True.

REINE FUNKTIONEN. `ist_offen` bekommt die Uhrzeit HEREINGEREICHT und liest sie
nicht selbst. Sonst waere der Test auf die Systemuhr angewiesen — und ein Test,
der um 23:59 anders ausgeht als um 00:01, macht eine CI unglaubwuerdig.

UEBER MITTERNACHT. Ein Fenster darf enden, nachdem der Tag gewechselt hat
(20:00 bis 02:00). Das ist kein Sonderfall fuer Abendveranstaltungen, sondern
der Normalfall bei jeder Spaetoeffnung. Wer nur `von <= t < bis` rechnet, sperrt
genau die Stunden aus, fuer die der Plan gemacht wurde. Deshalb wird immer AUCH
der Eintrag von GESTERN geprueft: der Teil nach Mitternacht gehoert zu dessen
Fenster, nicht zu dem von heute.
"""
import re

#: Tageskuerzel in der Reihenfolge von `datetime.weekday()` (Montag = 0).
TAGE = ("mo", "di", "mi", "do", "fr", "sa", "so")

#: Klartext fuer Meldungen und Oberflaeche.
TAG_NAMEN = {
    "mo": "Montag", "di": "Dienstag", "mi": "Mittwoch", "do": "Donnerstag",
    "fr": "Freitag", "sa": "Samstag", "so": "Sonntag",
}

#: Vorgabe je Tag: offen von Mitternacht bis Mitternacht.
STANDARD_TAG = {"an": True, "von": "00:00", "bis": "24:00"}

_MUSTER = re.compile(r"^(\d{1,2}):(\d{2})$")


def standard_zeitplan():
    """Die Vorgabe — Zeitsteuerung AUS, alle Tage ganztags offen.

    Frische Kopien je Tag: ein gemeinsames Dict wuerde bedeuten, dass das
    Aendern eines Tages alle sieben aendert.
    """
    return {"aktiv": False, "tage": {t: dict(STANDARD_TAG) for t in TAGE}}


def minuten(text, ende=False):
    """'HH:MM' -> Minuten seit Mitternacht. Wirft ValueError bei Unsinn.

    `ende=True` erlaubt zusaetzlich '24:00' als Tagesende. Ohne das muesste man
    '23:59' schreiben und haette eine Minute Luecke — genau die Art Detail, die
    erst auffaellt, wenn um Mitternacht kurz nichts spielt.
    """
    if not isinstance(text, str):
        raise ValueError("muss eine Uhrzeit 'HH:MM' sein")
    treffer = _MUSTER.match(text.strip())
    if not treffer:
        raise ValueError(f"{text!r} ist keine Uhrzeit 'HH:MM'")
    stunde, minute = int(treffer.group(1)), int(treffer.group(2))
    if minute > 59:
        raise ValueError(f"{text!r}: Minute liegt ausserhalb 00..59")
    if ende:
        if stunde > 24 or (stunde == 24 and minute != 0):
            raise ValueError(f"{text!r}: spaetestes Ende ist 24:00")
    elif stunde > 23:
        raise ValueError(f"{text!r}: spaetester Beginn ist 23:59")
    return stunde * 60 + minute


def _fenster_offen(eintrag, jetzt_min, uebernacht_teil):
    """Faellt `jetzt_min` in das Fenster dieses Eintrags?

    `uebernacht_teil=True` fragt nur nach dem Stueck NACH Mitternacht, das zu
    einem Fenster des VORTAGS gehoert.
    """
    if not isinstance(eintrag, dict) or not eintrag.get("an"):
        return False
    try:
        von = minuten(eintrag.get("von"), ende=False)
        bis = minuten(eintrag.get("bis"), ende=True)
    except ValueError:
        # Ein unbrauchbarer Eintrag sperrt, statt zu raten. Geheilt wird beim
        # Laden (`heile_zeitplan`); hier zaehlt nur, dass nichts erfunden wird.
        return False
    if von == bis:
        return False          # Null-Fenster = zu (fuer ganztags: 00:00-24:00)
    if von < bis:
        # Gewoehnliches Fenster innerhalb eines Tages — es reicht nicht ueber
        # Mitternacht, kann also zum Vortags-Stueck nichts beitragen.
        return False if uebernacht_teil else (von <= jetzt_min < bis)
    # von > bis: das Fenster laeuft ueber Mitternacht.
    return (jetzt_min < bis) if uebernacht_teil else (jetzt_min >= von)


def ist_offen(zeitplan, jetzt):
    """Spielt die Station zu diesem Zeitpunkt?

    `jetzt` ist ein `datetime`. Ist die Zeitsteuerung aus (oder der Plan
    unbrauchbar), gilt IMMER offen — eine kaputte Konfiguration darf eine
    Ausstellung nicht stumm schalten.
    """
    if not isinstance(zeitplan, dict) or not zeitplan.get("aktiv"):
        return True
    tage = zeitplan.get("tage")
    if not isinstance(tage, dict):
        return True
    jetzt_min = jetzt.hour * 60 + jetzt.minute
    heute = TAGE[jetzt.weekday()]
    gestern = TAGE[(jetzt.weekday() - 1) % 7]
    if _fenster_offen(tage.get(heute), jetzt_min, uebernacht_teil=False):
        return True
    return _fenster_offen(tage.get(gestern), jetzt_min, uebernacht_teil=True)


def _pruefe_tag(tag, eintrag):
    """Einen Tages-Eintrag pruefen. Wirft ValueError mit Tagesnamen."""
    if not isinstance(eintrag, dict):
        raise ValueError(f"zeitplan.{tag}: muss ein Objekt sein")
    an = eintrag.get("an", True)
    if not isinstance(an, bool):
        raise ValueError(f"zeitplan.{tag}.an: muss true oder false sein")
    try:
        von_m = minuten(eintrag.get("von", "00:00"), ende=False)
        bis_m = minuten(eintrag.get("bis", "24:00"), ende=True)
    except ValueError as e:
        raise ValueError(f"zeitplan.{tag}: {e}") from None
    if von_m == bis_m:
        raise ValueError(
            f"zeitplan.{tag}: Beginn und Ende sind gleich — das Fenster ist "
            "leer. Fuer ganztags 00:00 bis 24:00, fuer zu `an: false`.")
    return {"an": an,
            "von": eintrag.get("von", "00:00"),
            "bis": eintrag.get("bis", "24:00")}


def pruefe_zeitplan(roh):
    """Schreibweg: geprueften Zeitplan zurueck, oder ValueError mit Feldnamen.

    Wie `config_schema.pruefe_patch`: wer einen Wert setzt, soll erfahren, dass
    er nicht angekommen ist — nicht stillschweigend die Vorgabe bekommen.
    """
    if not isinstance(roh, dict):
        raise ValueError("zeitplan: muss ein Objekt sein")
    aktiv = roh.get("aktiv", False)
    if not isinstance(aktiv, bool):
        raise ValueError("zeitplan.aktiv: muss true oder false sein")
    rohtage = roh.get("tage", {})
    if not isinstance(rohtage, dict):
        raise ValueError("zeitplan.tage: muss ein Objekt sein")
    unbekannt = set(rohtage) - set(TAGE)
    if unbekannt:
        raise ValueError(f"zeitplan.tage: unbekannte Tage {sorted(unbekannt)} "
                         f"— erlaubt sind {list(TAGE)}")
    standard = standard_zeitplan()
    tage = {}
    for tag in TAGE:
        tage[tag] = (_pruefe_tag(tag, rohtage[tag]) if tag in rohtage
                     else standard["tage"][tag])
    return {"aktiv": aktiv, "tage": tage}


def heile_zeitplan(roh):
    """Ladeweg: unbrauchbare Werte auf die Vorgabe zuruecksetzen und sagen.

    KEIN Abbruch — ein Geraet ohne Tastatur, das wegen einer verhunzten
    Konfiguration nicht hochkommt, ist schlimmer als eines mit der Vorgabe.
    """
    standard = standard_zeitplan()
    if roh is None:
        return standard
    if not isinstance(roh, dict):
        print(f"[Zeitplan] {roh!r} ist kein Objekt — nehme die Vorgabe")
        return standard
    aktiv = roh.get("aktiv", False)
    if not isinstance(aktiv, bool):
        print(f"[Zeitplan] aktiv={aktiv!r} unbrauchbar — nehme False")
        aktiv = False
    rohtage = roh.get("tage")
    if not isinstance(rohtage, dict):
        if rohtage is not None:
            print(f"[Zeitplan] tage={rohtage!r} unbrauchbar — nehme die Vorgabe")
        rohtage = {}
    tage = {}
    for tag in TAGE:
        if tag not in rohtage:
            tage[tag] = standard["tage"][tag]
            continue
        try:
            tage[tag] = _pruefe_tag(tag, rohtage[tag])
        except ValueError as e:
            print(f"[Zeitplan] {e} — nehme die Vorgabe fuer {TAG_NAMEN[tag]}")
            tage[tag] = standard["tage"][tag]
    return {"aktiv": aktiv, "tage": tage}

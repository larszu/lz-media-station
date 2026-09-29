#!/usr/bin/env python3
"""Zugangsschutz: eine PIN vor der Verwaltung — wenn jemand sie setzt.

WARUM ES DAS GIBT. Die Station steht in einem Gastnetz, und bis 3.0 konnte
jeder darin `/admin` oeffnen, Videos loeschen und den Pi neu starten. Das
war in Ordnung, solange die Station in einem eigenen Netz hinter einem
Router stand — und falsch, sobald ein Tablet im Foyer die Anzeige holt.

OPTIONAL. Ohne PIN bleibt alles offen wie bisher (rueckwaertskompatibel).
Mit PIN gilt:

- `/admin` verlangt eine Anmeldung (Formular `/login`, Cookie-Sitzung).
- Jeder SCHREIBENDE Aufruf (POST/PUT/DELETE) braucht die Sitzung, den
  Kopf `X-LZ-Pin` (Station Manager) oder kommt von 127.0.0.1 — dem Kiosk
  auf dem Pi selbst.
- Die Meldewege der Anzeige bleiben frei (Puls, Screenshot, Proof-of-Play,
  Auto-Start): ein Tablet im Foyer soll sich melden koennen, ohne die PIN
  zu kennen. Damit kann es nichts veraendern.
- Lesende GETs bleiben offen: die Anzeige braucht `/api/scene`, der Manager
  `/api/identity`.

DIE PIN STEHT NICHT IN DER KONFIGURATION. `config.json` wandert per Backup
auf andere Stationen und steht in `/api/status` fuer jeden im Netz. Der
Hash und das Salz liegen in `zugang.json` (0600) daneben, der Sitzungs-
Schluessel in `geheim.key`. Beides bleibt beim Klonen zurueck — eine
geklonte Station beginnt offen und sagt es in der Verwaltung.

HASH. PBKDF2-HMAC-SHA256 mit 200 000 Runden und 16 Byte Salz; eine PIN von
4 bis 12 Zeichen. Fuenf Fehlversuche je Minute und Adresse, dann 429.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

RUNDEN = 200_000
PIN_MIN, PIN_MAX = 4, 12
SITZUNG_H = 24
FEHLVERSUCHE = 5
FENSTER_S = 60.0

LOKAL = ("127.0.0.1", "::1", "::ffff:127.0.0.1")

#: Schreibende Pfade, die OHNE Anmeldung erlaubt sind — die Meldewege der
#: Anzeigeseite und der Auto-Start. Praefixe: `/api/trigger/` hat ein eigenes
#: Token (Welle 2, Paket B).
FREIE_PFADE = ("/api/anzeige/puls", "/api/anzeige/screenshot", "/api/wiedergabe",
               "/api/start", "/api/zugang/login", "/api/zugang/logout")
FREIE_PRAEFIXE = ("/api/trigger/",)


def hash_pin(pin, salz):
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salz, RUNDEN).hex()


def pruefe_pin_form(pin):
    if not isinstance(pin, str):
        raise ValueError("pin: muss Text sein")
    if not (PIN_MIN <= len(pin) <= PIN_MAX):
        raise ValueError(f"pin: {PIN_MIN}..{PIN_MAX} Zeichen")
    if any(c.isspace() for c in pin):
        raise ValueError("pin: keine Leerzeichen")


class Zugang:
    """Der Stand: gesetzt oder offen, Hash, Sitzungsdauer, Fehlversuche."""

    def __init__(self, pfad):
        self.pfad = pfad
        self._lock = threading.Lock()
        self.pin_hash = ""
        self.salz = ""
        self.sitzungsdauer_h = SITZUNG_H
        #: Zaehlt jedes Setzen und Aufheben. Eine Sitzung traegt die Generation,
        #: unter der sie entstand — nach einem PIN-Wechsel passt sie nicht mehr
        #: und gilt nicht. Sonst bliebe das Tablet im Foyer angemeldet, dem
        #: gerade die PIN entzogen wurde.
        self.generation = 0
        self._versuche = {}   # adresse -> [zeitpunkte]
        #: Der zuletzt als richtig erkannte Kopfwert `X-LZ-Pin`, an den Hash
        #: gebunden, unter dem er stimmte. Spart die 200 000 PBKDF2-Runden
        #: je Manager-Aufruf; ein neuer Hash macht ihn wertlos.
        self._kopf_ok = None   # (pin_hash, pin) oder None
        self._laden()

    # --- Ablage -----------------------------------------------------------

    def _laden(self):
        try:
            with open(self.pfad, encoding="utf-8") as f:
                d = json.load(f)
            self.pin_hash = d.get("pin_hash") or ""
            self.salz = d.get("salz") or ""
            h = d.get("sitzungsdauer_h", SITZUNG_H)
            self.sitzungsdauer_h = h if isinstance(h, (int, float)) and 1 <= h <= 24 * 30 else SITZUNG_H
            g = d.get("generation", 0)
            self.generation = g if isinstance(g, int) and not isinstance(g, bool) and g >= 0 else 0
        except (OSError, ValueError):
            pass
        if self.pin_hash and not self.salz:
            print("[Zugang] zugang.json ohne Salz — die PIN gilt als nicht gesetzt")
            self.pin_hash = ""

    def _speichern(self):
        tmp = self.pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pin_hash": self.pin_hash, "salz": self.salz,
                       "sitzungsdauer_h": self.sitzungsdauer_h,
                       "generation": self.generation}, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.pfad)

    # --- Fachliches -------------------------------------------------------

    @property
    def gesetzt(self):
        return bool(self.pin_hash)

    def setzen(self, pin, sitzungsdauer_h=None):
        # ERST alles pruefen, DANN aendern: eine abgelehnte Sitzungsdauer darf
        # nicht schon die neue PIN im Speicher hinterlassen, waehrend in der
        # Datei die alte steht — bis zum Neustart gaelte dann eine PIN, die
        # laut Antwort abgelehnt wurde.
        pruefe_pin_form(pin)
        if sitzungsdauer_h is not None:
            if not isinstance(sitzungsdauer_h, (int, float)) or isinstance(sitzungsdauer_h, bool) \
                    or not 1 <= sitzungsdauer_h <= 24 * 30:
                raise ValueError("sitzungsdauer_h: 1..720 Stunden")
        salz = secrets.token_bytes(16)
        neuer_hash = hash_pin(pin, salz)
        with self._lock:
            alt = (self.pin_hash, self.salz, self.sitzungsdauer_h, self.generation)
            self.salz = salz.hex()
            self.pin_hash = neuer_hash
            if sitzungsdauer_h is not None:
                self.sitzungsdauer_h = sitzungsdauer_h
            self.generation += 1
            self._kopf_ok = None
            try:
                self._speichern()
            except OSError:
                self.pin_hash, self.salz, self.sitzungsdauer_h, self.generation = alt
                raise

    def aufheben(self):
        with self._lock:
            self.pin_hash = ""
            self.salz = ""
            self.generation += 1
            self._kopf_ok = None
            self._speichern()

    def stimmt(self, pin):
        if not self.gesetzt or not isinstance(pin, str):
            return False
        try:
            erwartet = self.pin_hash
            ist = hash_pin(pin, bytes.fromhex(self.salz))
        except ValueError:
            return False
        return hmac.compare_digest(erwartet, ist)

    def stimmt_kopf(self, pin):
        """Wie `stimmt`, aber mit Gedaechtnis fuer den letzten richtigen Wert.

        Der Manager schickt die PIN mit JEDEM Aufruf; jede Pruefung kostet
        ~0,5 s Rechenzeit auf einem Pi. Stimmt der Wert mit dem zuletzt als
        richtig erkannten ueberein (unter demselben Hash), ist er richtig —
        in konstanter Zeit verglichen. Falsche Werte werden nie gemerkt, ein
        Wechsel der PIN loescht das Gedaechtnis.
        """
        if not self.gesetzt or not isinstance(pin, str):
            return False
        with self._lock:
            merk = self._kopf_ok
        if merk is not None and merk[0] == self.pin_hash and hmac.compare_digest(merk[1], pin):
            return True
        if not self.stimmt(pin):
            return False
        with self._lock:
            self._kopf_ok = (self.pin_hash, pin)
        return True

    # --- Fehlversuche -----------------------------------------------------

    def gesperrt(self, adresse, jetzt=None):
        jetzt = time.monotonic() if jetzt is None else jetzt
        with self._lock:
            liste = [t for t in self._versuche.get(adresse, []) if jetzt - t < FENSTER_S]
            self._versuche[adresse] = liste
            return len(liste) >= FEHLVERSUCHE

    def fehlversuch(self, adresse, jetzt=None):
        jetzt = time.monotonic() if jetzt is None else jetzt
        with self._lock:
            self._versuche.setdefault(adresse, []).append(jetzt)

    def erfolg(self, adresse):
        with self._lock:
            self._versuche.pop(adresse, None)


def lade_geheim(pfad):
    """Der Sitzungs-Schluessel aus `geheim.key` — oder None, wenn es ihn nicht gibt."""
    try:
        with open(pfad, "rb") as f:
            schluessel = f.read()
        if len(schluessel) >= 32:
            return schluessel
    except OSError:
        pass
    return None


def schreibe_geheim(pfad, schluessel):
    """Den Schluessel ablegen (0600) — erst, wenn eine PIN gesetzt wird.

    Eine Station ohne PIN braucht keine Sitzungen; eine Datei anzulegen, die
    niemand braucht (in jeder Test-App, in jedem Klon), waere Rauschen.
    Gibt True zurueck, wenn die Datei steht.
    """
    if lade_geheim(pfad) == schluessel:
        return True
    try:
        tmp = pfad + ".tmp"
        with open(tmp, "wb") as f:
            f.write(schluessel)
        os.chmod(tmp, 0o600)
        os.replace(tmp, pfad)
        return True
    except OSError as e:
        print(f"[Zugang] geheim.key nicht schreibbar ({e}) — Sitzungen gelten nur bis zum Neustart")
        return False


#: Frei je nach Methode: `POST /api/zugang` prueft die alte PIN selbst (sonst
#: koennte niemand die PIN aendern, der noch keine Sitzung hat); `DELETE`
#: bleibt geschuetzt.
FREIE_METHODEN = {("POST", "/api/zugang")}


def ist_frei(pfad, methode="POST"):
    return (pfad in FREIE_PFADE or (methode, pfad) in FREIE_METHODEN
            or any(pfad.startswith(p) for p in FREIE_PRAEFIXE))


def ist_lokal(adresse):
    return adresse in LOKAL


def sicherer_weiter(pfad, vorgabe="/admin"):
    """Wohin es nach dem Anmelden geht — nur ein Pfad DIESER Station.

    `?weiter=https://fremd.example` oder `//fremd.example` (der Browser liest
    das als Adresse mit Schema) wuerde die Anmeldung zu einer Weiterleitung
    auf eine fremde Seite machen. Erlaubt ist genau ein einzelner Schraegstrich
    am Anfang, kein zweiter, kein Backslash, kein Zeilenumbruch.
    """
    if not isinstance(pfad, str) or not pfad.startswith("/") or len(pfad) > 512:
        return vorgabe
    if pfad.startswith("//") or pfad.startswith("/\\") or "\\" in pfad \
            or any(c in pfad for c in "\r\n\x00"):
        return vorgabe
    return pfad


def sitzung_gilt(zugang, sitzung_bis, sitzung_gen, jetzt):
    """Eine Sitzung gilt, wenn sie nicht abgelaufen ist UND aus der aktuellen
    PIN-Generation stammt. Ein Cookie aus der Zeit vor einem PIN-Wechsel
    oder Aufheben+Setzen ist wertlos — genau dafuer wechselt man die PIN."""
    return (isinstance(sitzung_bis, (int, float)) and sitzung_bis > jetzt
            and sitzung_gen == zugang.generation)


def entscheide(zugang, methode, pfad, adresse, sitzung_bis, pin_kopf, jetzt, sitzung_gen=None):
    """Reine Entscheidung: `None` = durchlassen, sonst ein Grund fuer 401/429/303.

    `sitzung_bis` ist der Zeitstempel aus dem Cookie (oder None), `sitzung_gen`
    die PIN-Generation aus dem Cookie, `pin_kopf` der Wert von `X-LZ-Pin`
    (oder None), `jetzt` die Unix-Zeit.
    """
    if not zugang.gesetzt:
        return None
    angemeldet = sitzung_gilt(zugang, sitzung_bis, sitzung_gen, jetzt)
    if pfad == "/admin":
        return None if angemeldet else "anmelden"
    if methode in ("GET", "HEAD", "OPTIONS"):
        return None
    if ist_frei(pfad, methode) or ist_lokal(adresse) or angemeldet:
        return None
    if pin_kopf is not None:
        if zugang.gesperrt(adresse):
            return "gesperrt"
        if zugang.stimmt_kopf(pin_kopf):
            zugang.erfolg(adresse)
            return None
        zugang.fehlversuch(adresse)
        return "falsche_pin"
    return "pin"

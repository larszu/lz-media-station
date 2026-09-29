# Zugang: eine PIN vor der Verwaltung

Seit 3.0, Karte **Zugang** in der Verwaltung. Optional — ohne PIN bleibt alles
offen wie bisher.

## Warum

Die Station steht in einem Gastnetz. Bis 3.0 konnte jeder darin `/admin`
öffnen, Videos aus den Zonen nehmen und den Pi neu starten. Das war in Ordnung,
solange die Station in einem eigenen Netz hinter einem Router stand — und
falsch, sobald ein Tablet im Foyer die Anzeige über das WLAN des Hauses holt.

## Was die PIN schützt

| | ohne PIN | mit PIN |
|---|---|---|
| `/admin` | offen | Anmeldung (`/login`), Cookie-Sitzung, Vorgabe 24 h |
| Lesen (`GET /api/scene`, `/api/status`, `/api/identity`, `/display`, …) | offen | **offen** — die Anzeige und die Discovery des Managers brauchen es |
| Schreiben (`POST`/`PUT`/`DELETE` unter `/api/…`) | offen | Sitzung, **oder** Kopf `X-LZ-Pin: <PIN>`, **oder** Aufruf von `127.0.0.1` (der Kiosk auf dem Pi selbst) — sonst `401 {"zugang": "pin"}` |
| Meldewege der Anzeige (`/api/anzeige/puls`, `/api/anzeige/screenshot`, `/api/wiedergabe`, `/api/start`) | offen | **offen** — ein Tablet im Foyer soll sich melden können, ohne die PIN zu kennen; ändern kann es damit nichts |
| `/api/trigger/…` (Auslöser, Paket B) | — | eigenes Token, nicht die PIN |

`/api/anzeige/screenshot/anfordern` ist **nicht** frei: ein Bild des Schirms
anzufordern ist Sache der Verwaltung.

## Setzen, ändern, aufheben

- **PIN setzen** in der Karte: 4–12 Zeichen, keine Leerzeichen, zweimal
  eingeben. Wer sie setzt, ist danach angemeldet.
- **Ändern** braucht die bisherige PIN (`alt`) — oder eine gültige Sitzung.
- **Jeder Wechsel** (setzen, ändern, aufheben) beendet alle bestehenden
  Sitzungen — wer die PIN ändert, will genau das: das Tablet im Foyer ist
  danach abgemeldet. Der Manager schickt seine PIN je Aufruf und merkt
  nichts davon, solange er die neue kennt.
- **Aufheben** braucht Sitzung oder Kopf; danach ist die Verwaltung wieder
  offen, und die Karte sagt es.
- **Vergessen?** Per SSH auf dem Pi:
  `curl -X POST -H 'Content-Type: application/json' -d '{"pin":"neu1234"}' http://127.0.0.1:5000/api/zugang`
  — vom Gerät selbst darf die PIN ohne die alte neu gesetzt werden.
- Fünf Fehlversuche je Minute und Adresse, dann `429` für eine Minute.

## Wo die PIN liegt — und wo nicht

Die PIN steht **nicht in `config.json`**. Die Konfiguration wandert per
Sicherung auf andere Stationen und steht in `/api/status` für jeden im Netz.
Stattdessen:

| Datei | Inhalt | Rechte |
|---|---|---|
| `zugang.json` | PBKDF2-HMAC-SHA256-Hash (200 000 Runden), 16 Byte Salz, Sitzungsdauer, Generation (zählt jeden Wechsel) | 0600 |
| `geheim.key` | Sitzungs-Schlüssel, entsteht mit der ersten PIN | 0600 |

Beide liegen neben `config.json` und bleiben beim Klonen zurück: eine geklonte
Station **beginnt offen** und sagt es in der Karte. Eine Sicherung
(`/api/backup`) enthält die PIN nicht.

## Station Manager

Der Manager schickt die PIN als Kopf `X-LZ-Pin`. Antwortet eine Station mit
`401` und `zugang`, fragt er sie ab (🔑 an der Karte, oder von selbst beim
ersten Schreibzugriff), merkt sie sich je `host:port` in `pins.json` seines
Profils und wiederholt den Aufruf einmal. Discovery und Statusabfrage brauchen
keine PIN.

## Schnittstelle

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/zugang` | `{gesetzt, angemeldet, lokal, sitzungsdauer_h}` |
| POST | `/api/zugang` | `{pin, alt?, sitzungsdauer_h?}` — setzen oder ändern |
| DELETE | `/api/zugang` | aufheben |
| POST | `/api/zugang/login` | `{pin}` → Sitzung |
| POST | `/api/zugang/logout` | Sitzung beenden |
| GET | `/login` | die Anmeldeseite (`?weiter=/admin` — nur Pfade dieser Station, alles andere wird zu `/admin`) |

Die Entscheidung selbst steht in `zugang.entscheide(...)` — rein, ohne Flask —
und ist in `tests/test_zugang.py` durchgespielt.

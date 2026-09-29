# Widgets — Uhr, Text, Ticker, Wetter, Kalender, QR und eigene

Eine Region eines Layouts (siehe [Architektur 3.0](architektur-v3.md)) kann
statt einer Playlist ein **Widget** zeigen: `typ: "widget"`, und im Feld
`widget` steht, welches und wie eingestellt. Widgets laufen im Browser der
Anzeige (`static/anzeige/widgets.js`); was aus dem Netz kommt, holt der Kern
(`widgets.py`, `api_widgets.py`) und reicht es als kleines JSON weiter.

```json
{ "id": "ecke", "typ": "widget", "x": 70, "y": 0, "w": 30, "h": 20,
  "widget": { "typ": "uhr", "stil": "digital", "sekunden": false, "datum": true } }
```

## Was überall gilt

- **Ohne Netz kein Absturz.** Fällt ein Abruf aus, zeigt das Widget den
  letzten Stand und darunter eine dezente Zeile („Stand: älter …"). Gab es
  noch nie einen Stand, steht dort der Grund — nie eine leere weiße Fläche,
  nie ein Fehler in der Konsole. Der Schirm bleibt an.
- **Der Kern holt, nicht der Browser.** RSS, ICS und Wetter laufen über
  `GET /api/widgets/rss|ics|wetter`. Nur `http://` und `https://`, höchstens
  1 MB, 5 s Zeit, keine Cookies, Zwischenspeicher je Adresse (Vorgabe 300 s,
  Wetter 15 min; Umgebung `LZ_WIDGET_CACHE_S` ändert die Vorgabe).
- **Die Größe folgt der Region.** Schriftgrößen entstehen aus der kleineren
  Kante der Region, mal dem Feld *Schriftgröße (%)*. Ein Ticker am unteren
  Rand und eine Vollbild-Uhr nutzen dieselbe Regel.
- **Zeit der Vorschau.** In `/display?vorschau=1&layout=…&zeit=…` rechnen
  Uhr, Kalender und Zähler von der gewählten Zeit weiter — die Uhr tickt,
  aber ab Dienstag 18:00.
- **Sprache.** Texte sind deutsch und werden über das Wörterbuch
  (`static/i18n/widgets.en.js`) übersetzt; Datum und Uhrzeit folgen der
  Sprache der Anzeige (`?lang=en`).
- **Farben.** Jedes Widget hat *Textfarbe* und *Hintergrund*; leer heißt
  durchsichtig, also der Grund des Layouts. Keine Rundungen, keine Schatten —
  die Marke gilt auch auf dem Schirm.

## Die Widgets

`GET`-frei: Der Layout-Editor liest `LZ_WIDGETS.katalog()` und baut daraus die
Formulare. Die Felder hier sind die Schlüssel im `widget`-Objekt.

### `uhr` — Uhr
| Feld | Bedeutung |
|---|---|
| `stil` | `digital` oder `analog` |
| `sekunden`, `datum`, `zwoelf` | Sekunden zeigen, Datum zeigen, 12-Stunden-Format |
| `zeitzone` | IANA-Name (`Europe/Berlin`); leer = Uhr der Station |

### `text` — Text-Folie mit Vorlagen
| Feld | Bedeutung |
|---|---|
| `vorlage` | `frei`, `willkommen`, `wegweiser`, `menuekarte`, `hinweis`, `oeffnungszeiten` — belegt leere Felder vor |
| `ueberschrift`, `text`, `fusszeile` | Die drei Zeilenarten; `text` darf Zeilenumbrüche haben |
| `pfeil` | `←` `→` `↑` `↓` `↖` `↗` `↘` `↙` oder leer (Wegweiser) |
| `ausrichtung` | `links`, `mitte`, `rechts` |
| `akzent` | Farbe für Überschrift und Pfeil |

- **Speisekarte:** eine Zeile je Gericht, `Gericht | Preis` — wird eine Tabelle
  mit rechtsbündigen Preisen.
- **Öffnungszeiten:** ohne eigenen Text kommen die Zeiten aus der
  [Zeitsteuerung](zeitsteuerung.md) der Station (Wochentag, von–bis oder
  „geschlossen"; Zeitsteuerung aus = „Täglich geöffnet").
- **Willkommen:** ohne Text steht der Stationsname darunter.

### `ticker` — Laufschrift
| Feld | Bedeutung |
|---|---|
| `text` | Eigener Text; Zeilenumbrüche werden zum Trennzeichen |
| `rss_url` | Alternativ die Schlagzeilen eines Feeds (alle 10 min neu) |
| `geschwindigkeit` | Pixel je Sekunde (10–600) |
| `trenner`, `richtung` | Zwischen den Meldungen; `links` oder `rechts` |

### `wetter` — Wetter (Open-Meteo)
| Feld | Bedeutung |
|---|---|
| `lat`, `lon` | Koordinaten des Orts (Berlin: 52.52 / 13.405) |
| `ort` | Nur zur Anzeige |
| `einheit` | `c` oder `f` |
| `tage` | Vorschau-Tage, 0–3 |

Datenquelle ist [Open-Meteo](https://open-meteo.com) — ohne Schlüssel, ohne
Konto. Es gehen nur die Koordinaten hinaus, sonst nichts.

### `rss` — Nachrichten als Liste
| Feld | Bedeutung |
|---|---|
| `url` | RSS 2.0 oder Atom |
| `anzahl` | Höchstens so viele Einträge (1–20) |
| `wechsel_s` | 0 = Liste; sonst ein Eintrag groß, alle *n* Sekunden der nächste |
| `quelle`, `zeit`, `vorschau_text` | Was je Eintrag mitkommt |

### `kalender` — Termine aus einem ICS-Abo
| Feld | Bedeutung |
|---|---|
| `url` | iCalendar-Adresse (Google, Nextcloud, Outlook …) |
| `ansicht` | `heute`, `woche` (nächste 7 Tage), `raum` (Jetzt / Danach) |
| `anzahl`, `zwoelf`, `titel` | Höchstens Termine; 12-Stunden-Format; Überschrift (leer = Kalendername) |

Wiederholungen (`RRULE`) werden für `FREQ=DAILY` und `FREQ=WEEKLY` (mit
`INTERVAL`, `COUNT`, `UNTIL`, `BYDAY`) ausgerollt; andere Regeln zählen als
Einzeltermin — lieber ein fehlender Termin als ein erfundener. Ein Termin
über Mitternacht steht an beiden Tagen.

### `qr` — QR-Code
| Feld | Bedeutung |
|---|---|
| `inhalt` | Text oder Adresse; leer = die Verwaltung dieser Station (`remote_url`) |
| `beschriftung` | Text darunter |
| `modulfarbe`, `codegrund` | Vorgabe Navy auf Hell — dunkel auf hell liest jedes Handy |

Der Code entsteht in der Anzeige selbst (Byte-Modus, Fehlerkorrektur M,
Versionen 1–10, bis 213 Zeichen) — kein fremdes Skript, geht offline.

### `webseite` — eine Webseite im Rahmen
| Feld | Bedeutung |
|---|---|
| `url` | `http://` oder `https://` |
| `reload_s` | Neu laden alle *n* Sekunden (0 = nie) |
| `zoom` | 25–300 % |
| `interaktiv` | Berührungen durchlassen (sonst ist der Rahmen nur Bild) |

Viele Seiten verbieten das Einbetten (`X-Frame-Options`,
`frame-ancestors`). Der Browser meldet das nicht — deshalb fragt die Anzeige
`GET /api/widgets/einbettbar?url=…` und sagt es in einer Zeile unten, statt
eine leere Fläche zu zeigen. Für Webseiten in einer Playlist (mit Standzeit)
gibt es weiterhin den Eintragstyp `web`.

### `html` — eigenes Widget
| Feld | Bedeutung |
|---|---|
| `name` | Ordner unter `widgets/` |
| `einstellungen` | Eine Zeile je `schluessel=wert` |
| `reload_s` | Neu laden (0 = nie) |

### `zaehler` — Countdown / Count-up
| Feld | Bedeutung |
|---|---|
| `ziel` | `JJJJ-MM-TTTHH:MM` (Ortszeit der Station) |
| `modus` | `countdown` (bis) oder `countup` (seit) |
| `beschriftung`, `danach` | Zeile darüber; Text, wenn der Zeitpunkt erreicht ist |
| `sekunden` | Sekunden zeigen |

## Eigene Widgets bauen

Ein Ordner `widgets/<name>/` mit `index.html` — fertig. Die Anzeige bettet
die Seite als Rahmen in die Region ein; sie ist so groß wie die Region.
`widgets/beispiel/index.html` ist die Vorlage mit allen Hinweisen im Kopf.

- **Einstellungen** kommen als Query-String (`?schluessel=wert&…`) und, sobald
  die Seite geladen ist, als `window.LZ_WIDGET_EINSTELLUNGEN`. Immer dabei:
  `sprache`, `station`, in der Vorschau `zeit`.
- **Dateien** daneben (CSS, Bilder, Skripte) kommen unter
  `/widgets/<name>/<datei>` heraus — nur aus diesem Ordner; `..` und absolute
  Pfade enden in 404.
- `GET /api/widgets/eigene` listet alle Ordner mit `index.html` (Name und
  `<title>`).
- Keine Dialoge (`alert`, `confirm`): sie halten den Kiosk an. Nichts laden,
  was die Station offline nicht hätte.

## Datenschutz und Netz

Der Pi ruft von sich aus nur das ab, was in einem Layout eingetragen ist:
die Feed-Adressen, die ICS-Adresse, Open-Meteo mit den Koordinaten. Es gehen
keine Cookies, keine Kennungen und nichts über Besucher hinaus. Wer die
Station ganz offline betreibt, nutzt Uhr, Text-Folie, Laufschrift mit eigenem
Text, QR-Code, Zähler und eigene Widgets — die brauchen kein Netz.

## Schnittstelle für Entwickler

`window.LZ_WIDGETS`:

| Aufruf | Bedeutung |
|---|---|
| `render(el, widget, ctx)` | Zeichnet `widget` in `el`; gibt `{ stop() }` zurück. `ctx`: `{ zeit, jetzt(), sprache, region, layout, stationsname, vorschau }` |
| `katalog()` | `[{ typ, name, beschreibung, felder: [{ key, label, typ, default, optionen?, min?, max? }] }]` — Feldtypen `text`, `zahl`, `farbe`, `auswahl`, `bool`, `url`, `textarea` |
| `stopAll()` | Hält alle laufenden Widgets an |
| `qr.matrix(text, {maske?})`, `qr.svg(text, {farbe, hintergrund})` | Der QR-Encoder, auch unter Node ohne DOM (`require`) |

Neue Widgets kommen als Eintrag in `WIDGETS` in `widgets.js` — `katalog()`
leitet sich daraus ab, ein Widget ohne Katalogeintrag kann es nicht geben.
Sichtbare Texte deutsch, Übersetzung in `static/i18n/widgets.en.js`.

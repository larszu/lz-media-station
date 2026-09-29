# Architektur 3.0 — Layouts, Ereignisse, Erweiterungspunkte

Was sich mit 3.0 unter der Haube ändert, und wo eine Erweiterung anfasst.
Stand: Welle 1 (Fundament). Der Layout-Editor, Widgets, Vorschau im Manager
und Zeitplanung je Playlist kommen in Welle 2 — **als Dateien, nicht als
Änderung am Kern** (siehe [Erweiterungspunkte](#erweiterungspunkte)).

---

## Datenmodell

### Layout

Ein Layout teilt den Schirm in **Regionen**. Jede Zone spielt genau ein
Layout. `config.json` trägt sie unter `layouts`:

```json
"layouts": {
  "zone-near": {
    "name": "Nah – Vollbild",
    "vorlage": "vollbild",
    "hintergrund": "#000000",
    "regionen": [ { …Region… } ]
  }
}
```

| Feld | Bedeutung | Grenze |
|---|---|---|
| Kennung (Schlüssel) | `^[a-z0-9][a-z0-9-]{0,39}$` | höchstens 60 Layouts |
| `name` | Anzeigename | 1..64 Zeichen |
| `vorlage` | `vollbild` · `geteilt` · `l-form` · `ticker` · `frei` — nur eine Merkhilfe, wie die Regionen einmal vorbelegt wurden | |
| `hintergrund` | Farbe hinter den Regionen | `#rrggbb` |
| `regionen` | Liste | höchstens 12, Kennungen eindeutig |

**Die drei Zonen-Layouts** `zone-near`, `zone-mid`, `zone-far` gibt es immer.
Eine Zone mit `layout: ""` spielt ihr Zonen-Layout; sie lassen sich nicht
löschen, solange eine Zone sie spielt (auch nicht die unausgesprochene
Vorgabe).

### Region

```json
{ "id": "haupt", "name": "Hauptbild",
  "x": 0, "y": 0, "w": 70, "h": 80, "z": 0,
  "typ": "medien", "ton": true,
  "playlist": [ …Eintrag… ], "shuffle": false, "einmal": false,
  "uebergang": "blende",
  "widget": {} }
```

| Feld | Bedeutung |
|---|---|
| `x` `y` `w` `h` | Prozent des Schirms (0..100); die Region darf nicht hinausragen. Beim Laden wird eingekürzt, beim Schreiben abgelehnt |
| `z` | Stapelreihenfolge (höher liegt oben) |
| `typ` | `medien` (spielt die Playlist) oder `widget` (überlässt die Fläche `LZ_WIDGETS`) |
| `ton` | Ob Videos in dieser Region hörbar sind — in einem geteilten Layout hat nur eine Region Ton |
| `shuffle` `einmal` | Wie bisher bei der Zone, jetzt je Region |
| `uebergang` | `blende` (0,8 s Deckkraft) oder `keiner` (harter Schnitt) |
| `widget` | Frei; `typ` benennt das Widget (Welle 2) |

### Eintrag (Playlist-Item)

```json
{ "typ": "video", "name": "film.mp4",   "dauer_s": null, "von": null,         "bis": null }
{ "typ": "image", "name": "tafel.jpg",  "dauer_s": 20,   "von": "2026-06-01", "bis": "2026-06-30" }
{ "typ": "web",   "url": "https://…",   "dauer_s": 60,   "von": null,         "bis": null }
{ "typ": "audio", "name": "musik.mp3",  "dauer_s": null, "von": null,         "bis": null }
```

- `dauer_s` — Standzeit für Bild und Webseite (1..86400 s); leer = der
  allgemeine Bildwechsel (`image_interval_s`) bzw. 30 s für eine Webseite.
  Videos und Audio bringen ihre Dauer mit.
- `von`/`bis` — Gültigkeit als Kalendertag (`JJJJ-MM-TT`), beide optional.
  **Gefiltert wird im Kern** (`get_scene`), nicht im Browser: die Anzeige
  bekommt nichts, was heute nicht gilt.
- Videos vor Bildern, Bilder vor Webseiten? Nein — die Reihenfolge der
  Liste zählt. Gemischt ist erlaubt und gewollt.

### Die Zone

```json
"near": { "layout": "", "audio": ["musik.mp3"],
          "videos": [], "images": [], "shuffle": false, "einmal": false, "bildzeiten": {} }
```

`layout` (leer = Zonen-Layout) und `audio` (Ton der Zone, läuft parallel zu
allen Regionen) gehören der Zone. **`videos`, `images`, `shuffle`, `einmal`
und `bildzeiten` sind seit 3.0 ein Spiegel der Hauptregion** (erste
Medien-Region) des Zonen-Layouts: `layouts.spiegle_zone` setzt sie nach
jedem Schreibzugriff neu. Die Wahrheit steht im Layout. Der Spiegel bleibt,
weil ihn lesen: alte Anzeigeseiten, der Station Manager (Config-Push), alte
Sicherungen, Skripte — und die Zustandsprüfung als Rückfall.

## Migration

Beim ersten Start mit einer `config.json` von vor 3.0 (kein `layouts`):

1. `heile_layouts_und_zonen` legt die drei Zonen-Layouts an.
2. Die alten Listen der Zone wandern in die Hauptregion: Videos zuerst, dann
   Bilder mit ihrer Standzeit aus `bildzeiten`; `shuffle`/`einmal` gehen mit.
3. Der Spiegel wird gesetzt. Danach sagen Zone und Layout dasselbe.

Dieselbe Regel gilt vor jedem Schreibzugriff (`uebernimm_spiegel`): trägt die
Zone Listen, die im **leeren** Layout fehlen, gehören sie ins Layout. Steht im
Layout schon etwas, ist das Layout die Wahrheit. Eine alte Sicherung über
`POST /api/restore` nimmt denselben Weg.

**Ein alter Manager schickt `{"near": {"videos": [...]}}`** — `POST /api/config`
schreibt das in die Hauptregion (`schreibe_zonen_teil`), erhält dabei
Gültigkeit und Standzeit vorhandener Einträge und hängt Web- und
Audio-Einträge hinten an. Es kommt also an, und nichts geht verloren.

## Ereignisse (SSE)

`GET /api/events` ist ein `text/event-stream`. Die Anzeige und die Verwaltung
hören zu, statt zweimal je Sekunde zu fragen; gefragt wird nur noch als
Rückfall (Anzeige alle 5 s, Verwaltung alle 2 s).

| Ereignis | Wann | Nutzlast |
|---|---|---|
| `scene` | Zonenwechsel, Start/Stopp, Öffnungszeit auf/zu, nach jedem Schreibzugriff | wie `GET /api/scene` |
| `config` | nach jedem Schreibzugriff (`/api/config`, `/api/restore`, `/api/layouts…`, Löschen einer Datei) | die ganze Konfiguration |
| `status` | jede Sekunde, nur mit `?status=1` | wie `GET /api/status` |
| `befehl` | `POST /api/befehl` | siehe unten |

Alle 15 s ein Kommentar (`: puls`), damit Proxys die Verbindung nicht
schließen. Ein Abonnent, der nicht liest, verliert nach 100 Ereignissen die
ältesten — der Kern wächst nicht.

Im Kern: `ereignisse.Ereignisbus` (ohne Flask), `Controller.melde_szene()`
(nur bei Wechsel von aktiv/Zone/offen, sonst kein Ereignis) und
`Controller.melde_config()` (setzt die Kennung zurück, damit die Szene auch
ohne Zonenwechsel hinausgeht).

### Befehle

`POST /api/befehl` reicht einen Befehl an alle Anzeigen, die gerade zuhören:

```json
{ "typ": "reload" }
{ "typ": "zeige_layout", "layout_id": "durchsage", "dauer_s": 30 }
{ "typ": "zeige_layout", "layout_id": null }
{ "typ": "screenshot" }
```

- `reload` — die Anzeigeseite lädt sich neu (nach einem Update).
- `zeige_layout` — ein Layout zwischendurch zeigen (Durchsage, Probe am
  echten Schirm). `dauer_s` leer = bis zum nächsten Befehl; `layout_id` leer =
  zurück zur Zone. Die Anzeige holt sich dazu `GET /api/scene?layout=<id>`.
- `screenshot` — wird durchgereicht; die Auswertung kommt mit Welle 2.

Weitere Befehle senden die Erweiterungen selbst über den Bus (nicht über
`/api/befehl`): `meldung` (die Sofortmeldung, Felder wie `GET /api/meldung`)
und `schwarz` `{an}` (Schirm schwarz/an) — siehe [Auslöser](ausloeser.md).

Die Antwort nennt, wie viele Anzeigen zuhörten (`empfaenger`).

## Vorschau

`/display?vorschau=1&layout=<id>[&zone=near][&zeit=JJJJ-MM-TTTHH:MM]` zeigt
ein Layout mit **derselben Seite, die auch auf dem Schirm läuft** — ohne
Sensor, ohne Auto-Start, ohne Zonenwechsel. `GET /api/scene?layout=…` liefert
die Szene dazu; `zeit` entscheidet, welche Einträge an dem Tag gelten, und
geht als `ctx.zeit` an Widgets. Ändert sich die Konfiguration, holt die
Vorschau die Szene neu (Ereignis `config`) — der Editor der Welle 2 zeigt
damit live, was er baut.

## Die Anzeige (display.js)

- Container `#buehne`; je Region ein absolut positioniertes `div.region`
  (Prozent), darin A/B-Paare für Video und Bild, ein `iframe` für Webseiten
  und ein `audio` für Audio-Einträge. Blende per Deckkraft; `uebergang:
  keiner` schaltet sie ab.
- Die Regionen werden **nur neu aufgesetzt, wenn sich ihre Kennung ändert**
  (Geometrie, Playlist, Schalter). Eine laufende Seitenleiste beginnt nicht
  von vorn, weil im Hauptbild ein Video dazukam.
- Fehler: ein nicht ladbarer Eintrag wird übersprungen; ist keiner
  abspielbar, bleibt die Region dunkel und probiert es nach 30 s wieder.
- **Keine Umleitung zum Admin.** Nach 30 s ohne Inhalt, ohne Kontakt zur
  Station oder ohne ladbares Medium steht unten eine dezente Zeile Klartext.
  ESC führt weiterhin zum Admin.
- Ein Kern von vor 3.0 (ohne `layout` in der Szene) wird erkannt: die Seite
  baut dann ein Vollbild-Layout aus den Zonenlisten.

## Erweiterungspunkte

Welle 2 (Editor, Widgets, Zeitplanung, Manager-Vorschau) legt Dateien hin.
Nichts davon muss in `web_ui.py`, `admin.html` oder `i18n.js` eingetragen
werden.

| Was | Wo | Wie |
|---|---|---|
| API-Routen | `api_<name>.py` im Wurzelverzeichnis | `def erzeuge_blueprint(controller)` gibt einen Flask-Blueprint zurück; `create_app` registriert jedes `api_*.py`. Vorbild: `api_layouts.py`. Schreibzugriffe: unter `controller.lock`, danach `controller.save_config()` und `controller.melde_config()` |
| Karten im Admin | `templates/admin/zusatz/<name>.html` | wird alphabetisch vor der Karte „Über" eingebunden (Jinja `include`) |
| Skripte im Admin | `static/module/<name>.js` | läuft nach `app.js`; `el()`, `esc()`, `tr()`, `config`, `sendeZone()` stehen bereit |
| Skripte auf der Anzeige | `static/anzeige/<name>.js` | läuft vor `display.js` — hier gehört `widgets.js` hin |
| Englische Texte | `static/i18n/<name>.en.js` | `(window.LZ_I18N_EN_EXTRA = window.LZ_I18N_EN_EXTRA \|\| []).push(/*JSON*/{ "texte": {}, "muster": [], "html": {} }/*JSON*/);` — `tests/test_i18n.py` prüft sie mit denselben Regeln wie den Kern |
| Layout-Regel | `controller.layout_regeln.append(regel)` | `regel(zone, jetzt, config) -> layout_id \| None`; die erste Antwort gewinnt, eine unbekannte Kennung zählt nicht. So hängt sich das [Wochenprogramm](programm.md) ein (`api_programm.py`) |
| Szenen-Zusatz | `controller.szene_zusatz.append(zusatz)` | `zusatz(jetzt) -> dict`, wird in jede Szene gemischt. So kommen `meldung` (Sofortmeldung), `schwarz` und `ausloeser_video_ende` zur Anzeige |
| Config-Beobachter | `controller.config_beobachter.append(fn)` | `fn()` ohne Argumente, gerufen aus `melde_config` nach JEDEM Schreibzugriff (auch `/api/restore`). So folgen die GPIO-Taster der Ausloeser jeder Konfigurationsaenderung, nicht nur ihrer eigenen Route |
| Ereignisse auf der Anzeige | `document.addEventListener('lz-szene' \| 'lz-befehl' \| 'lz-eintrag', …)` | display.js meldet jede Szene, jeden Befehl (auch unbekannte Typen) und jeden gestarteten Eintrag; `window.LZ_ANZEIGE.regionen()` nennt den Stand. So legen `static/anzeige/meldung.js` und `ausloeser.js` ihre Ebenen darüber |
| Widgets | `window.LZ_WIDGETS.render(el, widget, ctx)` | `el` ist die Regionsfläche, `widget` das Objekt aus der Region, `ctx` = `{ zeit: Date, jetzt(): Date, sprache, region, layout, stationsname, vorschau }`. Rückgabe optional `{ stop() }` — wird beim Abbau der Region gerufen. In der Vorschau ist `zeit` die gewählte Zeit, nicht die Uhr |

Bestehende Karten des Admins liegen als Includes unter `templates/admin/`
(`_status.html`, `_zonen.html`, `_layouts.html`, …). Die Karte
„Einstellungen" bleibt in `admin.html` selbst — zwei Tests lesen sie dort.

## Regeln, die weiter gelten

- **Ohne Messung wird nichts erfunden.** Layouts ändern daran nichts: keine
  Zone, kein Layout, kein Bild.
- **Rückwärtskompatibel.** Eine Station von vor 3.0 spielt nach dem Update
  exakt dasselbe: je Zone ein Vollbild-Layout mit den alten Listen. Alte
  Anzeigeseiten, alte Manager und alte Sicherungen werden verstanden.
- **Deutsch ist die Quelle**, im Code wie in der Oberfläche; Englisch kommt
  aus dem Wörterbuch. Neue Texte brauchen einen Eintrag — der Test findet
  fehlende.
- **Zwei Politiken:** `layouts.pruefe_*` lehnt ab und nennt das Feld
  (Schreibweg), `layouts.heile_*` repariert und sagt es im Log (Ladeweg).
- **Eine Version:** die Datei `VERSION`. `/api/identity`, `/api/status` und
  `python3 main.py --version` lesen sie.

### Ereignisse in der Verwaltung

`static/app.js` haelt die EINE SSE-Verbindung je Tab und reicht die Ereignisse als `CustomEvent` am `document` weiter: `lz-status` (mit `detail` = Status), `lz-config` und `lz-layouts`. Module unter `static/module/*.js` hoeren darauf und oeffnen KEINE eigene `EventSource` — drei Verbindungen je Tab erschoepften mit zwei Tabs das Verbindungslimit des Browsers.

# Monitoring, Proof-of-Play, Benachrichtigung

Was die Anzeige gerade tut, was sie gespielt hat — und wer es erfährt, wenn
etwas nicht stimmt. Seit 3.0, Karte **Monitor** in der Verwaltung.

## Warum

Der Kern wusste bis 3.0, welche Zone er spielt. Ob irgendwo ein Schirm sie
auch **zeigte**, wusste niemand: Chromium abgestürzt, HDMI-Kabel raus, Tablet
im Foyer ausgegangen — für `/api/status` war alles in Ordnung. Und wer eine
Ausstellung im Auftrag bespielt, konnte nicht sagen, wie oft der Clip des
Sponsors gelaufen ist. Die kommerziellen Systeme nennen das Monitoring und
Proof-of-Play und verkaufen es als Zusatzstufe.

## Puls: was die Anzeige gerade spielt

Jede Anzeigeseite (`/display`) meldet sich alle **10 s** mit `POST
/api/anzeige/puls` (Skript `static/anzeige/puls.js`): eine zufällige Kennung je
Browser-Tab, Layout, Zone, was in **jeder Region** läuft, dazu die letzten
JavaScript-Fehler der Seite.

- `GET /api/anzeige/system` liefert die Systemwerte (Temperatur, Last, RAM, Platte).
- `GET /api/anzeige` listet alle Anzeigen mit `online` (Puls jünger als 30 s),
  `alter_s`, `seit`, den Regionen und dem Zeitpunkt des letzten Screenshots;
  dazu die **Systemwerte** des Kerns (unten).
- `/api/status` trägt `anzeige: {anzahl, online, alter_s}`.
- Die **Vorschau** im Editor meldet sich mit `vorschau: true` und zählt nicht
  als Schirm — sie steht in der Liste, aber nicht in der Zusammenfassung.
- Nach 24 h ohne Puls fällt eine Anzeige aus der Liste. Alles liegt im
  Speicher des Kerns: nach einem Neustart ist die Liste leer, bis sich die
  erste Anzeige meldet — und das ist richtig so.

**Zustandsprüfung.** Ist die Steuerung aktiv und die Öffnungszeit offen, aber
seit 60 s kein Puls da (oder noch nie), meldet `/api/health` eine **Warnung**
„Keine Anzeige verbunden". Nachts und bei gestoppter Steuerung nicht — dann
soll gar nichts zu sehen sein.

## Screenshot auf Abruf

**Screenshot jetzt** in der Karte ruft `POST /api/anzeige/screenshot/anfordern`:

1. Läuft auf dem Pi eine grafische Sitzung mit `grim` (Wayland) oder `scrot`
   (X11), nimmt der Kern den **echten Bildschirm** auf. Dann stimmt auch, was
   in einem Webseiten-Rahmen steht.
2. Sonst geht der Befehl `screenshot` an alle Anzeigeseiten (`/api/events`).
   Die Seite zeichnet ihre Bühne in ein Canvas — Bilder und das laufende
   Videobild echt, Webseiten und Widgets als beschriftete Fläche, weil ein
   fremdes iframe nicht auslesbar ist — und schickt ein JPEG (höchstens
   1280 px breit, 2 MB) an `POST /api/anzeige/screenshot`. Der Kern wartet bis
   4 s auf ein frisches Bild.

`GET /api/anzeige/screenshot[?kennung=…]` liefert das jüngste Bild (Kopf
`X-LZ-Zeit`), 404, wenn noch keines da ist; 409, wenn keine Anzeige zuhört;
504, wenn keine rechtzeitig liefert.

## Systemwerte

`gesundheit.systemwerte()` liest, was das Gerät hergibt — und **erfindet
nichts**: auf einem Mac gibt es kein `/sys/class/thermal`, dann steht dort
`None`, und die Verwaltung zeigt die Kachel nicht.

| Wert | Quelle | Befund |
|---|---|---|
| CPU-Temperatur | `/sys/class/thermal/thermal_zone*/temp` (die höchste) | ≥ 70 °C Warnung, ≥ 80 °C Fehler (der Pi drosselt, das Bild ruckelt) |
| Last (1 min) und Kerne | `os.getloadavg()` | Last über 2 × Kerne: Warnung |
| Arbeitsspeicher | `/proc/meminfo` (`MemAvailable`) | unter 10 % frei: Warnung |
| Platte | `shutil.disk_usage` | wie bisher (200 MB Fehler, 1 GB Warnung) |

## Proof-of-Play: was wann gelaufen ist

Die Anzeigeseite hört jeden **Start eines Eintrags** (`lz-eintrag`) und
schickt die Starts gesammelt alle 30 s an `POST /api/wiedergabe`. Die Wahrheit
liegt also im Browser, der gespielt hat — nicht im Kern, der geglaubt hat zu
spielen. In der Vorschau wird nichts gemeldet.

Der Kern schreibt in `wiedergabe.sqlite` neben `config.json` (SQLite aus der
Standardbibliothek): Zeit, Region, Typ, Datei oder URL, Layout, Zone, Kennung
der Anzeige. **Nichts über Personen.**

- **Deduplizierung** über (Kennung, Zeit, Region): ein Browser, der nach einem
  Netzabriss seinen Puffer erneut schickt, zählt nichts doppelt.
- **Aufbewahrung**: `wiedergabe_aufbewahrung_tage` in der Konfiguration
  (Vorgabe 90, 1..3650). Aufgeräumt wird beim Eintragen.
- `GET /api/wiedergabe/zusammenfassung?von=&bis=&gruppe=datei|tag|stunde|layout|zone`
  zählt Starts je Gruppe; `von`/`bis` sind Kalendertage, `bis` schließt den
  Tag ein.
- `GET /api/wiedergabe.csv?von=&bis=` — jeder Start eine Zeile, Trennzeichen
  `;`, Spalten `zeit;typ;name;region;layout;zone;anzeige`.

## Benachrichtigung: die Station meldet sich

Die Station schickt eine Nachricht, wenn sich etwas **ändert** — nicht alle
30 s „immer noch kaputt". Ein Melder, der dauernd schreibt, wird stummgeschaltet
und meldet dann auch den echten Ausfall nicht mehr.

| Ereignis | Wann |
|---|---|
| `gesundheit_fehler` | die Gesamtstufe der Zustandsprüfung wird `fehler` |
| `gesundheit_ok` | sie ist es nicht mehr |
| `anzeige_verloren` | keine Anzeige mehr online (Puls älter als 30 s) |
| `anzeige_zurueck` | wieder eine Anzeige online |
| `offline_ende` | die Öffnungszeit beginnt — ein tägliches Lebenszeichen |

Der erste Durchlauf nach dem Start merkt sich nur die Lage und meldet nichts;
sonst käme bei jedem Neustart „Anzeige wieder da".

**Ziele.** `ntfy` (Push aufs Handy ohne Konto: App installieren, Topic wählen,
Topic hier eintragen — Titel und Priorität kommen mit) oder ein **Webhook**
(JSON `{station, ereignis, titel, text, prioritaet, zeit}` per POST; damit
lässt sich Node-RED, Home Assistant oder ein Chat anbinden).

Einstellungen in der Karte oder per `PUT /api/benachrichtigung`
`{aktiv, ziel_typ: ntfy|webhook, url, topic, ereignisse: [...]}`; **Probenachricht
senden** (`POST /api/benachrichtigung/test`) prüft den Weg vor dem Speichern.
Der Wächter läuft als Nebenfaden nur, wenn der Versand an ist; ein Netzfehler
wird geloggt, nie geworfen. Zeitlimit 5 s.

## Auf einen Blick

```
Anzeigeseite ──10 s──▶ POST /api/anzeige/puls ──▶ Liste, /api/status, Zustandsprüfung
             ──30 s──▶ POST /api/wiedergabe   ──▶ wiedergabe.sqlite ──▶ Zusammenfassung, CSV
             ◀─Befehl─ screenshot ◀── POST /api/anzeige/screenshot/anfordern
             ──JPEG──▶ POST /api/anzeige/screenshot ──▶ GET /api/anzeige/screenshot
Wächter (30 s) ──▶ Übergang? ──▶ ntfy / Webhook
```

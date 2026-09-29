# Wochenprogramm und Sofortmeldung

Der [Wochenplan](zeitsteuerung.md) sagt, **ob** die Station wach ist. Das
Wochenprogramm sagt, **was** eine Zone wann spielt: morgens das Tagesprogramm,
mittags die Speisekarte, abends der Film — ohne dass jemand vorbeikommt und
umschaltet. Die Sofortmeldung legt eine Zeile über alles, sofort und auf jedem
Schirm dieser Station.

## Standardverhalten: unverändert

Ohne Eintrag spielt jede Zone ihr Layout aus der Zonen-Übersicht — exakt wie
vor 3.0. Das Programm ist in der Vorgabe leer, die Sofortmeldung aus.

## Einrichten

Im Admin unter **Wochenprogramm**:

1. Oben die **Zone** wählen, deren Kalender angezeigt wird (ein Eintrag kann
   für alle Zonen gelten oder nur für einige).
2. Im Kalender **über die Stunden ziehen** (Maus oder Finger). Es öffnet sich
   ein Eintrag mit den Vorgaben, die in den meisten Fällen stimmen: alle
   Zonen, Priorität 5, aktiv. Name eingeben, Layout wählen, speichern.
3. Auf einen Block tippen, um ihn zu bearbeiten oder zu löschen.

**Was läuft jetzt?** zeigt je Zone das Layout, das gerade gespielt wird, und
woher es kommt: aus dem Programm, von einem Ausnahmetag oder aus der Zone.

### Ein Eintrag

| Feld | Bedeutung |
|---|---|
| Name | Nur für die Übersicht |
| Layout | Welches Layout in diesem Fenster läuft ([Architektur 3.0](architektur-v3.md)) |
| Tage | Wochentage, an denen das Fenster gilt |
| Von / Bis | Uhrzeit. Ein Ende **vor** dem Beginn läuft über Mitternacht (20:00 bis 02:00); Ende **00:00** heißt Tagesende |
| Priorität | 1 (niedrig) bis 9 (hoch). Überschneiden sich Einträge, gewinnt die höhere; bei Gleichstand der, der später begonnen hat |
| Zonen | Keine Auswahl = alle Zonen. Sonst nur die gewählten |
| Gültig ab / bis | Kalendertage; leer = immer. Für eine Aktion, die nur im Dezember läuft |
| Aktiv | Ein ausgeschalteter Eintrag bleibt stehen (gestrichelt), zählt aber nicht |

### Die Regel, in dieser Reihenfolge

1. Ein **Ausnahmetag** gewinnt vor allem anderen. Sein Layout gilt für alle
   Zonen den ganzen Tag. „Standard der Zone" als Layout heißt: an diesem Tag
   gilt **kein** Programm — die Zonen spielen ihr eigenes Layout.
2. Von den **Einträgen**, die jetzt passen, gewinnt die höchste Priorität; bei
   Gleichstand der spätere Beginn. Wer eine Sonderschicht über ein
   Dauerprogramm legt, soll sie sehen, ohne die Priorität anzufassen.
3. Passt nichts: das Layout der Zone.

Ein Eintrag, dessen Layout es nicht mehr gibt, zählt nicht — der Schirm bleibt
nicht schwarz, er spielt die Zone. Beim Speichern lehnt die Station ein
unbekanntes Layout ab, damit es gar nicht so weit kommt.

### Über Mitternacht

Wie im Wochenplan: das Fenster `20:00`–`02:00` gehört zum Eintrag des Tages,
an dem es beginnt. Wer es am Samstag einträgt, ist Sonntag um 01:00 im
Programm — im Kalender steht der Teil nach Mitternacht in der Sonntagsspalte
mit einem `↳`.

## Sofortmeldung

Im Admin unter **Sofortmeldung**: Text (und eine zweite Zeile), Hintergrund-
und Schriftfarbe, Dauer, optional ein Signalton. **Jetzt einblenden** zeigt sie
auf jedem Schirm dieser Station — sofort, auch über einem gerade
eingeblendeten Layout. **Beenden** nimmt sie weg. Drei Schnellvorlagen
(Räumung, Hinweis, Pause) füllen die Felder.

- Die Meldung steht in der Konfiguration. Lädt eine Anzeige neu, zeigt sie
  sie wieder — bis sie beendet wird oder die Dauer abläuft.
- Nach einem **Neustart der Station** ist eine abgelaufene Meldung aus; eine
  ohne Dauer bleibt.
- Von außen: als Aktion eines [Auslösers](ausloeser.md), also auch per
  Webhook aus Home Assistant oder Node-RED.

## Schnittstelle

| Method | Path | Beschreibung |
|---|---|---|
| GET / PUT | `/api/programm` | Das ganze Programm `{eintraege, ausnahmen}`; PUT **lehnt ab** und nennt das Feld |
| GET | `/api/programm/jetzt` | Je Zone: `layout_id`, `layout_name`, `quelle` (`programm` · `ausnahme` · `zone`), `eintrag` |
| GET | `/api/programm/vorschau` | `?von=&bis=&zone=&raster=` — die Auflösung als Abschnitte (Kalenderansicht) |
| GET | `/api/meldung` | Die Sofortmeldung, `aktiv` schon gegen `bis` gerechnet |
| POST | `/api/meldung` | `{text, untertext?, farbe?, textfarbe?, dauer_s?, ton?}` — setzen; `dauer_s` rechnet `bis` aus |
| DELETE | `/api/meldung` | Beenden |

Ein Eintrag:

```json
{ "id": "speisekarte", "name": "Speisekarte mittags", "layout_id": "menue",
  "zonen": [], "tage": ["mo","di","mi","do","fr"], "von": "11:30", "bis": "14:00",
  "prioritaet": 5, "gueltig_von": null, "gueltig_bis": null, "aktiv": true }
```

Eine Ausnahme: `{ "datum": "2026-12-25", "layout_id": "weihnachten", "name": "1. Weihnachtstag" }`.

## Unter der Haube

`programm.py` ist rein — keine Uhr, keine Platte. `aufloesen(programm, zone,
jetzt)` beantwortet die Frage, und `Controller.layout_fuer_zone` fragt es
über `layout_regeln` ([Architektur 3.0](architektur-v3.md#erweiterungspunkte)).
Der Ladeweg heilt **eintragsweise**: ein Eintrag mit `25:00` fliegt raus und
wird im Log genannt, die anderen bleiben.

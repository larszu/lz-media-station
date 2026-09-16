# Besucher-Statistik

Die Zahlen entstanden ohnehin — der Sensor weiß jede Zehntelsekunde, ob jemand
in der Nah-Zone ist — und wurden bisher weggeworfen. Für den Betreiber einer
Ausstellung sind genau sie der Nachweis, dass die Installation wirkt.

## Was erfasst wird — und was nicht

Erfasst wird ein **Besuch**: ein Zeitraum, in dem irgendjemand in der Nah-Zone
war. Gespeichert werden Datum, Stunde des Beginns und Dauer.

**Nicht** erfasst wird irgendetwas über einzelne Personen: kein Bild, kein
Merkmal, keine Wiedererkennung. Das gilt auch für die Kamera-Quelle — sie
liefert an die Station nur eine Entfernung, keine Identität.

Besuche **kürzer als 1 Sekunde** zählen nicht. Ohne diese Schwelle zählt jeder
Durchgänger mit und die Zahlen werden wertlos.

## Im Admin

Der Abschnitt **Besucher-Statistik** zeigt:

- Besuche heute, durchschnittliche Verweildauer, Besuche gesamt
- den heutigen Tagesverlauf als Balken je Stunde
- die letzten 14 Tage als Liste

**CSV herunterladen** gibt die Tageswerte heraus (Semikolon getrennt,
Komma als Dezimalzeichen — eine deutsche Excel-Installation öffnet die Datei
damit ohne Import-Dialog):

```
Datum;Besuche;Gesamtdauer_s;Durchschnitt_s
2026-09-14;12;340,5;28,4
```

**Zähler zurücksetzen** löscht alle erfassten Zahlen — gedacht für den Umzug in
die nächste Ausstellung. Das ist ein eigener Endpunkt und bewusst **nicht** Teil
des Einstellungen-Speicherns: Messwerte sollen nicht als Nebenwirkung
verschwinden können.

## Betrieb

| Thema | Verhalten |
|---|---|
| Speicherort | `statistik.json` neben der `config.json` (nicht im Git) |
| Neustart | Die Zahlen überleben Neustart und Stromausfall — sie werden beim Start geladen |
| Schreiben | Nur wenn ein Besuch **endet**, nicht zehnmal pro Sekunde. Sonst wäre das der sichere Weg, eine SD-Karte in einer Saison durchzuschreiben |
| Absturzsicherheit | Atomar geschrieben (erst daneben, dann umbenennen). Die Station wird per Stecker ausgeschaltet; eine halb geschriebene Datei darf den Start nicht verhindern |
| Kaputte Datei | Wird gemeldet und übersprungen, die Zählung fängt neu an — kein Startabbruch |
| Wachstum | Es werden die letzten **90 Tage** aufgehoben. Ohne Grenze wüchse die Datei auf einem Gerät, das jahrelang steht, unbegrenzt |

## Wo es im Code steht

| Teil | Ort |
|---|---|
| Zählung und Auswertung (rein, ohne Uhr) | `statistik.py` |
| Persistenz | `statistik.laden` / `statistik.speichern` (getrennt von der Rechnung) |
| Fortschreiben | `main.Controller._zaehle`, einmal je Schleifendurchlauf |
| Endpunkte | `/api/statistik`, `/api/statistik.csv`, `POST /api/statistik/reset` |

### Warum ein Eingang statt `beginnt`/`endet`

`Statistik.verfolge(ist_nah, jetzt)` erkennt die Wechsel **selbst**. Ein Paar
aus `besuch_beginnt`/`besuch_endet` an den Zustandsübergängen der
Zustandsmaschine wäre naheliegend und falsch: jeder neue Pfad — etwa der
Wochenplan, der mitten im Besuch zumacht, oder das Stoppen am Tagesende — hätte
vergessen können, den offenen Besuch zu beenden. Der wäre dann still verloren
gegangen. Mit einem Eingang kann das nicht passieren; `abschliessen()` deckt
zusätzlich Stopp und Herunterfahren ab.

# Gleichtakt mehrerer Stationen

Eine Videowand aus drei Schirmen, oder ein Exponat, bei dem ein Sensor mehrere
Aufbauten auslösen soll. Bisher brauchte jeder Schirm eine eigene Station **mit
eigenem Sensor** — und drei Sensoren nebeneinander schalten nie gleichzeitig.

## Einrichten

Auf der **folgenden** Station im Admin unter *Systemeinstellungen →
Gleichtakt*:

1. „Folgt einer anderen Station" wählen.
2. IP oder Hostname des Taktgebers eintragen, ggf. den Port.
3. Speichern und die Station **neu starten**.

Auf dem **Taktgeber** ist nichts einzustellen.

## Es gibt keine „Master"-Rolle

Jede Station beantwortet `/api/sync` mit ihrer aktuellen Zone — damit ist jede
Station potenziell ein Taktgeber, ohne dass man das irgendwo einstellt.

Eine deklarative „master"-Rolle wäre Zierde: sie würde nichts bewirken, weil
ohnehin jede Station antwortet. Konfiguration, die nichts tut, ist schlimmer
als keine — irgendwann verlässt sich jemand darauf. Deshalb kennt
`sync_rolle` nur `aus` und `follower`.

## Was synchron ist — und was nicht

**Synchron ist die ZONE**, also welche Szene läuft. Bei einem Zonenwechsel
starten die Follower ihre Szene neu, so wie sie es auch mit eigenem Sensor
täten.

**Nicht** synchronisiert wird die Position *innerhalb* eines Videos. Dafür
bräuchte es eine gemeinsame Zeitbasis und ein Nachregeln der Abspielrate; das
ist ein anderes Projekt. Für eine Wand, auf der jeder Schirm **seinen eigenen**
Inhalt zeigt (der übliche Fall), spielt das keine Rolle.

## Verhalten im Betrieb

| Situation | Verhalten |
|---|---|
| Taktgeber wechselt die Zone | Follower zieht innerhalb von ~0,4 s nach |
| Kontakt reißt ab | Nach 3 s fällt der Follower auf **Fern** zurück, und die Zustandsprüfung meldet einen **Fehler** |
| Taktgeber hat Betriebsruhe (Wochenplan) | Der Follower übernimmt sie |
| Follower hat einen eigenen Zeitplan | Gilt **zusätzlich** — wer eine Station früher schließen will, kann das |

**Keine Hysterese beim Follower.** Der Taktgeber hat sie schon angewandt; ein
zweites Mal zu warten hieße, dass die Wand sichtbar nacheinander umschaltet.

**Kein Kontakt heißt kein Wert** — dieselbe Regel wie beim Sensor. Der Follower
behauptet die zuletzt empfangene Zone nicht weiter: ein abgerissenes Netzkabel
darf nicht aussehen wie ein Besucher, der sich nicht vom Fleck rührt.

**Der eigene Sensor bleibt aus.** Ein Follower wertet ihn nicht aus, also wird
er auch nicht gestartet — kein Grund, GPIO oder eine Kamera zu belegen. Auf
einem Rechner, der nur einen zweiten Schirm bespielt, ist oft gar keine
Hardware angeschlossen. Entsprechend meldet die Zustandsprüfung dort **nicht**
den fehlenden Sensor (das wäre ein Dauerfehler ohne Ursache), sondern den
fehlenden Kontakt zum Taktgeber.

## Voraussetzung im Netz

Die Stationen müssen sich gegenseitig erreichen. In Gastnetzen mit
Client-Isolation geht das nicht — dort hilft ein eigener Switch/Router für die
Installation oder Tailscale (siehe README).

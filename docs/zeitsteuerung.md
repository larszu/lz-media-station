# Zeitsteuerung (Öffnungszeiten)

Die Station steht unbeaufsichtigt in einer Ausstellung und lief bisher rund um
die Uhr: nachts spielt sie vor einem leeren Raum, der Ton läuft, das Panel
altert. Mit einem Wochenplan spielt sie nur, wenn jemand da sein kann.

**Außerhalb der Öffnungszeit gilt:** Schirm schwarz, Ton aus, es wird **nicht
ausgelöst** — auch dann nicht, wenn jemand direkt vor dem Sensor steht.

## Standardverhalten: unverändert

`zeitplan.aktiv` ist in der Vorgabe **`false`**. Eine bestehende Installation
verhält sich also exakt wie vorher, bis jemand die Zeitsteuerung einschaltet.
Auch ein **unbrauchbarer** Zeitplan sperrt nie: `ist_offen` gibt im Zweifel
„offen" zurück. Eine verhunzte Konfiguration darf eine Ausstellung nicht stumm
schalten.

## Einrichten

Im Admin unter **Zeitsteuerung**:

1. **Zeitsteuerung aktiv** anhaken.
2. Pro Wochentag: Haken = der Tag ist offen, dazu **von** und **bis**.
3. Speichern.

Ein Tag ohne Haken ist ganztags zu.

### Uhrzeiten

| Eingabe | Bedeutung |
|---|---|
| `09:00` bis `18:00` | offen von 9 bis 18 Uhr; **18:00 ist bereits zu** (das Ende ist nicht die letzte offene Minute) |
| `00:00` bis `00:00` | ganztags offen (Ende `00:00` = Mitternacht/Tagesende) |
| `20:00` bis `02:00` | **über Mitternacht**: offen ab 20 Uhr bis 2 Uhr in der Nacht |

Das Ende `00:00` wird intern als `24:00` geführt. Der Grund: `23:59` hätte eine
Minute Lücke, und genau die fällt irgendwann als kurzer Aussetzer um
Mitternacht auf.

### Über Mitternacht

Ein Fenster, dessen Ende **vor** dem Beginn liegt, läuft in den nächsten Tag.
Der Teil nach Mitternacht gehört zum Eintrag des **Vortags** — wer am Montag
`20:00–02:00` einträgt, ist Dienstag um 01:00 Uhr offen, ohne dass am Dienstag
etwas eingetragen sein muss.

## Fernseher mitabschalten (HDMI-CEC, optional)

Schwarzer Schirm heißt nicht „Fernseher aus": das Gerät läuft weiter. Mit
**HDMI-CEC** lässt es sich über dasselbe Kabel mit abschalten. Im Admin die
Option anhaken; auf dem Pi muss `cec-client` installiert sein:

```bash
sudo apt install cec-utils
```

Fehlt es, passiert **nichts außer einer Zeile im Log** — die Wiedergabe hängt
nie an CEC. CEC ist zwischen Herstellern notorisch unzuverlässig; wenn der
Fernseher nicht reagiert, ist das keine Störung der Station.

## Wo es im Code steht

| Teil | Ort |
|---|---|
| Rechnung (rein, ohne Uhr) | `zeitplan.py` — `ist_offen`, `pruefe_zeitplan`, `heile_zeitplan` |
| Auslöse-Sperre | `main.Controller._control_loop` (Plan steht **vor** dem Sensor) |
| Zweite Absicherung | `main.Controller.get_scene` gibt außerhalb der Zeit **keine Zone** heraus |
| Schwarzer Schirm | `static/display.js` — `scene.geschlossen` wird vor allem anderen geprüft |
| CEC | `tv_cec.py` (wirft nie) |

Die Sperre sitzt **an zwei Stellen**, und das ist Absicht: die Steuerschleife
löst nicht aus, und `get_scene()` gibt nichts heraus. Damit bleibt der Schirm
auch dann schwarz, wenn der Controller gerade gestoppt ist — sonst stünde
nachts die zuletzt gespielte Szene auf dem Schirm.

---

# Mehrstufige Zonen

Bis 2026-09-16 gab es genau zwei Zonen: **Nah** und **Fern**. Das Herantreten
war damit ein Schalter. Mit einer dritten Stufe wird es eine Dramaturgie:

```
  fern  ────────>  mitte  ────────>  nah
        > 2,5 m          ≤ 2,5 m        ≤ 1,0 m
```

Im Admin unter **Einstellungen → Zonen** auf „Drei Stufen" umstellen; die
Schwelle der Mitte erscheint dann als zweiter Regler, und die Zonen-Übersicht
zeigt eine dritte Karte.

**Die Vorgabe bleibt bei zwei Stufen** — eine bestehende Installation verhält
sich exakt wie vorher. Die Mitte steht zwar auch dann in der Konfiguration
(damit eine Zuweisung beim Hin- und Herschalten nicht verloren geht), zählt
aber nirgends mit: nicht in der Zustandsmaschine und nicht in der
Zustandsprüfung. Sonst meldete jede gewöhnliche Station dauerhaft „Zone Mitte
hat keine Medien".

## Die Schwellen dürfen sich nicht überholen

`threshold_mid_m` muss größer sein als `threshold_m`, sonst gibt es die Mitte
rechnerisch nicht und die Station spränge von fern direkt auf nah. Wieder eine
Bedingung, die **kein Feld für sich** sieht: `threshold_m: 3.0` ist gültig,
`threshold_mid_m: 2.0` ist gültig — zusammen sind sie es nicht. Geprüft wird
deshalb gegen den zusammengeführten Stand, sonst rutscht es über zwei getrennte
Anfragen durch.

## Eine Maschine statt einer Falltabelle

Vorher standen vier Fälle einzeln da: `far`, `near`, `pending_near`,
`pending_far`. Mit einer dritten Stufe wären daraus neun geworden — bei
gleichbleibender Regel.

Jetzt gibt es **eine** Regel:

1. Das Ziel ergibt sich aus dem Abstand (`zone_fuer`).
2. Weicht es von der bestätigten Zone ab, läuft eine Frist.
3. War dasselbe Ziel `delay_s` lang stabil, wird es die neue Zone.

Der Zustandstext (`far`, `pending_near`, …), den `/api/status` seit jeher
nennt, wird daraus **abgeleitet** statt gespeichert: „welche Zone gilt",
„wohin ist sie unterwegs" und „was spielt gerade" sind drei Fragen an einen
Zustand. Als drei Felder wären sie irgendwann uneinig.

**Während der Hysterese spielt die alte Zone weiter.** Der Kandidat schaltet
die Wiedergabe nicht um — sonst flackert genau das, was die Verzögerung
verhindern soll.

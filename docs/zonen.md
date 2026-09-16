# Zonen und Wiedergabe

Welche Szene wann läuft — und wie sie abgespielt wird.

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

---

# Playlist-Optionen je Zone

Jede Zone (Nah / Fern) hat eigene Wiedergabe-Optionen, direkt in der
Zonen-Übersicht des Admin:

| Option | Wirkung |
|---|---|
| **Zufällige Reihenfolge** (`shuffle`) | Videos, Bilder und Ton werden gemischt statt in Listenreihenfolge gespielt |
| **Einmal abspielen** (`einmal`) | Am letzten Element stehen bleiben statt endlos zu wiederholen — der Unterschied zwischen einer Präsentation und einer Endlosschleife |
| **Reihenfolge** (▲ ▼) | Die Liste umsortieren. Bewusst Pfeile statt Drag-and-Drop: die Verwaltung wird vom **Handy** bedient, und Ziehen mit dem Daumen ist dort der unzuverlässigste Weg |
| **Standzeit je Bild** | Sekundenfeld neben jedem zugewiesenen Bild. Leer = der allgemeine Bildwechsel. Ein Titelbild darf 3 s stehen, eine Detailtafel 20 s |

Die Optionen wirken **sofort** (kein Speichern-Knopf): sie gehören zur
Zonen-Übersicht, nicht zum Einstellungen-Formular.

## Nebenbefund: mehrteilige Playlists spielten nur das erste Element

Beim Einbau fiel ein bestehender Defekt auf. Die Anzeigeseite entschied mit

```js
if (currentVideoFile !== videos[0]) { ... neu starten ... }
```

ob die Wiedergabe neu aufzusetzen ist. Sobald das erste Video endete und auf
das zweite weiterschaltete, war `currentVideoFile` nicht mehr `videos[0]` —
der nächste Poll (500 ms später) fand den Vergleich wieder wahr und **sprang
zurück auf das erste Video**. Eine Playlist mit mehreren Videos spielte
faktisch nur das erste, immer wieder. Für Audio galt dasselbe.

Ersetzt durch eine **Kennung der laufenden Liste** (Dateien + Shuffle-Schalter):
neu aufgesetzt wird nur, wenn sich die Liste wirklich ändert.

## Warum eine Timeout-Kette statt `setInterval`

Die Diashow lief mit einem festen Intervall. Damit haben alle Bilder
zwangsläufig dieselbe Standzeit — `bildzeiten` wäre wirkungslos gewesen. Sie
läuft jetzt als Kette aus `setTimeout`, bei der jedes Bild seine eigene Dauer
bestimmt.

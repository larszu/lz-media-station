# Mehrsprachigkeit (Untertitel)

In einer Ausstellung ist Mehrsprachigkeit fast immer ein Thema. Umgesetzt als
**Untertitelspuren je Video** mit Sprachknöpfen auf der Anzeige.

## Einrichten

1. **Sprachen** im Admin unter *Untertitel & Sprachen* eintragen, durch Komma
   getrennt: `de, en`. Die Reihenfolge bestimmt die Reihenfolge der Knöpfe —
   und die **erste ist die Vorgabesprache**.
2. **`.vtt`-Dateien hochladen** (Knopf im selben Abschnitt).
3. Je Video und Sprache die Spur im Auswahlfeld zuordnen, dann speichern.

Ab **zwei** Sprachen erscheinen unten rechts auf der Anzeige Knöpfe
(`DE` / `EN`). Eine einzige Sprache ist keine Wahl — dann bleiben sie weg.

## Nur WebVTT

Akzeptiert wird ausschließlich **`.vtt`**. Das ist das einzige Format, das ein
Browser ohne Umwege abspielt. Eine `.srt` anzunehmen und sie dann stumm nicht
anzuzeigen wäre schlimmer, als sie abzulehnen.

Umwandeln geht mit ffmpeg:

```bash
ffmpeg -i film-de.srt film-de.vtt
```

## Verhalten

| Situation | Verhalten |
|---|---|
| Keine Sprachen konfiguriert | Keine Knöpfe, keine Spuren — wie bisher |
| Eine Sprache | Spur wird gezeigt, aber keine Umschaltung |
| Video ohne Spur für die gewählte Sprache | Video läuft ohne Untertitel |
| Sprache wird umgeschaltet | Wirkt sofort auf das laufende Video |

Untertitel sind eine **eigene Medienart** und lassen sich **keiner Zone**
zuweisen: sie hängen an einem *Video*, nicht an einer Entfernung. Stünden sie
in den Zonen-Medienarten, ließe sich eine `.vtt` einer Zone zuordnen und
niemand wüsste, was das bedeuten soll.

## Zwei Details, die im Betrieb zählen

**Alte Spuren werden entfernt.** Die Anzeige benutzt zwei Video-Elemente im
Wechsel (für die Überblendung). Übrig gebliebene `<track>` eines anderen Films
würden sonst mitlaufen.

**Die Spur wird erst nach `canplay` gewählt.** Vorher hängen die `<track>` zwar
am Element, aber `textTracks` ist noch leer — die Auswahl liefe ins Leere.

## Was das *nicht* ist

Es ist keine Umschaltung der **Bedienoberfläche** und kein getrennter
Medienbestand je Sprache. Wer pro Sprache eigene Videos zeigen will, legt sie
als eigene Dateien an und weist sie zu; der Sprachknopf schaltet Untertitel,
nicht Filme.

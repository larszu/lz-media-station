# Betrieb: Medien-Check und Sicherung

## Medien-Check beim Upload

Der häufigste Ausfallgrund einer Medienstation ist kein Defekt, sondern eine
**Datei**: ein 4K-Video mit 60 fps sieht auf dem Notebook großartig aus und
ruckelt auf dem Pi zur Diashow. Bemerkt wurde das bisher beim Aufbau — oder in
der Ausstellung, denn der Upload war stumm: jede Datei mit erlaubter Endung
galt als gut.

Nach dem Upload eines Videos prüft die Station und meldet in der
Medienbibliothek:

| Befund | Schwelle |
|---|---|
| Auflösung zu hoch | über 1920×1080 |
| Codec ohne Hardware-Dekodierung | alles außer H.264 |
| Bildrate zu hoch | über 31 fps |
| Bitrate sehr hoch | über 20 Mbit/s |

**Es sind Hinweise, keine Sperren.** Wer weiß, was er tut (ein Pi 5 mit einem
kurzen 4K-Clip), soll nicht vom Werkzeug ausgebremst werden — die Datei ist
hochgeladen und zuweisbar.

Gemessen wird mit `ffprobe` (Teil von ffmpeg). Fehlt es, gibt es **keine
Warnung und keinen Fehler**, sondern schlicht keine Prüfung — ein fehlendes
Hilfsprogramm darf keinen Upload verhindern. „Nicht geprüft" ist dabei
ausdrücklich keine Entwarnung und wird auch nicht als solche gemeldet.

```bash
sudo apt install ffmpeg     # falls die Prüfung genutzt werden soll
```

## Sicherung und Wiederherstellung

Eine Station wird geklont (die nächste Ausstellung, derselbe Aufbau) oder nach
einem SD-Karten-Defekt wiederhergestellt. Bisher hieß das: die `config.json`
von Hand über SSH kopieren.

Im Admin unter **Sicherung**:

- **Konfiguration sichern** lädt alle Einstellungen als JSON herunter (Zonen
  inkl. Playlist-Optionen, Zeitplan, Sensor, Lautstärken, Netzwerk-Anzeige-IP).
- **Sicherung einspielen** ersetzt die laufende Konfiguration vollständig.

**Medien-Dateien sind nicht enthalten** — nur die Konfiguration. Die Videos und
Bilder gehen weiterhin über den Upload (oder den Bulk-Upload des Station
Managers).

### Wiederherstellen heilt, statt abzulehnen

Anders als `POST /api/config`, das einen falschen Wert mit Feldnamen
zurückweist, wird beim Einspielen **repariert**: unbrauchbare Werte fallen auf
die Vorgabe zurück, fehlende Felder werden ergänzt, unbekannte Felder wandern
nicht ein.

Der Grund ist der Ernstfall. Eine Sicherung kann aus einer älteren Fassung
stammen, in der es Felder noch nicht gab oder anders hießen. Eine
Wiederherstellung, die an einem einzigen veralteten Feld scheitert, ist genau
dann nutzlos, wenn man sie braucht: Karte tot, Ausstellung öffnet in einer
Stunde.

Sensor- und Port-Änderungen wirken erst nach einem **Neustart** der Station —
die Abstandsquelle wird beim Programmstart gebaut. Die Antwort sagt das auch,
sonst sucht jemand den Fehler in der Verdrahtung.

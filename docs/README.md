# Dokumentation

Die Themen, die mehr als einen Absatz brauchen. Das [README](../README.md) gibt
den Überblick; hier steht das Wie und — wichtiger — das **Warum**.

| Dokument | Worum es geht |
|---|---|
| [Abstandsquellen](sensoren.md) | Ultraschall, Kamera und Taster einrichten; Kalibrierung der Kamera; **Vergleichsmatrix** aller gängigen Sensortypen mit Empfehlung je Anwendungsfall |
| [Zonen und Wiedergabe](zonen.md) | Zwei oder drei Stufen (Nah/Mitte/Fern); Shuffle, „einmal abspielen", Reihenfolge, Standzeit je Bild |
| [Zeitsteuerung](zeitsteuerung.md) | Wochenplan mit Öffnungszeiten (auch über Mitternacht), Fernseher per HDMI-CEC mitabschalten |
| [Statistik und Zustand](statistik-und-zustand.md) | Besucherzahlen und Verweildauer, CSV-Export; Zustandsprüfung über `/api/health` |
| [Mehrsprachigkeit](mehrsprachigkeit.md) | Untertitelspuren (WebVTT) je Video, Sprachknöpfe auf der Anzeige |
| [Gleichtakt](gleichtakt.md) | Mehrere Stationen im Takt: eine folgt der Zone einer anderen |
| [Betrieb](betrieb.md) | Medien-Check beim Upload, Sicherung und Wiederherstellung der Konfiguration |
| [Monitoring](monitoring.md) | Puls der Anzeigeseiten („was läuft gerade"), Screenshot auf Abruf, Systemwerte, **Proof-of-Play** (SQLite, CSV), **Benachrichtigung** per ntfy oder Webhook bei Störung, verlorener Anzeige, Beginn der Öffnungszeit |
| [Zugang](zugang.md) | Optionale PIN vor der Verwaltung: Anmeldeseite, Kopf `X-LZ-Pin` für den Manager, freie Meldewege der Anzeige, Ablage außerhalb der Konfiguration |
| [Architektur 3.0](architektur-v3.md) | Layouts und Regionen mit gemischten Playlists, Gültigkeit je Eintrag, Ereignisse (SSE) statt Polling, Befehle an die Anzeige, Vorschau, Erweiterungspunkte für Welle 2 |

## Zwei Dinge, die überall gelten

**Ohne Messung wird nichts erfunden.** Fehlt der Sensor, die Kamera oder der
Kontakt zum Taktgeber, gibt es *keinen* Wert — nicht den letzten, nicht einen
gemittelten und schon gar keinen zufälligen. Die Station löst dann nicht aus
und sagt im Klartext, warum. Ein nicht angeschlossener Sensor darf nicht
aussehen wie ein Besucher, der sich nicht vom Fleck rührt.

**Alle Vorgaben sind rückwärtskompatibel.** Zeitsteuerung aus, zwei Zonen,
keine Sprachen, kein Gleichtakt, Shuffle aus: eine bestehende Installation
verhält sich nach einem Update exakt wie vorher, bis jemand etwas einschaltet.

## Zwei Politiken für Konfiguration

Dieselbe Tabelle, zwei Wege — und das ist Absicht:

- **Schreibweg** (`POST /api/config`) **lehnt ab** und nennt das Feld. Wer
  einen Wert setzt, soll erfahren, dass er nicht angekommen ist.
- **Ladeweg** (Start, und `POST /api/restore`) **repariert** auf die Vorgabe
  und schreibt es ins Log. Ein Gerät ohne Tastatur, das wegen einer verhunzten
  `config.json` nicht hochkommt, ist schlimmer als eines mit einer Vorgabe.

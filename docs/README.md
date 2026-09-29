# Dokumentation

Die Themen, die mehr als einen Absatz brauchen. Das [README](../README.md) gibt
den Überblick; hier steht das Wie und — wichtiger — das **Warum**.

| Dokument | Worum es geht |
|---|---|
| [Handbuch](handbuch.md) | **Für den Betrieb, ohne Technik**: einrichten per Handy, erster Inhalt, Layouts und Vorschau, Wochenprogramm, Sofortmeldung, Auslöser, Überwachung, PIN, Sicherung, Probleme lösen |
| [Änderungen in 3.0](aenderungen-3.0.md) | Alles Neue in 3.0 und wie eine bestehende Station übernommen wird |
| [Abstandsquellen](sensoren.md) | Ultraschall, Kamera und Taster einrichten; Kalibrierung der Kamera; **Vergleichsmatrix** aller gängigen Sensortypen mit Empfehlung je Anwendungsfall |
| [Zonen und Wiedergabe](zonen.md) | Zwei oder drei Stufen (Nah/Mitte/Fern); Shuffle, „einmal abspielen", Reihenfolge, Standzeit je Bild |
| [Zeitsteuerung](zeitsteuerung.md) | Wochenplan mit Öffnungszeiten (auch über Mitternacht), Fernseher per HDMI-CEC mitabschalten |
| [Statistik und Zustand](statistik-und-zustand.md) | Besucherzahlen und Verweildauer, CSV-Export; Zustandsprüfung über `/api/health` |
| [Mehrsprachigkeit](mehrsprachigkeit.md) | Untertitelspuren (WebVTT) je Video, Sprachknöpfe auf der Anzeige |
| [Gleichtakt](gleichtakt.md) | Mehrere Stationen im Takt: eine folgt der Zone einer anderen |
| [Betrieb](betrieb.md) | Medien-Check beim Upload, Sicherung und Wiederherstellung der Konfiguration |
| [Layouts](layouts.md) | Regionen mit gemischten Playlists, Vorlagen, der Editor (ziehen und skalieren mit Maus und Finger, Gültigkeit je Eintrag), Live-Vorschau mit Zeitpunkt, „Was läuft gerade?" |
| [Monitoring](monitoring.md) | Puls der Anzeigeseiten („was läuft gerade"), Screenshot auf Abruf, Systemwerte, **Proof-of-Play** (SQLite, CSV), **Benachrichtigung** per ntfy oder Webhook bei Störung, verlorener Anzeige, Beginn der Öffnungszeit |
| [Zugang](zugang.md) | Optionale PIN vor der Verwaltung: Anmeldeseite, Kopf `X-LZ-Pin` für den Manager, freie Meldewege der Anzeige, Ablage außerhalb der Konfiguration |
| [Wochenprogramm und Sofortmeldung](programm.md) | Welches Layout eine Zone wann spielt: Wochenkalender mit Prioritäten, Ausnahmetage; eine Meldung über allem, sofort auf jedem Schirm |
| [Auslöser](ausloeser.md) | Wenn … dann …: Webhook (Home Assistant, Node-RED), Taster, Uhrzeit, Video zu Ende, Zonenwechsel → Layout einblenden, Meldung, Schirm schwarz |
| [Architektur 3.0](architektur-v3.md) | Layouts und Regionen mit gemischten Playlists, Gültigkeit je Eintrag, Ereignisse (SSE) statt Polling, Befehle an die Anzeige, Vorschau, Erweiterungspunkte |
| [Widgets](widgets.md) | Uhr, Text-Folie mit Vorlagen, Laufschrift, Wetter, Nachrichten (RSS), Kalender (ICS), QR-Code, Webseite, Zähler und eigene HTML-Widgets; Proxys mit Zwischenspeicher, Verhalten ohne Netz |

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

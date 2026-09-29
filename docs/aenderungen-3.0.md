# Änderungen in 3.0

Mit 3.0 wird aus der sensorgesteuerten Medienstation ein vollständiges
Digital-Signage-System: Layouts mit Regionen, ein Wochenprogramm, Widgets,
Auslöser, Überwachung und ein Manager für viele Stationen. Die Bedienung
Schritt für Schritt steht im [Handbuch](handbuch.md).

---

## Übernahme einer bestehenden Station

Beim ersten Start legt 3.0 die Videos und Bilder jeder Zone in ein Layout
`zone-near`, `zone-mid` beziehungsweise `zone-far` mit einer
Vollbild-Region. Reihenfolge, zufällige Reihenfolge, „einmal abspielen“ und
die Standzeit je Bild werden übernommen; der Ton der Zone bleibt bei der
Zone. Jede Zone spielt danach genau das, was sie vorher gespielt hat.

- **Sicherungen aus 2.x** lassen sich einspielen und werden auf dieselbe Weise
  übernommen.
- **Station Manager 2.x** kann weiter Medien hochladen und Einstellungen
  verteilen: Zonenlisten, die er schickt, landen in der Hauptregion des
  Zonen-Layouts.
- **Alles Neue ist aus**, bis jemand es einschaltet: kein Programm, keine
  Auslöser, keine PIN, keine Benachrichtigung.

Einzelheiten zum Datenmodell: [Architektur 3.0](architektur-v3.md).

---

## Neu

### Inhalte
- **Layouts mit Regionen** und fünf Vorlagen (Vollbild, geteilt, L-Form,
  Laufschrift, frei); jede Region mit eigener, **gemischter Playlist** aus
  Video, Bild, Webseite und Ton, **Standzeit** und **Gültigkeit** je Eintrag
  — [Layouts](layouts.md)
- **Layout-Editor** mit Ziehen und Skalieren (Maus und Finger), Ebenen,
  Hoch- und Querformat, Playlist-Editor und Widget-Formularen
- **Live-Vorschau** in derselben Seite wie auf dem Schirm, mit **simuliertem
  Zeitpunkt**; „Was läuft gerade?“ zeigt die echte Szene stumm
- **Zehn Widgets**: Uhr, Text-Folie mit Vorlagen, Laufschrift, Wetter,
  Nachrichten (RSS/Atom), Kalender (ICS, auch Raumbelegung), QR-Code,
  Webseite, Zähler und eigene HTML-Widgets — [Widgets](widgets.md)

### Zeit und Ereignisse
- **Wochenprogramm** als Kalender mit Prioritäten, Einträgen über Mitternacht
  und Ausnahmetagen — [Wochenprogramm](programm.md)
- **Sofortmeldung** auf allen Schirmen, mit Dauer und Signalton
- **Auslöser**: Webhook, GPIO-Taster, Uhrzeit, Video zu Ende, Zonenwechsel →
  Layout einblenden, Meldung, Schirm schwarz/an (mit HDMI-CEC), Start/Stop;
  mit Test-Knopf und Protokoll — [Auslöser](ausloeser.md)

### Betrieb
- **Sofort veröffentlicht**: Änderungen erreichen die Anzeige per
  Server-Sent Events im selben Augenblick
- **Monitoring**: Puls jeder Anzeige, was in jeder Region läuft,
  **Screenshot auf Abruf**, Systemwerte — [Monitoring](monitoring.md)
- **Proof-of-Play** mit Auswertung und CSV-Export
- **Benachrichtigung** per ntfy oder Webhook bei Störung, verlorener Anzeige
  und Beginn der Öffnungszeit
- **Zugangsschutz**: optionale PIN vor der Verwaltung, Anmeldeseite, Kopf
  `X-LZ-Pin` für den Manager — [Zugang](zugang.md)
- **Einrichten per Handy**: QR-Code zur Verwaltung auf der Startseite
- **In 3 Schritten zum ersten Inhalt**: Anleitung in der Verwaltung, solange
  die Station leer ist

### Station Manager
- **Kacheln** mit Vorschaubild, Layout, Zustand und Anzeigen je Station;
  Listenansicht, Suche
- **Gruppen und Tags**
- **Massenaktionen**: Layout zuweisen, Layout und Wochenprogramm kopieren
  (mit Prüfung auf fehlende Medien und Layouts), Sofortmeldung, Start/Stop/
  Neustart, Upload
- **Alarme** mit Systembenachrichtigung, je Station stummschaltbar
- **Verwaltung eingebettet** im Manager
- **PIN** je Station

---

## Verändert

- Die **Anzeige springt nie in die Verwaltung**. Fehlt etwas, bleibt sie
  schwarz und nennt den Grund in einer dezenten Zeile; ist die Station kurz
  nicht erreichbar, spielt sie die letzte Szene weiter.
- Die **Gesundheitsprüfung** sieht jetzt auch Anzeigen: meldet sich keine,
  gibt es eine Warnung.
- **Sicherungen** enthalten Layouts, Wochenprogramm und Auslöser.
- **Die Konfiguration** wird atomar geschrieben — ein Stromausfall mitten im
  Speichern hinterlässt keine halbe Datei.
- Die **Version** steht an einer Stelle (Datei `VERSION`).

---

## Bewusst nicht in 3.0

Diese Punkte sind als Issues festgehalten, jeweils mit Ansatz und Aufwand:

- Videowand mit bildgenau synchroner Wiedergabe
- Automatisches Umwandeln von Videos in Pi-taugliche Formate
- Import von PDF und PowerPoint
- Fertiges Pi-Image mit Kopplungscode

[Issues](https://github.com/larszu/lz-media-station/issues)

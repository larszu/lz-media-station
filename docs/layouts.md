# Layouts: Regionen, Playlists, Editor und Vorschau

Wie ein Schirm aufgeteilt wird, was in jedem Teil läuft — und wie man das
ohne Handbuch zusammenzieht.

---

## Das Konzept in drei Begriffen

**Layout.** Eine Aufteilung des Schirms. Jede Zone (Nah, Mitte, Fern) spielt
genau ein Layout; zugeordnet wird es in der Zonen-Übersicht. Eine frische
Station hat je Zone ein Vollbild-Layout (`zone-near`, `zone-mid`,
`zone-far`), das sich verhält wie die Station vor 3.0: eine Fläche, eine
Playlist.

**Region.** Ein Rechteck im Layout, angegeben in Prozent des Schirms. Eine
Region ist entweder eine **Medien-Region** mit eigener Playlist oder eine
**Widget-Region**, die ihre Fläche einem Widget überlässt (Uhr, Text,
Wetter und weitere, siehe [Widgets](widgets.md)). Regionen dürfen sich
überlappen; die **Ebene** (▲ ▼ im Panel) entscheidet, was oben liegt.

**Eintrag.** Ein Element der Playlist: Video, Bild, Audio oder Webseite. Ein
Bild und eine Webseite haben eine **Standzeit**; Video und Audio bringen ihre
Dauer mit. Jeder Eintrag kann eine **Gültigkeit** tragen (von/bis als
Kalendertag) — ein Plakat für die Sommerausstellung verschwindet am
1. September von selbst, ohne dass jemand daran denken muss. Gefiltert wird
im Kern, nicht im Browser: die Anzeige bekommt gar nicht, was heute nicht
gilt.

Die Reihenfolge der Liste zählt. Video, Bild, Video, Webseite — gemischt ist
erlaubt und gewollt.

## Vorlagen

Ein neues Layout beginnt mit einer Vorlage, damit man nicht bei Null zeichnet:

| Vorlage | Regionen |
|---|---|
| **Vollbild** | eine Region über den ganzen Schirm |
| **Geteilt** | zwei Regionen nebeneinander, je die halbe Breite |
| **L-Form** | Hauptbild links oben (70 × 80 %), Seitenleiste rechts, Laufschrift unten |
| **Ticker** | Vollbild mit Laufschrift am unteren Rand |
| **Frei** | ohne Regionen — selbst anlegen |

Die Vorlage ist nur der Anfang; danach lässt sich jede Region ziehen,
skalieren, löschen oder ergänzen. Höchstens 12 Regionen je Layout, höchstens
60 Layouts je Station.

## Der Editor (Karte „Layouts" im Admin)

**Oben** steht, welches Layout bearbeitet wird, daneben die Zonen, die es
spielen. „Neues Layout" legt eines aus einer Vorlage an, „Duplizieren" kopiert
das gewählte, „Umbenennen" ändert den Namen (er geht mit dem nächsten
Speichern mit). **Löschen** geht nur, wenn keine Zone das Layout spielt —
sonst nennt die Station die Zone, und der Knopf ist gesperrt. Erst dort ein
anderes Layout wählen, dann löschen.

**Die Leinwand** links zeigt den Schirm im Seitenverhältnis 16:9; der
Umschalter 9:16 dreht sie für einen hochkant montierten Schirm (nur die
Darstellung — die Prozentwerte bleiben dieselben). Jede Region ist ein
Rechteck darauf:

- **Antippen** wählt sie aus.
- **Ziehen** verschiebt sie. Die Leinwand hält ein Raster von 5 %; eine
  Region schnappt darauf ein, damit zwei Regionen bündig nebeneinander
  liegen, ohne dass man Zahlen tippt.
- **Die Ecken** skalieren. Die gegenüberliegende Ecke bleibt stehen.
- Das funktioniert mit der Maus wie mit **einem Finger auf dem Handy** — die
  Verwaltung wird beim Aufbau vom Handy bedient, und dort ist es die
  schnellste Art, ein Layout zurechtzurücken.

Wem Zahlen lieber sind: im Panel stehen **Links, Oben, Breite, Höhe** in
Prozent. Ragt eine Region über den Schirm hinaus, kürzt der Editor sie ein,
statt es dem Kern zu überlassen, der sie ablehnen würde.

**Das Panel** rechts gehört der gewählten Region: Bezeichnung, Inhalt
(Medien oder Widget), Übergang (Blende oder harter Schnitt), **Ton**,
zufällige Reihenfolge, einmal abspielen. In einem geteilten Layout sollte nur
eine Region Ton haben; eine neue Region bekommt ihn nur, wenn noch keine
andere ihn hat.

**Die Playlist** einer Medien-Region: unten die Bibliothek der Station nach
Videos, Bildern und Audio — ein Klick auf „+ Hinzufügen" (oder die Datei auf
die Liste ziehen) hängt sie an, der Reiter „Webseite" nimmt eine Adresse.
Je Eintrag: Standzeit (leer = der allgemeine Bildwechsel aus den
Einstellungen), gültig von / bis, Reihenfolge per ▲ ▼ oder Ziehen, ✕
entfernt ihn aus der Liste (die Datei bleibt auf der Station). Ein Eintrag,
dessen Gültigkeit abgelaufen ist, steht in Warnfarbe — er ist noch da, wird
aber nicht mehr ausgeliefert.

**Widget-Region:** der Widget-Typ kommt aus dem Katalog der installierten
Widgets, die Felder darunter aus seiner Beschreibung. Sind keine Widgets
installiert, gibt es ein Feld für den Typ und die Einstellungen als JSON.

### Speichern

Der Editor arbeitet auf einer **Kopie**. Erst „Layout speichern" schreibt
das ganze Layout auf die Station; bis dahin steht „Nicht gespeicherte
Änderungen" neben dem Knopf, und ein Wechsel zu einem anderen Layout fragt
nach. Der Grund: was hier halb gezogen ist, soll nicht auf dem Schirm im
Foyer aufblitzen. Die Anzeige bekommt den neuen Stand in dem Moment, in dem
er gespeichert ist (Ereignis `config`, siehe
[Architektur 3.0](architektur-v3.md)).

Lehnt der Kern etwas ab, steht der Grund mit Feldnamen unter dem Knopf —
etwa `haupt.playlist[2].url: muss mit http:// oder https:// beginnen`.

## Die Live-Vorschau

Unter dem Editor läuft das Layout in einem Rahmen — **mit derselben Seite,
die auch auf dem Schirm läuft** (`/display?vorschau=1&layout=…`), nicht mit
einer Nachbildung. Was hier zu sehen ist, ist das, was der Schirm zeigt:
dieselben Blenden, dieselben Standzeiten, dieselben Widgets.

- **Als Zone:** Nah, Mitte (nur mit drei Stufen) oder Fern — bestimmt den
  Ton der Zone, der parallel läuft.
- **Zeitpunkt simulieren:** Datum und Uhrzeit setzen, und die Vorschau zeigt,
  was an diesem Tag gilt — der Test für eine Gültigkeit, ohne bis zum
  1. September zu warten. Widgets bekommen den Zeitpunkt ebenfalls (eine Uhr
  zeigt dann diese Zeit). „Jetzt" setzt zurück.
- **Vollbild öffnen** zeigt dieselbe Vorschau in einem eigenen Tab.

Die Vorschau folgt dem **gespeicherten** Stand, nicht dem Entwurf — erst
speichern, dann sehen. Ohne Sensor, ohne Auto-Start, ohne Zonenwechsel.

## „Was läuft gerade?"

In der Status-Karte oben öffnet der Knopf einen Rahmen mit der **echten
Szene** der Station (`/display?zuschauen=1`): dieselbe Seite wie der Schirm,
aber stumm und ohne den Auto-Start, den die Anzeigeseite sonst auslöst. Ein
zweiter Betrachter darf die Steuerung nicht anwerfen und nicht aus dem Büro
heraus Ton machen. Der Rahmen zeigt Zonenwechsel live mit — der Blick auf den
Schirm, ohne ins Foyer zu gehen.

## Was die Startseite daraus macht

Die Startseite (`/`) startet die Anzeige nach 15 Sekunden von selbst, wenn
eine aktive Zone etwas zu zeigen hat. Seit 3.0 zählt dafür das **Layout**
der Zone: eine Region mit Playlist oder ein Widget ist Inhalt — auch ohne
eine einzige Datei (eine Webseite, eine Uhr). Der Ton der Zone zählt weiter.
Ein Kern von vor 3.0 wird an den alten Listen gemessen.

## Zwei Regeln, die weiter gelten

- **Ohne Messung wird nichts erfunden.** Ein Layout ändert daran nichts:
  keine Zone, kein Layout, kein Bild.
- **Rückwärtskompatibel.** Eine Station von vor 3.0 spielt nach dem Update
  dasselbe wie vorher — je Zone ein Vollbild-Layout mit den alten Listen.
  Die Medien-Toggles in der Bibliothek und der Config-Push des Managers
  schreiben weiter in die Hauptregion des Zonen-Layouts.

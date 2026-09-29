# Auslöser: Wenn … dann …

Der Abstandssensor ist ein Auslöser — bis 3.0 der einzige. Ein Foyer braucht
mehr: ein Knopf am Empfang blendet die Durchsage ein, die Hausautomation
meldet per Webhook „Veranstaltung beginnt", um 18:00 geht der Schirm aus, und
wenn der Film zu Ende ist, kommt das Menü zurück.

Ein Auslöser hat eine **Quelle** (wenn) und eine **Aktion** (dann). Der
Abstandssensor und seine Zonen bleiben davon unberührt.

## Quellen

| Quelle | Wann sie feuert | Einstellungen |
|---|---|---|
| **Webhook** | `POST http://<station>:5000/api/trigger/<kennung>` | optional ein **Token**, das der Aufrufer mitschicken muss |
| **Taster am GPIO** | Ein Taster gegen Masse an einem BCM-Pin wird gedrückt (entprellt) | Pin. Darf nicht der Pin des Sensors sein — die Station lehnt das ab |
| **Uhrzeit** | Zu dieser Uhrzeit an diesen Wochentagen, einmal je Minute | Tage, `HH:MM` |
| **Video zu Ende** | Die Anzeige meldet das Ende eines Videos | optional ein bestimmtes Video (leer = jedes) |
| **Zonenwechsel** | Die Zone hat zu Nah/Mitte/Fern gewechselt | Zone |

Ein Taster braucht `gpiozero` — auf einem Notebook gibt es kein GPIO, und die
Karte sagt das. Ein **Video zu Ende** meldet die Anzeige nur, wenn es einen
solchen Auslöser gibt, und nie aus der Vorschau.

## Aktionen

| Aktion | Was passiert |
|---|---|
| **Layout einblenden** | Ein Layout zwischendurch zeigen — `dauer_s` Sekunden oder bis zum nächsten Befehl (wie `POST /api/befehl` `zeige_layout`) |
| **Eingeblendetes Layout beenden** | Zurück zur Zone |
| **Sofortmeldung zeigen** | Wie im Admin unter [Sofortmeldung](programm.md#sofortmeldung): Text, zweite Zeile, Farbe, Dauer, Ton |
| **Schirm schwarz** | Eine schwarze Ebene über allem; ist `cec-client` da, geht auch der Fernseher aus |
| **Schirm wieder an** | Die Ebene weg, Fernseher an |
| **Sensor-Steuerung starten / anhalten** | Wie die Knöpfe im Admin |

Der Schirm-Zustand steht in der Szene (`schwarz`): eine Anzeige, die neu
lädt, ist danach genauso schwarz wie die anderen.

## Einrichten

Im Admin unter **Auslöser**: **+ Auslöser**, Name, Quelle, Aktion, speichern.
**Test** führt die Aktion sofort aus — ohne auf den Knopf oder die Uhrzeit zu
warten. Das **Protokoll** zeigt die letzten Auslösungen mit Anlass und
Ergebnis (im Speicher, die letzten 200).

### Webhook aus Home Assistant

Die Karte zeigt die Adresse und ein `curl`-Beispiel. In Home Assistant als
`rest_command`:

```yaml
rest_command:
  foyer_durchsage:
    url: "http://192.168.1.50:5000/api/trigger/durchsage"
    method: POST
    headers:
      X-LZ-Token: "geheim"
```

Danach in einer Automation `service: rest_command.foyer_durchsage`. Das Token
geht wahlweise als Kopfzeile `X-LZ-Token`, als `?token=` in der Adresse oder
als `{"token": "…"}` im JSON-Körper — Node-RED, ioBroker und ein Taster mit
WLAN (ESP) kommen so alle hin.

Antworten: `200` ausgelöst, `403` falsches Token, `404` keine
Webhook-Kennung, `409` der Auslöser ist ausgeschaltet.

### Ein Beispiel-Satz für ein Foyer

1. **Uhrzeit** Mo–Fr 18:00 → **Schirm schwarz**; 08:00 → **Schirm wieder an**.
2. **Webhook** `durchsage` mit Token → **Layout einblenden** „Durchsage", 60 s.
3. **Video zu Ende** → **Eingeblendetes Layout beenden** (nach dem Film zurück
   zum Menü).
4. **Taster** an BCM 27 → **Sofortmeldung** „Bitte am Empfang melden".

## Schnittstelle

| Method | Path | Beschreibung |
|---|---|---|
| GET / PUT | `/api/ausloeser` | Die ganze Liste; PUT **lehnt ab** und nennt das Feld (auch Pin-Kollisionen) |
| GET | `/api/ausloeser/protokoll` | Die letzten Auslösungen |
| POST | `/api/ausloeser/<id>/test` | Von Hand auslösen |
| POST | `/api/trigger/<id>` | Der Webhook (`X-LZ-Token` oder `?token=`) |
| POST | `/api/trigger/_video_ende` | `{datei, region}` — von der Anzeige |

Ein Auslöser:

```json
{ "id": "durchsage", "name": "Durchsage vom Empfang", "aktiv": true,
  "quelle": { "typ": "webhook", "token": "geheim" },
  "aktion": { "typ": "zeige_layout", "layout_id": "durchsage", "dauer_s": 60 } }
```

## Unter der Haube

`ausloeser.py` kennt kein Flask. Die Maschine `Ausloeser` läuft in einem
eigenen Faden (alle 0,25 s: Uhrzeit, Zonenwechsel), hält die GPIO-Taster und
redet über den Ereignisbus mit den Anzeigen. **Ein Auslöser, der schiefgeht,
ist kein Fehler der Station**: jede Aktion ist abgesichert, das Ergebnis steht
im Protokoll, die Wiedergabe läuft weiter. Der Ladeweg heilt eintragsweise;
bei zwei Tastern am selben Pin verliert der spätere.

# LZ Media Station Manager – Desktop App

Verwaltet mehrere LZ Media Stations (Raspberry Pi) im LAN über eine Electron-Oberfläche.

## Features

- **Auto-Discovery** via mDNS (Avahi auf den Pis: `_lzstation._tcp`)
- **Manuelles Hinzufügen** per IP/Hostname
- **Kacheln oder Liste**: Zone, aktives Layout, Gesundheit, Anzeigen online, letzter Screenshot (Klick = neues Bild anfordern), Version
- **Suche, Gruppen, Tags** — nur im Manager gespeichert (`gruppen.json`)
- **Massenaktionen auf die Auswahl**, Ergebnis je Station:
  - Layout einer Zone zuweisen (angeboten wird nur, was alle Ziele kennen)
  - Layout kopieren (`GET /api/layouts/<id>` → anlegen/ersetzen; fehlende Medien werden aufgelistet)
  - Wochenprogramm kopieren (fehlende Layouts auf dem Ziel werden vorher gemeldet)
  - Sofortmeldung ein/aus
  - Start / Stop / Reboot, Upload, Config-Push
- **Alarme**: Abfrage alle 10 s; gemeldet wird nur ein Übergang (offline, Gesundheit *Fehler*, Anzeige weg) — als Systembenachrichtigung und in der Alarmliste, je Station stummschaltbar. Die Logik steht in `alarme.js` und wird mit `npm test` (`node --test`) geprüft.
- **Verwaltung eingebettet** im `webview`; „Im Browser öffnen" bleibt
- **PIN** je Station (`pins.json`, Datei 0600), gesendet als `X-LZ-Pin`

## Voraussetzung auf jedem Pi

- `lz-media-station` ≥ v2.1.0 (`/api/identity` Endpoint); Layouts, Programm, Sofortmeldung, Screenshot und Anzeigen-Zahl ab 3.0 — ältere Stationen erscheinen weiter, die neuen Aktionen melden dort einen Fehler je Station
- `avahi-daemon` läuft (wird vom `install_pi.sh` mitinstalliert)
- Datei `/etc/avahi/services/lzstation.service` vorhanden

## Entwicklung

```bash
cd station-manager
npm install
npm start
```

## Tests

```bash
npm test          # node --test test/*.test.js (Alarm-Übergänge)
```

Die Verdrahtung Preload ↔ Hauptprozess prüft `tests/test_manager.py` im Wurzelverzeichnis.

## Build

```bash
# Windows installer + portable
npm run dist:win

# Mac Intel + Apple Silicon (DMG)
npm run dist:mac
```

Artefakte landen in `dist/`, etwa `LZ Media Station Manager Setup X.Y.Z.exe` und `LZ Media Station Manager-X.Y.Z-arm64.dmg`.

Gespeicherte Stationen (`stations.json`) liegen in der installierten App weiter im Ordner `LZ Station Manager` unter `%APPDATA%` bzw. `~/Library/Application Support/` – fest gepinnt, damit Updates ihre Daten finden. Beim Entwicklungsstart (`npm start`) ist es der Ordner `station-manager`.

## Tailscale (optional, empfohlen für Remote-Verwaltung)

Wenn die Pis nicht im selben LAN wie der Manager sind:

1. Auf jedem Pi:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. Auf dem Manager-Rechner ebenfalls Tailscale installieren und im selben Tailnet anmelden.
3. Pis erreichen sich dann unter `100.x.y.z` (oder `pi-name.tail-scale.ts.net` mit MagicDNS).
4. mDNS funktioniert nicht über Tailscale → die Stationen einmalig manuell mit ihrer Tailscale-IP / MagicDNS-Hostname hinzufügen.

Danach kannst du die Pis von überall verwalten, ohne Portfreigaben oder VPN.

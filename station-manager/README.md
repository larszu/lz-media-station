# LZ Media Station Manager – Desktop App

Verwaltet mehrere LZ Media Stations (Raspberry Pi) im LAN über eine Electron-Oberfläche.

## Features

- **Auto-Discovery** via mDNS (Avahi auf den Pis: `_lzstation._tcp`)
- **Manuelles Hinzufügen** per IP/Hostname
- Live-Status pro Station (Distanz, Zone, Online)
- **Bulk-Aktionen**: Start / Stop / Reboot mehrerer Stationen
- **Bulk-Upload** Videos / Bilder / Audio (gleiche Dateien an N Stationen)
- **Config-Push**: Stationsname, Schwelle, Verzögerung an Auswahl pushen
- Direkter Sprung in die Web-Admin-UI jeder Station

## Voraussetzung auf jedem Pi

- `pi-media-station` ≥ v2.1.0 (`/api/identity` Endpoint)
- `avahi-daemon` läuft (wird vom `install_pi.sh` mitinstalliert)
- Datei `/etc/avahi/services/lzstation.service` vorhanden

## Entwicklung

```bash
cd station-manager
npm install
npm start
```

## Build

```bash
# Windows installer + portable
npm run dist:win

# Mac Intel + Apple Silicon (DMG)
npm run dist:mac
```

Artefakte landen in `dist/`, etwa `LZ Media Station Manager Setup X.Y.Z.exe` und `LZ Media Station Manager-X.Y.Z-arm64.dmg`.

Gespeicherte Stationen (`stations.json`) liegen in der installierten App weiter im Ordner `LZ Station Manager` unter `%APPDATA%` bzw. `~/Library/Application Support/` – der Name vor der Umbenennung, damit Updates ihre Daten finden. Beim Entwicklungsstart (`npm start`) ist es der Ordner `station-manager`.

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

# FACES Media Station

Sensor-gesteuerte Medien-Station mit Web-Interface.
Läuft auf **Raspberry Pi** (HC-SR04 Ultraschallsensor) und für Tests auf **Windows** (Dummy-Sensor).

---

## Schnellstart Raspberry Pi (One-Shot Installer)

Auf dem Pi in einem Terminal:

```bash
curl -sSL https://raw.githubusercontent.com/larszu/pi-media-station/main/install_pi.sh | bash
```

Installiert:
- Python, Flask, gpiozero, Chromium
- App in `~/pi_media_station`
- Autostart beim Login (Kiosk-Modus)
- Chromium-Policy gegen Übersetzungs-Popup
- Unterdrückung störender System-Dialoge (Keyring etc.)

Danach `sudo reboot` — die Station startet automatisch.

---

## Schnellstart Windows

1. [Python 3.10+](https://www.python.org/downloads/) installieren (Häkchen "Add to PATH").
2. Repo herunterladen (Code → Download ZIP) oder klonen:
   ```powershell
   git clone https://github.com/larszu/pi-media-station.git
   cd pi-media-station
   ```
3. Doppelklick auf **`run_windows.bat`**.

Der Browser öffnet `http://localhost:5000/` automatisch.
Sensor läuft im Dummy-Modus (zufällige Distanzwerte).

---

## Bedienung

| Seite | URL | Zweck |
|---|---|---|
| Startseite | `/` | 3 Karten: Präsentation / Konfiguration / Remote |
| Admin | `/admin` | Medien hochladen, Zonen zuweisen, Einstellungen |
| Display | `/display` | Vollbild-Wiedergabe (Kiosk) |

- **ESC** auf der Display-Seite → zurück zur Admin-Seite
- "Fertig"-Button im Admin → zurück zur Startseite

---

## Hardware (Pi)

HC-SR04 Ultraschallsensor an GPIO 23 (Trigger) / GPIO 24 (Echo) — konfigurierbar im Admin.

## Lizenz

MIT

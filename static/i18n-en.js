/* Englisches Woerterbuch der Web-Oberflaeche — gelesen von i18n.js.
   `texte`: deutscher Text (Leerraum zusammengezogen) -> Englisch.
   `muster`: regulaere Ausdruecke fuer Meldungen mit Werten; {n} ist die
   n-te Gruppe, selbst wieder uebersetzt. Reihenfolge zaehlt: das erste
   passende Muster gewinnt.
   `html`: ganze Absaetze mit Auszeichnung, Schluessel = data-i18n.
   Der Block zwischen den Markern ist reines JSON — tests/test_i18n.py liest
   ihn und prueft, dass jeder Text der Templates hier steht. */
window.LZ_I18N_EN = /*JSON*/{
 "texte": {
  "Startseite": "Start page",
  "Inaktiv": "Inactive",
  "✔ Fertig — Startseite": "✔ Done — start page",
  "Gedrückt": "Pressed",
  "Frei": "Released",
  "Geschlossen": "Closed",
  "→ Nah…": "→ Near…",
  "→ Mitte…": "→ Mid…",
  "→ Fern…": "→ Far…",
  "startet": "starting",
  "Zonen-Übersicht": "Zone overview",
  "Nah": "Near",
  "Mitte": "Mid",
  "Fern": "Far",
  "Zufällige Reihenfolge": "Shuffle",
  "Einmal abspielen": "Play once",
  "Keine Medien zugewiesen": "No media assigned",
  "nach oben": "move up",
  "nach unten": "move down",
  "Std.": "Def.",
  "Standzeit in Sekunden (leer = allgemeiner Bildwechsel)": "Display time in seconds (empty = general image interval)",
  "Bildschirme dieses Rechners": "Screens of this computer",
  "Die Anzeige läuft als Vollbild-Fenster auf jedem Schirm, der an diesem Rechner hängt — der eingebaute zählt mit.": "The display runs as a full-screen window on every screen connected to this computer — the built-in one included.",
  "Auf allen zeigen": "Show on all",
  "Alle schließen": "Close all",
  "Keine Bildschirme gefunden.": "No screens found.",
  "zeigt": "showing",
  "aus": "off",
  "Zeigen": "Show",
  "Schließen": "Close",
  "Kein Chrome, Chromium oder Edge gefunden.": "No Chrome, Chromium or Edge found.",
  "Medienbibliothek": "Media library",
  "🖼 Bilder": "🖼 Images",
  "📁 Videos hochladen (Klick oder Drag&Drop)": "📁 Upload videos (click or drag & drop)",
  "📁 Bilder hochladen (Klick oder Drag&Drop)": "📁 Upload images (click or drag & drop)",
  "📁 Audio hochladen (Klick oder Drag&Drop)": "📁 Upload audio (click or drag & drop)",
  "Keine Dateien": "No files",
  "Löschen": "Delete",
  "Wiedergabe-Hinweise": "Playback notes",
  "Einstellungen": "Settings",
  "Stationsname": "Station name",
  "Zonen": "Zones",
  "Zwei Stufen (Nah / Fern)": "Two levels (near / far)",
  "Drei Stufen (Nah / Mitte / Fern)": "Three levels (near / mid / far)",
  "Schwelle Nah:": "Near threshold:",
  "Schwelle Mitte:": "Mid threshold:",
  "Verzögerung:": "Delay:",
  "Bildwechsel:": "Image interval:",
  "Gesamt:": "Master:",
  "Video bei Zonenwechsel an gleicher Stelle fortsetzen (statt von vorne)": "Resume video where it left off when the zone changes (instead of from the start)",
  "Einstellungen speichern": "Save settings",
  "Untertitel & Sprachen": "Subtitles & languages",
  "Sprachen": "Languages",
  ".vtt hochladen": "Upload .vtt",
  "Untertitel speichern": "Save subtitles",
  "Erst Sprachen eintragen und speichern.": "Enter and save languages first.",
  "Noch keine Videos hochgeladen.": "No videos uploaded yet.",
  "— keine —": "— none —",
  "Sicherung": "Backup",
  "Konfiguration sichern": "Back up configuration",
  "Sicherung einspielen": "Restore backup",
  "Wiederhergestellt": "Restored",
  "Datei nicht lesbar": "File not readable",
  "Wiederhergestellt. Fuer Sensor- und Port-Aenderungen die Station neu starten.": "Restored. Restart the station for sensor and port changes.",
  "Zustand": "Health",
  "Alles in Ordnung": "All good",
  "Hinweis": "Note",
  "Achtung": "Warning",
  "Störung": "Fault",
  "Keine Befunde — Sensor misst, Platte hat Platz, beide Zonen haben Medien.": "No findings — sensor measuring, disk has space, both zones have media.",
  "Die Sensor-Steuerung ist gestoppt — es wird nichts gespielt.": "Sensor control is stopped — nothing is playing.",
  "Ausserhalb der Oeffnungszeiten — Schirm schwarz, Ton aus.": "Outside opening hours — screen black, sound off.",
  "Besucher-Statistik": "Visitor statistics",
  "Besuche heute": "Visits today",
  "Ø Verweildauer": "Ø dwell time",
  "Besuche gesamt": "Visits total",
  "Heute nach Stunde": "Today by hour",
  "Letzte Tage": "Recent days",
  "CSV herunterladen": "Download CSV",
  "Zähler zurücksetzen": "Reset counters",
  "Noch keine Besuche erfasst": "No visits recorded yet",
  "Zurückgesetzt": "Reset",
  "Alle erfassten Besuchszahlen unwiderruflich löschen?": "Permanently delete all recorded visitor counts?",
  "Zeitsteuerung": "Scheduling",
  "Außerhalb der Öffnungszeiten bleibt der Schirm schwarz, der Ton aus, und es wird nicht ausgelöst. Ist die Zeitsteuerung aus, spielt die Station wie bisher rund um die Uhr.": "Outside opening hours the screen stays black, the sound off, and nothing triggers. With scheduling off, the station plays around the clock.",
  "Zeitsteuerung aktiv": "Scheduling active",
  "Zeitsteuerung speichern": "Save schedule",
  "Montag": "Monday",
  "Dienstag": "Tuesday",
  "Mittwoch": "Wednesday",
  "Donnerstag": "Thursday",
  "Freitag": "Friday",
  "Samstag": "Saturday",
  "Sonntag": "Sunday",
  "bis": "to",
  "Systemeinstellungen": "System settings",
  "Lade Netzwerkstatus...": "Loading network status...",
  "Verbindung": "Connection",
  "Modus": "Mode",
  "DHCP (automatisch)": "DHCP (automatic)",
  "Statische IP": "Static IP",
  "IP-Adresse / CIDR": "IP address / CIDR",
  "z.B. 192.168.1.50/24": "e.g. 192.168.1.50/24",
  "z.B. 192.168.1.50": "e.g. 192.168.1.50",
  "DNS (kommagetrennt)": "DNS (comma-separated)",
  "Anzeige-IP für Fernsteuerung (leer = Auto-Erkennung)": "Display IP for remote control (empty = auto-detect)",
  "Abstandsquelle": "Distance source",
  "Automatisch (Ultraschall, sonst Kamera)": "Automatic (ultrasonic, otherwise camera)",
  "Nur Ultraschall (HC-SR04 am GPIO)": "Ultrasonic only (HC-SR04 on GPIO)",
  "Kamera (Webcam, auch Mac/Windows)": "Camera (webcam, also Mac/Windows)",
  "Taster (Besucher drückt)": "Push button (visitor presses)",
  "Kamera-Index": "Camera index",
  "Brennweite (px, kalibriert)": "Focal length (px, calibrated)",
  "Gleichtakt mit anderen Stationen": "Lockstep with other stations",
  "Aus — eigener Sensor": "Off — own sensor",
  "Folgt einer anderen Station": "Follows another station",
  "Taktgeber (IP/Hostname)": "Clock station (IP/hostname)",
  "Port des Taktgebers": "Clock station port",
  "Taster GPIO (BCM)": "Button GPIO (BCM)",
  "Haltezeit nach Druck (s)": "Hold time after press (s)",
  "Anzeige & Sensor speichern": "Save display & sensor",
  "Netzwerk übernehmen": "Apply network",
  "Pi neu starten": "Restart Pi",
  "Hinweis: Eine geänderte IP unterbricht die Verbindung. Die neue Adresse danach im Browser eingeben.": "Note: changing the IP interrupts the connection. Then enter the new address in the browser.",
  "Aktive Verbindung:": "Active connection:",
  "Modus:": "Mode:",
  "Statisch": "Static",
  "Kein aktiver Adapter gefunden.": "No active adapter found.",
  "Netzwerk-API nicht erreichbar.": "Network API unreachable.",
  "Keine Verbindung gewählt.": "No connection selected.",
  "IP-Adresse fehlt.": "IP address missing.",
  "Netzwerk-Einstellungen jetzt anwenden? Die Verbindung wird kurz unterbrochen.": "Apply network settings now? The connection will drop briefly.",
  "Wende an...": "Applying...",
  "Übernommen. Neue IP ggf. im Browser eingeben.": "Applied. Enter the new IP in the browser if needed.",
  "Verbindung verloren (evtl. neue IP aktiv).": "Connection lost (a new IP may be active).",
  "Pi wirklich neu starten?": "Really restart the Pi?",
  "Pi wird neu gestartet...": "Pi is restarting...",
  "WLAN": "Wi-Fi",
  "Lade WLAN-Status...": "Loading Wi-Fi status...",
  "WLAN aktiviert": "Wi-Fi enabled",
  "↻ Netzwerke scannen": "↻ Scan networks",
  "SSID (manuell)": "SSID (manual)",
  "MeinNetzwerk": "MyNetwork",
  "Passwort": "Password",
  "(leer = offen)": "(empty = open)",
  "Mit WLAN verbinden": "Connect to Wi-Fi",
  "WLAN ist deaktiviert.": "Wi-Fi is disabled.",
  "Verbunden mit:": "Connected to:",
  "WLAN aktiv, keine Verbindung.": "Wi-Fi on, not connected.",
  "WLAN-API nicht erreichbar.": "Wi-Fi API unreachable.",
  "Aktiviere WLAN...": "Enabling Wi-Fi...",
  "Deaktiviere WLAN...": "Disabling Wi-Fi...",
  "WLAN aktiv": "Wi-Fi on",
  "WLAN aus": "Wi-Fi off",
  "SSID fehlt.": "SSID missing.",
  "Verbindung fehlgeschlagen": "Connection failed",
  "Über": "About",
  "Gespeichert": "Saved",
  "Fehler": "Error",
  "kein Sensor: gpiozero nicht installiert": "no sensor: gpiozero not installed",
  "Kamera: opencv nicht installiert (pip install opencv-python-headless)": "Camera: opencv not installed (pip install opencv-python-headless)",
  "kein Taster: gpiozero nicht installiert": "no button: gpiozero not installed",
  "kein Taktgeber eingetragen": "no clock station set",
  "Keine Daten": "No data",
  "Ungültiger Typ": "Invalid type",
  "Keine Datei": "No file",
  "Kein Dateiname": "No file name",
  "Format nicht erlaubt": "Format not allowed",
  "Kein lesbares Konfigurations-Objekt": "No readable configuration object",
  "connection und method (auto|manual) erforderlich": "connection and method (auto|manual) required",
  "Adresse muss CIDR sein, z.B. 192.168.1.50/24": "Address must be CIDR, e.g. 192.168.1.50/24",
  "ssid erforderlich": "ssid required",
  "Präsentation": "Presentation",
  "Vollbild-Anzeige starten": "Start full-screen display",
  "Auto-Start in": "Auto-start in",
  "Konfiguration": "Configuration",
  "Medien, Sensor & Zonen einrichten": "Set up media, sensor & zones",
  "Andere Geräte": "Other devices",
  "Im selben Netz, Anzeige:": "Same network, display:",
  "Konfiguration:": "Configuration:",
  "Adresse:": "Address:",
  "Keine Medien konfiguriert — bitte erst Konfiguration öffnen": "No media configured — open the configuration first",
  "Starte Sensor-Steuerung...": "Starting sensor control...",
  "Warte auf Sensor": "Waiting for sensor",
  "Bewege etwas vor den Sensor um eine Zone auszuwählen.": "Move something in front of the sensor to select a zone.",
  "Konfiguriere Medien im Admin-Panel:": "Configure media in the admin panel:",
  "Medien konnten nicht geladen werden": "Media could not be loaded",
  "Zur Admin-Seite...": "To the admin page...",
  "Video nicht abspielbar": "Video cannot be played",
  "Bild nicht ladbar": "Image cannot be loaded",
  "Audio nicht abspielbar": "Audio cannot be played"
 },
 "muster": [
  [
   "^✓ (.+)$",
   "✓ {1}"
  ],
  [
   "^✗ (.+)$",
   "✗ {1}"
  ],
  [
   "^(.+) abgelehnt \\(nur \\.vtt\\)$",
   "{1} rejected (.vtt only)"
  ],
  [
   "^Die aktuelle Konfiguration durch \"(.+)\" ersetzen\\?$",
   "Replace the current configuration with \"{1}\"?"
  ],
  [
   "^\"(.+)\" aus allen Zonen entfernen\\? \\(Die Datei bleibt auf dem Pi erhalten\\.\\)$",
   "Remove \"{1}\" from all zones? (The file stays on the Pi.)"
  ],
  [
   "^Außerhalb der Öffnungszeiten — Schirm schwarz, Ton aus\\. ?(.*)$",
   "Outside opening hours — screen black, sound off. {1}"
  ],
  [
   "^(\\d+) Uhr: (\\d+) Besuche$",
   "{1}:00: {2} visits"
  ],
  [
   "^(\\d+) Besuche$",
   "{1} visits"
  ],
  [
   "^auf (.+)$",
   "on {1}"
  ],
  [
   "^nmcli nicht verfügbar: (.+)$",
   "nmcli not available: {1}"
  ],
  [
   "^Verbinde mit (.+)\\.\\.\\.$",
   "Connecting to {1}..."
  ],
  [
   "^Verbunden mit (.+)$",
   "Connected to {1}"
  ],
  [
   "^(.+) — (\\d+)×(\\d+) bei (-?\\d+),(-?\\d+) · Hauptschirm$",
   "{1} — {2}×{3} at {4},{5} · main screen"
  ],
  [
   "^(.+) — (\\d+)×(\\d+) bei (-?\\d+),(-?\\d+)$",
   "{1} — {2}×{3} at {4},{5}"
  ],
  [
   "^Gesucht wurde: (.*)\\. \\(Firefox und Safari können kein Fenster auf einem bestimmten Schirm öffnen\\.\\)$",
   "Searched: {1}. (Firefox and Safari cannot open a window on a specific screen.)"
  ],
  [
   "^Schirm (\\d+) gibt es nicht \\((\\d+) gefunden\\)\\.$",
   "Screen {1} does not exist ({2} found)."
  ],
  [
   "^Schirm (\\d+) zeigt schon\\.$",
   "Screen {1} is already showing."
  ],
  [
   "^Schirm (\\d+): (.+)$",
   "Screen {1}: {2}"
  ],
  [
   "^Zone \\\"(.+)\\\" ist leer$",
   "Zone \"{1}\" is empty"
  ],
  [
   "^kein Sensor: GPIO-Fehler \\((.+)\\)$",
   "no sensor: GPIO error ({1})"
  ],
  [
   "^Kamera: Index (\\d+) nicht gefunden$",
   "Camera: index {1} not found"
  ],
  [
   "^Kamera aktiv \\(Index (\\d+), (.+)\\)$",
   "Camera active (index {1}, {2})"
  ],
  [
   "^Taster an BCM (\\d+) \\(Haltezeit (\\d+) s\\)$",
   "Button on BCM {1} (hold time {2} s)"
  ],
  [
   "^kein Taster: GPIO-Fehler \\((.+)\\)$",
   "no button: GPIO error ({1})"
  ],
  [
   "^(.+) \\(Rueckfall: kein Ultraschallsensor\\)$",
   "{1} (fallback: no ultrasonic sensor)"
  ],
  [
   "^folgt (.+)$",
   "follows {1}"
  ],
  [
   "^kein Kontakt zu (.+) \\((.+)\\)$",
   "no contact to {1} ({2})"
  ],
  [
   "^Kein Kontakt zum Taktgeber — es wird die Fern-Szene gespielt\\. \\((.+)\\)$",
   "No contact to the clock station — the far scene is playing. ({1})"
  ],
  [
   "^Keine Messung — es wird nicht ausgeloest\\. \\((.+)\\)$",
   "No measurement — nothing triggers. ({1})"
  ],
  [
   "^Nur noch (\\d+) MB frei — Uploads und die Statistik koennen nicht mehr schreiben\\.$",
   "Only {1} MB free — uploads and statistics can no longer write."
  ],
  [
   "^Noch (\\d+) MB frei — vor der naechsten Ausstellung aufraeumen\\.$",
   "{1} MB free — clean up before the next exhibition."
  ],
  [
   "^Zone (.+) hat keine Medien — dort bleibt der Schirm leer\\.$",
   "Zone {1} has no media — the screen stays empty there."
  ],
  [
   "^Zone (.+): (\\d+) zugewiesene Datei\\(en\\) fehlen auf der Platte \\((.+)\\)\\.$",
   "Zone {1}: {2} assigned file(s) missing on disk ({3})."
  ],
  [
   "^Codec (.+) wird auf dem Pi nicht in Hardware dekodiert — H\\.264 \\(MP4\\) laeuft dort deutlich fluessiger\\.$",
   "Codec {1} is not hardware-decoded on the Pi — H.264 (MP4) runs much more smoothly there."
  ],
  [
   "^Aufloesung (\\d+)x(\\d+) liegt ueber (\\d+)x(\\d+) — auf einem Pi ruckelt das erfahrungsgemaess\\.$",
   "Resolution {1}x{2} is above {3}x{4} — on a Pi this tends to stutter."
  ],
  [
   "^(\\d+) Bilder/s — 25 oder 30 reichen fuer eine Medienstation und entlasten den Dekoder\\.$",
   "{1} frames/s — 25 or 30 are enough for a media station and relieve the decoder."
  ],
  [
   "^Bitrate ([\\d.]+) Mbit/s ist sehr hoch — hier limitiert eher die SD-Karte als der Dekoder\\.$",
   "Bitrate {1} Mbit/s is very high — the SD card limits here rather than the decoder."
  ],
  [
   "^([^:]+): (.+)$",
   "{1}: {2}"
  ]
 ],
 "html": {
  "untertitel-hinweis": "Language codes separated by commas (e.g. <code>de, en</code>). From two languages on, buttons appear on the display. Empty = no switching. Subtitles must be <strong>WebVTT (.vtt)</strong> — that is all a browser plays.",
  "sicherung-hinweis": "Saves all settings (zones, schedule, sensor, volumes) as a file — to clone a station or to restore after an SD card failure. <strong>Media files are not included.</strong>",
  "statistik-hinweis": "What is counted is <strong>when</strong> and <strong>how long</strong> someone stood in the near zone — nothing about individual people.",
  "zeitplan-mitternacht": "End <strong>00:00</strong> means midnight (end of day). An end <em>before</em> the start runs past midnight — e.g. 20:00 to 02:00.",
  "cec-label": "Switch the TV off outside the hours via HDMI-CEC (needs <code>cec-client</code>)"
 }
}/*JSON*/;

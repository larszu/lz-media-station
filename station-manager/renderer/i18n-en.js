/* Englisches Woerterbuch des Station Managers — gelesen von i18n.js.
   Aufbau wie static/i18n-en.js der Web-Oberflaeche. */
window.LZ_I18N_EN = /*JSON*/{
 "texte": {
  "↻ Neu scannen": "↻ Rescan",
  "+ Station hinzufügen": "+ Add station",
  "Bulk-Aktionen": "Bulk actions",
  "Medien hochladen": "Upload media",
  "🖼 Bilder": "🖼 Images",
  "Stationsname": "Station name",
  "(leer = behalten)": "(empty = keep)",
  "Schwelle (m)": "Threshold (m)",
  "z.B. 1.0": "e.g. 1.0",
  "Verzögerung (s)": "Delay (s)",
  "z.B. 1.5": "e.g. 1.5",
  "Config pushen": "Push config",
  "Über": "About",
  "Station hinzufügen": "Add station",
  "Hinzufügen": "Add",
  "Abbrechen": "Cancel",
  "Keine Stationen gefunden. mDNS scannt automatisch im LAN, oder Station manuell hinzufügen.": "No stations found. mDNS scans the LAN automatically, or add a station manually.",
  "Scanne...": "Scanning...",
  "Prüfe...": "Checking...",
  "Hinzugefügt": "Added",
  "Nicht erreichbar": "Not reachable",
  "Keine Auswahl": "Nothing selected",
  "Keine Felder gesetzt": "No fields set",
  "Station neu starten": "Restart station",
  "Aus der Liste entfernen": "Remove from list",
  "Nah": "Near",
  "Mitte": "Mid",
  "Fern": "Far",
  "Inaktiv": "Inactive",
  "manuell": "manual",
  "PIN der Station": "Station PIN",
  "PIN eingeben": "Enter PIN",
  "Speichern": "Save",
  "Vergessen": "Forget",
  "Die Station verlangt eine PIN": "The station requires a PIN",
  "PIN gespeichert": "PIN stored",
  "Diese Station hat keine PIN": "This station has no PIN",
  "Eine Station verlangt eine PIN — 🔑 an der Karte": "A station requires a PIN — 🔑 on its card",
  "Alarme": "Alerts",
  "🔔 Alarme": "🔔 Alerts",
  "Alle Gruppen": "All groups",
  "Alle sichtbaren": "All visible",
  "Angeboten werden Layouts, die es auf allen ausgewählten Stationen gibt.": "Only layouts that exist on every selected station are offered.",
  "Ansicht": "View",
  "Auf Auswahl kopieren": "Copy to selection",
  "Auswahl": "Selection",
  "Beenden": "End",
  "Dauer (min)": "Duration (min)",
  "Einblenden": "Show",
  "Farbe": "Colour",
  "Gruppe": "Group",
  "Gruppe filtern": "Filter by group",
  "Gruppe setzen": "Set group",
  "Gruppe und Tags": "Group and tags",
  "Im Browser öffnen": "Open in browser",
  "Kacheln": "Tiles",
  "▦ Kacheln": "▦ Tiles",
  "Keine": "None",
  "Layout kopieren": "Copy layout",
  "Layout zuweisen": "Assign layout",
  "Liste": "List",
  "☰ Liste": "☰ List",
  "Liste leeren": "Clear list",
  "Schließen": "Close",
  "Sofortmeldung": "Instant message",
  "Station suchen": "Search stations",
  "Steuerung": "Control",
  "Tag entfernen": "Remove tag",
  "Tag hinzufügen": "Add tag",
  "Tags filtern": "Filter by tag",
  "Untertext": "Subtext",
  "Von Station": "From station",
  "Wochenprogramm kopieren": "Copy weekly schedule",
  "Zuweisen": "Assign",
  "leer = bis Ende": "empty = until ended",
  "z.B. Bitte Gebäude verlassen": "e.g. Please leave the building",
  "z.B. Eingang": "e.g. Entrance",
  "z.B. Foyer": "e.g. Lobby",
  "offline": "offline",
  "geschlossen": "closed",
  "Lade Vorschau …": "Loading preview …",
  "Keine Vorschau": "No preview",
  "Vorschau aktualisieren": "Refresh preview",
  "Gesundheit": "Health",
  "Anzeigen": "Displays",
  "in Ordnung": "OK",
  "Hinweis": "Note",
  "Warnung": "Warning",
  "Fehler": "Error",
  "Verwaltung": "Admin",
  "Verwaltung öffnen": "Open admin",
  "Alarme stummschalten": "Mute alerts",
  "Alarme wieder einschalten": "Unmute alerts",
  "Keine Station passt zum Filter.": "No station matches the filter.",
  "Arbeite …": "Working …",
  "ok": "ok",
  "Kein Layout gewählt": "No layout selected",
  "Erst Stationen auswählen": "Select stations first",
  "Nicht alle Stationen kennen Layouts": "Not every station supports layouts",
  "Kein gemeinsames Layout": "No shared layout",
  "Keine Station erreichbar": "No station reachable",
  "Keine Layouts": "No layouts",
  "Quelle": "Source",
  "Es fehlen Medien": "Missing media",
  "Es fehlen Layouts": "Missing layouts",
  "Text fehlt": "Text missing",
  "Sofortmeldung beenden": "End instant message",
  "Upload": "Upload",
  "Keine Alarme": "No alerts",
  "stumm": "muted",
  "Station nicht mehr erreichbar": "Station no longer reachable",
  "Station wieder erreichbar": "Station reachable again",
  "Gesundheit: Fehler": "Health: error",
  "Gesundheit: Fehler behoben": "Health: error resolved",
  "Keine Anzeige mehr verbunden": "No display connected any more",
  "Eine Anzeige ist nicht mehr verbunden": "A display disconnected",
  "Anzeige wieder verbunden": "Display reconnected",
  "keine Antwort": "no answer"
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
   "^Station \"(.*)\" neu starten\\?$",
   "Restart station \"{1}\"?"
  ],
  [
   "^Station \"(.*)\" aus der Liste entfernen\\?$",
   "Remove station \"{1}\" from the list?"
  ],
  [
   "^(\\d+) gestartet$",
   "{1} started"
  ],
  [
   "^(\\d+) gestoppt$",
   "{1} stopped"
  ],
  [
   "^(\\d+) Stationen neu starten\\?$",
   "Restart {1} stations?"
  ],
  [
   "^Reboot an (\\d+)$",
   "Reboot sent to {1}"
  ],
  [
   "^Lade (\\d+) (\\w+) an (\\d+) hoch\\.\\.\\.$",
   "Uploading {1} {2} to {3}..."
  ],
  [
   "^(\\d+) Fehler von (\\d+)$",
   "{1} of {2} failed"
  ],
  [
   "^Alle (\\d+) Uploads ok$",
   "All {1} uploads ok"
  ],
  [
   "^(\\d+) Fehler$",
   "{1} errors"
  ],
  [
   "^Config an (\\d+) gepusht$",
   "Config pushed to {1}"
  ],
  [
   "^Station \"(.+)\" neu starten\\?$",
   "Restart station \"{1}\"?"
  ],
  [
   "^Station \"(.+)\" aus der Liste entfernen\\?$",
   "Remove station \"{1}\" from the list?"
  ]
 ],
 "html": {}
}/*JSON*/;

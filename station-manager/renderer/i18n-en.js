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
  "Aus der Liste entfernen": "Remove from list"
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
  ]
 ],
 "html": {}
}/*JSON*/;

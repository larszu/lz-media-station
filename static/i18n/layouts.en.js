/* Englisches Woerterbuch der Layout-Karte — ein Beispiel fuer den Weg, den
   Erweiterungen nehmen: eine Datei in static/i18n/, automatisch eingebunden,
   von tests/test_i18n.py mitgeprueft. Der Block zwischen den Markern ist
   reines JSON. */
(window.LZ_I18N_EN_EXTRA = window.LZ_I18N_EN_EXTRA || []).push(/*JSON*/{
 "texte": {
  "Layouts": "Layouts",
  "Layout": "Layout",
  "Neues Layout": "New layout",
  "Name, z. B. Foyer links": "Name, e.g. Foyer left",
  "Vorlage": "Template",
  "Layout anlegen": "Create layout",
  "Vorschau": "Preview",
  "Duplizieren": "Duplicate",
  "Löschen": "Delete",
  "Standard (Vollbild)": "Default (full screen)",
  "Noch keine Layouts.": "No layouts yet.",
  "Bitte einen Namen eingeben.": "Please enter a name.",
  "✓ Angelegt": "✓ Created",
  "✓ Gelöscht": "✓ Deleted",
  "✓ Kopiert": "✓ Copied",
  "Vollbild": "Full screen",
  "Geteilt": "Split",
  "L-Form": "L-shape",
  "Ticker": "Ticker",
  "Frei": "Free",
  "Eine Region ueber den ganzen Schirm.": "One region over the whole screen.",
  "Zwei Regionen nebeneinander, je die halbe Breite.": "Two regions side by side, half width each.",
  "Hauptbild links oben, Seitenleiste rechts, Laufschrift unten.": "Main picture top left, sidebar right, ticker below.",
  "Vollbild mit Laufschrift am unteren Rand.": "Full screen with a ticker at the bottom.",
  "Ohne Regionen — selbst anlegen.": "No regions — add your own."
 },
 "muster": [
  ["^(\\d+) Regionen?$", "{1} region(s)"],
  ["^Zonen: (.+)$", "Zones: {1}"],
  ["^Layout \"(.+)\" löschen\\? Die Medien bleiben erhalten\\.$", "Delete layout \"{1}\"? The media files stay."],
  ["^Layout '(.+)' wird von Zone (.+) gespielt$", "Layout '{1}' is played by zone {2}"],
  ["^Layout '(.+)' gibt es (schon|nicht)$", "Layout '{1}' {2}"],
  ["^schon$", "already exists"],
  ["^nicht$", "does not exist"]
 ],
 "html": {
  "layouts-hinweis": "A layout divides the screen into <strong>regions</strong> — each with its own playlist of videos, images and web pages. Every zone plays one layout; it is assigned in the zone overview. <strong>Preview</strong> opens the layout the way it runs on the screen."
 }
}/*JSON*/);

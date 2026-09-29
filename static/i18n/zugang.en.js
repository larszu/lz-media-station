/* Englisches Woerterbuch der Zugang-Karte, der Anmeldeseite und der
   Server-Meldungen aus zugang.py / api_zugang.py. */
(window.LZ_I18N_EN_EXTRA = window.LZ_I18N_EN_EXTRA || []).push(/*JSON*/{
 "texte": {
  "Zugang": "Access",
  "LZ Media Station – Anmeldung": "LZ Media Station – Login",
  "Diese Station ist mit einer PIN geschützt. Die Anzeige läuft ohne Anmeldung weiter.": "This station is protected by a PIN. The display keeps running without logging in.",
  "PIN eingeben": "Enter PIN",
  "Anmelden": "Log in",
  "Abmelden": "Log out",
  "Bisherige PIN": "Current PIN",
  "nur beim Ändern": "only when changing",
  "Neue PIN (4–12 Zeichen)": "New PIN (4–12 characters)",
  "mindestens 4 Zeichen": "at least 4 characters",
  "Neue PIN wiederholen": "Repeat new PIN",
  "noch einmal": "once more",
  "Angemeldet bleiben (Stunden)": "Stay logged in (hours)",
  "PIN setzen": "Set PIN",
  "PIN ändern": "Change PIN",
  "PIN aufheben": "Remove PIN",
  "PIN ist gesetzt — du bist angemeldet.": "A PIN is set — you are logged in.",
  "PIN ist gesetzt.": "A PIN is set.",
  "Keine PIN gesetzt — die Verwaltung ist für jeden im Netz offen.": "No PIN set — the admin is open to everyone on the network.",
  "Die beiden PINs stimmen nicht überein": "The two PINs do not match",
  "✓ PIN gesetzt — ab jetzt verlangt die Verwaltung eine Anmeldung": "✓ PIN set — from now on the admin requires a login",
  "PIN aufheben? Die Verwaltung ist dann wieder für jeden im Netz offen.": "Remove the PIN? The admin will be open to everyone on the network again.",
  "✓ PIN aufgehoben": "✓ PIN removed",
  "PIN stimmt nicht": "Wrong PIN",
  "alt: die bisherige PIN stimmt nicht": "alt: the current PIN is wrong",
  "Zu viele Fehlversuche — eine Minute warten": "Too many failed attempts — wait a minute",
  "Anmeldung erforderlich — PIN im Kopf X-LZ-Pin oder Sitzung": "Login required — PIN in the X-LZ-Pin header or a session",
  "pin: muss Text sein": "pin: must be text",
  "pin: keine Leerzeichen": "pin: no spaces",
  "sitzungsdauer_h: 1..720 Stunden": "sitzungsdauer_h: 1..720 hours"
 },
 "muster": [
  ["^pin: (\\d+)\\.\\.(\\d+) Zeichen$", "pin: {1}..{2} characters"],
  ["^zugang\\.json nicht schreibbar: (.+)$", "zugang.json not writable: {1}"]
 ],
 "html": {
  "zugang-hinweis": "Without a PIN the admin is open to everyone on the network — as before. With a PIN, <code>/admin</code> requires a login, and every change via the API needs the PIN in the <code>X-LZ-Pin</code> header (that is how the Station Manager sends it). The display page and the kiosk on the Pi itself stay free. The PIN is <strong>not</strong> part of the configuration and does not travel with a backup."
 }
}/*JSON*/);

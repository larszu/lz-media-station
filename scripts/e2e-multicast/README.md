# Ende-zu-Ende-Test IPTV-Kanal (Linux-Container)

Prüft den Multicast-Kanal ohne Pi: Station im Container starten, Kanal
senden, per Multicast empfangen, ein Bild nach `out/frame.png` schreiben.

```sh
docker build -t lzms-test scripts/e2e-multicast
mkdir -p ~/.cache/lzms-e2e && cp scripts/e2e-multicast/*.sh ~/.cache/lzms-e2e/
docker run --rm -v "$PWD":/src:ro -v ~/.cache/lzms-e2e:/out lzms-test bash /out/anzeige.sh
```

- `anzeige.sh` — Speiseplan-Layout setzen, Kanal (Modus `anzeige`) starten,
  Codecs prüfen, `frame.png` mitschneiden.
- `autostart.sh` — falsche Adresse wird abgelehnt, Einstellungen speichern,
  Neustart, Kanal muss von selbst senden.

Auf macOS mit colima muss der Ausgabeordner unter `~` liegen (nur das
Home-Verzeichnis ist in die VM eingebunden).

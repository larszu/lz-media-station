#!/usr/bin/env bash
# LZ Media Station — lokal starten (Linux / macOS)
#
# ─── WAS GEMELDET WURDE (Nutzer, 2026-09-09) ────────────────────────────────
#
#   „Ebenso die Medien Station [muss man lokal starten koennen]. Man muss bei
#    Medien Station auch Web Clients haben. Also Server lokal und andere
#    Geraete koennen drauf zu greifen wenn im gleichen Netzwerk."
#
# ─── WAS ES VORHER GAB ──────────────────────────────────────────────────────
#
#   run_windows.bat   Doppelklick unter Windows — vollstaendig
#   start.sh          der KIOSK-Start auf dem Pi: wartet auf einen
#                     Wayland-Socket, erschiesst piwiz und zenity, startet
#                     Chromium im Vollbild. Auf einem Notebook laeuft davon
#                     nichts, und der Abbruch kommt beim Wayland-Socket —
#                     also mit einer Meldung ueber ein fehlendes Fenster,
#                     nicht ueber die Sache.
#
# Fuer Linux und macOS fehlte damit genau das, was Windows hatte: EIN Befehl.
#
# Der Server bindet an alle Schnittstellen; `main.py` gibt die Adresse aus,
# unter der andere Geraete im selben Netz drankommen. Mit `--host 127.0.0.1`
# bleibt er auf diesem Rechner.

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[LZ] $PY nicht gefunden. Python 3.10+ installieren." >&2
  exit 1
fi

# Eine eigene Umgebung, damit die Abhaengigkeiten nicht im System landen.
# Sie liegt neben dem Repo und wird nur angelegt, wenn sie fehlt.
if [ ! -x ".venv/bin/python" ]; then
  echo "[LZ] Lege virtuelle Umgebung .venv an ..."
  "$PY" -m venv .venv
fi
VENV_PY=".venv/bin/python"

echo "[LZ] Installiere Abhaengigkeiten ..."
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements.txt

mkdir -p videos images audio

# `--dummy` wird NICHT gesetzt: `sensor.py` erkennt selbst, ob `gpiozero`
# und ein GPIO-Chip da sind, und faellt sonst zurueck. Ein Schalter, der das
# von aussen erzwingt, wuerde auf einem Pi den echten Sensor abschalten —
# und dieses Skript soll auch dort laufen koennen.
echo "[LZ] Starte Server ..."
exec "$VENV_PY" main.py "$@"

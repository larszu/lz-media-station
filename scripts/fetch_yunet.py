#!/usr/bin/env python3
"""Laedt das optionale YuNet-Gesichtsmodell fuer die Kamera-Abstandsquelle.

Die Kamera-Quelle (`camera_sensor.py`) funktioniert OHNE dieses Modell: fehlt
es, nutzt sie den in OpenCV mitgelieferten Haar-Cascade (kein Download, laeuft
offline sofort). YuNet ist die genauere Kuer -- ein ~233 KB grosses,
MIT-lizenziertes ONNX-Modell aus dem OpenCV Model Zoo.

Aufruf:
    python3 scripts/fetch_yunet.py

Legt die Datei unter `models/face_detection_yunet.onnx` ab. Danach nutzt die
Station beim naechsten Start automatisch YuNet statt des Haar-Cascade.

Quelle (MIT): https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
"""
import hashlib
import os
import sys
import urllib.request

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(WURZEL, "models", "face_detection_yunet.onnx")

# Mehrere Spiegel, weil raw.githubusercontent LFS-Zeiger statt der Binaerdatei
# liefern kann. Der erste erreichbare, der eine ONNX-Datei zurueckgibt, gewinnt.
QUELLEN = [
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "https://raw.githubusercontent.com/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
]

# ONNX-Dateien beginnen mit dem Protobuf-Feld 0x08 (ir_version). Ein
# LFS-Zeiger beginnt mit dem ASCII-Text "version https://git-lfs...". So laesst
# sich eine echte Modelldatei von einem Zeiger unterscheiden, ohne zu raten.
def ist_onnx(daten):
    return len(daten) > 1000 and not daten.lstrip().startswith(b"version http")


def main():
    os.makedirs(os.path.dirname(ZIEL), exist_ok=True)
    for url in QUELLEN:
        try:
            print(f"[YuNet] lade {url}")
            with urllib.request.urlopen(url, timeout=30) as antwort:
                daten = antwort.read()
        except Exception as e:
            print(f"[YuNet]   fehlgeschlagen: {e}")
            continue
        if not ist_onnx(daten):
            print("[YuNet]   Antwort ist kein ONNX (evtl. LFS-Zeiger) -- naechste Quelle")
            continue
        with open(ZIEL, "wb") as f:
            f.write(daten)
        pruef = hashlib.sha256(daten).hexdigest()[:16]
        print(f"[YuNet] gespeichert: {ZIEL} ({len(daten)} Bytes, sha256:{pruef}...)")
        return 0
    print("[YuNet] Kein Spiegel lieferte das Modell. Die Kamera nutzt weiter den "
          "Haar-Cascade -- das ist in Ordnung, nur etwas ungenauer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

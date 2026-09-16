# models/

Optionale Modelle fuer die **Kamera-Abstandsquelle** (`camera_sensor.py`).

## `face_detection_yunet.onnx` (optional)

YuNet-Gesichtsdetektor aus dem OpenCV Model Zoo — ~233 KB, **MIT-lizenziert**.
Genauer als der Haar-Cascade, laeuft auf einer Pi-CPU in Echtzeit.

**Die Kamera funktioniert auch ohne diese Datei.** Fehlt sie, nutzt
`camera_sensor.py` den in OpenCV mitgelieferten Haar-Cascade — kein Download
noetig, laeuft offline sofort, nur etwas ungenauer. Ist die Datei da, wird
beim naechsten Start automatisch YuNet genutzt.

Holen:

```bash
python3 scripts/fetch_yunet.py
```

Die Datei ist bewusst **nicht eingecheckt** (Binaerblob, per Git LFS im
Upstream) — sie wird bei Bedarf geladen. Quelle:
<https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>

"""Kamera-basierte Abstandsschaetzung — plattformuebergreifend (Pi/Mac/Windows).

Alternative zum Ultraschallsensor: statt eines HC-SR04 am GPIO schaetzt diese
Quelle den Abstand des naechsten Besuchers aus einem gewoehnlichen Webcam-Bild.
Sie erfuellt dieselbe Schnittstelle wie `SensorThread` (`distance` in Metern
oder `None`, `start`, `stop`, `status`) und ist damit im `Controller`
austauschbar.

WARUM OPENCV + YUNET (recherchiert 2026-09-16, siehe docs/sensoren.md):
* `opencv-python-headless` hat fertige Wheels fuer Raspberry Pi (aarch64),
  macOS (Intel + Apple Silicon) und Windows — ein `pip install`, kein
  Kompilieren, keine Torch-Abhaengigkeit. Lizenz Apache-2.0/MIT.
* YuNet (`cv2.FaceDetectorYN`) ist ein ~233 KB grosses, MIT-lizenziertes
  ONNX-Modell, das auf einer Pi-CPU in Echtzeit laeuft und deutlich genauer
  ist als ein Haar-Cascade. Ist die Modelldatei da, wird sie genutzt; fehlt
  sie, faellt die Quelle auf den in OpenCV mitgelieferten Haar-Cascade zurueck
  (kein Download noetig, funktioniert offline sofort).
* YOLO waere genauer fuer viele Personen auf Distanz, ist aber AGPL-lizenziert
  und auf dem Pi ohne Export zu langsam. MediaPipe braucht glibc >= 2.28.
  Beides bewusst NICHT der Standard.

ENTFERNUNG (Lochkamera-Modell / Strahlensatz):

    distance_m = (GESICHTSBREITE_M * brennweite_px) / gesichtsbreite_px

Die Brennweite ist pro Kamera+Aufloesung fest. Kalibrieren: ein Gesicht in
bekanntem Abstand D aufnehmen, seine Pixelbreite P messen, dann
`brennweite_px = P * D / GESICHTSBREITE_M`. Der Wert steht in der Konfiguration
(`camera_focal_px`) und laesst sich im Admin einstellen. Die Schaetzung taugt
fuer eine Schwelle („jemand ist naeher als ~1,5 m"), nicht fuer Millimeter.

GRENZE (ehrlich dokumentiert): `cv2.VideoCapture(index)` spricht UVC-/USB-
Webcams auf allen drei Systemen an. Die Pi-KAMERA am CSI-Anschluss laeuft unter
aktuellem Raspberry Pi OS ueber libcamera und ist so nicht immer ein
VideoCapture-Geraet — dort eine USB-Webcam nutzen oder libcamera als
V4L2-Geraet bereitstellen. Details in docs/sensoren.md.
"""
import os
import threading
import time

from sensor import AbstandsQuelle

#: Durchschnittliche Gesichtsbreite (Schlaefe zu Schlaefe) eines Erwachsenen.
#: Referenz fuer den Strahlensatz; bewusst eine Konstante und kein Regler —
#: kalibriert wird ueber die Brennweite, nicht ueber die Kopfgroesse.
GESICHTSBREITE_M = 0.16

#: Erkennungsbreite in Pixeln. Das Bild wird vor der Erkennung auf diese Breite
#: skaliert — schneller auf der Pi-CPU, und die Brennweite bezieht sich damit
#: auf eine feste Aufloesung, egal was die Kamera liefert.
ERKENNUNGSBREITE_PX = 320

#: Pfad, an dem das optionale YuNet-Modell gesucht wird.
_MODELL_PFAD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "models", "face_detection_yunet.onnx")


def schaetze_abstand(gesichtsbreite_px, brennweite_px):
    """Abstand in Metern aus der Gesichtsbreite im Bild (Lochkamera-Modell).

    Reine Funktion, damit die Rechnung ohne Kamera und ohne Thread pruefbar
    ist. Gibt `None` bei unbrauchbarer Eingabe (0 oder negativ), statt zu
    werfen oder durch Null zu teilen.
    """
    if gesichtsbreite_px is None or gesichtsbreite_px <= 0 or brennweite_px <= 0:
        return None
    return (GESICHTSBREITE_M * brennweite_px) / gesichtsbreite_px


def groesstes_gesicht(gesichter):
    """Aus einer Liste von (x, y, w, h) das breiteste zurueckgeben — das ist
    das naechste. Leere Liste -> None.

    Ebenfalls rein und ohne OpenCV, damit die Auswahl testbar bleibt.
    """
    breitestes = None
    for kasten in gesichter:
        w = kasten[2]
        if breitestes is None or w > breitestes[2]:
            breitestes = kasten
    return breitestes


class CameraSensorThread(AbstandsQuelle):
    """Schaetzt den Abstand des naechsten Besuchers aus dem Kamerabild.

    Fehlt OpenCV oder laesst sich die Kamera nicht oeffnen, misst der Thread
    nichts: `distance` bleibt `None`, `status` nennt den Grund. Wie beim
    Ultraschallsensor werden KEINE Werte erfunden.
    """

    LABEL = "Kamera"

    def __init__(self, camera_index=0, focal_px=700.0):
        super().__init__()
        self.camera_index = camera_index
        self.focal_px = focal_px
        self._cap = None
        self._detector = None
        self._detector_art = None  # "yunet" | "haar" | None

    # -- Aufbau -------------------------------------------------------------

    def _oeffne_kamera(self, cv2):
        """VideoCapture mit passendem Backend je Betriebssystem."""
        import sys
        if sys.platform.startswith("win"):
            backend = cv2.CAP_DSHOW      # DirectShow: schnelles Oeffnen unter Windows
        elif sys.platform == "darwin":
            backend = cv2.CAP_AVFOUNDATION
        else:
            backend = cv2.CAP_ANY        # Linux/Pi: V4L2 ueber die Auto-Wahl
        cap = cv2.VideoCapture(self.camera_index, backend)
        return cap

    def _baue_detektor(self, cv2):
        """YuNet, wenn das Modell da ist; sonst der mitgelieferte Haar-Cascade."""
        if os.path.isfile(_MODELL_PFAD) and hasattr(cv2, "FaceDetectorYN_create"):
            try:
                det = cv2.FaceDetectorYN_create(
                    _MODELL_PFAD, "", (ERKENNUNGSBREITE_PX, ERKENNUNGSBREITE_PX),
                    score_threshold=0.7)
                self._detector = det
                self._detector_art = "yunet"
                return
            except Exception as e:
                print(f"[Kamera] YuNet-Modell unbrauchbar ({e}) — nehme Haar-Cascade")
        pfad = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._detector = cv2.CascadeClassifier(pfad)
        self._detector_art = "haar"

    def _erkenne(self, cv2, frame):
        """Liste von (x, y, w, h) im skalierten Bild zurueckgeben."""
        if self._detector_art == "yunet":
            h, w = frame.shape[:2]
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(frame)
            if faces is None:
                return []
            return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]
        grau = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gesichter = self._detector.detectMultiScale(grau, 1.2, 5, minSize=(24, 24))
        return [tuple(int(v) for v in g) for g in gesichter]

    # -- Schleife -----------------------------------------------------------

    def run(self):
        self._running = True
        try:
            import cv2
        except ImportError:
            self._setze_status("Kamera: opencv nicht installiert "
                               "(pip install opencv-python-headless)")
            print(f"[Kamera] {self._status} — es wird nicht ausgeloest")
            return

        self._cap = self._oeffne_kamera(cv2)
        if not self._cap or not self._cap.isOpened():
            self._setze_status(f"Kamera: Index {self.camera_index} nicht gefunden")
            print(f"[Kamera] {self._status} — es wird nicht ausgeloest")
            return

        self._baue_detektor(cv2)
        self._setze_status(f"Kamera aktiv (Index {self.camera_index}, {self._detector_art})")
        print(f"[Kamera] {self._status}")

        while self._running:
            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    # Kein Bild -> kein `_uebernimm`. Der letzte Wert veraltet
                    # von selbst nach STALE_AFTER_S; ein abgezogenes Kabel
                    # sieht nicht aus wie ein ruhiger Besucher.
                    time.sleep(0.1)
                    continue

                h, w = frame.shape[:2]
                skala = ERKENNUNGSBREITE_PX / float(w)
                klein = cv2.resize(frame, (ERKENNUNGSBREITE_PX, max(1, int(h * skala))))

                naechstes = groesstes_gesicht(self._erkenne(cv2, klein))
                if naechstes is not None:
                    abstand = schaetze_abstand(naechstes[2], self.focal_px)
                    if abstand is not None:
                        self._uebernimm(abstand)
                # Kein Gesicht -> nichts uebernehmen. `distance` faellt nach
                # STALE_AFTER_S auf None: niemand da = nicht nah.
            except Exception as e:
                print(f"[Kamera] Fehler: {e}")
            time.sleep(0.1)

    def _quelle_schliessen(self):
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass

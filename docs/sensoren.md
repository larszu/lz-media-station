# Abstandsquellen der LZ Media Station

Die Station spielt die **Nah**-Szene, wenn jemand näher als die eingestellte
Schwelle ist, sonst die **Fern**-Szene. Woher der Abstand kommt, entscheidet
`sensor_type` in der Konfiguration (im Admin unter **Abstandsquelle**):

| `sensor_type` | Quelle | Läuft auf |
|---|---|---|
| `auto` (Vorgabe) | HC-SR04 — und wenn es den nicht gibt, die Kamera | überall |
| `ultrasonic` | nur der HC-SR04 Ultraschallsensor am GPIO | Raspberry Pi |
| `camera` | Webcam + Gesichtserkennung (OpenCV) | Pi, **macOS, Windows** |
| `button` | GPIO-Taster: der Besucher **drückt**, statt gemessen zu werden | Raspberry Pi |

Alle drei liefern denselben Wert — den Abstand des nächsten Besuchers in
Metern, oder „unbekannt" (beim Taster ist dieser Abstand eine Übersetzung,
siehe unten). **Ist keine Hardware angeschlossen, wird nichts erfunden**
(kein Demo-Modus): die Station löst nicht aus, und der Admin zeigt im Klartext,
warum. Das war früher anders und für Endnutzer irreführend — ein nicht
angeschlossener Sensor sah aus wie ein ruhiger Besucher.

---

## Rückfall auf die Kamera (`sensor_type: "auto"`, Issue #13)

„Wenn kein Sensor verfügbar, dann Abstandserkennung mit Kamera." Genau das tut
`auto`, und es ist seit Issue #13 die Vorgabe: die Station startet den
HC-SR04, und **nur wenn es ihn auf diesem Gerät nicht gibt**, übernimmt die
Kamera. Auf einem Mac oder Windows-Rechner heißt das: es läuft sofort etwas,
ohne dass jemand erst in den Admin geht.

**Woran „nicht verfügbar" erkannt wird — und woran nicht.** Nicht an einem
fehlenden Messwert. Kein Messwert heißt „niemand steht davor" genauso wie
„kein Sensor angeschlossen"; wer das gleichsetzt, schaltet mitten im Betrieb
auf die Kamera um, weil gerade niemand im Raum war, und wieder zurück, sobald
jemand kommt. Erkannt wird es daran, dass die Quelle es **selbst sagt**
(`AbstandsQuelle.verfuegbar`), nach ihrer Initialisierung. Solange das noch
nicht feststeht, wird gewartet — höchstens zwei Sekunden, danach bleibt es
beim Sensor: im Zweifel die konfigurierte Quelle und nicht die geratene.

**Einmal, nicht ständig.** Der Rückfall passiert beim Start. Ein Sensor, der
später ausfällt, wird **nicht** durch die Kamera ersetzt: ein Ausfall im
Betrieb gehört gemeldet und nicht kaschiert. Die Kamera hat eine andere
Reichweite, eine andere Genauigkeit und ein anderes Blickfeld; dass die
Station „irgendwie weiterläuft", wäre schlimmer als dass sie schweigt.

**`ultrasonic` bleibt** und ist nicht dasselbe wie `auto`: es ist die Ansage
„an dieser Station gehört ein Sensor hin". Fällt er aus, soll sie schweigen
und es melden.

Im Admin steht der Rückfall im Klartext: „Kamera aktiv (Index 0, YuNet)
(Rückfall: kein Ultraschallsensor)". „Kamera aktiv" allein ließe offen, ob das
jemand so eingestellt hat oder ob der Sensor fehlt.

---

## Kamera-Erkennung einrichten

### 1. OpenCV installieren

```bash
pip install -r requirements-camera.txt   # opencv-python-headless
```

Fertige Wheels gibt es für **Raspberry Pi (aarch64)**, **macOS (Intel + Apple
Silicon)** und **Windows** — kein Kompilieren, keine Torch-Abhängigkeit.

### 2. Im Admin auf „Kamera" umstellen

Unter **Systemeinstellungen → Abstandsquelle** „Kamera" wählen, **Kamera-Index**
setzen (meist `0`) und speichern. Die Quelle wird beim **Programmstart** gebaut
(wie die GPIO-Pins) — nach dem Umstellen also die Station bzw. den Prozess neu
starten (auf dem Pi „Pi neu starten", lokal den Server neu starten), damit die
Kamera geöffnet wird.

### 3. Brennweite kalibrieren (einmalig pro Kamera + Auflösung)

Die Entfernung kommt aus dem **Lochkamera-Modell** (Strahlensatz):

```
distance_m = (GESICHTSBREITE_M * brennweite_px) / gesichtsbreite_px
```

`GESICHTSBREITE_M` ist fest (0,16 m, Schläfe zu Schläfe eines Erwachsenen).
Kalibriert wird die **Brennweite**, nicht die Kopfgröße:

1. Eine Person in **bekanntem Abstand D** (z. B. 1,00 m) vor die Kamera stellen.
2. Die **Pixelbreite P** des erkannten Gesichts ablesen (bezogen auf die interne
   Erkennungsbreite von 320 px — die Live-Distanz im Admin hilft: solange die
   Brennweite noch nicht stimmt, ist die angezeigte Distanz proportional falsch).
3. `brennweite_px = P * D / 0.16` rechnen und als **Brennweite (px)** eintragen.

Praktisch reicht meist: Brennweite so lange nachstellen, bis die angezeigte
Distanz bei bekanntem Abstand passt. Die Schätzung taugt für eine **Schwelle**
(„jemand ist näher als ~1,5 m"), nicht für Millimeter.

### 4. Optional: genaueres Modell (YuNet)

Ohne Extra-Datei nutzt die Kamera den in OpenCV **mitgelieferten Haar-Cascade**
— kein Download, läuft offline sofort, nur etwas ungenauer und frontal-lastig.
Für mehr Genauigkeit das **YuNet**-Modell holen (~233 KB, MIT-Lizenz):

```bash
python3 scripts/fetch_yunet.py    # legt models/face_detection_yunet.onnx an
```

Ist die Datei da, nutzt die Station beim nächsten Start automatisch YuNet.

### Grenze: Pi-Kamera am CSI-Anschluss

`cv2.VideoCapture(index)` spricht **UVC-/USB-Webcams** auf allen drei Systemen
an. Die **Pi-Kamera am CSI-Ribbon** läuft unter aktuellem Raspberry Pi OS über
`libcamera` und ist so nicht immer ein VideoCapture-Gerät. Zwei Wege: eine
USB-Webcam nutzen, oder libcamera als V4L2-Gerät bereitstellen. Eine native
`picamera2`-Anbindung ist bewusst nicht Teil dieser Quelle (Pi-spezifisch,
bräche die Plattformunabhängigkeit).

---

## Warum OpenCV + YuNet (und nicht YOLO / MediaPipe)

Recherche 2026-09-16 für „plattformübergreifend, leicht genug für einen Pi,
Distanz aus einem Monokamera-Bild":

- **OpenCV `opencv-python-headless` + YuNet** — permissive Lizenz (Apache-2.0 /
  MIT), fertige Wheels für alle drei Systeme, YuNet läuft auf einer Pi-CPU in
  Echtzeit, Gesichtsbreite ist die **stabilste** Referenz für die
  Distanzschätzung. **Gewählt.**
- **MediaPipe** — ebenfalls leicht und Apache-2.0, aber die aarch64-Wheels
  brauchen glibc ≥ 2.28 (Pi OS Bookworm+); als Standard zu heikel.
- **Ultralytics YOLO** — genauer für viele Personen auf Distanz, aber
  **AGPL-3.0** (Netzwerk-Copyleft) und auf dem Pi ohne Export nach ONNX/NCNN zu
  langsam (~3 fps roh). Nur bei echtem Bedarf an Personen-Zählung.

---

## Welcher Sensor für welchen Zweck?

Für den Fall „jemand tritt an eine Ausstellungs-Station heran" gibt es mehr als
Ultraschall und Kamera. Kurzvergleich als Entscheidungshilfe:

| Sensor | Reichweite | Liefert | Sichtfeld | Robustheit | Privatsphäre | ~Preis | Pi-Bus |
|---|---|---|---|---|---|---|---|
| **HC-SR04 Ultraschall** | 2 cm – ~4 m | **echte Distanz** | schmaler Kegel ~15–30° | licht­unabhängig; weiche/schräge Flächen (Kleidung, Schaum) schlucken das Echo; nur nächstes Objekt | keine | ~2–4 € | GPIO (Echo braucht **Spannungsteiler** auf 3,3 V) |
| **PIR (HC-SR501)** | bis ~7 m | **nur Bewegung** | weit ~110–120° | reagiert nur auf **Änderung** von Körperwärme → **verpasst still Stehende**; HVAC/Sonne stören | keine | ~1–3 € | GPIO (1 Pin) |
| **ToF-Laser (VL53L0X/L1X)** | L0X bis 2 m, **L1X bis 4 m, 50 Hz** | **echte Distanz** | schmal ~15–27° | indoor sehr gut, schnell, genau; Sonne/Spiegel stören; nur nächstes Objekt | keine | ~5–12 € | **I2C** (3,3 V) |
| **mmWave-Radar (HLK-LD2410)** | ~5–6 m | **Distanz (grob) + Präsenz** | weit ±60° | erkennt **bewegte UND stehende** Personen (Mikrobewegung/Atmung), licht-/kleidungs-/glas­unabhängig; kann überempfindlich sein | keine (kein Bild) | ~3–8 € | **UART** (256000 Baud) + OUT-Pin |
| **IR-Lichtschranke** | cm bis mehrere m | **nur Präsenz** (Linie) | eine Linie | sehr deterministisch; braucht ausgerichteten Sender+Empfänger; starke Sonne blendet | keine | ~2–5 €/Paar | GPIO |
| **Kamera** | mehrere m (objektiv-/auflösungsabhängig) | **geschätzte Distanz** + Zählung/Position | weit | robust bei mehreren Personen; **schwächer bei schlechtem/Gegenlicht**; höchste CPU-Last | **höchste** — Bilder von Besuchern, Hinweis-/Datenschutzpflicht | Kamera ~5–25 € | CSI oder USB |

### Empfehlung nach Anwendungsfall

- **„Jemand ist im Auslöse-Abstand" (die heutige Aufgabe):** **HC-SR04**
  genügt und ist am günstigsten; für saubere, schnelle Distanz bis 4 m ohne
  5-V-Teiler ist der **VL53L1X (ToF)** das Upgrade.
- **Person tritt heran UND bleibt stehen** (Kiosk, der beim Lesen nicht
  „einschläft"): **HLK-LD2410 mmWave** — die einzige günstige Option, die eine
  **regungslose** Person zuverlässig hält, licht- und kleidungsunabhängig. Der
  beste Ein-Sensor-Standard für eine Ausstellung.
- **Nur „ist überhaupt jemand da?", stromsparend:** **PIR** — akzeptiert aber
  nur Bewegung und verpasst Stehende.
- **„Genau diese Linie überschritten"** (Durchgang, Podest, deterministisch):
  **IR-Lichtschranke**.
- **Personen zählen / nächste unter mehreren / reichere Interaktion** (und
  Privatsphäre/Licht sind beherrschbar): **Kamera** — idealerweise **kombiniert**
  mit PIR/mmWave, das die Kamera nur einschaltet, wenn wirklich jemand da ist
  (spart CPU und reduziert die Dauer-Aufnahme).

### Quellen

- OpenCV YuNet Model Zoo (Größe, MIT, WIDER-Face-Genauigkeit): <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>
- opencv-python Wheels (aarch64/mac-arm64/Windows): <https://pypi.org/project/opencv-python/>
- Ultralytics YOLO (Größe/AGPL-3.0): <https://github.com/ultralytics/ultralytics>
- MediaPipe (Wheel-Plattformen): <https://pypi.org/project/mediapipe/>
- Monokamera-Distanz (Formel + Kalibrierung): <https://github.com/Asadullah-Dal17/Distance_measurement_using_single_camera>
- VL53L1X ToF: <https://learn.adafruit.com/adafruit-vl53l1x> · HLK-LD2410 mmWave: <https://www.espboards.dev/sensors/ld2410/>


---

## Taster (`sensor_type: "button"`)

Viele Exponate wollen nicht „jemand steht nah", sondern **„jemand hat
gedrückt"**: ein Knopf am Podest, der die Vorführung startet. Das ist eine
Absicht und kein Zufall — wer vorbeigeht, löst nichts aus.

Einstellungen im Admin unter **Abstandsquelle → Taster**:

| Feld | Bedeutung |
|---|---|
| **Taster GPIO (BCM)** | Der Pin, an dem der Taster hängt (Vorgabe 17) |
| **Haltezeit nach Druck** | Wie lange ein Druck als „nah" gilt (Vorgabe 30 s) |

Verdrahtung: Taster zwischen dem GPIO-Pin und **GND**. Der interne Pull-up
wird gesetzt (`pull_up=True`), ein Widerstand ist nicht nötig. Gegen das
Prellen mechanischer Taster ist eine Entprellzeit von 50 ms eingebaut — ohne
sie meldet ein einziger Druck mehrere Flanken.

### Wie er sich einfügt

Die Station rechnet durchgehend mit einem Abstand (`dist <= threshold`). Der
Taster übersetzt sich in genau diese Sprache, statt einen zweiten Weg durch
die Zustandsmaschine zu öffnen:

| Zustand | gemeldeter „Abstand" |
|---|---|
| gedrückt (Haltezeit läuft) | 0,0 m — unter jeder erlaubten Schwelle |
| sonst | 25,0 m — über jeder erlaubten Schwelle (Maximum ist 20 m) |

**„Frei" ist ein Wert und nicht „keine Messung".** `None` würde von der
Zustandsprüfung zu Recht als Störung gemeldet — ein nicht gedrückter Taster
ist aber keine Störung, sondern die Antwort „gerade niemand". Die Station muss
zwischen „Taster sagt nein" und „Taster ist abgerissen" unterscheiden können.

**Kein Mittelwert.** Die anderen Quellen mitteln über fünf Messwerte, um
Ausreißer zu dämpfen. Zwischen 0,0 und 25,0 gemittelt kämen Zwischenwerte
heraus, die es nie gab — und je nach Schwelle schaltete die Station auf einem
Wert, den niemand ausgelöst hat. Ein Taster ist digital, deshalb
`_filter_size = 1`.

Im Admin zeigt die Statuszeile deshalb **Gedrückt / Frei** statt einer
Entfernung: „25,00 m" wäre ehrlich gemeint und trotzdem irreführend.

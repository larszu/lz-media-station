"""Taster als Ausloeser — statt Abstand zu messen, drueckt der Besucher.

WARUM ES DAS GIBT. Viele Exponate wollen nicht „jemand steht nah", sondern
„jemand hat gedrueckt": ein Knopf am Podest, der die Vorfuehrung startet. Das
ist eine Absicht und kein Zufall — wer vorbeigeht, loest nichts aus.

WIE ES SICH EINFUEGT. Die Station rechnet durchgehend mit einem Abstand
(`dist <= threshold`). Der Taster uebersetzt sich deshalb in genau diese
Sprache, statt einen zweiten Weg durch die Zustandsmaschine zu eroeffnen:

    gedrueckt (und Haltezeit laeuft)  ->  NAH_M   (0,0 m — unter jeder Schwelle)
    sonst                             ->  FERN_M  (25,0 m — ueber jeder Schwelle;
                                                   die groesste erlaubte
                                                   Schwelle ist 20 m)

FERN_M ist bewusst ein WERT und nicht `None`. `None` heisst „kein gueltiger
Messwert", und die Zustandspruefung meldet das zu Recht als Stoerung. Ein
nicht gedrueckter Taster ist aber keine Stoerung, sondern die Antwort
„gerade niemand" — die Station muss zwischen „Taster sagt nein" und „Taster
ist abgerissen" unterscheiden koennen.

KEIN MITTELWERT. Die Basis mittelt sonst ueber fuenf Messwerte. Zwischen 0,0
und 25,0 gemittelt kaemen Zwischenwerte heraus, die es nie gab — und je nach
Schwelle schaltete die Station auf einem Wert, den niemand ausgeloest hat.
Ein Taster ist digital; deshalb `_filter_size = 1`.
"""
import time

from sensor import AbstandsQuelle, GPIOZERO_AVAILABLE

#: „Jemand ist da" — unter jeder erlaubten Schwelle (Minimum 0,05 m).
NAH_M = 0.0

#: „Gerade niemand" — ueber jeder erlaubten Schwelle (Maximum 20,0 m).
FERN_M = 25.0


class ButtonSensorThread(AbstandsQuelle):
    """Ein GPIO-Taster als Ausloeser.

    `haltezeit_s` bestimmt, wie lange ein Druck als „nah" gilt. Ohne sie waere
    die Nah-Szene vorbei, sobald der Finger den Knopf verlaesst.
    """

    LABEL = "Taster"

    def __init__(self, pin=17, haltezeit_s=30.0):
        super().__init__()
        self.pin = pin
        self.haltezeit_s = haltezeit_s
        self._button = None
        # Digital: kein Mittelwert ueber fuenf Werte (siehe Modulkopf).
        self._filter_size = 1
        #: Zeitpunkt, bis zu dem der letzte Druck noch gilt.
        self._gilt_bis = 0.0

    def run(self):
        self._running = True
        if not GPIOZERO_AVAILABLE:
            self._setze_verfuegbar(False)
            self._setze_status("kein Taster: gpiozero nicht installiert")
            print(f"[Taster] {self._status} — es wird nicht ausgeloest")
            return
        try:
            from gpiozero import Button
            # `bounce_time` gegen das Prellen mechanischer Taster: ohne das
            # meldet ein einziger Druck mehrere Flanken.
            self._button = Button(self.pin, pull_up=True, bounce_time=0.05)
            self._setze_verfuegbar(True)
            self._setze_status(f"Taster an BCM {self.pin} "
                               f"(Haltezeit {self.haltezeit_s:.0f} s)")
            print(f"[Taster] {self._status} initialisiert")
        except Exception as e:
            self._setze_verfuegbar(False)
            self._setze_status(f"kein Taster: GPIO-Fehler ({e})")
            print(f"[Taster] {self._status} — es wird nicht ausgeloest")
            return

        while self._running:
            try:
                jetzt = time.monotonic()
                if self._button.is_pressed:
                    self._gilt_bis = jetzt + self.haltezeit_s
                self._uebernimm(NAH_M if jetzt < self._gilt_bis else FERN_M)
            except Exception as e:
                print(f"[Taster] Fehler: {e}")
            time.sleep(0.1)

    def _quelle_schliessen(self):
        if self._button:
            try:
                self._button.close()
            except Exception:
                pass

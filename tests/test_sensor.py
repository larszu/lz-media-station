"""Tests fuer `SensorThread` in `sensor.py`.

Der Sensor misst den Abstand des Besuchers und entscheidet damit, ob die
Station die Nah- oder die Fern-Szene spielt. Die einzige Logik darin ist ein
gleitender Mittelwert ueber fuenf Messwerte -- der Rest ist GPIO.

Bewusst NICHT getestet: die Messschleife in `run()`. Sie laeuft mit
`time.sleep(0.1)` in einem Thread; sie zu testen hiesse, auf Zeit zu warten,
und zeitabhaengige Tests sind der zuverlaessigste Weg, eine CI unglaubwuerdig
zu machen. Geprueft wird stattdessen, was ohne Warten pruefbar ist: der
Aufbau, die Dummy-Erkennung, das Filterfenster und das Anhalten.

Lauf: `python3 -m unittest discover -s tests -v`
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sensor  # noqa: E402


class Aufbau(unittest.TestCase):
    def test_ohne_gpiozero_faellt_er_auf_dummy_zurueck(self):
        # Auf einem Rechner ohne gpiozero MUSS der Dummy greifen -- sonst
        # stuerzt die Station beim Start ab, statt ohne Sensor weiterzulaufen.
        s = sensor.SensorThread()
        if not sensor.GPIOZERO_AVAILABLE:
            self.assertTrue(s.use_dummy, 'ohne gpiozero muss use_dummy greifen')

    def test_dummy_laesst_sich_erzwingen(self):
        self.assertTrue(sensor.SensorThread(use_dummy=True).use_dummy)

    def test_pins_sind_uebernehmbar(self):
        s = sensor.SensorThread(trigger_pin=5, echo_pin=6)
        self.assertEqual((s.trigger_pin, s.echo_pin), (5, 6))

    def test_standardpins_sind_23_und_24(self):
        # Die Belegung steht so in der Verdrahtungsanleitung; sie still zu
        # aendern wuerde jede bestehende Installation stumm machen.
        s = sensor.SensorThread()
        self.assertEqual((s.trigger_pin, s.echo_pin), (23, 24))

    def test_laeuft_als_daemon(self):
        # Sonst haengt der Prozess beim Beenden am Sensor-Thread.
        self.assertTrue(sensor.SensorThread().daemon)

    def test_vor_der_ersten_messung_gibt_es_keinen_abstand(self):
        # HIER STAND DAS GEGENTEIL, und die Begruendung war ehrlich gemeint:
        # „`distance` wird ohne Pruefung in Vergleiche gesteckt; None waere
        # ein TypeError im ersten Zehntelsekunden-Fenster nach dem Start."
        #
        # Der Satz stimmte — und beschrieb damit den Defekt, statt ihn zu
        # verhindern. Der ungeprueft verglichene Wert war 0.0, und 0,0 m
        # heisst „jemand steht direkt vor dem Sensor". Der Test hielt also
        # fest, dass die Station beim Start einen Besucher meldet.
        #
        # Die Pruefung gehoert an die Auswertung (`main.py` behandelt `None`
        # jetzt als „nicht nah"), nicht in einen Startwert, der zufaellig auch
        # eine Bedeutung hat.
        self.assertIsNone(sensor.SensorThread().distance)


class Filterfenster(unittest.TestCase):
    """Der gleitende Mittelwert -- ohne die Thread-Schleife nachgebaut.

    Der Test spiegelt die Rechnung aus `run()` gegen die Zusicherung, dass das
    Fenster genau `_filter_size` Werte haelt. Waechst das Fenster unbegrenzt,
    wird der Sensor mit der Laufzeit immer traeger; ist es zu klein, zittert
    die Zonenumschaltung.
    """

    def push(self, s, raw):
        # Ruft die PRODUKTIONS-Methode auf, statt Fenster und Mittelwert
        # nachzubauen. Der Nachbau stand hier vorher und war bereits
        # auseinandergelaufen: als `run()` einen Zeitstempel setzte, kannte
        # ihn nur die Schleife, und der Test pruefte einen Zustand, den es im
        # Betrieb nicht gibt.
        s._uebernimm(raw)

    def test_fenstergroesse_ist_fuenf(self):
        self.assertEqual(sensor.SensorThread()._filter_size, 5)

    def test_mittelwert_ueber_wenige_werte(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in (1.0, 2.0, 3.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 2.0)

    def test_fenster_waechst_nicht_ueber_die_grenze(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in range(20):
            self.push(s, float(v))
        self.assertEqual(len(s._values), 5, 'das Fenster laeuft voll statt zu rollen')

    def test_alte_werte_fallen_hinten_raus(self):
        s = sensor.SensorThread(use_dummy=True)
        for v in (10.0, 10.0, 10.0, 10.0, 10.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 10.0)
        for v in (0.0, 0.0, 0.0, 0.0, 0.0):
            self.push(s, v)
        self.assertAlmostEqual(s.distance, 0.0, msg='ein alter Wert haengt noch im Fenster')


class Anhalten(unittest.TestCase):
    def test_stop_setzt_das_laufflag(self):
        s = sensor.SensorThread(use_dummy=True)
        s._running = True
        s.stop()
        self.assertFalse(s._running)

    def test_stop_ohne_sensor_wirft_nicht(self):
        # Wird gestoppt, bevor `run()` je lief, ist `_sensor` None.
        sensor.SensorThread(use_dummy=True).stop()


if __name__ == "__main__":
    unittest.main()


class KeinMesswertIstEinEigenerZustand(unittest.TestCase):
    """Der Befund aus dem Defektformen-Sweep (Backlog B-36), Form
    `zustand-nach-fehler`.

    `SensorThread._distance` startete bei **0.0**, und `distance` gab diese
    Null als Messwert aus. Null Meter heisst aber nicht „noch nichts
    gemessen", sondern „jemand steht direkt vor dem Sensor" — und die
    Auswertung in `main.py` fragt genau `dist <= threshold`.

    Damit war `is_near` ab dem allerersten Schleifendurchlauf wahr:

    * Beim Start ging die Station nach `delay_s` in die Nah-Szene, ohne dass
      jemand da war.
    * Antwortete der Sensor gar nicht (GPIO-Fehler in jeder Runde), blieb sie
      dauerhaft dort — ein toter Sensor sah aus wie ein Besucher, der sich
      nicht vom Fleck ruehrt.
    * Fiel er im Betrieb aus, blieb der zuletzt gemessene Wert stehen, ohne
      Ablauf: die Anzeige im Admin zeigte weiter eine plausible Zahl.

    Deshalb ist „kein Messwert" jetzt ein eigener Wert (`None`) und kein
    Zahlenwert, der zufaellig auch etwas bedeutet.
    """

    def test_ohne_messung_ist_der_abstand_unbekannt(self):
        s = sensor.SensorThread(use_dummy=True)
        self.assertIsNone(s.distance, 'vor der ersten Messung gibt es keinen Abstand')

    def test_null_ist_kein_ersatz_fuer_unbekannt(self):
        # Der eigentliche Defekt in einem Satz: 0.0 ist ein gueltiger, sehr
        # naher Abstand. Wer ihn als Startwert nimmt, meldet einen Besucher.
        s = sensor.SensorThread(use_dummy=True)
        self.assertNotEqual(s.distance, 0.0)

    def test_ein_messwert_wird_gemeldet(self):
        s = sensor.SensorThread(use_dummy=True)
        s._values = [1.2, 1.4]
        s._distance = 1.3
        s._measured_at = time.monotonic()
        self.assertAlmostEqual(s.distance, 1.3)

    def test_ein_alter_messwert_gilt_nicht_mehr(self):
        # Ohne Ablauf blieb der letzte Wert ewig stehen. Ein Sensor, der
        # aufhoert zu antworten, haette die Station in ihrem Zustand
        # eingefroren, und nichts haette es gesagt.
        s = sensor.SensorThread(use_dummy=True)
        s._distance = 1.3
        s._measured_at = time.monotonic() - (sensor.STALE_AFTER_S + 0.5)
        self.assertIsNone(s.distance, 'ein veralteter Messwert ist keiner')

    def test_vor_der_ersten_messung_gibt_es_auch_keinen_zeitstempel(self):
        # `_measured_at = 0.0` waere kein „nie gemessen", sondern „vor sehr
        # langer Zeit gemessen". Das faellt heute nicht auf, weil der Ablauf
        # es abfaengt — aber es waere ein Startwert, der wieder etwas
        # bedeutet, und genau davon handelt dieser Befund.
        self.assertIsNone(sensor.SensorThread(use_dummy=True)._measured_at)

    def test_nur_eine_stelle_setzt_den_zeitstempel(self):
        """Der Zeitstempel wird an GENAU EINER Stelle gesetzt: `_uebernimm`.

        Ohne diese Zusicherung ist der Fix eine Zeile weit von seiner
        Umkehrung entfernt. Wer den Zeitstempel auch im `except`-Zweig
        fortschreibt — etwa um eine laute Log-Zeile ruhigzustellen —, macht
        den Ablauf wirkungslos: der letzte Wert gilt dann wieder ewig, und
        ein toter Sensor sieht aus wie ein ruhiger Besucher. Das ist keine
        hypothetische Sorge, sondern die Gegenprobe zu diesem Fix.
        """
        quelle = (Path(__file__).resolve().parent.parent / 'sensor.py').read_text()
        zuweisungen = [
            z.strip() for z in quelle.splitlines()
            if 'self._measured_at =' in z and 'None' not in z
        ]
        # Geprueft wird die ANZAHL und der ORT, nicht der Wortlaut. Die erste
        # Fassung verlangte woertlich `= time.monotonic()` und ging kaputt,
        # als die Zeit einmal vorher in eine Variable gelegt wurde — an der
        # Zusicherung hatte sich dabei nichts geaendert. Ein Waechter, der bei
        # einer folgenlosen Umschreibung rot wird, wird beim naechsten Mal
        # angepasst statt gelesen.
        self.assertEqual(len(zuweisungen), 1,
                         f'genau eine Stelle darf fortschreiben: {zuweisungen}')
        koerper = quelle.split('def _uebernimm(')[1].split('\n    @')[0]
        self.assertIn(zuweisungen[0], koerper,
                      'der Zeitstempel darf nur in `_uebernimm` fortgeschrieben werden')

    def test_nach_einem_ausfall_faengt_der_mittelwert_neu_an(self):
        """Der Ablauf bewachte den Zeitstempel — das Mittelwertfenster nicht.

        BEFUND (Defektformen-Sweep, Form `fixture-erreicht-grenze-nicht`,
        gemessen 2026-09-08). Nach einem Ausfall lagen die alten Werte noch im
        Fenster: der erste neue Messwert wurde mit vier Werten von VOR dem
        Ausfall gemittelt und galt sofort als frisch. Eine halbe Sekunde lang
        stand damit ein Abstand im Umlauf, den es nie gegeben hat — genau in
        dem Moment, in dem die Station entscheidet, ob jemand davorsteht.
        """
        s = sensor.SensorThread(use_dummy=True)
        for _ in range(5):
            s._uebernimm(3.0)          # der Raum ist leer
        self.assertAlmostEqual(s.distance, 3.0)

        # Der Sensor faellt aus; waehrenddessen tritt jemand heran.
        s._measured_at = time.monotonic() - (sensor.STALE_AFTER_S + 0.1)
        self.assertIsNone(s.distance, 'waehrend des Ausfalls gibt es keinen Wert')

        s._uebernimm(0.5)
        self.assertAlmostEqual(
            s.distance, 0.5,
            msg='der erste Wert nach dem Ausfall darf nicht mit den alten '
                'gemittelt werden — vorher kamen hier 2,5 m heraus')

    def test_ein_aussetzer_INNERHALB_der_grenze_leert_das_fenster_NICHT(self):
        # Die Gegenprobe. Waere jede Luecke ein Neuanfang, waere der
        # Mittelwertfilter wirkungslos — ein einzelner Ausreisser schluege
        # dann voll durch, und genau dagegen gibt es ihn.
        s = sensor.SensorThread(use_dummy=True)
        for _ in range(4):
            s._uebernimm(3.0)
        s._measured_at = time.monotonic() - (sensor.STALE_AFTER_S - 0.5)
        s._uebernimm(0.5)
        self.assertAlmostEqual(s.distance, (3.0 * 4 + 0.5) / 5,
                               msg='innerhalb der Grenze wird weiter gemittelt')

    def test_die_grenze_ist_grosszuegig_genug_fuer_einen_aussetzer(self):
        # Ein einzelner verschluckter Messwert darf die Station nicht
        # umschalten — die Schleife misst alle 0,1 s.
        s = sensor.SensorThread(use_dummy=True)
        s._distance = 1.3
        s._measured_at = time.monotonic() - 0.5
        self.assertAlmostEqual(s.distance, 1.3)
        self.assertGreaterEqual(sensor.STALE_AFTER_S, 1.0)

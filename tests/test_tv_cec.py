"""Tests fuer `tv_cec.py` — das optionale Abschalten des Fernsehers.

Absichtlich NICHT getestet: der tatsaechliche Schaltvorgang. Dafuer braeuchte
es einen Fernseher und ein CEC-faehiges HDMI-Kabel; ein Test, der davon
abhaengt, laeuft in keiner CI.

Getestet wird der Weg, der im Betrieb wirklich zaehlt: auf den allermeisten
Geraeten ist `cec-client` NICHT installiert. Dann muss die Funktion das sagen
und darf nicht werfen — die Medienwiedergabe haengt an dieser Zeile, und ein
fehlendes Hilfsprogramm darf eine Ausstellung nicht anhalten.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tv_cec  # noqa: E402


class OhneCecClient(unittest.TestCase):
    def test_nicht_verfuegbar_wirft_nicht(self):
        with mock.patch.object(tv_cec.shutil, "which", return_value=None):
            self.assertFalse(tv_cec.verfuegbar())
            ok, meldung = tv_cec.schalte(True)
        self.assertFalse(ok)
        self.assertIn("nicht installiert", meldung)

    def test_meldung_nennt_das_programm(self):
        # Wer im Log liest, soll wissen, was zu installieren waere.
        with mock.patch.object(tv_cec.shutil, "which", return_value=None):
            _ok, meldung = tv_cec.schalte(False)
        self.assertIn(tv_cec.PROGRAMM, meldung)


class MitCecClient(unittest.TestCase):
    def test_einschalten_sendet_on(self):
        with mock.patch.object(tv_cec.shutil, "which", return_value="/usr/bin/cec-client"), \
             mock.patch.object(tv_cec.subprocess, "run") as lauf:
            ok, _meldung = tv_cec.schalte(True)
        self.assertTrue(ok)
        self.assertEqual(lauf.call_args.kwargs["input"], b"on 0")

    def test_ausschalten_sendet_standby(self):
        with mock.patch.object(tv_cec.shutil, "which", return_value="/usr/bin/cec-client"), \
             mock.patch.object(tv_cec.subprocess, "run") as lauf:
            ok, _meldung = tv_cec.schalte(False)
        self.assertTrue(ok)
        self.assertEqual(lauf.call_args.kwargs["input"], b"standby 0")

    def test_ein_fehler_wird_gemeldet_statt_geworfen(self):
        # Ein haengendes oder abstuerzendes `cec-client` darf die
        # Steuerschleife nicht mitreissen.
        with mock.patch.object(tv_cec.shutil, "which", return_value="/usr/bin/cec-client"), \
             mock.patch.object(tv_cec.subprocess, "run", side_effect=OSError("kaputt")):
            ok, meldung = tv_cec.schalte(True)
        self.assertFalse(ok)
        self.assertIn("kaputt", meldung)

    def test_es_gibt_eine_zeitgrenze(self):
        # Ohne Zeitgrenze blockiert ein haengendes cec-client die Schleife.
        with mock.patch.object(tv_cec.shutil, "which", return_value="/usr/bin/cec-client"), \
             mock.patch.object(tv_cec.subprocess, "run") as lauf:
            tv_cec.schalte(True)
        self.assertEqual(lauf.call_args.kwargs["timeout"], tv_cec.ZEITGRENZE_S)


if __name__ == "__main__":
    unittest.main()

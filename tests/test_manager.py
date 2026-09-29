"""Station Manager (3.0): Verdrahtung zwischen Renderer, Preload und Hauptprozess.

WARUM: Der Manager hat keinen Browser-Testlauf in der CI. Was hier bricht,
bricht leise: ein Kanal, den der Preload anbietet, aber der Hauptprozess nicht
bedient, liefert im Renderer ein Promise, das mit „No handler registered"
abgewiesen wird — der Knopf tut dann einfach nichts. Genau das halten diese
Tests fest, am Quelltext.
"""
import json
import os
import re
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SM = os.path.join(WURZEL, "station-manager")


def lies(*teile):
    with open(os.path.join(SM, *teile), encoding="utf-8") as f:
        return f.read()


MAIN = lies("main.js")
PRELOAD = lies("preload.js")
APP = lies("renderer", "app.js")
INDEX = lies("renderer", "index.html")


class DieKanaeleSindVerdrahtet(unittest.TestCase):
    def test_jeder_preload_kanal_hat_einen_handler(self):
        kanaele = set(re.findall(r"ipcRenderer\.invoke\('([^']+)'", PRELOAD))
        self.assertIn("ordnung:setzen", kanaele)
        self.assertIn("station:screenshot", kanaele)
        for k in kanaele:
            with self.subTest(kanal=k):
                self.assertIn(f"ipcMain.handle('{k}'", MAIN)

    def test_jedes_ereignis_des_hauptprozesses_hat_einen_hoerer(self):
        gesendet = set(re.findall(r"webContents\.send\('([^']+)'", MAIN))
        self.assertIn("alarme:update", gesendet)
        for k in gesendet:
            with self.subTest(ereignis=k):
                self.assertIn(f"ipcRenderer.on('{k}'", PRELOAD)

    def test_der_renderer_nutzt_nur_was_der_preload_anbietet(self):
        angeboten = set(re.findall(r"^\s{4}(\w+):", PRELOAD, re.M))
        benutzt = set(re.findall(r"window\.station\.(\w+)", APP))
        self.assertEqual(benutzt - angeboten, set())


class DerRendererBleibtEingesperrt(unittest.TestCase):
    def test_keine_node_integration(self):
        self.assertIn("nodeIntegration: false", MAIN)
        self.assertIn("contextIsolation: true", MAIN)

    def test_renderer_kennt_kein_require(self):
        self.assertNotRegex(APP, r"\brequire\(")


class DieOberflaeche(unittest.TestCase):
    def test_die_eingebettete_verwaltung_wird_benutzt(self):
        # Das <webview> stand jahrelang ungenutzt im HTML; jetzt oeffnet
        # „Verwaltung" die Station darin, der Browser bleibt ein Knopf.
        self.assertIn('id="detail-frame"', INDEX)
        self.assertIn("el('detail-frame').src = url", APP)
        self.assertIn("detail-extern", INDEX)

    def test_confirm_geht_durch_tr(self):
        for m in re.finditer(r"confirm\(([^)]*)", APP):
            self.assertTrue(m.group(1).startswith("tr("), m.group(0))

    def test_dynamische_texte_stehen_im_woerterbuch(self):
        wb = json.loads(lies("renderer", "i18n-en.js").split("/*JSON*/")[1])
        texte = set(re.findall(r"tr\('([^'$`]+)'\)", APP))
        # Aus den Tabellen, die tr() durchlaufen
        texte |= {"Nah", "Mitte", "Fern", "in Ordnung", "Warnung", "Fehler"}
        fehlt = sorted(t for t in texte if t not in wb["texte"])
        self.assertEqual(fehlt, [])

    def test_alarmtexte_sind_uebersetzbar(self):
        wb = json.loads(lies("renderer", "i18n-en.js").split("/*JSON*/")[1])
        alarme = set(re.findall(r"text: [^']*'([^']+)'", lies("alarme.js")))
        self.assertTrue(alarme)
        self.assertEqual(sorted(a for a in alarme if a not in wb["texte"]), [])


class DerBauNimmtAllesMit(unittest.TestCase):
    def test_alarme_js_ist_im_paket(self):
        # Fehlt eine vom Hauptprozess geladene Datei in `build.files`, startet
        # die gepackte App gar nicht — lokal mit `npm start` faellt es nie auf.
        paket = json.loads(lies("package.json"))
        geladen = set(re.findall(r"require\('\./([\w-]+)'\)", MAIN))
        for modul in geladen:
            with self.subTest(modul=modul):
                self.assertIn(f"{modul}.js", paket["build"]["files"])


if __name__ == "__main__":
    unittest.main()

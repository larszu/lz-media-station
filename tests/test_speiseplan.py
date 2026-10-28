import io
import unittest
import zipfile

import speiseplan


def _xlsx(zeilen):
    geteilt, zellen_xml = [], []
    for r, zeile in enumerate(zeilen, 1):
        cs = []
        for c, wert in enumerate(zeile):
            ref = f"{chr(65 + c)}{r}"
            if isinstance(wert, (int, float)):
                cs.append(f'<c r="{ref}"><v>{wert}</v></c>')
            else:
                geteilt.append(wert)
                cs.append(f'<c r="{ref}" t="s"><v>{len(geteilt) - 1}</v></c>')
        zellen_xml.append(f'<row r="{r}">{"".join(cs)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(
            f"<si><t>{s}</t></si>" for s in geteilt) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {ns}><sheetData>{"".join(zellen_xml)}</sheetData></worksheet>')
    return puffer.getvalue()


class SpeiseplanTest(unittest.TestCase):
    def test_text(self):
        t = ("Speiseplan KW 45\n\nMontag 03.11.: Linsensuppe 3,50 €\n- Schnitzel mit Pommes 7,90\n"
             "Di\nGemüsecurry\nMittwoch - Pasta\n")
        tage = speiseplan.lies(t.encode(), ".txt")["tage"]
        self.assertEqual([d["tag"] for d in tage], ["mo", "di", "mi"])
        self.assertEqual(tage[0]["datum"][5:], "11-03")
        self.assertEqual(tage[0]["gerichte"][0], {"name": "Linsensuppe", "preis": "3,50 €"})
        self.assertEqual(tage[0]["gerichte"][1]["name"], "Schnitzel mit Pommes")
        self.assertEqual(tage[1]["gerichte"][0]["name"], "Gemüsecurry")
        self.assertEqual(tage[2]["gerichte"][0]["name"], "Pasta")

    def test_csv_mit_kopf_und_folgezeile(self):
        c = "Tag;Gericht;Preis\nMontag;Eintopf;4,20\n;Salat;2,00\nDienstag;Fisch;8.50 €\n"
        tage = speiseplan.lies(c.encode("cp1252"), ".csv")["tage"]
        self.assertEqual(len(tage), 2)
        self.assertEqual(tage[0]["gerichte"], [{"name": "Eintopf", "preis": "4,20 €"},
                                               {"name": "Salat", "preis": "2,00 €"}])
        self.assertEqual(tage[1]["gerichte"][0]["preis"], "8,50 €")

    def test_xlsx(self):
        daten = _xlsx([["Tag", "Menü 1", "Menü 2"], ["Mo", "Gulasch", "Käsespätzle"],
                       ["Fr", "Fischstäbchen", 5.5]])
        tage = speiseplan.lies(daten, ".xlsx")["tage"]
        self.assertEqual([d["name"] for d in tage], ["Montag", "Freitag"])
        self.assertEqual(len(tage[0]["gerichte"]), 2)
        self.assertEqual(tage[1]["gerichte"][0], {"name": "Fischstäbchen", "preis": "5,50 €"})

    def test_unlesbar(self):
        with self.assertRaises(ValueError):
            speiseplan.lies(b"kein zip", ".xlsx")


if __name__ == "__main__":
    unittest.main()

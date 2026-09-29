// Alarme des Station Managers — reine Logik, ohne Electron.
//
// Der Hauptprozess fragt alle 10 s jede Station ab und legt den neuen Stand
// neben den alten. Gemeldet wird nur ein UEBERGANG: eine Station, die seit
// einer Stunde offline ist, soll nicht alle 10 s eine Benachrichtigung
// ausloesen, und eine, die offline war, als der Manager startete, auch nicht
// (dafuer ist die rote Markierung an der Kachel da).
//
// Liegt in einer eigenen Datei, damit `node --test` sie ohne Electron pruefen
// kann (station-manager/test/alarme.test.js).

'use strict';

const STUFEN = ['ok', 'hinweis', 'warnung', 'fehler'];

function stufeIndex(s) {
    const i = STUFEN.indexOf(s);
    return i < 0 ? 0 : i;
}

// Ein Stand ist das, was der Manager je Station weiss:
//   { online: bool, health: 'ok'|'hinweis'|'warnung'|'fehler'|null,
//     anzeigenOnline: number|null, anzeigenAnzahl: number|null }
// `alt` ist undefined beim ersten Blick auf eine Station.
function uebergaenge(alt, neu) {
    if (!alt || !neu) return [];
    const alarme = [];

    if (alt.online && !neu.online) {
        alarme.push({ typ: 'offline', stufe: 'fehler', text: 'Station nicht mehr erreichbar' });
        // Wer offline ist, liefert keine Gesundheit und keine Anzeigen —
        // daraus weitere Alarme abzuleiten waere dieselbe Nachricht dreimal.
        return alarme;
    }
    if (!alt.online && neu.online) {
        alarme.push({ typ: 'online', stufe: 'ok', text: 'Station wieder erreichbar' });
        return alarme;
    }
    if (!neu.online) return alarme;

    const a = stufeIndex(alt.health), n = stufeIndex(neu.health);
    if (neu.health === 'fehler' && alt.health !== 'fehler') {
        alarme.push({ typ: 'gesundheit', stufe: 'fehler', text: 'Gesundheit: Fehler' });
    } else if (alt.health === 'fehler' && n < a) {
        alarme.push({ typ: 'gesundheit', stufe: 'ok', text: 'Gesundheit: Fehler behoben' });
    }

    // Eine Anzeige verloren: es gab mindestens eine Anzeige online, jetzt
    // weniger. `null` heisst "unbekannt" (alte Station ohne Puls) — daraus
    // wird nie ein Alarm.
    if (typeof alt.anzeigenOnline === 'number' && typeof neu.anzeigenOnline === 'number') {
        if (neu.anzeigenOnline < alt.anzeigenOnline) {
            alarme.push({ typ: 'anzeige', stufe: 'warnung',
                          text: neu.anzeigenOnline === 0 ? 'Keine Anzeige mehr verbunden'
                                                          : 'Eine Anzeige ist nicht mehr verbunden' });
        } else if (alt.anzeigenOnline === 0 && neu.anzeigenOnline > 0) {
            alarme.push({ typ: 'anzeige', stufe: 'ok', text: 'Anzeige wieder verbunden' });
        }
    }
    return alarme;
}

// Die Kachel ist rot, solange etwas im Argen liegt — unabhaengig davon, ob
// ein Alarm gemeldet wurde.
function istRot(stand) {
    if (!stand) return false;
    if (!stand.online) return true;
    if (stand.health === 'fehler') return true;
    if (typeof stand.anzeigenAnzahl === 'number' && stand.anzeigenAnzahl > 0
        && stand.anzeigenOnline === 0) return true;
    return false;
}

// Alarmliste: neueste zuerst, gedeckelt.
function haengeAn(liste, eintraege, max = 200) {
    return eintraege.concat(liste).slice(0, max);
}

module.exports = { uebergaenge, istRot, haengeAn, STUFEN };

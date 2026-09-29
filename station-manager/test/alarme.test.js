// node --test station-manager/test/
// WARUM: Der Manager meldet Ausfaelle als Systembenachrichtigung. Meldet er
// zu oft (jede Abfrage), stellt man ihn stumm; meldet er zu selten (Uebergang
// verpasst), steht ein schwarzer Schirm unbemerkt im Foyer. Beides haengt an
// dieser einen Vergleichsfunktion.
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { uebergaenge, istRot, haengeAn } = require('../alarme.js');

const gut = { online: true, health: 'ok', anzeigenOnline: 1, anzeigenAnzahl: 1 };

test('erster Blick auf eine Station meldet nichts', () => {
    assert.deepStrictEqual(uebergaenge(undefined, { online: false }), []);
});

test('gleichbleibend offline meldet nichts', () => {
    assert.deepStrictEqual(uebergaenge({ online: false }, { online: false }), []);
});

test('online nach offline ist genau ein Alarm', () => {
    const a = uebergaenge(gut, { online: false, health: null, anzeigenOnline: null });
    assert.strictEqual(a.length, 1);
    assert.strictEqual(a[0].typ, 'offline');
});

test('wieder erreichbar wird gemeldet', () => {
    const a = uebergaenge({ online: false }, gut);
    assert.deepStrictEqual(a.map(x => x.typ), ['online']);
});

test('Gesundheit kippt auf Fehler', () => {
    const a = uebergaenge(gut, { ...gut, health: 'fehler' });
    assert.deepStrictEqual(a.map(x => x.typ), ['gesundheit']);
    assert.strictEqual(a[0].stufe, 'fehler');
});

test('Fehler bleibt Fehler meldet nicht erneut', () => {
    const f = { ...gut, health: 'fehler' };
    assert.deepStrictEqual(uebergaenge(f, f), []);
});

test('Warnung allein ist kein Alarm', () => {
    assert.deepStrictEqual(uebergaenge(gut, { ...gut, health: 'warnung' }), []);
});

test('Anzeige verloren', () => {
    const a = uebergaenge(gut, { ...gut, anzeigenOnline: 0 });
    assert.deepStrictEqual(a.map(x => x.typ), ['anzeige']);
    assert.match(a[0].text, /Keine Anzeige/);
});

test('unbekannte Anzeigenzahl erzeugt nie einen Alarm', () => {
    assert.deepStrictEqual(uebergaenge({ ...gut, anzeigenOnline: null }, { ...gut, anzeigenOnline: 0 }), []);
});

test('rot bei offline, Fehler oder allen Anzeigen weg', () => {
    assert.strictEqual(istRot(gut), false);
    assert.strictEqual(istRot({ online: false }), true);
    assert.strictEqual(istRot({ ...gut, health: 'fehler' }), true);
    assert.strictEqual(istRot({ ...gut, anzeigenOnline: 0 }), true);
    assert.strictEqual(istRot({ ...gut, anzeigenAnzahl: 0, anzeigenOnline: 0 }), false);
});

test('Alarmliste ist gedeckelt, neueste zuerst', () => {
    let l = [];
    for (let i = 0; i < 5; i++) l = haengeAn(l, [{ n: i }], 3);
    assert.deepStrictEqual(l.map(x => x.n), [4, 3, 2]);
});

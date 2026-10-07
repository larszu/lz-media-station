// Renderer des LZ Station Managers (Signage 3.0).
//
// Alles, was hier sichtbar wird, ist deutsch; i18n.js uebersetzt es. Texte,
// die nicht durchs DOM gehen (confirm) oder zusammengesetzt werden, laufen
// ueber tr() und stehen als Text oder Muster in i18n-en.js.
const grid = document.getElementById('station-grid');
const selCount = document.getElementById('sel-count');
const feedback = document.getElementById('bulk-feedback');
const ergebnisListe = document.getElementById('ergebnis');
const selected = new Set();
const tagFilter = new Set();
let stations = [];
let alarme = [];
let gesehen = 0;               // Alarme bis zum letzten Oeffnen der Liste
const vorschau = new Map();    // id -> { bild, zeit, laedt, fehler }
const layoutsJe = new Map();   // id -> { layouts: {id: layout}, zonen: {...} }

function el(id) { return document.getElementById(id); }

// Klartext statt der Codes aus /api/status; i18n.js uebersetzt ihn weiter.
const ZUSTAND = { near: 'Nah', mid: 'Mitte', far: 'Fern', idle: 'Inaktiv' };
const QUELLE = { mdns: 'mDNS', manual: 'manuell' };
const GESUNDHEIT = { ok: 'in Ordnung', hinweis: 'Hinweis', warnung: 'Warnung', fehler: 'Fehler' };
const MEDIENART = { video: 'videos', image: 'images', audio: 'audio' };

const tr = (text) => (window.LZ && window.LZ.t) ? window.LZ.t(text) : text;

function lies(k, vorgabe) { try { return localStorage.getItem(k) || vorgabe; } catch { return vorgabe; } }
function merke(k, v) { try { localStorage.setItem(k, v); } catch { /* egal */ } }
let ansicht = lies('lz-manager-ansicht', 'kacheln');

function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[<>&"']/g, c => ({ '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;' }[c]));
}

/* ---- Filter ---- */

function sichtbar(s) {
    const q = el('suche').value.trim().toLowerCase();
    if (q) {
        const heu = [s.name, s.host, s.hostname, s.gruppe, s.layoutName, ...(s.tags || [])].join(' ').toLowerCase();
        if (!heu.includes(q)) return false;
    }
    const g = el('filter-gruppe').value;
    if (g && s.gruppe !== g) return false;
    for (const t of tagFilter) if (!(s.tags || []).includes(t)) return false;
    return true;
}

function renderFilter() {
    const gruppen = Array.from(new Set(stations.map(s => s.gruppe).filter(Boolean))).sort();
    const sel = el('filter-gruppe');
    const wert = sel.value;
    const html = `<option value="">${esc(tr('Alle Gruppen'))}</option>` +
        gruppen.map(g => `<option value="${esc(g)}">${esc(g)}</option>`).join('');
    if (sel.dataset.html !== html) {
        sel.innerHTML = html;
        sel.dataset.html = html;
        sel.value = gruppen.includes(wert) ? wert : '';
    }
    el('gruppen-liste').innerHTML = gruppen.map(g => `<option value="${esc(g)}">`).join('');

    const tags = Array.from(new Set(stations.flatMap(s => s.tags || []))).sort();
    for (const t of Array.from(tagFilter)) if (!tags.includes(t)) tagFilter.delete(t);
    el('tag-filter').innerHTML = tags.map(t =>
        `<button type="button" class="chip${tagFilter.has(t) ? ' an' : ''}" data-tag="${esc(t)}">${esc(t)}</button>`).join('');
    el('tag-filter').querySelectorAll('[data-tag]').forEach(b => b.onclick = () => {
        const t = b.dataset.tag;
        if (tagFilter.has(t)) tagFilter.delete(t); else tagFilter.add(t);
        render();
    });
}

/* ---- Kacheln ---- */

function zeile(label, wert, cls) {
    return `<div class="zeile"><span>${esc(tr(label))}</span><span class="${cls || ''}">${wert}</span></div>`;
}

function kachel(s) {
    const card = document.createElement('div');
    card.className = 'station' + (selected.has(s.id) ? ' selected' : '') +
        (s.online ? '' : ' offline') + (s.rot ? ' rot' : '');
    card.dataset.id = s.id;

    const zustand = !s.online ? tr('offline')
        : s.geschlossen ? tr('geschlossen')
        : (tr(ZUSTAND[s.zone] || ZUSTAND[s.state] || s.state || '–'));
    const badgeCls = !s.online ? '' : s.zone === 'near' ? 'near' : s.zone === 'far' ? 'far' : 'idle';
    const v = vorschau.get(s.id) || {};
    const bild = v.bild
        ? `<img src="${v.bild}" alt="">`
        : `<span>${esc(tr(v.laedt ? 'Lade Vorschau …' : (s.online ? 'Keine Vorschau' : 'offline')))}</span>`;
    const anz = s.anzeige
        ? `${s.anzeige.online} / ${s.anzeige.anzahl}` : '–';
    const anzCls = (s.anzeige && s.anzeige.anzahl > 0 && s.anzeige.online === 0) ? 'schlecht' : '';
    const health = s.health ? tr(GESUNDHEIT[s.health] || s.health) : '–';
    const healthCls = s.health === 'fehler' ? 'schlecht' : s.health === 'warnung' ? 'mittel' : '';
    const tags = (s.tags || []).map(t => `<span class="chip klein">${esc(t)}</span>`).join('');

    card.innerHTML = `
        <div class="station-head">
            <div><span class="dot ${s.online ? 'online' : 'offline'}"></span>
                <span class="station-name">${esc(s.name || s.host)}</span></div>
            <span class="badge ${badgeCls}">${esc(zustand)}</span>
        </div>
        <button type="button" class="vorschau" data-act="bild" title="${esc(tr('Vorschau aktualisieren'))}">${bild}
            ${v.zeit ? `<span class="bild-zeit">${esc(v.zeit.slice(11, 16))}</span>` : ''}</button>
        <div class="station-meta">
            ${zeile('Layout', esc(s.layoutName || s.layoutId || '–'))}
            ${zeile('Gesundheit', esc(health), healthCls)}
            ${zeile('Anzeigen', esc(anz), anzCls)}
            ${zeile('Gruppe', esc(s.gruppe || '–'))}
            <div class="zeile fein"><span>${esc(s.host)}:${s.port}</span><span>v${esc(s.version || '?')} · ${esc(tr(QUELLE[s.source] || s.source || ''))}</span></div>
        </div>
        <div class="tags">${tags}</div>
        <div class="station-actions">
            <button data-act="start" title="Start">▶</button>
            <button data-act="stop" title="Stop">■</button>
            <button data-act="open" title="${esc(tr('Verwaltung öffnen'))}">${esc(tr('Verwaltung'))}</button>
            <button data-act="pin" title="${esc(tr('PIN der Station'))}">PIN</button>
            <button data-act="stumm" title="${esc(tr(s.stumm ? 'Alarme wieder einschalten' : 'Alarme stummschalten'))}">${esc(tr(s.stumm ? 'Ton an' : 'Stumm'))}</button>
            <button data-act="reboot" class="danger" title="${esc(tr('Station neu starten'))}">⟲</button>
            <button data-act="remove" class="rechts" title="${esc(tr('Aus der Liste entfernen'))}">${esc(tr('Entfernen'))}</button>
        </div>`;
    card.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        if (selected.has(s.id)) selected.delete(s.id); else selected.add(s.id);
        auswahlGeaendert();
    });
    card.querySelectorAll('button[data-act]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleAction(s, btn.dataset.act);
        });
    });
    return card;
}

function render() {
    renderFilter();
    grid.className = 'grid ' + (ansicht === 'liste' ? 'liste' : 'kacheln');
    el('ansicht-kacheln').classList.toggle('aktiv', ansicht !== 'liste');
    el('ansicht-liste').classList.toggle('aktiv', ansicht === 'liste');
    grid.innerHTML = '';
    if (!stations.length) {
        grid.innerHTML = `<div class="leer">${esc(tr('Keine Stationen gefunden. mDNS scannt automatisch im LAN, oder Station manuell hinzufügen.'))}</div>`;
    } else {
        const liste = stations.filter(sichtbar);
        if (!liste.length) grid.innerHTML = `<div class="leer">${esc(tr('Keine Station passt zum Filter.'))}</div>`;
        liste.forEach(s => grid.appendChild(kachel(s)));
    }
    selCount.textContent = `(${selected.size})`;
    renderQuellen();
}

/* ---- Vorschaubilder ---- */

async function holeVorschau(s, anfordern) {
    const v = vorschau.get(s.id) || {};
    if (v.laedt) return;
    vorschau.set(s.id, { ...v, laedt: true });
    if (anfordern) render();
    let r = await window.station.screenshot(s.id, anfordern);
    if (r && r.needsPin && await fragePin(s, 'Die Station verlangt eine PIN')) {
        r = await window.station.screenshot(s.id, anfordern);
    }
    const neu = { ...(vorschau.get(s.id) || {}), laedt: false };
    if (r && r.ok) {
        neu.bild = r.bild; neu.zeit = r.zeit; neu.fehler = null;
        if (r.hinweis && anfordern) setFeedback(`${s.name}: ${tr(r.hinweis)} — ${tr('letztes Bild')}`, 'error');
    }
    else if (r && r.error && anfordern) {
        neu.fehler = r.error;
        setFeedback(`${s.name}: ${tr(r.error)}`, 'error');
    }
    vorschau.set(s.id, neu);
    render();
}

// Das zuletzt abgelegte Bild jeder erreichbaren Station, ohne neues
// anzufordern — das kostet die Station nichts.
function vorschauenAuffrischen() {
    stations.filter(s => s.online).forEach(s => holeVorschau(s, false));
}

/* ---- Zugangsschutz (3.0): PIN je Station ----
   Antwortet eine Station mit 401 und `zugang`, verlangt sie eine PIN. Der
   Dialog fragt sie ab, der Hauptprozess merkt sie sich und schickt sie ab
   dann als X-LZ-Pin mit; der Aufruf wird einmal wiederholt. */
let pinAufloesung = null;
let pinStation = null;

function fragePin(s, hinweis) {
    return new Promise((resolve) => {
        pinAufloesung = resolve;
        pinStation = s;
        el('pin-station').textContent = `${s.name || s.host} (${s.host}:${s.port})` + (hinweis ? ' — ' + tr(hinweis) : '');
        el('pin-wert').value = '';
        el('pin-feedback').textContent = '';
        el('pin-dialog').classList.remove('hidden');
        el('pin-wert').focus();
    });
}
function schliessePin(ergebnis) {
    el('pin-dialog').classList.add('hidden');
    if (pinAufloesung) { const r = pinAufloesung; pinAufloesung = null; r(ergebnis); }
}
el('pin-ok').onclick = async () => {
    const pin = el('pin-wert').value.trim();
    if (!pin) { el('pin-feedback').textContent = tr('PIN eingeben'); el('pin-feedback').className = 'error'; return; }
    if (pinStation) await window.station.setPin(pinStation.id, pin);
    schliessePin(true);
};
el('pin-loeschen').onclick = async () => {
    if (pinStation) await window.station.setPin(pinStation.id, null);
    schliessePin(false);
};
el('pin-cancel').onclick = () => schliessePin(false);
el('pin-wert').addEventListener('keydown', (e) => { if (e.key === 'Enter') el('pin-ok').click(); });

// Ein API-Aufruf, der bei 401 die PIN erfragt und es einmal noch versucht.
async function apiMitPin(s, action, method, body) {
    let r = await window.station.api(s.id, action, method, body);
    if (r && r.needsPin) {
        const ok = await fragePin(s, 'Die Station verlangt eine PIN');
        if (ok) r = await window.station.api(s.id, action, method, body);
    }
    return r;
}

/* ---- Detail: die Verwaltung der Station, eingebettet ---- */

let detailStation = null;
async function oeffneDetail(s) {
    const url = await window.station.adminUrl(s.id);
    if (!url) return;
    detailStation = s;
    el('detail-title').textContent = `${s.name || s.host} — ${s.host}:${s.port}`;
    el('detail-frame').src = url;
    el('detail').classList.remove('hidden');
}
el('detail-close').onclick = () => {
    el('detail').classList.add('hidden');
    el('detail-frame').src = 'about:blank';
    detailStation = null;
};
el('detail-extern').onclick = () => { if (detailStation) window.station.openAdmin(detailStation.id); };

async function handleAction(s, action) {
    if (action === 'start') await apiMitPin(s, 'start', 'POST');
    else if (action === 'stop') await apiMitPin(s, 'stop', 'POST');
    else if (action === 'open') await oeffneDetail(s);
    else if (action === 'bild') await holeVorschau(s, true);
    else if (action === 'stumm') await window.station.setStumm(s.id, !s.stumm);
    else if (action === 'pin') {
        const info = await window.station.accessInfo(s.id);
        await fragePin(s, info.gesetzt ? (info.gespeichert ? 'PIN gespeichert' : 'Die Station verlangt eine PIN')
                                       : 'Diese Station hat keine PIN');
    }
    else if (action === 'reboot') {
        if (confirm(tr(`Station "${s.name}" neu starten?`)))
            await apiMitPin(s, 'system/reboot', 'POST');
    }
    else if (action === 'remove') {
        if (confirm(tr(`Station "${s.name}" aus der Liste entfernen?`)))
            await window.station.removeStation(s.id);
    }
}

/* ---- Rueckmeldung ---- */

function setFeedback(msg, cls) {
    feedback.textContent = msg;
    feedback.className = cls || '';
}

// Ergebnis je Station: ok / Warnung / Fehler, mit Grund.
function zeigeErgebnis(titel, zeilen) {
    const ok = zeilen.filter(z => z.stufe === 'ok').length;
    setFeedback(`${tr(titel)}: ${ok} / ${zeilen.length} ${tr('ok')}`,
        ok === zeilen.length ? 'success' : 'error');
    ergebnisListe.innerHTML = zeilen.map(z =>
        `<li class="${z.stufe}"><b>${esc(z.name)}</b> ${esc(z.text ? tr(z.text) : '')}</li>`).join('');
}

function auswahl() {
    return Array.from(selected).map(stationById).filter(s => s && s.host !== '?');
}
function stationById(id) { return stations.find(x => x.id === id) || { id, name: id, host: '?', port: '' }; }

function brauchtAuswahl() {
    if (selected.size) return true;
    setFeedback(tr('Keine Auswahl'), 'error');
    return false;
}

function grund(r) {
    if (!r) return 'keine Antwort';
    if (r.error) return r.error;
    if (r.body && r.body.error) return r.body.error;
    return `HTTP ${r.status}`;
}

async function jeStation(titel, fn) {
    if (!brauchtAuswahl()) return;
    setFeedback(tr('Arbeite …'));
    const zeilen = [];
    for (const s of auswahl()) {
        try { zeilen.push({ name: s.name || s.host, ...(await fn(s)) }); }
        catch (e) { zeilen.push({ name: s.name || s.host, stufe: 'fehler', text: e.message }); }
    }
    zeigeErgebnis(titel, zeilen);
}

/* ---- Kopf und Auswahl ---- */

el('btn-rescan').onclick = async () => {
    setFeedback(tr('Scanne...'));
    await window.station.rescan();
    setFeedback('');
};
el('btn-add').onclick = () => el('add-dialog').classList.remove('hidden');
el('add-cancel').onclick = () => el('add-dialog').classList.add('hidden');
el('add-ok').onclick = async () => {
    const host = el('add-host').value.trim();
    const port = parseInt(el('add-port').value) || 5000;
    if (!host) return;
    el('add-feedback').textContent = tr('Prüfe...');
    el('add-feedback').className = '';
    const ok = await window.station.addStation(host, port);
    if (ok) {
        el('add-feedback').textContent = tr('Hinzugefügt');
        el('add-feedback').className = 'success';
        setTimeout(() => {
            el('add-dialog').classList.add('hidden');
            el('add-feedback').textContent = '';
            el('add-host').value = '';
        }, 800);
    } else {
        el('add-feedback').textContent = tr('Nicht erreichbar');
        el('add-feedback').className = 'error';
    }
};
el('suche').addEventListener('input', render);
el('filter-gruppe').addEventListener('change', render);
el('ansicht-kacheln').onclick = () => { ansicht = 'kacheln'; merke('lz-manager-ansicht', ansicht); render(); };
el('ansicht-liste').onclick = () => { ansicht = 'liste'; merke('lz-manager-ansicht', ansicht); render(); };
el('sel-alle').onclick = () => { stations.filter(sichtbar).forEach(s => selected.add(s.id)); auswahlGeaendert(); };
el('sel-keine').onclick = () => { selected.clear(); auswahlGeaendert(); };

function auswahlGeaendert() {
    render();
    ladeZuweisbareLayouts();
}

/* ---- Steuerung ---- */

async function einfach(titel, action) {
    await jeStation(titel, async (s) => {
        const r = await apiMitPin(s, action, 'POST');
        return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
    });
}
el('bulk-start').onclick = () => einfach('Start', 'start');
el('bulk-stop').onclick = () => einfach('Stop', 'stop');
el('bulk-reboot').onclick = async () => {
    if (!brauchtAuswahl()) return;
    if (!confirm(tr(`${selected.size} Stationen neu starten?`))) return;
    await einfach('Reboot', 'system/reboot');
};

/* ---- Layouts ---- */

async function layoutsVon(s, frisch) {
    if (!frisch && layoutsJe.has(s.id)) return layoutsJe.get(s.id);
    const r = await apiMitPin(s, 'layouts', 'GET');
    const daten = (r && r.ok && r.body && r.body.layouts) ? r.body : null;
    if (daten) layoutsJe.set(s.id, daten);
    return daten;
}

function optionen(eintraege, leer) {
    if (!eintraege.length) return `<option value="">${esc(tr(leer))}</option>`;
    return eintraege.map(([id, name]) => `<option value="${esc(id)}">${esc(name)}</option>`).join('');
}

// Zuweisen: nur Layouts, die es auf JEDER ausgewaehlten Station gibt —
// sonst bekaeme eine Zone eine Kennung, die dort nichts bedeutet.
async function ladeZuweisbareLayouts() {
    const sel = el('zuweisen-layout');
    const ziele = auswahl().filter(s => s.online);
    if (!ziele.length) { sel.innerHTML = optionen([], 'Erst Stationen auswählen'); return; }
    const alle = await Promise.all(ziele.map(s => layoutsVon(s)));
    if (alle.some(x => !x)) { sel.innerHTML = optionen([], 'Nicht alle Stationen kennen Layouts'); return; }
    const gemeinsam = Object.keys(alle[0].layouts).filter(id => alle.every(a => id in a.layouts));
    const alt = sel.value;
    sel.innerHTML = optionen(gemeinsam.map(id => [id, alle[0].layouts[id].name || id]),
                             'Kein gemeinsames Layout');
    if (gemeinsam.includes(alt)) sel.value = alt;
}

el('bulk-zuweisen').onclick = async () => {
    const zone = el('zuweisen-zone').value;
    const lid = el('zuweisen-layout').value;
    if (!lid) return setFeedback(tr('Kein Layout gewählt'), 'error');
    await jeStation('Layout zuweisen', async (s) => {
        const r = await apiMitPin(s, 'config', 'POST', { [zone]: { layout: lid } });
        layoutsJe.delete(s.id);
        return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
    });
};

function renderQuellen() {
    const online = stations.filter(s => s.online);
    const html = optionen(online.map(s => [s.id, s.name || s.host]), 'Keine Station erreichbar');
    for (const id of ['kopie-quelle', 'programm-quelle']) {
        const sel = el(id);
        if (sel.dataset.html === html) continue;
        const alt = sel.value;
        sel.innerHTML = html;
        sel.dataset.html = html;
        if (online.some(s => s.id === alt)) sel.value = alt;
        if (id === 'kopie-quelle') ladeKopieLayouts();
    }
}

async function ladeKopieLayouts() {
    const s = stations.find(x => x.id === el('kopie-quelle').value);
    const sel = el('kopie-layout');
    if (!s) { sel.innerHTML = optionen([], 'Keine Station erreichbar'); return; }
    const d = await layoutsVon(s, true);
    const eintraege = d ? Object.entries(d.layouts).map(([id, l]) => [id, l.name || id]) : [];
    sel.innerHTML = optionen(eintraege, 'Keine Layouts');
}
el('kopie-quelle').addEventListener('change', ladeKopieLayouts);

// Welche Dateien ein Layout braucht, je Medienart.
function medienDes(layout) {
    const noetig = { videos: new Set(), images: new Set(), audio: new Set() };
    for (const r of layout.regionen || []) {
        for (const e of r.playlist || []) {
            const art = MEDIENART[e.typ];
            if (art && e.name) noetig[art].add(e.name);
        }
    }
    return noetig;
}

async function fehlendeMedien(s, layout) {
    const noetig = medienDes(layout);
    const fehlt = [];
    for (const art of Object.keys(noetig)) {
        if (!noetig[art].size) continue;
        const r = await apiMitPin(s, `media/${art}`, 'GET');
        const da = new Set((r && r.ok && Array.isArray(r.body) ? r.body : []).map(f => f.name));
        for (const n of noetig[art]) if (!da.has(n)) fehlt.push(n);
    }
    return fehlt;
}

el('bulk-kopieren').onclick = async () => {
    const quelle = stations.find(x => x.id === el('kopie-quelle').value);
    const lid = el('kopie-layout').value;
    if (!quelle || !lid) return setFeedback(tr('Kein Layout gewählt'), 'error');
    const q = await apiMitPin(quelle, `layouts/${encodeURIComponent(lid)}`, 'GET');
    if (!q || !q.ok || !q.body || !q.body.layout) return setFeedback(`${tr('Quelle')}: ${grund(q)}`, 'error');
    const layout = q.body.layout;
    await jeStation('Layout kopieren', async (s) => {
        if (s.id === quelle.id) return { stufe: 'ok', text: 'Quelle' };
        const pfad = `layouts/${encodeURIComponent(lid)}`;
        const da = await apiMitPin(s, pfad, 'GET');
        if (!da || da.status === 404) {
            const neu = await apiMitPin(s, 'layouts', 'POST', { id: lid, name: layout.name, vorlage: 'frei' });
            if (!neu || !neu.ok) return { stufe: 'fehler', text: grund(neu) };
        }
        const r = await apiMitPin(s, pfad, 'PUT', layout);
        layoutsJe.delete(s.id);
        if (!r || !r.ok) return { stufe: 'fehler', text: grund(r) };
        const fehlt = await fehlendeMedien(s, layout);
        return fehlt.length
            ? { stufe: 'warnung', text: `${tr('Es fehlen Medien')}: ${fehlt.join(', ')}` }
            : { stufe: 'ok' };
    });
};

/* ---- Wochenprogramm ---- */

el('bulk-programm').onclick = async () => {
    const quelle = stations.find(x => x.id === el('programm-quelle').value);
    if (!quelle) return setFeedback(tr('Keine Station erreichbar'), 'error');
    const q = await apiMitPin(quelle, 'programm', 'GET');
    if (!q || !q.ok || !q.body) return setFeedback(`${tr('Quelle')}: ${grund(q)}`, 'error');
    const programm = q.body.programm || q.body;
    const brauchtLayouts = new Set([...(programm.eintraege || []), ...(programm.ausnahmen || [])]
        .map(e => e.layout_id).filter(Boolean));
    await jeStation('Wochenprogramm kopieren', async (s) => {
        if (s.id === quelle.id) return { stufe: 'ok', text: 'Quelle' };
        const d = await layoutsVon(s, true);
        const fehlt = d ? Array.from(brauchtLayouts).filter(id => !(id in d.layouts)) : [];
        if (fehlt.length) return { stufe: 'fehler', text: `${tr('Es fehlen Layouts')}: ${fehlt.join(', ')}` };
        const r = await apiMitPin(s, 'programm', 'PUT', programm);
        return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
    });
};

/* ---- Sofortmeldung ---- */

el('meldung-an').onclick = async () => {
    const text = el('meldung-text').value.trim();
    if (!text) return setFeedback(tr('Text fehlt'), 'error');
    const min = parseFloat(el('meldung-dauer').value);
    const body = { text, untertext: el('meldung-untertext').value.trim(), farbe: el('meldung-farbe').value };
    if (min > 0) body.dauer_s = Math.round(min * 60);
    await jeStation('Sofortmeldung', async (s) => {
        const r = await apiMitPin(s, 'meldung', 'POST', body);
        return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
    });
};
el('meldung-aus').onclick = () => jeStation('Sofortmeldung beenden', async (s) => {
    const r = await apiMitPin(s, 'meldung', 'DELETE');
    return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
});

/* ---- Gruppe und Tags ---- */

async function ordnung(aenderung) {
    if (!brauchtAuswahl()) return;
    await window.station.setOrdnung(Array.from(selected), aenderung);
    setFeedback(tr(`${selected.size} geändert`), 'success');
}
el('ordnung-gruppe-setzen').onclick = () => ordnung({ gruppe: el('ordnung-gruppe').value });
el('ordnung-tag-dazu').onclick = () => {
    const t = el('ordnung-tag').value.trim();
    if (t) ordnung({ tagDazu: t });
};
el('ordnung-tag-weg').onclick = () => {
    const t = el('ordnung-tag').value.trim();
    if (t) ordnung({ tagWeg: t });
};

/* ---- Upload und Config-Push (wie bisher) ---- */

document.querySelectorAll('[data-upload]').forEach(btn => {
    btn.onclick = async () => {
        if (!brauchtAuswahl()) return;
        const type = btn.dataset.upload;
        const files = await window.station.pickFiles(type);
        if (!files.length) return;
        setFeedback(tr(`Lade ${files.length} ${type} an ${selected.size} hoch...`));
        const r = await window.station.uploadTo(Array.from(selected), type, files);
        zeigeErgebnis('Upload', r.map(x => ({
            name: `${stationById(x.id).name || x.id} · ${x.file || ''}`,
            stufe: x.ok ? 'ok' : 'fehler',
            text: x.ok ? '' : (x.needsPin ? 'Die Station verlangt eine PIN' : x.error),
        })));
    };
});

el('bulk-push-config').onclick = async () => {
    if (!brauchtAuswahl()) return;
    const cfg = {};
    const name = el('bulk-name').value.trim();
    const thr = el('bulk-threshold').value;
    const dly = el('bulk-delay').value;
    if (name) cfg.system_name = name;
    if (thr) cfg.threshold_m = parseFloat(thr);
    if (dly) cfg.delay_s = parseFloat(dly);
    if (!Object.keys(cfg).length) return setFeedback(tr('Keine Felder gesetzt'), 'error');
    await jeStation('Config-Push', async (s) => {
        const r = await apiMitPin(s, 'config', 'POST', cfg);
        return r && r.ok ? { stufe: 'ok' } : { stufe: 'fehler', text: grund(r) };
    });
};

/* ---- Alarme ---- */

function renderAlarme() {
    const neu = Math.max(0, alarme.filter(a => a.stufe !== 'ok' && !a.stumm).length - gesehen);
    el('alarm-zahl').textContent = neu;
    el('alarm-zahl').hidden = !neu;
    el('btn-alarme').classList.toggle('alarm', neu > 0);
    el('alarm-liste').innerHTML = alarme.length
        ? alarme.map(a => `<li class="${a.stufe}${a.stumm ? ' stumm' : ''}">
            <span class="zeit">${esc(new Date(a.zeit).toLocaleString())}</span>
            <b>${esc(a.name)}</b> ${esc(tr(a.text))}${a.stumm ? ` <small>(${esc(tr('stumm'))})</small>` : ''}</li>`).join('')
        : `<li class="leer">${esc(tr('Keine Alarme'))}</li>`;
}
el('btn-alarme').onclick = () => {
    gesehen = alarme.filter(a => a.stufe !== 'ok' && !a.stumm).length;
    renderAlarme();
    el('alarm-panel').classList.remove('hidden');
};
el('alarme-zu').onclick = () => el('alarm-panel').classList.add('hidden');
el('alarme-leeren').onclick = async () => { await window.station.alarmeLeeren(); gesehen = 0; };
window.station.onAlarme((liste) => {
    alarme = liste;
    gesehen = Math.min(gesehen, alarme.filter(a => a.stufe !== 'ok' && !a.stumm).length);
    renderAlarme();
});

/* ---- Start ---- */

window.station.onStations((list) => {
    const neueOnline = list.filter(s => s.online && !vorschau.has(s.id));
    stations = list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    for (const id of selected) if (!stations.find(s => s.id === id)) selected.delete(id);
    render();
    neueOnline.forEach(s => holeVorschau(s, false));
});

window.station.listStations().then(list => {
    stations = list;
    render();
    vorschauenAuffrischen();
});
window.station.alarme().then(l => { alarme = l || []; renderAlarme(); });
setInterval(vorschauenAuffrischen, 30000);
ladeZuweisbareLayouts();

window.station.version().then(v => { el('about-version').textContent = v; }).catch(() => {});

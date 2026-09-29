// Renderer for LZ Station Manager
const grid = document.getElementById('station-grid');
const selCount = document.getElementById('sel-count');
const feedback = document.getElementById('bulk-feedback');
const selected = new Set();
let stations = [];

function el(id) { return document.getElementById(id); }

// Klartext statt der Codes aus /api/status; i18n.js uebersetzt ihn weiter.
const ZUSTAND = { near: 'Nah', mid: 'Mitte', far: 'Fern', idle: 'Inaktiv' };
const QUELLE = { mdns: 'mDNS', manual: 'manuell' };

// confirm-Dialoge gehen nicht durchs DOM — i18n.js uebersetzt sie nur hier.
const tr = (text) => (window.LZ && window.LZ.t) ? window.LZ.t(text) : text;

function render() {
    grid.innerHTML = '';
    if (!stations.length) {
        grid.innerHTML = '<div style="color:var(--muted);padding:20px">Keine Stationen gefunden. mDNS scannt automatisch im LAN, oder Station manuell hinzufügen.</div>';
        return;
    }
    stations.forEach(s => {
        const card = document.createElement('div');
        card.className = 'station' + (selected.has(s.id) ? ' selected' : '') + (s.online ? '' : ' offline');
        const stateBadge = s.online
            ? `<span class="badge ${s.state === 'near' ? 'near' : s.state === 'far' ? 'far' : 'idle'}">${ZUSTAND[s.state] || s.state || '–'}</span>`
            : '<span class="badge">offline</span>';
        const dist = (s.distance != null) ? s.distance.toFixed(2) + ' m' : '–';
        card.innerHTML = `
            <div class="station-head">
                <div><span class="dot ${s.online ? 'online' : 'offline'}"></span>
                    <span class="station-name">${esc(s.name || s.host)}</span></div>
                ${stateBadge}
            </div>
            <div class="station-meta">
                <span>${esc(s.host)}:${s.port}</span>
                <span>${esc(s.hostname || '')}</span>
                <span>v${esc(s.version || '?')}</span>
                <span>${dist}</span>
                <span style="float:right; opacity:0.6">${QUELLE[s.source] || s.source || ''}</span>
            </div>
            <div class="station-actions">
                <button data-act="start">▶ Start</button>
                <button data-act="stop">■ Stop</button>
                <button data-act="open">🌐 Admin</button>
                <button data-act="pin" title="PIN der Station">🔑</button>
                <button data-act="reboot" class="danger">⟲</button>
                <button data-act="remove" style="margin-left:auto">🗑</button>
            </div>`;
        card.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            if (selected.has(s.id)) selected.delete(s.id); else selected.add(s.id);
            render();
        });
        card.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleAction(s, btn.dataset.act);
            });
        });
        grid.appendChild(card);
    });
    selCount.textContent = `(${selected.size})`;
}

function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[<>&"']/g, c => ({ '<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;' }[c]));
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

async function handleAction(s, action) {
    if (action === 'start') await apiMitPin(s, 'start', 'POST');
    else if (action === 'stop') await apiMitPin(s, 'stop', 'POST');
    else if (action === 'open') await window.station.openAdmin(s.id);
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

function setFeedback(msg, cls) {
    feedback.textContent = msg;
    feedback.className = cls || '';
}

// Bulk handlers
el('btn-rescan').onclick = async () => {
    setFeedback('Scanne...');
    await window.station.rescan();
    setFeedback('');
};
el('btn-add').onclick = () => el('add-dialog').classList.remove('hidden');
el('add-cancel').onclick = () => el('add-dialog').classList.add('hidden');
el('add-ok').onclick = async () => {
    const host = el('add-host').value.trim();
    const port = parseInt(el('add-port').value) || 5000;
    if (!host) return;
    el('add-feedback').textContent = 'Prüfe...';
    el('add-feedback').className = '';
    const ok = await window.station.addStation(host, port);
    if (ok) {
        el('add-feedback').textContent = '✓ Hinzugefügt';
        el('add-feedback').className = 'success';
        setTimeout(() => {
            el('add-dialog').classList.add('hidden');
            el('add-feedback').textContent = '';
            el('add-host').value = '';
        }, 800);
    } else {
        el('add-feedback').textContent = '✗ Nicht erreichbar';
        el('add-feedback').className = 'error';
    }
};

function stationById(id) { return stations.find(x => x.id === id) || { id, name: id, host: '?', port: '' }; }

async function bulk(action, method) {
    let fehler = 0;
    for (const id of selected) {
        const r = await apiMitPin(stationById(id), action, method);
        if (!r || !r.ok) fehler++;
    }
    return fehler;
}

el('bulk-start').onclick = async () => {
    if (!selected.size) return setFeedback('Keine Auswahl', 'error');
    const fehler = await bulk('start', 'POST');
    setFeedback(fehler ? `✗ ${fehler} Fehler von ${selected.size}` : `✓ ${selected.size} gestartet`, fehler ? 'error' : 'success');
};
el('bulk-stop').onclick = async () => {
    if (!selected.size) return setFeedback('Keine Auswahl', 'error');
    const fehler = await bulk('stop', 'POST');
    setFeedback(fehler ? `✗ ${fehler} Fehler von ${selected.size}` : `✓ ${selected.size} gestoppt`, fehler ? 'error' : 'success');
};
el('bulk-reboot').onclick = async () => {
    if (!selected.size) return setFeedback('Keine Auswahl', 'error');
    if (!confirm(tr(`${selected.size} Stationen neu starten?`))) return;
    const fehler = await bulk('system/reboot', 'POST');
    setFeedback(fehler ? `✗ ${fehler} Fehler von ${selected.size}` : `✓ Reboot an ${selected.size}`, fehler ? 'error' : 'success');
};

document.querySelectorAll('[data-upload]').forEach(btn => {
    btn.onclick = async () => {
        if (!selected.size) return setFeedback('Keine Auswahl', 'error');
        const type = btn.dataset.upload;
        const files = await window.station.pickFiles(type);
        if (!files.length) return;
        setFeedback(`Lade ${files.length} ${type} an ${selected.size} hoch...`);
        const r = await window.station.uploadTo(Array.from(selected), type, files);
        const fails = r.filter(x => !x.ok);
        if (fails.some(x => x.needsPin)) return setFeedback('✗ Eine Station verlangt eine PIN — 🔑 an der Karte', 'error');
        setFeedback(fails.length
            ? `✗ ${fails.length} Fehler von ${r.length}`
            : `✓ Alle ${r.length} Uploads ok`,
            fails.length ? 'error' : 'success');
    };
});

el('bulk-push-config').onclick = async () => {
    if (!selected.size) return setFeedback('Keine Auswahl', 'error');
    const cfg = {};
    const name = el('bulk-name').value.trim();
    const thr = el('bulk-threshold').value;
    const dly = el('bulk-delay').value;
    if (name) cfg.system_name = name;
    if (thr) cfg.threshold_m = parseFloat(thr);
    if (dly) cfg.delay_s = parseFloat(dly);
    if (!Object.keys(cfg).length) return setFeedback('Keine Felder gesetzt', 'error');
    const r = await window.station.pushConfig(Array.from(selected), cfg);
    const fails = r.filter(x => !x.ok);
    if (fails.some(x => x.needsPin)) return setFeedback('✗ Eine Station verlangt eine PIN — 🔑 an der Karte', 'error');
    setFeedback(fails.length ? `✗ ${fails.length} Fehler` : `✓ Config an ${r.length} gepusht`,
        fails.length ? 'error' : 'success');
};

window.station.onStations((list) => {
    stations = list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    // prune selections that vanished
    for (const id of selected) if (!stations.find(s => s.id === id)) selected.delete(id);
    render();
});

// Initial fetch
window.station.listStations().then(list => {
    stations = list;
    render();
});

window.station.version().then(v => { el('about-version').textContent = v; }).catch(() => {});

// LZ Media Station Manager – Electron main process
// Handles: window, mDNS discovery (_lzstation._tcp), HTTP calls to stations, multi-upload.

const { app, BrowserWindow, ipcMain, dialog, shell, Notification } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { Bonjour } = require('bonjour-service');
const alarme = require('./alarme');

// Bis v2.0.4 hiess die App "LZ Station Manager"; Electron leitet userData
// vom Produktnamen ab. Ohne den Pin faende eine installierte App ihre
// gespeicherten Stationen nicht mehr. Im Entwicklungsstart gilt der npm-Name.
const USERDATA_ORDNER = 'LZ Station Manager';
if (app.isPackaged) app.setPath('userData', path.join(app.getPath('appData'), USERDATA_ORDNER));

let mainWindow;
let bonjour;
let browser;

// In-memory station store: id -> { id, name, host, port, version, lastSeen, online, source }
const stations = new Map();
// Manually added IPs (persisted)
const storePath = path.join(app.getPath('userData'), 'stations.json');
let manual = [];
try { manual = JSON.parse(fs.readFileSync(storePath, 'utf8')); } catch { manual = []; }
function persistManual() {
    try { fs.writeFileSync(storePath, JSON.stringify(manual, null, 2)); } catch { /* ignore */ }
}

// PINs je Station (Zugangsschutz 3.0, `zugang.py` auf der Station). Schluessel
// ist host:port, damit die PIN auch nach einem Neustart der Station (neue
// Kennung) passt. Liegt in userData wie stations.json — nicht im Log, nicht
// in der Oberflaeche.
const pinPath = path.join(app.getPath('userData'), 'pins.json');
let pins = {};
try { pins = JSON.parse(fs.readFileSync(pinPath, 'utf8')); } catch { pins = {}; }
function persistPins() {
    try { fs.writeFileSync(pinPath, JSON.stringify(pins, null, 2), { mode: 0o600 }); } catch { /* ignore */ }
}
function pinFor(s) { return s ? (pins[`${s.host}:${s.port}`] || null) : null; }
function pinHeaders(s) { const p = pinFor(s); return p ? { 'X-LZ-Pin': p } : {}; }

// Gruppen, Tags und Stummschaltung (3.0) — nur im Manager, die Station weiss
// davon nichts. Schluessel wie bei den PINs host:port, damit die Zuordnung
// eine neue Stations-Kennung ueberlebt.
const gruppenPath = path.join(app.getPath('userData'), 'gruppen.json');
let ordnung = { gruppe: {}, tags: {}, stumm: {} };
try { ordnung = { ...ordnung, ...JSON.parse(fs.readFileSync(gruppenPath, 'utf8')) }; } catch { /* neu */ }
function persistOrdnung() {
    try { fs.writeFileSync(gruppenPath, JSON.stringify(ordnung, null, 2)); } catch { /* ignore */ }
}
function schluessel(s) { return `${s.host}:${s.port}`; }
function ordnungFuer(s) {
    const k = schluessel(s);
    return { gruppe: ordnung.gruppe[k] || '', tags: ordnung.tags[k] || [], stumm: !!ordnung.stumm[k] };
}

// Alarme (3.0): neueste zuerst, gedeckelt; Stand je Station fuer den Vergleich.
let alarmListe = [];
const letzterStand = new Map();

function emitAlarme() {
    if (mainWindow) mainWindow.webContents.send('alarme:update', alarmListe);
}

function melde(s, eintraege) {
    if (!eintraege.length) return;
    const zeit = new Date().toISOString();
    const stumm = ordnungFuer(s).stumm;
    const neu = eintraege.map(a => ({ ...a, zeit, station: s.id, name: s.name || s.host, stumm }));
    alarmListe = alarme.haengeAn(alarmListe, neu);
    emitAlarme();
    if (stumm || !Notification.isSupported()) return;
    for (const a of neu) {
        if (a.stufe === 'ok') continue;  // Entwarnung steht in der Liste, ohne Benachrichtigung
        try { new Notification({ title: `${a.name}`, body: a.text, silent: false }).show(); } catch { /* ignore */ }
    }
}

function emitStations() {
    if (!mainWindow) return;
    mainWindow.webContents.send('stations:update', Array.from(stations.values()).map(s => ({ ...s, ...ordnungFuer(s) })));
}

function upsertStation(s) {
    const existing = stations.get(s.id) || {};
    stations.set(s.id, { ...existing, ...s, lastSeen: Date.now(), online: true });
    emitStations();
}

// HTTP GET helper (lightweight, no extra deps)
function httpJson(url, opts = {}, body = null) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const req = http.request({
            hostname: u.hostname, port: u.port || 80, path: u.pathname + u.search,
            method: opts.method || 'GET',
            headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
            timeout: opts.timeout || 4000,
        }, (res) => {
            let chunks = '';
            res.on('data', d => chunks += d);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: chunks ? JSON.parse(chunks) : null }); }
                catch { resolve({ status: res.statusCode, body: chunks }); }
            });
        });
        req.on('error', reject);
        req.on('timeout', () => { req.destroy(new Error('timeout')); });
        if (body) req.write(typeof body === 'string' ? body : JSON.stringify(body));
        req.end();
    });
}

// Binaerer GET (Screenshots) — Puffer, Inhaltstyp, Aufnahmezeit.
function httpRaw(url, opts = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const req = http.request({
            hostname: u.hostname, port: u.port || 80, path: u.pathname + u.search,
            method: 'GET', timeout: opts.timeout || 4000,
        }, (res) => {
            const teile = [];
            res.on('data', d => teile.push(d));
            res.on('end', () => resolve({
                status: res.statusCode, daten: Buffer.concat(teile),
                typ: res.headers['content-type'], zeit: res.headers['x-lz-zeit'],
            }));
        });
        req.on('error', reject);
        req.on('timeout', () => { req.destroy(new Error('timeout')); });
        req.end();
    });
}

async function probeHost(host, port = 5000) {
    try {
        const r = await httpJson(`http://${host}:${port}/api/identity`, { timeout: 3500 });
        if (r.status === 200 && r.body && r.body.id) {
            upsertStation({
                id: r.body.id,
                name: r.body.name || host,
                host, port,
                version: r.body.version,
                hostname: r.body.hostname,
                source: 'manual',
            });
            return true;
        }
    } catch { /* offline */ }
    return false;
}

function standVon(s) {
    return { online: !!s.online, health: s.health || null,
             anzeigenOnline: s.anzeige ? s.anzeige.online : null,
             anzeigenAnzahl: s.anzeige ? s.anzeige.anzahl : null };
}

// Alle 10 s: Status, Szene und Identitaet je Station. Drei kleine GETs statt
// eines neuen Sammel-Endpunkts, damit der Manager auch mit Stationen der
// Version 2 spricht (die kennen /api/scene und /api/identity schon).
async function pollStation(s) {
    const basis = `http://${s.host}:${s.port}`;
    try {
        const r = await httpJson(`${basis}/api/status`, { timeout: 3000 });
        if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
        s.online = true;
        s.lastSeen = Date.now();
        s.distance = r.body.distance;
        s.state = r.body.state;
        s.active = r.body.active;
        s.geschlossen = !!r.body.geschlossen;
        s.anzeige = r.body.anzeige || null;
    } catch {
        s.online = false;
        return;
    }
    try {
        const r = await httpJson(`${basis}/api/scene`, { timeout: 3000 });
        if (r.status === 200 && r.body) {
            s.zone = r.body.zone || null;
            s.layoutId = r.body.layout_id || null;
            s.layoutName = (r.body.layout && r.body.layout.name) || null;
        }
    } catch { /* bleibt beim letzten Stand */ }
    try {
        const r = await httpJson(`${basis}/api/identity`, { timeout: 3000 });
        if (r.status === 200 && r.body) {
            s.health = r.body.health || null;
            s.healthAnzahl = r.body.health_anzahl || 0;
            s.version = r.body.version || s.version;
            s.name = r.body.name || s.name;
        }
    } catch { /* bleibt beim letzten Stand */ }
}

async function pollAll() {
    await Promise.allSettled(Array.from(stations.values()).map(pollStation));
    for (const s of stations.values()) {
        const neu = standVon(s);
        melde(s, alarme.uebergaenge(letzterStand.get(s.id), neu));
        letzterStand.set(s.id, neu);
        s.rot = alarme.istRot(neu);
    }
    emitStations();
}

function startDiscovery() {
    try {
        bonjour = new Bonjour();
        browser = bonjour.find({ type: 'lzstation' }, (svc) => {
            const host = (svc.referer && svc.referer.address) || (svc.addresses && svc.addresses[0]) || svc.host;
            const port = svc.port || 5000;
            // Probe to get identity
            probeHost(host, port).then(ok => {
                if (ok) {
                    const found = Array.from(stations.values()).find(x => x.host === host && x.port === port);
                    if (found) found.source = 'mdns';
                    emitStations();
                }
            });
        });
    } catch (e) {
        console.warn('mDNS discovery unavailable:', e.message);
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280, height: 800,
        title: 'LZ Media Station Manager',
        backgroundColor: '#132040',
        icon: path.join(__dirname, 'renderer', 'brand', 'icon-512.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            webviewTag: true,
        },
    });
    mainWindow.removeMenu();
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
    // mainWindow.webContents.openDevTools({ mode: 'detach' });
}

// ---- IPC handlers ----
ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('stations:list', () => Array.from(stations.values()));
ipcMain.handle('stations:addManual', async (_e, host, port = 5000) => {
    const ok = await probeHost(host, port);
    if (ok && !manual.find(m => m.host === host && m.port === port)) {
        manual.push({ host, port });
        persistManual();
    }
    return ok;
});
ipcMain.handle('stations:remove', (_e, id) => {
    const s = stations.get(id);
    if (s) {
        stations.delete(id);
        manual = manual.filter(m => !(m.host === s.host && m.port === s.port));
        persistManual();
        emitStations();
    }
    return true;
});
ipcMain.handle('stations:rescanManual', async () => {
    for (const m of manual) await probeHost(m.host, m.port);
    return Array.from(stations.values());
});
ipcMain.handle('station:apiCall', async (_e, id, action, method = 'POST', body = null) => {
    const s = stations.get(id);
    if (!s) return { error: 'unknown station' };
    try {
        const r = await httpJson(`http://${s.host}:${s.port}/api/${action}`, { method, headers: pinHeaders(s) }, body);
        // 401 mit `zugang`: die Station verlangt eine PIN (oder die gespeicherte
        // stimmt nicht mehr). Der Renderer fragt dann nach und wiederholt.
        return { ok: r.status >= 200 && r.status < 300, status: r.status, body: r.body,
                 needsPin: r.status === 401 && !!(r.body && r.body.zugang) };
    } catch (e) { return { error: e.message }; }
});
ipcMain.handle('station:setPin', (_e, id, pin) => {
    const s = stations.get(id);
    if (!s) return false;
    const key = `${s.host}:${s.port}`;
    if (pin) pins[key] = String(pin); else delete pins[key];
    persistPins();
    return true;
});
ipcMain.handle('station:hasPin', (_e, id) => !!pinFor(stations.get(id)));
ipcMain.handle('station:accessInfo', async (_e, id) => {
    const s = stations.get(id);
    if (!s) return { error: 'unknown station' };
    try {
        const r = await httpJson(`http://${s.host}:${s.port}/api/zugang`, { timeout: 3000 });
        return { ok: r.status === 200, gesetzt: !!(r.body && r.body.gesetzt), gespeichert: !!pinFor(s) };
    } catch (e) { return { error: e.message, gespeichert: !!pinFor(s) }; }
});
ipcMain.handle('ordnung:setzen', (_e, ids, aenderung) => {
    // {gruppe?: string, tagDazu?: string, tagWeg?: string}
    for (const id of ids) {
        const s = stations.get(id);
        if (!s) continue;
        const k = schluessel(s);
        if (typeof aenderung.gruppe === 'string') {
            const g = aenderung.gruppe.trim().slice(0, 40);
            if (g) ordnung.gruppe[k] = g; else delete ordnung.gruppe[k];
        }
        const tags = new Set(ordnung.tags[k] || []);
        if (aenderung.tagDazu) tags.add(String(aenderung.tagDazu).trim().slice(0, 30));
        if (aenderung.tagWeg) tags.delete(aenderung.tagWeg);
        tags.delete('');
        if (tags.size) ordnung.tags[k] = Array.from(tags).sort(); else delete ordnung.tags[k];
    }
    persistOrdnung();
    emitStations();
    return true;
});
ipcMain.handle('station:setStumm', (_e, id, stumm) => {
    const s = stations.get(id);
    if (!s) return false;
    if (stumm) ordnung.stumm[schluessel(s)] = true; else delete ordnung.stumm[schluessel(s)];
    persistOrdnung();
    emitStations();
    return true;
});
ipcMain.handle('alarme:list', () => alarmListe);
ipcMain.handle('alarme:clear', () => { alarmListe = []; emitAlarme(); return true; });
// Letzter Screenshot einer Station als data:-URL. `anfordern` bittet die
// Station erst um ein frisches Bild (bis zu ~5 s).
ipcMain.handle('station:screenshot', async (_e, id, anfordern) => {
    const s = stations.get(id);
    if (!s) return { error: 'unknown station' };
    const basis = `http://${s.host}:${s.port}`;
    let pfad = '/api/anzeige/screenshot';
    let hinweis = null;
    try {
        if (anfordern) {
            const r = await httpJson(`${basis}/api/anzeige/screenshot/anfordern`,
                                     { method: 'POST', headers: pinHeaders(s), timeout: 8000 }, {});
            if (r.status === 401) return { needsPin: true };
            // Kein frisches Bild in der Wartezeit (z. B. Anzeige gedrosselt):
            // das letzte vorhandene zeigen und den Grund dazu sagen, statt
            // eine leere Kachel zu lassen.
            if (r.status === 200) pfad = r.body.url || pfad;
            else hinweis = (r.body && r.body.error) || `HTTP ${r.status}`;
        }
        const b = await httpRaw(`${basis}${pfad}`, { timeout: 5000 });
        if (b.status !== 200) return hinweis ? { error: hinweis } : { fehlt: true };
        return { ok: true, bild: `data:${b.typ || 'image/jpeg'};base64,${b.daten.toString('base64')}`,
                 zeit: b.zeit || null, hinweis };
    } catch (e) { return { error: e.message }; }
});
ipcMain.handle('station:adminUrl', (_e, id) => {
    const s = stations.get(id);
    return s ? `http://${s.host}:${s.port}/admin` : null;
});
ipcMain.handle('station:openAdmin', (_e, id) => {
    const s = stations.get(id);
    if (s) shell.openExternal(`http://${s.host}:${s.port}/admin`);
});
ipcMain.handle('media:pickFiles', async (_e, type) => {
    const filters = {
        videos: [{ name: 'Videos', extensions: ['mp4', 'mkv', 'avi', 'mov', 'webm'] }],
        images: [{ name: 'Bilder', extensions: ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'] }],
        audio:  [{ name: 'Audio',  extensions: ['mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac'] }],
    }[type] || [];
    const r = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile', 'multiSelections'],
        filters,
    });
    return r.canceled ? [] : r.filePaths;
});
ipcMain.handle('media:uploadToStations', async (_e, ids, type, files) => {
    // Upload each file to each station via multipart POST
    const results = [];
    for (const id of ids) {
        const s = stations.get(id);
        if (!s) { results.push({ id, ok: false, error: 'unknown' }); continue; }
        for (const file of files) {
            try {
                await uploadFile(s.host, s.port, type, file, pinHeaders(s));
                results.push({ id, file: path.basename(file), ok: true });
            } catch (e) {
                results.push({ id, file: path.basename(file), ok: false, error: e.message,
                               needsPin: /^HTTP 401/.test(e.message) });
            }
            mainWindow.webContents.send('upload:progress', { id, file: path.basename(file) });
        }
    }
    return results;
});
ipcMain.handle('config:pushToStations', async (_e, ids, partialConfig) => {
    const results = [];
    for (const id of ids) {
        const s = stations.get(id);
        if (!s) { results.push({ id, ok: false, error: 'unknown' }); continue; }
        try {
            const r = await httpJson(`http://${s.host}:${s.port}/api/config`, { method: 'POST', headers: pinHeaders(s) }, partialConfig);
            results.push({ id, ok: r.status === 200, status: r.status, needsPin: r.status === 401 });
        } catch (e) { results.push({ id, ok: false, error: e.message }); }
    }
    return results;
});

// Multipart uploader (raw, no extra deps)
function uploadFile(host, port, type, filePath, extraHeaders = {}) {
    return new Promise((resolve, reject) => {
        const boundary = '----lzstation' + Date.now();
        const filename = path.basename(filePath);
        const head = Buffer.from(
            `--${boundary}\r\n` +
            `Content-Disposition: form-data; name="file"; filename="${filename}"\r\n` +
            `Content-Type: application/octet-stream\r\n\r\n`);
        const tail = Buffer.from(`\r\n--${boundary}--\r\n`);
        const stat = fs.statSync(filePath);
        const total = head.length + stat.size + tail.length;
        const req = http.request({
            hostname: host, port, path: `/api/upload/${type}`, method: 'POST',
            headers: {
                'Content-Type': `multipart/form-data; boundary=${boundary}`,
                'Content-Length': total,
                ...extraHeaders,
            },
            timeout: 600000,
        }, (res) => {
            let body = '';
            res.on('data', d => body += d);
            res.on('end', () => {
                if (res.statusCode === 200) resolve(body);
                else reject(new Error(`HTTP ${res.statusCode}: ${body}`));
            });
        });
        req.on('error', reject);
        req.write(head);
        const stream = fs.createReadStream(filePath);
        stream.on('data', c => req.write(c));
        stream.on('end', () => { req.write(tail); req.end(); });
        stream.on('error', reject);
    });
}

app.whenReady().then(() => {
    createWindow();
    startDiscovery();
    // probe persisted manual entries
    manual.forEach(m => probeHost(m.host, m.port));
    setInterval(pollAll, 10000);
    setTimeout(pollAll, 1500);
});

app.on('window-all-closed', () => {
    if (browser) browser.stop();
    if (bonjour) bonjour.destroy();
    if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

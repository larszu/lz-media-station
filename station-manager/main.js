// LZ Station Manager – Electron main process
// Handles: window, mDNS discovery (_lzstation._tcp), HTTP calls to stations, multi-upload.

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { Bonjour } = require('bonjour-service');

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

function emitStations() {
    if (!mainWindow) return;
    mainWindow.webContents.send('stations:update', Array.from(stations.values()));
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

async function pollAll() {
    // Re-probe all known stations to update online state
    const promises = [];
    for (const s of stations.values()) {
        promises.push((async () => {
            try {
                const r = await httpJson(`http://${s.host}:${s.port}/api/status`, { timeout: 3000 });
                if (r.status === 200) {
                    s.online = true;
                    s.lastSeen = Date.now();
                    s.distance = r.body.distance;
                    s.state = r.body.state;
                    s.active = r.body.active;
                } else {
                    s.online = false;
                }
            } catch {
                s.online = false;
            }
        })());
    }
    await Promise.allSettled(promises);
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
        title: 'LZ Station Manager',
        backgroundColor: '#1a1a2e',
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
        const r = await httpJson(`http://${s.host}:${s.port}/api/${action}`, { method }, body);
        return { ok: r.status >= 200 && r.status < 300, status: r.status, body: r.body };
    } catch (e) { return { error: e.message }; }
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
                await uploadFile(s.host, s.port, type, file);
                results.push({ id, file: path.basename(file), ok: true });
            } catch (e) {
                results.push({ id, file: path.basename(file), ok: false, error: e.message });
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
            const r = await httpJson(`http://${s.host}:${s.port}/api/config`, { method: 'POST' }, partialConfig);
            results.push({ id, ok: r.status === 200, status: r.status });
        } catch (e) { results.push({ id, ok: false, error: e.message }); }
    }
    return results;
});

// Multipart uploader (raw, no extra deps)
function uploadFile(host, port, type, filePath) {
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
    setInterval(pollAll, 4000);
});

app.on('window-all-closed', () => {
    if (browser) browser.stop();
    if (bonjour) bonjour.destroy();
    if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

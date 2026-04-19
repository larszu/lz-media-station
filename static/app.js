document.addEventListener('DOMContentLoaded', function () {
    loadAllMedia();
    setInterval(fetchStatus, 500);
    fetchStatus();
    setupSliders();
    setupUploads();
});

/* ---- Status Polling ---- */

var allMedia = { videos: [], images: [], audio: [] };
var config = {};

async function fetchStatus() {
    try {
        var r = await fetch('/api/status');
        var d = await r.json();
        config = d.config;
        updateStatusUI(d);
    } catch (e) {
        document.getElementById('status-dot').className = 'status-dot';
    }
}

function updateStatusUI(d) {
    var cfg = d.config;
    var dist = d.distance;
    var threshold = cfg.threshold_m;

    document.getElementById('status-dot').className = 'status-dot' + (d.active ? ' active' : ' connected');
    document.getElementById('system-name').textContent = cfg.system_name || 'Station';

    document.getElementById('dist-value').textContent = dist.toFixed(2);
    var pct = Math.min(dist / 4, 1) * 100;
    document.getElementById('dist-fill').style.width = pct + '%';
    document.getElementById('dist-fill').className = 'fill' + (dist <= threshold && d.active ? ' near' : '');
    document.getElementById('dist-marker').style.left = Math.min(threshold / 4, 1) * 100 + '%';

    var badge = document.getElementById('state-badge');
    var states = {
        idle: ['Inaktiv', ''],
        far: ['Fern', 'far'],
        near: ['Nah', 'near'],
        pending_near: ['\u2192 Nah\u2026', 'pending'],
        pending_far: ['\u2192 Fern\u2026', 'pending'],
    };
    var s = states[d.state] || ['?', ''];
    badge.textContent = s[0];
    badge.className = 'badge ' + s[1];

    var a = document.activeElement;
    if (!a || a.id !== 'cfg-name') el('cfg-name').value = cfg.system_name || '';
    if (!a || a.id !== 'cfg-threshold') { el('cfg-threshold').value = cfg.threshold_m; el('threshold-display').textContent = cfg.threshold_m.toFixed(2); }
    if (!a || a.id !== 'cfg-delay') { el('cfg-delay').value = cfg.delay_s; el('delay-display').textContent = cfg.delay_s.toFixed(1); }
    if (!a || a.id !== 'cfg-imginterval') { el('cfg-imginterval').value = cfg.image_interval_s; el('imgint-display').textContent = cfg.image_interval_s; }
    if (!a || a.id !== 'cfg-volume') { el('cfg-volume').value = cfg.audio_volume; el('vol-display').textContent = cfg.audio_volume; }
    if (!a || a.id !== 'cfg-gpio-trigger') el('cfg-gpio-trigger').value = cfg.gpio_trigger;
    if (!a || a.id !== 'cfg-gpio-echo') el('cfg-gpio-echo').value = cfg.gpio_echo;

    document.querySelectorAll('.threshold-val').forEach(function (e) { e.textContent = cfg.threshold_m.toFixed(1); });

    renderZoneOverview('near', cfg.near || {});
    renderZoneOverview('far', cfg.far || {});
}

function renderZoneOverview(zone, data) {
    var container = document.getElementById('zone-' + zone + '-media');
    var items = [];
    (data.videos || []).forEach(function (f) { items.push('\uD83C\uDFAC ' + f); });
    (data.images || []).forEach(function (f) { items.push('\uD83D\uDDBC ' + f); });
    (data.audio || []).forEach(function (f) { items.push('\uD83C\uDFB5 ' + f); });
    container.innerHTML = items.length
        ? items.map(function (i) { return '<div class="zone-item">' + esc(i) + '</div>'; }).join('')
        : '<div class="zone-empty">Keine Medien zugewiesen</div>';
}

/* ---- Sliders ---- */

function setupSliders() {
    slider('cfg-threshold', 'threshold-display', function (v) { return v.toFixed(2); });
    slider('cfg-delay', 'delay-display', function (v) { return v.toFixed(1); });
    slider('cfg-imginterval', 'imgint-display', function (v) { return String(v); });
    slider('cfg-volume', 'vol-display', function (v) { return String(v); });
}

function slider(id, displayId, fmt) {
    el(id).addEventListener('input', function (e) {
        el(displayId).textContent = fmt(parseFloat(e.target.value));
    });
}

/* ---- Media Library ---- */

async function loadAllMedia() {
    for (var type of ['videos', 'images', 'audio']) {
        try {
            var r = await fetch('/api/media/' + type);
            allMedia[type] = await r.json();
        } catch (e) { allMedia[type] = []; }
    }
    try {
        var r2 = await fetch('/api/status');
        var d = await r2.json();
        config = d.config;
    } catch (e) {}
    renderMediaLists();
}

function renderMediaLists() {
    ['videos', 'images', 'audio'].forEach(function (type) {
        var list = document.getElementById('list-' + type);
        if (!allMedia[type].length) {
            list.innerHTML = '<div class="empty">Keine Dateien</div>';
            return;
        }
        var nearFiles = (config.near && config.near[type]) || [];
        var farFiles = (config.far && config.far[type]) || [];

        list.innerHTML = allMedia[type].map(function (f) {
            var inNear = nearFiles.indexOf(f.name) >= 0;
            var inFar = farFiles.indexOf(f.name) >= 0;
            return '<div class="media-item">' +
                '<div class="media-info">' +
                    '<span class="media-name">' + esc(f.name) + '</span>' +
                    '<span class="media-size">' + f.size_mb + ' MB</span>' +
                '</div>' +
                '<div class="media-actions">' +
                    '<button class="zone-btn' + (inNear ? ' active near' : '') + '" onclick="toggleZone(\'near\',\'' + type + '\',\'' + escAttr(f.name) + '\')">Nah</button>' +
                    '<button class="zone-btn' + (inFar ? ' active far' : '') + '" onclick="toggleZone(\'far\',\'' + type + '\',\'' + escAttr(f.name) + '\')">Fern</button>' +
                    '<button class="del-btn" onclick="deleteMedia(\'' + type + '\',\'' + escAttr(f.name) + '\')" title="L\u00f6schen">\u2715</button>' +
                '</div>' +
            '</div>';
        }).join('');
    });
}

async function toggleZone(zone, type, name) {
    if (!config[zone]) config[zone] = { videos: [], images: [], audio: [] };
    var list = config[zone][type] || [];
    var idx = list.indexOf(name);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(name);
    }
    config[zone][type] = list;

    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(makeZonePayload(zone, type, list)),
    });
    renderMediaLists();
}

function makeZonePayload(zone, type, list) {
    var payload = {};
    payload[zone] = {};
    payload[zone][type] = list;
    return payload;
}

async function deleteMedia(type, name) {
    if (!confirm('"' + name + '" l\u00f6schen?')) return;
    await fetch('/api/media/' + type + '/' + encodeURIComponent(name), { method: 'DELETE' });
    await loadAllMedia();
}

/* ---- Tabs ---- */

function switchTab(type, btn) {
    document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-content').forEach(function (t) { t.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + type).classList.add('active');
}

/* ---- Config Save ---- */

async function saveConfig() {
    var data = {
        system_name: el('cfg-name').value,
        threshold_m: parseFloat(el('cfg-threshold').value),
        delay_s: parseFloat(el('cfg-delay').value),
        image_interval_s: parseInt(el('cfg-imginterval').value),
        audio_volume: parseInt(el('cfg-volume').value),
        gpio_trigger: parseInt(el('cfg-gpio-trigger').value),
        gpio_echo: parseInt(el('cfg-gpio-echo').value),
    };
    var fb = el('save-feedback');
    try {
        var r = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (r.ok) {
            fb.textContent = '\u2713 Gespeichert';
            fb.className = 'feedback success';
        } else { throw 0; }
    } catch (e) {
        fb.textContent = '\u2717 Fehler';
        fb.className = 'feedback error';
    }
    setTimeout(function () { fb.textContent = ''; }, 2000);
}

/* ---- Upload ---- */

function setupUploads() {
    document.querySelectorAll('.upload-area').forEach(function (area) {
        var type = area.dataset.type;
        var input = area.querySelector('input[type="file"]');
        area.addEventListener('click', function (e) { if (e.target !== input) input.click(); });
        area.addEventListener('dragover', function (e) { e.preventDefault(); area.classList.add('dragover'); });
        area.addEventListener('dragleave', function () { area.classList.remove('dragover'); });
        area.addEventListener('drop', function (e) {
            e.preventDefault();
            area.classList.remove('dragover');
            uploadFiles(type, e.dataTransfer.files, area);
        });
        input.addEventListener('change', function () { uploadFiles(type, input.files, area); input.value = ''; });
    });
}

async function uploadFiles(type, files, area) {
    var text = area.querySelector('.upload-text');
    var prog = area.querySelector('.progress');
    var fill = area.querySelector('.progress-fill');
    var ptext = area.querySelector('.progress-text');
    text.hidden = true;
    prog.hidden = false;

    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        var fd = new FormData();
        fd.append('file', file);
        try {
            await new Promise(function (ok, fail) {
                var xhr = new XMLHttpRequest();
                xhr.upload.onprogress = function (e) {
                    if (e.lengthComputable) {
                        var p = Math.round(e.loaded / e.total * 100);
                        fill.style.width = p + '%';
                        ptext.textContent = file.name + ': ' + p + '%';
                    }
                };
                xhr.onload = function () { xhr.status === 200 ? ok() : fail(); };
                xhr.onerror = fail;
                xhr.open('POST', '/api/upload/' + type);
                xhr.send(fd);
            });
        } catch (e) { /* upload failed */ }
    }
    text.hidden = false;
    prog.hidden = true;
    fill.style.width = '0%';
    await loadAllMedia();
}

/* ---- API Shortcut ---- */

async function api(action) {
    await fetch('/api/' + action, { method: 'POST' });
}

/* ---- Helpers ---- */

function el(id) { return document.getElementById(id); }

function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function escAttr(s) {
    return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

document.addEventListener('DOMContentLoaded', function () {
    loadAllMedia();
    setInterval(fetchStatus, 500);
    fetchStatus();
    setupSliders();
    setupUploads();
    loadNetwork();
    loadWifi();
    // Umschalten der Quelle sofort auf die Felder anwenden — nicht erst beim
    // naechsten Status-Poll, sonst springt die Auswahl fuer den Nutzer zurueck.
    el('cfg-sensor-type').addEventListener('change', function (e) {
        toggleSensorFields(e.target.value);
    });
});

// ESC -> zurück zum Home-Menü (von Admin aus)
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' || e.keyCode === 27) {
        window.location.href = '/';
    }
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

    // `null` heisst „keine gueltige Messung" — noch nie gemessen oder der
    // Sensor antwortet nicht mehr. Frueher kam hier 0.00 an, also die Zahl,
    // die auch „Besucher steht direkt davor" bedeutet: die Oberflaeche konnte
    // einen toten Sensor nicht von einem sehr nahen Besucher unterscheiden.
    if (dist === null || dist === undefined) {
        document.getElementById('dist-value').textContent = '--';
        document.getElementById('dist-fill').style.width = '0%';
        document.getElementById('dist-fill').className = 'fill';
    } else {
        document.getElementById('dist-value').textContent = dist.toFixed(2);
        var pct = Math.min(dist / 4, 1) * 100;
        document.getElementById('dist-fill').style.width = pct + '%';
        document.getElementById('dist-fill').className = 'fill' + (dist <= threshold && d.active ? ' near' : '');
    }
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
    if (!a || a.id !== 'cfg-mastervol') { el('cfg-mastervol').value = cfg.master_volume; el('mastervol-display').textContent = cfg.master_volume; }
    if (!a || a.id !== 'cfg-vidvol') { el('cfg-vidvol').value = cfg.video_volume; el('vidvol-display').textContent = cfg.video_volume; }
    if (!a || a.id !== 'cfg-audvol') { el('cfg-audvol').value = cfg.audio_volume; el('audvol-display').textContent = cfg.audio_volume; }
    if (!a || a.id !== 'cfg-gpio-trigger') el('cfg-gpio-trigger').value = cfg.gpio_trigger;
    if (!a || a.id !== 'cfg-gpio-echo') el('cfg-gpio-echo').value = cfg.gpio_echo;
    if (!a || a.id !== 'cfg-camera-index') el('cfg-camera-index').value = cfg.camera_index;
    if (!a || a.id !== 'cfg-camera-focal') el('cfg-camera-focal').value = cfg.camera_focal_px;
    if (!a || a.id !== 'cfg-sensor-type') { el('cfg-sensor-type').value = cfg.sensor_type || 'ultrasonic'; toggleSensorFields(cfg.sensor_type || 'ultrasonic'); }
    if (!a || a.id !== 'cfg-display-ip') el('cfg-display-ip').value = cfg.display_ip || '';
    if (!a || a.id !== 'cfg-video-resume') el('cfg-video-resume').checked = !!cfg.video_resume;

    // Klartext-Zustand der Quelle. Ohne gueltige Messung sagt er, warum —
    // „kein Sensor angeschlossen" statt einer stumm erfundenen Zahl.
    var st = el('sensor-status');
    if (st) {
        st.textContent = d.sensor_status || '';
        st.className = 'sensor-status' + (d.sensor_ok ? ' ok' : ' warn');
    }

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
    slider('cfg-mastervol', 'mastervol-display', function (v) { return String(v); });
    slider('cfg-vidvol', 'vidvol-display', function (v) { return String(v); });
    slider('cfg-audvol', 'audvol-display', function (v) { return String(v); });
}

function slider(id, displayId, fmt) {
    el(id).addEventListener('input', function (e) {
        el(displayId).textContent = fmt(parseFloat(e.target.value));
    });
}

/* ---- Abstandsquelle: Felder je nach Typ zeigen/verbergen ---- */

function toggleSensorFields(type) {
    var istKamera = (type === 'camera');
    document.querySelectorAll('.sensor-ultrasonic').forEach(function (e) {
        e.style.display = istKamera ? 'none' : '';
    });
    document.querySelectorAll('.sensor-camera').forEach(function (e) {
        e.style.display = istKamera ? '' : 'none';
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
    if (!confirm('"' + name + '" aus allen Zonen entfernen?\n(Die Datei bleibt auf dem Pi erhalten.)')) return;
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
        master_volume: parseInt(el('cfg-mastervol').value),
        video_volume: parseInt(el('cfg-vidvol').value),
        audio_volume: parseInt(el('cfg-audvol').value),
        sensor_type: el('cfg-sensor-type').value,
        gpio_trigger: parseInt(el('cfg-gpio-trigger').value),
        gpio_echo: parseInt(el('cfg-gpio-echo').value),
        camera_index: parseInt(el('cfg-camera-index').value),
        camera_focal_px: parseFloat(el('cfg-camera-focal').value),
        display_ip: el('cfg-display-ip').value.trim(),
        video_resume: el('cfg-video-resume').checked,
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

/* ---- Network ---- */

async function loadNetwork() {
    var info = el('net-info');
    try {
        var r = await fetch('/api/system/network');
        var d = await r.json();
        if (d.error && (!d.available_connections || !d.available_connections.length)) {
            info.textContent = d.error;
            return;
        }
        var lines = [];
        if (d.connection) lines.push('Aktive Verbindung: <strong>' + esc(d.connection) + '</strong> auf ' + esc(d.interface || '?'));
        if (d.method)     lines.push('Modus: <strong>' + (d.method === 'auto' ? 'DHCP' : 'Statisch') + '</strong>');
        if (d.addresses && d.addresses.length) lines.push('IP: <strong>' + d.addresses.map(esc).join(', ') + '</strong>');
        if (d.gateway)    lines.push('Gateway: ' + esc(d.gateway));
        if (d.dns && d.dns.length) lines.push('DNS: ' + d.dns.map(esc).join(', '));
        info.innerHTML = lines.length ? lines.join('<br>') : 'Kein aktiver Adapter gefunden.';

        var sel = el('net-connection');
        sel.innerHTML = '';
        (d.available_connections || []).forEach(function (c) {
            var opt = document.createElement('option');
            opt.value = c.name;
            opt.textContent = c.name + ' (' + c.device + ', ' + c.state + ')';
            if (c.name === d.connection) opt.selected = true;
            sel.appendChild(opt);
        });
        if (d.method === 'manual') {
            el('net-method-manual').checked = true;
        } else {
            el('net-method-auto').checked = true;
        }
        if (d.addresses && d.addresses.length) el('net-address').value = d.addresses[0];
        if (d.gateway) el('net-gateway').value = d.gateway;
        if (d.dns && d.dns.length) el('net-dns').value = d.dns.join(',');
    } catch (e) {
        info.textContent = 'Netzwerk-API nicht erreichbar.';
    }
}

async function saveNetwork() {
    var fb = el('net-feedback');
    var method = document.querySelector('input[name="net-method"]:checked').value;
    var body = {
        connection: el('net-connection').value,
        method: method,
        address: el('net-address').value,
        gateway: el('net-gateway').value,
        dns: el('net-dns').value,
    };
    if (!body.connection) { fb.textContent = 'Keine Verbindung gewählt.'; fb.className = 'feedback error'; return; }
    if (method === 'manual' && !body.address) { fb.textContent = 'IP-Adresse fehlt.'; fb.className = 'feedback error'; return; }
    if (!confirm('Netzwerk-Einstellungen jetzt anwenden?\nDie Verbindung wird kurz unterbrochen.')) return;
    fb.textContent = 'Wende an...';
    fb.className = 'feedback';
    try {
        var r = await fetch('/api/system/network', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '✓ Übernommen. Neue IP ggf. im Browser eingeben.';
            fb.className = 'feedback success';
            setTimeout(loadNetwork, 2000);
        } else {
            fb.textContent = '✗ ' + (d.error || 'Fehler');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '✗ Verbindung verloren (evtl. neue IP aktiv).';
        fb.className = 'feedback error';
    }
}

async function rebootPi() {
    if (!confirm('Pi wirklich neu starten?')) return;
    try { await fetch('/api/system/reboot', { method: 'POST' }); } catch (e) { /* expected */ }
    el('net-feedback').textContent = 'Pi wird neu gestartet...';
}

/* ---- WLAN ---- */

async function loadWifi() {
    var info = el('wifi-info');
    var list = el('wifi-list');
    info.textContent = 'Lade WLAN-Status...';
    list.innerHTML = '';
    try {
        var r = await fetch('/api/system/wifi');
        var d = await r.json();
        if (d.error && d.enabled === undefined) {
            info.textContent = d.error;
            return;
        }
        el('wifi-enabled').checked = !!d.enabled;
        if (!d.enabled) {
            info.textContent = 'WLAN ist deaktiviert.';
            return;
        }
        info.innerHTML = d.current_ssid
            ? 'Verbunden mit: <strong>' + esc(d.current_ssid) + '</strong>'
            : 'WLAN aktiv, keine Verbindung.';
        (d.networks || []).forEach(function (n) {
            var card = document.createElement('div');
            card.className = 'form-group';
            var lock = (n.security && n.security !== '--') ? '🔒 ' : '';
            var act = n.active ? ' ✓' : '';
            card.innerHTML = '<button class="btn" style="text-align:left" onclick="pickWifi(\'' +
                escAttr(n.ssid) + '\')">' + lock + esc(n.ssid) +
                ' <small>(' + n.signal + '%)' + act + '</small></button>';
            list.appendChild(card);
        });
    } catch (e) {
        info.textContent = 'WLAN-API nicht erreichbar.';
    }
}

function pickWifi(ssid) {
    el('wifi-ssid').value = ssid;
    el('wifi-password').focus();
}

async function toggleWifi() {
    var enabled = el('wifi-enabled').checked;
    var fb = el('wifi-feedback');
    fb.textContent = enabled ? 'Aktiviere WLAN...' : 'Deaktiviere WLAN...';
    fb.className = 'feedback';
    try {
        var r = await fetch('/api/system/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled }),
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '✓ ' + (enabled ? 'WLAN aktiv' : 'WLAN aus');
            fb.className = 'feedback success';
            setTimeout(loadWifi, 1500);
        } else {
            fb.textContent = '✗ ' + (d.error || 'Fehler');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '✗ ' + e.message;
        fb.className = 'feedback error';
    }
}

async function connectWifi() {
    var ssid = el('wifi-ssid').value.trim();
    var password = el('wifi-password').value;
    var fb = el('wifi-feedback');
    if (!ssid) { fb.textContent = 'SSID fehlt.'; fb.className = 'feedback error'; return; }
    fb.textContent = 'Verbinde mit ' + ssid + '...';
    fb.className = 'feedback';
    try {
        var r = await fetch('/api/system/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid: ssid, password: password }),
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '✓ Verbunden mit ' + ssid;
            fb.className = 'feedback success';
            el('wifi-password').value = '';
            setTimeout(function () { loadWifi(); loadNetwork(); }, 2500);
        } else {
            fb.textContent = '✗ ' + (d.error || 'Verbindung fehlgeschlagen');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '✗ ' + e.message;
        fb.className = 'feedback error';
    }
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

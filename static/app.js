document.addEventListener('DOMContentLoaded', function () {
    loadAllMedia();
    setInterval(fetchStatus, 500);
    fetchStatus();
    setupSliders();
    setupUploads();
    loadNetwork();
    loadWifi();
    // Die Statistik aendert sich in Minuten, nicht in Millisekunden — alle
    // 15 s reicht. Sie an den 500-ms-Status-Poll zu haengen waere Last ohne
    // Gegenwert, und zwar auf einem Pi.
    loadStatistik();
    setInterval(loadStatistik, 15000);
    // Der Zustand darf nicht erst beim naechsten Neuladen auffallen, muss aber
    // auch nicht im 500-ms-Takt geprueft werden: er liest die Platte aus.
    loadHealth();
    setInterval(loadHealth, 10000);
    ladeUntertitelListe();
    // Umschalten der Quelle sofort auf die Felder anwenden — nicht erst beim
    // naechsten Status-Poll, sonst springt die Auswahl fuer den Nutzer zurueck.
    el('cfg-sensor-type').addEventListener('change', function (e) {
        toggleSensorFields(e.target.value);
    });
    el('cfg-zonen-stufen').addEventListener('change', function (e) {
        toggleStufen(Number(e.target.value));
    });
    el('cfg-sync-rolle').addEventListener('change', function (e) {
        toggleSync(e.target.value);
    });
    // Zonen-Optionen wirken sofort: sie gehoeren zur Zonen-Uebersicht und
    // nicht zum Einstellungen-Formular, also gibt es dort auch keinen
    // Speichern-Knopf, auf den jemand warten muesste.
    ['near', 'mid', 'far'].forEach(function (zone) {
        ['shuffle', 'einmal'].forEach(function (opt) {
            el('zone-' + zone + '-' + opt).addEventListener('change', function (e) {
                setzeZonenOption(zone, opt, e.target.checked);
            });
        });
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
    var istTaster = (cfg.sensor_type === 'button');
    // Beim Taster IST der Abstand nur eine Uebersetzung (0 m = gedrueckt,
    // 25 m = frei). Die Zahl anzuzeigen waere ehrlich gemeint und trotzdem
    // irrefuehrend: „25.00 m" sagt niemandem, dass der Knopf nicht gedrueckt
    // ist. Deshalb hier der Zustand im Klartext.
    if (dist === null || dist === undefined) {
        document.getElementById('dist-value').textContent = '--';
        document.getElementById('dist-fill').style.width = '0%';
        document.getElementById('dist-fill').className = 'fill';
    } else if (istTaster) {
        var gedrueckt = dist <= threshold;
        document.getElementById('dist-value').textContent = gedrueckt ? 'Gedrückt' : 'Frei';
        document.getElementById('dist-fill').style.width = gedrueckt ? '100%' : '0%';
        document.getElementById('dist-fill').className = 'fill' + (gedrueckt && d.active ? ' near' : '');
    } else {
        document.getElementById('dist-value').textContent = dist.toFixed(2);
        var pct = Math.min(dist / 4, 1) * 100;
        document.getElementById('dist-fill').style.width = pct + '%';
        document.getElementById('dist-fill').className = 'fill' + (dist <= threshold && d.active ? ' near' : '');
    }
    // Die Schwellen-Marke ergibt beim Taster keinen Sinn — es gibt keine
    // Entfernung, auf die sie zeigen koennte.
    document.getElementById('dist-marker').style.display = istTaster ? 'none' : '';
    document.getElementById('dist-marker').style.left = Math.min(threshold / 4, 1) * 100 + '%';

    var badge = document.getElementById('state-badge');
    var states = {
        idle: ['Inaktiv', ''],
        far: ['Fern', 'far'],
        mid: ['Mitte', 'mid'],
        near: ['Nah', 'near'],
        pending_near: ['\u2192 Nah\u2026', 'pending'],
        pending_mid: ['\u2192 Mitte\u2026', 'pending'],
        pending_far: ['\u2192 Fern\u2026', 'pending'],
    };
    var s = states[d.state] || ['?', ''];
    // Der Wochenplan schlaegt den Zonen-Zustand: „Fern" waere nachts
    // irrefuehrend — es spielt ja gar nichts, und zwar absichtlich.
    if (d.geschlossen) s = ['Geschlossen', 'pending'];
    badge.textContent = s[0];
    badge.className = 'badge ' + s[1];

    var a = document.activeElement;
    if (!a || a.id !== 'cfg-name') el('cfg-name').value = cfg.system_name || '';
    if (!a || a.id !== 'cfg-threshold') { el('cfg-threshold').value = cfg.threshold_m; el('threshold-display').textContent = cfg.threshold_m.toFixed(2); }
    if (!a || a.id !== 'cfg-delay') { el('cfg-delay').value = cfg.delay_s; el('delay-display').textContent = cfg.delay_s.toFixed(1); }
    if (!a || a.id !== 'cfg-threshold-mid') { el('cfg-threshold-mid').value = cfg.threshold_mid_m; el('threshold-mid-display').textContent = Number(cfg.threshold_mid_m).toFixed(2); }
    if (!a || a.id !== 'cfg-zonen-stufen') { el('cfg-zonen-stufen').value = String(cfg.zonen_stufen || 2); }
    toggleStufen(Number(cfg.zonen_stufen || 2));
    if (!a || a.id !== 'cfg-imginterval') { el('cfg-imginterval').value = cfg.image_interval_s; el('imgint-display').textContent = cfg.image_interval_s; }
    if (!a || a.id !== 'cfg-mastervol') { el('cfg-mastervol').value = cfg.master_volume; el('mastervol-display').textContent = cfg.master_volume; }
    if (!a || a.id !== 'cfg-vidvol') { el('cfg-vidvol').value = cfg.video_volume; el('vidvol-display').textContent = cfg.video_volume; }
    if (!a || a.id !== 'cfg-audvol') { el('cfg-audvol').value = cfg.audio_volume; el('audvol-display').textContent = cfg.audio_volume; }
    if (!a || a.id !== 'cfg-gpio-trigger') el('cfg-gpio-trigger').value = cfg.gpio_trigger;
    if (!a || a.id !== 'cfg-gpio-echo') el('cfg-gpio-echo').value = cfg.gpio_echo;
    if (!a || a.id !== 'cfg-camera-index') el('cfg-camera-index').value = cfg.camera_index;
    if (!a || a.id !== 'cfg-camera-focal') el('cfg-camera-focal').value = cfg.camera_focal_px;
    if (!a || a.id !== 'cfg-button-pin') el('cfg-button-pin').value = cfg.button_pin;
    if (!a || a.id !== 'cfg-button-haltezeit') el('cfg-button-haltezeit').value = cfg.button_haltezeit_s;
    if (!a || a.id !== 'cfg-sensor-type') { el('cfg-sensor-type').value = cfg.sensor_type || 'auto'; toggleSensorFields(cfg.sensor_type || 'auto'); }
    if (!a || a.id !== 'cfg-sync-master') el('cfg-sync-master').value = cfg.sync_master || '';
    if (!a || a.id !== 'cfg-sync-port') el('cfg-sync-port').value = cfg.sync_port;
    if (!a || a.id !== 'cfg-sync-rolle') { el('cfg-sync-rolle').value = cfg.sync_rolle || 'aus'; toggleSync(cfg.sync_rolle || 'aus'); }
    if (!a || a.id !== 'cfg-sprachen') el('cfg-sprachen').value = (cfg.sprachen || []).join(', ');
    if (!a || a.id !== 'cfg-display-ip') el('cfg-display-ip').value = cfg.display_ip || '';
    if (!a || a.id !== 'cfg-video-resume') el('cfg-video-resume').checked = !!cfg.video_resume;

    // Klartext-Zustand der Quelle. Ohne gueltige Messung sagt er, warum —
    // „kein Sensor angeschlossen" statt einer stumm erfundenen Zahl.
    var st = el('sensor-status');
    if (st) {
        if (d.geschlossen) {
            // Erklaeren, warum nichts spielt — sonst sieht der Wochenplan aus
            // wie ein Defekt, und jemand sucht am Sensor.
            st.textContent = 'Außerhalb der Öffnungszeiten — Schirm schwarz, Ton aus. '
                + (d.sensor_status || '');
            st.className = 'sensor-status warn';
        } else {
            st.textContent = d.sensor_status || '';
            st.className = 'sensor-status' + (d.sensor_ok ? ' ok' : ' warn');
        }
    }

    renderZeitplan(cfg);

    document.querySelectorAll('.threshold-val').forEach(function (e) { e.textContent = cfg.threshold_m.toFixed(1); });
    document.querySelectorAll('.threshold-mid-val').forEach(function (e) { e.textContent = Number(cfg.threshold_mid_m).toFixed(1); });

    renderZoneOverview('near', cfg.near || {});
    renderZoneOverview('mid', cfg.mid || {});
    renderZoneOverview('far', cfg.far || {});
}

var ZONE_SYMBOL = { videos: '\uD83C\uDFAC', images: '\uD83D\uDDBC', audio: '\uD83C\uDFB5' };

function renderZoneOverview(zone, data) {
    var container = document.getElementById('zone-' + zone + '-media');
    var a = document.activeElement;

    // Optionen der Zone (nicht anfassen, was gerade den Fokus hat).
    ['shuffle', 'einmal'].forEach(function (opt) {
        var id = 'zone-' + zone + '-' + opt;
        if (!a || a.id !== id) el(id).checked = !!data[opt];
    });

    var zeiten = data.bildzeiten || {};
    var zeilen = [];
    ['videos', 'images', 'audio'].forEach(function (art) {
        (data[art] || []).forEach(function (f, i, liste) {
            // Pfeile zum Umsortieren statt Drag: die Verwaltung wird vom
            // HANDY bedient, und Drag-and-Drop mit dem Daumen auf einer Liste
            // ist dort der unzuverlaessigste Weg, den es gibt.
            var hoch = i > 0
                ? '<button class="ord-btn" onclick="verschiebe(\'' + zone + '\',\'' + art + '\',' + i + ',-1)" title="nach oben">\u25B2</button>'
                : '<span class="ord-btn leer"></span>';
            var runter = i < liste.length - 1
                ? '<button class="ord-btn" onclick="verschiebe(\'' + zone + '\',\'' + art + '\',' + i + ',1)" title="nach unten">\u25BC</button>'
                : '<span class="ord-btn leer"></span>';
            // Standzeit nur bei Bildern: Videos und Audio bringen ihre Dauer
            // selbst mit.
            var zeit = '';
            if (art === 'images') {
                var wert = zeiten[f];
                var zid = 'bz-' + zone + '-' + i;
                zeit = '<input type="number" class="bildzeit" id="' + zid + '" min="1" max="3600" step="1"' +
                    ' placeholder="Std." title="Standzeit in Sekunden (leer = allgemeiner Bildwechsel)"' +
                    ' value="' + (wert ? esc(String(wert)) : '') + '"' +
                    ' onchange="setzeBildzeit(\'' + zone + '\',\'' + escAttr(f) + '\',this.value)">';
            }
            zeilen.push('<div class="zone-item">' + hoch + runter +
                '<span class="zone-item-name">' + ZONE_SYMBOL[art] + ' ' + esc(f) + '</span>' +
                zeit + '</div>');
        });
    });
    container.innerHTML = zeilen.length
        ? zeilen.join('')
        : '<div class="zone-empty">Keine Medien zugewiesen</div>';
}

/* ---- Reihenfolge und Standzeit ---- */

async function sendeZone(zone, teil) {
    var payload = {};
    payload[zone] = teil;
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    fetchStatus();
}

function verschiebe(zone, art, index, richtung) {
    var liste = ((config[zone] || {})[art] || []).slice();
    var ziel = index + richtung;
    if (ziel < 0 || ziel >= liste.length) return;
    var t = liste[index]; liste[index] = liste[ziel]; liste[ziel] = t;
    var teil = {};
    teil[art] = liste;
    sendeZone(zone, teil);
}

function setzeBildzeit(zone, datei, wert) {
    var zeiten = Object.assign({}, (config[zone] || {}).bildzeiten || {});
    var zahl = parseFloat(wert);
    if (!wert || !isFinite(zahl)) {
        // Leer heisst \u201Eallgemeiner Bildwechsel" \u2014 der Eintrag verschwindet,
        // statt eine 0 zu speichern, die der Kern ohnehin ablehnen wuerde.
        delete zeiten[datei];
    } else {
        zeiten[datei] = zahl;
    }
    sendeZone(zone, { bildzeiten: zeiten });
}

function setzeZonenOption(zone, option, an) {
    var teil = {};
    teil[option] = an;
    sendeZone(zone, teil);
}

/* ---- Sliders ---- */

function setupSliders() {
    slider('cfg-threshold', 'threshold-display', function (v) { return v.toFixed(2); });
    slider('cfg-threshold-mid', 'threshold-mid-display', function (v) { return v.toFixed(2); });
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

/* ---- Untertitel ---- */

var vttDateien = [];

async function ladeUntertitelListe() {
    try {
        var r = await fetch('/api/media/subtitles');
        vttDateien = (await r.json()).map(function (f) { return f.name; });
    } catch (e) { vttDateien = []; }
    renderUntertitel();
}

async function ladeUntertitelHoch(eingabe) {
    var fb = el('untertitel-feedback');
    for (var i = 0; i < eingabe.files.length; i++) {
        var fd = new FormData();
        fd.append('file', eingabe.files[i]);
        try {
            var r = await fetch('/api/upload/subtitles', { method: 'POST', body: fd });
            if (!r.ok) throw 0;
        } catch (e) {
            fb.textContent = '\u2717 ' + eingabe.files[i].name + ' abgelehnt (nur .vtt)';
            fb.className = 'feedback error';
        }
    }
    eingabe.value = '';
    await ladeUntertitelListe();
}

function renderUntertitel() {
    var kasten = el('untertitel-zuordnung');
    if (!kasten) return;
    var sprachen = config.sprachen || [];
    var videos = (allMedia.videos || []).map(function (f) { return f.name; });
    if (!sprachen.length) {
        kasten.innerHTML = '<div class="zone-empty">Erst Sprachen eintragen und speichern.</div>';
        return;
    }
    if (!videos.length) {
        kasten.innerHTML = '<div class="zone-empty">Noch keine Videos hochgeladen.</div>';
        return;
    }
    var zuordnung = config.untertitel || {};
    kasten.innerHTML = videos.map(function (video) {
        var spuren = zuordnung[video] || {};
        var felder = sprachen.map(function (code) {
            var gewaehlt = spuren[code] || '';
            // Die leere Auswahl ist Absicht: sie ist der einzige Weg, eine
            // falsch gesetzte Spur wieder zu entfernen.
            var optionen = ['<option value="">\u2014 keine \u2014</option>'].concat(
                vttDateien.map(function (d) {
                    return '<option value="' + escAttr(d) + '"' +
                        (d === gewaehlt ? ' selected' : '') + '>' + esc(d) + '</option>';
                })).join('');
            return '<label class="ut-spur"><span>' + code.toUpperCase() + '</span>' +
                '<select data-video="' + escAttr(video) + '" data-code="' + code + '">' +
                optionen + '</select></label>';
        }).join('');
        return '<div class="ut-zeile"><div class="ut-video">\uD83C\uDFAC ' + esc(video) +
            '</div><div class="ut-spuren">' + felder + '</div></div>';
    }).join('');
}

async function saveUntertitel() {
    var untertitel = {};
    document.querySelectorAll('#untertitel-zuordnung select').forEach(function (sel) {
        var video = sel.getAttribute('data-video');
        if (!sel.value) return;
        untertitel[video] = untertitel[video] || {};
        untertitel[video][sel.getAttribute('data-code')] = sel.value;
    });
    var sprachen = el('cfg-sprachen').value.split(',')
        .map(function (t) { return t.trim().toLowerCase(); })
        .filter(function (t) { return t.length > 0; });
    var fb = el('untertitel-feedback');
    try {
        var r = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sprachen: sprachen, untertitel: untertitel }),
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '\u2713 Gespeichert';
            fb.className = 'feedback success';
            await fetchStatus();
            renderUntertitel();
        } else {
            fb.textContent = '\u2717 ' + (d.error || 'Fehler');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '\u2717 Fehler';
        fb.className = 'feedback error';
    }
    setTimeout(function () { fb.textContent = ''; }, 4000);
}

/* ---- Sicherung ---- */

async function spieleEin(eingabe) {
    var datei = eingabe.files && eingabe.files[0];
    var fb = el('restore-feedback');
    if (!datei) return;
    // Rueckfrage, weil das die laufende Konfiguration ERSETZT — und zwar
    // vollstaendig, nicht ergaenzend.
    if (!confirm('Die aktuelle Konfiguration durch "' + datei.name + '" ersetzen?')) {
        eingabe.value = '';
        return;
    }
    try {
        var text = await datei.text();
        var r = await fetch('/api/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: text,
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '✓ ' + (d.hinweis || 'Wiederhergestellt');
            fb.className = 'feedback success';
            fetchStatus();
        } else {
            fb.textContent = '✗ ' + (d.error || 'Fehler');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '✗ Datei nicht lesbar';
        fb.className = 'feedback error';
    }
    eingabe.value = '';
    setTimeout(function () { fb.textContent = ''; }, 8000);
}

/* ---- Zustand ---- */

var HEALTH_TEXT = {
    ok: 'Alles in Ordnung',
    hinweis: 'Hinweis',
    warnung: 'Achtung',
    fehler: 'Störung',
};

async function loadHealth() {
    try {
        var r = await fetch('/api/health');
        var d = await r.json();
        var punkt = el('health-punkt');
        punkt.className = 'health-punkt ' + d.stufe;
        punkt.textContent = HEALTH_TEXT[d.stufe] || d.stufe;
        el('health-liste').innerHTML = d.befunde.length
            ? d.befunde.map(function (b) {
                return '<div class="health-befund ' + b.stufe + '">' + esc(b.text) + '</div>';
            }).join('')
            : '<div class="zone-empty">Keine Befunde — Sensor misst, Platte hat Platz, '
              + 'beide Zonen haben Medien.</div>';
    } catch (e) {
        /* Die Zustandsanzeige darf die Seite nicht mitreissen. */
    }
}

/* ---- Besucher-Statistik ---- */

function dauerText(sekunden) {
    if (!sekunden) return '0 s';
    if (sekunden < 60) return Math.round(sekunden) + ' s';
    var m = Math.floor(sekunden / 60), s = Math.round(sekunden % 60);
    return m + ' min ' + (s ? s + ' s' : '');
}

async function loadStatistik() {
    try {
        var r = await fetch('/api/statistik');
        var d = await r.json();
        el('stat-heute-besuche').textContent = d.heute.besuche;
        el('stat-heute-schnitt').textContent = dauerText(d.heute.schnitt_s);
        el('stat-gesamt-besuche').textContent = d.gesamt_besuche;

        // Tagesverlauf als Balken. Der hoechste Wert gibt den Massstab -- sonst
        // sind alle Balken gleich hoch, sobald die Zahlen klein sind.
        var max = Math.max.apply(null, d.heute.stunden.concat([1]));
        el('stat-stunden').innerHTML = d.heute.stunden.map(function (n, stunde) {
            var hoehe = Math.round((n / max) * 100);
            return '<div class="stat-stunde" title="' + stunde + ' Uhr: ' + n + ' Besuche">' +
                '<div class="stat-balken' + (n ? '' : ' leer') + '" style="height:' + hoehe + '%"></div>' +
                '<span class="stat-stunde-name">' + (stunde % 6 === 0 ? stunde : '') + '</span>' +
                '</div>';
        }).join('');

        el('stat-tage').innerHTML = d.letzte_tage.length
            ? d.letzte_tage.slice().reverse().map(function (t) {
                return '<div class="stat-tag-zeile">' +
                    '<span class="stat-tag-datum">' + esc(t.tag) + '</span>' +
                    '<span>' + t.besuche + ' Besuche</span>' +
                    '<span class="stat-tag-dauer">Ø ' + dauerText(t.schnitt_s) + '</span>' +
                    '</div>';
            }).join('')
            : '<div class="zone-empty">Noch keine Besuche erfasst</div>';
    } catch (e) {
        /* Die Statistik ist Beiwerk -- ihr Ausfall darf die Seite nicht stoeren. */
    }
}

async function resetStatistik() {
    if (!confirm('Alle erfassten Besuchszahlen unwiderruflich löschen?')) return;
    var fb = el('stat-feedback');
    try {
        await fetch('/api/statistik/reset', { method: 'POST' });
        fb.textContent = '✓ Zurückgesetzt';
        fb.className = 'feedback success';
        loadStatistik();
    } catch (e) {
        fb.textContent = '✗ Fehler';
        fb.className = 'feedback error';
    }
    setTimeout(function () { fb.textContent = ''; }, 2000);
}

/* ---- Zeitsteuerung ---- */

var ZP_TAGE = [
    ['mo', 'Montag'], ['di', 'Dienstag'], ['mi', 'Mittwoch'], ['do', 'Donnerstag'],
    ['fr', 'Freitag'], ['sa', 'Samstag'], ['so', 'Sonntag'],
];
var zeitplanGebaut = false;

// `<input type="time">` kennt kein 24:00 -- das Feld geht bis 23:59. Im Kern
// ist 24:00 aber genau das, was "bis Mitternacht" heisst, und 23:59 waere eine
// Minute Luecke. Deshalb wird in der Oberflaeche 00:00 als Ende angezeigt und
// beim Speichern wieder zu 24:00. Fuer den Nutzer liest sich "20:00 bis 00:00"
// ohnehin natuerlicher als "20:00 bis 24:00".
function bisFuerUi(v) { return (v === '24:00') ? '00:00' : (v || '00:00'); }
function bisAusUi(v) { return (!v || v === '00:00') ? '24:00' : v; }

function renderZeitplan(cfg) {
    var box = el('zeitplan-tage');
    if (!box) return;
    if (!zeitplanGebaut) {
        box.innerHTML = ZP_TAGE.map(function (t) {
            return '<div class="zeitplan-zeile">' +
                '<label class="checkbox-label zp-tag">' +
                '<input type="checkbox" id="zp-an-' + t[0] + '"><span>' + t[1] + '</span></label>' +
                '<input type="time" id="zp-von-' + t[0] + '">' +
                '<span class="zp-bis">bis</span>' +
                '<input type="time" id="zp-bis-' + t[0] + '">' +
                '</div>';
        }).join('');
        zeitplanGebaut = true;
    }
    var zp = cfg.zeitplan || { aktiv: false, tage: {} };
    var a = document.activeElement;
    if (!a || a.id !== 'cfg-zeitplan-aktiv') el('cfg-zeitplan-aktiv').checked = !!zp.aktiv;
    if (!a || a.id !== 'cfg-cec') el('cfg-cec').checked = !!cfg.cec_aktiv;
    ZP_TAGE.forEach(function (t) {
        var tag = (zp.tage || {})[t[0]] || { an: true, von: '00:00', bis: '24:00' };
        if (!a || a.id !== 'zp-an-' + t[0]) el('zp-an-' + t[0]).checked = !!tag.an;
        if (!a || a.id !== 'zp-von-' + t[0]) el('zp-von-' + t[0]).value = tag.von || '00:00';
        if (!a || a.id !== 'zp-bis-' + t[0]) el('zp-bis-' + t[0]).value = bisFuerUi(tag.bis);
    });
}

async function saveZeitplan() {
    var tage = {};
    ZP_TAGE.forEach(function (t) {
        tage[t[0]] = {
            an: el('zp-an-' + t[0]).checked,
            von: el('zp-von-' + t[0]).value || '00:00',
            bis: bisAusUi(el('zp-bis-' + t[0]).value),
        };
    });
    var fb = el('zeitplan-feedback');
    try {
        var r = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                zeitplan: { aktiv: el('cfg-zeitplan-aktiv').checked, tage: tage },
                cec_aktiv: el('cfg-cec').checked,
            }),
        });
        var d = await r.json();
        if (r.ok) {
            fb.textContent = '✓ Gespeichert';
            fb.className = 'feedback success';
        } else {
            // Der Kern lehnt ab und sagt WELCHES Feld -- das gehoert angezeigt,
            // sonst sucht jemand den Fehler in der falschen Zeile.
            fb.textContent = '✗ ' + (d.error || 'Fehler');
            fb.className = 'feedback error';
        }
    } catch (e) {
        fb.textContent = '✗ Fehler';
        fb.className = 'feedback error';
    }
    setTimeout(function () { fb.textContent = ''; }, 4000);
}

/* ---- Gleichtakt ---- */

function toggleSync(rolle) {
    var folgt = (rolle === 'follower');
    document.querySelectorAll('.sync-follower').forEach(function (e) {
        e.style.display = folgt ? '' : 'none';
    });
}

/* ---- Zonen-Stufen ---- */

// Die Mitte verschwindet aus der Oberflaeche, wenn sie nicht benutzt wird.
// Sie BLEIBT dabei in der Konfiguration: wer zwischen zwei und drei Stufen
// hin- und herschaltet, soll seine Zuweisung nicht jedes Mal verlieren.
function toggleStufen(stufen) {
    var drei = (stufen >= 3);
    var karte = el('zone-mid-karte');
    if (karte) karte.style.display = drei ? '' : 'none';
    document.querySelectorAll('.nur-drei-stufen').forEach(function (e) {
        e.style.display = drei ? '' : 'none';
    });
}

/* ---- Abstandsquelle: Felder je nach Typ zeigen/verbergen ---- */

function toggleSensorFields(type) {
    // Je Quelle genau ihre Felder. Vorher war es ein Zweiweg-Schalter
    // („Kamera ja/nein"); mit einer dritten Quelle waere daraus stillschweigend
    // „alles ausser Kamera zeigt GPIO-Trigger/Echo" geworden — also Felder, die
    // fuer den Taster nichts bedeuten.
    //
    // „auto" (Issue #13) zeigt BEIDE Bloecke: es benutzt den Sensor, und wenn
    // es den nicht gibt, die Kamera — also braucht es auch beider Angaben.
    // Nur die des gerade Aktiven zu zeigen hiesse, die Brennweite erst
    // einstellen zu koennen, wenn der Sensor schon fehlt.
    var klassen = {
        auto: ['.sensor-ultrasonic', '.sensor-camera'],
        ultrasonic: ['.sensor-ultrasonic'],
        camera: ['.sensor-camera'],
        button: ['.sensor-button'],
    };
    var sichtbar = klassen[type] || [];
    ['.sensor-ultrasonic', '.sensor-camera', '.sensor-button'].forEach(function (k) {
        document.querySelectorAll(k).forEach(function (e) {
            e.style.display = (sichtbar.indexOf(k) >= 0) ? '' : 'none';
        });
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
        threshold_mid_m: parseFloat(el('cfg-threshold-mid').value),
        zonen_stufen: parseInt(el('cfg-zonen-stufen').value),
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
        sync_rolle: el('cfg-sync-rolle').value,
        sync_master: el('cfg-sync-master').value.trim(),
        sync_port: parseInt(el('cfg-sync-port').value),
        button_pin: parseInt(el('cfg-button-pin').value),
        button_haltezeit_s: parseFloat(el('cfg-button-haltezeit').value),
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
                xhr.onload = function () {
                    if (xhr.status !== 200) return fail();
                    // Hinweise des Medien-Checks einsammeln (z. B. 4K, das auf
                    // einem Pi ruckelt). Sie sind KEINE Ablehnung — die Datei
                    // ist hochgeladen.
                    try {
                        var antwort = JSON.parse(xhr.responseText);
                        (antwort.hinweise || []).forEach(function (h) {
                            uploadHinweise.push(file.name + ': ' + h);
                        });
                    } catch (e) { /* ohne Hinweise weiter */ }
                    ok();
                };
                xhr.onerror = fail;
                xhr.open('POST', '/api/upload/' + type);
                xhr.send(fd);
            });
        } catch (e) { /* upload failed */ }
    }
    text.hidden = false;
    prog.hidden = true;
    fill.style.width = '0%';
    zeigeUploadHinweise();
    await loadAllMedia();
}

// Gesammelt und EINMAL am Ende gezeigt: bei einem Stapel-Upload waere eine
// Meldung je Datei eine Kette von Dialogen, die niemand liest.
var uploadHinweise = [];

function zeigeUploadHinweise() {
    var kasten = el('upload-hinweise');
    if (!kasten) { uploadHinweise = []; return; }
    kasten.innerHTML = uploadHinweise.length
        ? '<div class="health-befund warnung"><strong>Wiedergabe-Hinweise</strong></div>'
          + uploadHinweise.map(function (h) {
              return '<div class="health-befund warnung">' + esc(h) + '</div>';
          }).join('')
        : '';
    uploadHinweise = [];
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

/* ─────────────────────────────────────────────────────────────────────────
   DIE BILDSCHIRME DIESES RECHNERS (Nutzer, 2026-09-15)

   „im mediaplayer das endgeraet selbst und externe displays die ans
    endgeraet angeschlossen sind als mediaplayer nutzen koennen."

   Die Karte ist VERSTECKT, solange es nichts zu zeigen gibt — auf einem Pi
   ohne X, auf einem Server, auf einem Rechner ohne zweiten Schirm. Eine
   Karte mit einer leeren Liste und zwei Knoepfen, die nichts tun, ist
   schlimmer als keine: sie sieht aus wie ein Defekt.
   ───────────────────────────────────────────────────────────────────────── */

async function ladeSchirme() {
    var karte = el('card-displays');
    if (!karte) { return; }
    try {
        var r = await fetch('/api/displays');
        var d = await r.json();
        var schirme = d.schirme || [];
        if (!schirme.length && !d.browser) {
            karte.hidden = true;
            return;
        }
        karte.hidden = false;
        zeichneSchirme(schirme, d);
    } catch (e) {
        karte.hidden = true;
    }
}

function zeichneSchirme(schirme, d) {
    var liste = el('displays-list');
    if (!schirme.length) {
        liste.innerHTML = '<div class="empty">Keine Bildschirme gefunden.</div>';
    } else {
        liste.innerHTML = schirme.map(function (s) {
            var marke = s.haupt ? ' &middot; Hauptschirm' : '';
            var zustand = s.zeigt
                ? '<span class="badge">zeigt</span>'
                : '<span class="badge badge-off">aus</span>';
            return '<div class="media-item">' +
                '<span>' + esc(s.name) + ' &mdash; ' + s.breite + '&times;' + s.hoehe +
                ' bei ' + s.x + ',' + s.y + marke + '</span>' +
                zustand +
                '<button class="btn btn-small" data-schirm="' + s.index + '" ' +
                'data-was="' + (s.zeigt ? 'stop' : 'play') + '">' +
                (s.zeigt ? 'Schliessen' : 'Zeigen') + '</button>' +
                '</div>';
        }).join('');
        liste.querySelectorAll('button[data-schirm]').forEach(function (b) {
            b.addEventListener('click', function () {
                schalteSchirm(Number(b.dataset.schirm), b.dataset.was);
            });
        });
    }

    // OHNE BROWSER GEHT NICHTS, und dann steht da, WO gesucht wurde.
    // Ein „geht nicht" ohne Ort ist fuer den Nutzer dasselbe wie Schweigen.
    var hint = el('displays-hint');
    if (!d.browser) {
        hint.innerHTML = '<strong>Kein Chrome, Chromium oder Edge gefunden.</strong> ' +
            'Gesucht wurde: ' + esc((d.suchorte || []).join(', ')) +
            '. (Firefox und Safari koennen kein Fenster auf einem bestimmten ' +
            'Schirm oeffnen.)';
    }
}

async function schalteSchirm(index, was) {
    await schirmBefehl(was, [index]);
}

async function schirmBefehl(was, auswahl) {
    var fb = el('displays-feedback');
    try {
        var r = await fetch('/api/displays/' + was, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(auswahl ? { schirme: auswahl } : {}),
        });
        var d = await r.json();
        var meldungen = d.meldungen || [];
        fb.textContent = meldungen.length ? meldungen.join(' · ') : '✓';
        fb.className = 'feedback' + (meldungen.length ? ' error' : '');
    } catch (e) {
        fb.textContent = '✗ ' + e.message;
        fb.className = 'feedback error';
    }
    await ladeSchirme();
}

document.addEventListener('DOMContentLoaded', function () {
    var auf = el('btn-displays-play');
    var zu = el('btn-displays-stop');
    if (auf) { auf.addEventListener('click', function () { schirmBefehl('play', null); }); }
    if (zu) { zu.addEventListener('click', function () { schirmBefehl('stop', null); }); }
    ladeSchirme();
});

/* Monitor-Karte (3.0): verbundene Anzeigen, Screenshot, Systemwerte,
   Proof-of-Play, Benachrichtigung. Laeuft nach app.js — `el()`, `esc()`,
   `tr()` und `config` stehen bereit. Vorlage: templates/admin/zusatz/40-monitor.html */
(function () {
    'use strict';

    var ART = { video: 'Video', image: 'Bild', web: 'Webseite', audio: 'Audio', widget: 'Widget' };
    var EREIGNIS_TEXT = {
        gesundheit_fehler: 'Störung',
        gesundheit_ok: 'Störung behoben',
        anzeige_verloren: 'Anzeige verloren',
        anzeige_zurueck: 'Anzeige wieder da',
        offline_ende: 'Öffnungszeit beginnt'
    };

    function feedback(text, cls) {
        var f = el('monitor-feedback');
        if (!f) return;
        f.textContent = text;
        f.className = 'feedback' + (cls ? ' ' + cls : '');
        if (text) setTimeout(function () { if (f.textContent === text) { f.textContent = ''; f.className = 'feedback'; } }, 4000);
    }

    function alterText(s) {
        if (s == null) return '–';
        if (s < 60) return Math.round(s) + ' s';
        if (s < 3600) return Math.round(s / 60) + ' min';
        return Math.round(s / 3600) + ' h';
    }

    /* ---- Anzeigen ---- */

    async function ladeAnzeigen() {
        try {
            var r = await fetch('/api/anzeige');
            var d = await r.json();
            var punkt = el('monitor-punkt');
            var liste = el('monitor-anzeigen');
            if (!liste) return;
            if (punkt) {
                var stufe = !d.anzahl ? 'warnung' : (d.online ? 'ok' : 'fehler');
                punkt.className = 'health-punkt ' + stufe;
                punkt.textContent = !d.anzahl ? 'Keine Anzeige gemeldet'
                    : (d.online + ' von ' + d.anzahl + ' online');
            }
            if (!d.anzeigen.length) {
                liste.innerHTML = '<div class="zone-empty">Noch hat sich keine Anzeigeseite gemeldet — '
                    + '<a href="/display" target="_blank">Anzeige öffnen</a>.</div>';
                return;
            }
            // Eine Vorschau aus der Verwaltung ist keine Anzeige: offline
            // (Tab zu) hat sie in der Liste nichts verloren.
            var anzeigen = d.anzeigen.filter(function (a) { return a.online || !a.vorschau; });
            liste.innerHTML = anzeigen.map(function (a) {
                var regionen = (a.regionen || []).map(function (r) {
                    var was = r.item ? (ART[r.item.typ] || r.item.typ) + ': ' + esc(r.item.name)
                        : (r.typ === 'widget' ? 'Widget' : 'leer');
                    return '<div class="monitor-region"><span class="media-size">' + esc(r.id) + '</span> ' + was + '</div>';
                }).join('');
                var fehler = (a.fehler || []).length
                    ? '<div class="health-befund warnung">' + a.fehler.map(esc).join('<br>') + '</div>' : '';
                return '<div class="media-item monitor-anzeige ' + (a.online ? 'online' : 'offline') + '">'
                    + '<div style="flex:1; min-width:0">'
                    + '<div class="media-name"><span class="status-dot ' + (a.online ? 'active' : '') + '"></span> '
                    + esc(a.adresse || a.kennung) + (a.vorschau ? ' <span class="badge">Vorschau</span>' : '')
                    // Jeder Teil ein eigener Knoten: nur so greifen die
                    // Uebersetzungsmuster („Puls vor …") einzeln.
                    + ' <span class="media-size"><span>' + (a.online ? 'online' : 'offline') + '</span> · <span>Puls vor '
                    + alterText(a.alter_s) + '</span>'
                    + (a.zone ? ' · <span>' + esc(zonenName(a.zone)) + '</span>' : '')
                    + (a.layout_id ? ' · <span>' + esc(a.layout_id) + '</span>' : '') + '</span></div>'
                    + regionen + fehler
                    + '</div></div>';
            }).join('');
        } catch (e) { /* die Karte darf die Seite nicht mitreissen */ }
    }

    function zonenName(z) { return (window.ZONEN_NAMEN && window.ZONEN_NAMEN[z]) || z; }

    window.screenshotAnfordern = async function () {
        feedback('Bild wird angefordert …');
        try {
            var r = await fetch('/api/anzeige/screenshot/anfordern', { method: 'POST',
                headers: { 'Content-Type': 'application/json' }, body: '{}' });
            var d = await r.json();
            if (!r.ok) { feedback('✗ ' + tr(d.error || 'Kein Bild'), 'error'); return; }
            var img = new Image();
            img.alt = 'Screenshot';
            img.src = d.url + '&t=' + Date.now();
            var ziel = el('monitor-screenshot');
            ziel.innerHTML = '';
            ziel.appendChild(img);
            el('monitor-screenshot-zeit').textContent = (d.quelle === 'bildschirm' ? tr('echter Bildschirm') : tr('Anzeigeseite'))
                + ' · ' + new Date().toLocaleTimeString();
            feedback('✓ Bild da', 'success');
        } catch (e) { feedback('✗ ' + tr('Station nicht erreichbar'), 'error'); }
    };

    /* ---- System ---- */

    async function ladeSystem() {
        try {
            var r = await fetch('/api/anzeige/system');
            var d = await r.json();
            var sys = d.system || null;
            var ziel = el('monitor-system');
            if (!ziel) return;
            if (!sys) { ziel.innerHTML = '<div class="zone-empty">Keine Systemwerte auf diesem Rechner.</div>'; return; }
            var kacheln = [];
            if (sys.temp_c != null) kacheln.push(['CPU', sys.temp_c.toFixed(0) + ' °C']);
            if (sys.last_1m != null) kacheln.push(['Last (1 min)', sys.last_1m.toFixed(1) + (sys.kerne ? ' / ' + sys.kerne : '')]);
            if (sys.ram_frei_mb != null) kacheln.push(['RAM frei', sys.ram_frei_mb + ' MB']);
            if (sys.platte_frei_mb != null) kacheln.push(['Platte frei', (sys.platte_frei_mb / 1024).toFixed(1) + ' GB']);
            ziel.innerHTML = kacheln.length ? kacheln.map(function (k) {
                return '<div class="stat-kachel"><span class="stat-wert">' + esc(k[1]) + '</span><span class="stat-name">' + esc(k[0]) + '</span></div>';
            }).join('') : '<div class="zone-empty">Keine Systemwerte auf diesem Rechner.</div>';
        } catch (e) { /* still */ }
    }

    /* ---- Proof-of-Play ---- */

    function bereich() {
        var q = [];
        var von = el('pop-von').value, bis = el('pop-bis').value;
        if (von) q.push('von=' + von);
        if (bis) q.push('bis=' + bis);
        return q;
    }

    window.ladeWiedergabe = async function () {
        var q = bereich();
        el('pop-csv').href = '/api/wiedergabe.csv' + (q.length ? '?' + q.join('&') : '');
        q.push('gruppe=' + el('pop-gruppe').value);
        try {
            var r = await fetch('/api/wiedergabe/zusammenfassung?' + q.join('&'));
            var d = await r.json();
            if (!r.ok) { feedback('✗ ' + tr(d.error || 'Fehler'), 'error'); return; }
            el('pop-summe').textContent = d.starts_gesamt + ' ' + tr('Starts') + ' · ' + d.anzeigen + ' ' + tr('Anzeigen');
            el('pop-tabelle').innerHTML = d.zeilen.length ? d.zeilen.map(function (z) {
                return '<div class="media-item"><span class="media-name">' + esc(z.schluessel || '–')
                    + ' <span class="media-size">' + esc(ART[z.typ] || z.typ) + '</span></span>'
                    + '<span class="media-size">' + z.starts + ' ×</span></div>';
            }).join('') : '<div class="zone-empty">Keine Starts im Zeitraum.</div>';
        } catch (e) { feedback('✗ ' + tr('Station nicht erreichbar'), 'error'); }
    };

    window.speichereAufbewahrung = async function () {
        var tage = parseInt(el('cfg-wiedergabe-tage').value, 10);
        var r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wiedergabe_aufbewahrung_tage: tage }) });
        var d = await r.json();
        feedback(r.ok ? '✓ Gespeichert' : '✗ ' + tr(d.error || 'Fehler'), r.ok ? 'success' : 'error');
    };

    /* ---- Benachrichtigung ---- */

    function zeigeTopic() {
        var g = el('bn-topic-gruppe');
        if (g) g.hidden = el('bn-typ').value !== 'ntfy';
    }

    async function ladeBenachrichtigung() {
        try {
            var r = await fetch('/api/benachrichtigung');
            var d = await r.json();
            el('bn-aktiv').value = d.aktiv ? '1' : '0';
            el('bn-typ').value = d.ziel_typ;
            el('bn-url').value = d.url || '';
            el('bn-topic').value = d.topic || '';
            el('bn-ereignisse').innerHTML = (d.ereignisse_moeglich || []).map(function (e) {
                var an = (d.ereignisse || []).indexOf(e) >= 0;
                return '<label class="zone-option"><input type="checkbox" data-ereignis="' + e + '"' + (an ? ' checked' : '')
                    + '> ' + esc(EREIGNIS_TEXT[e] || e) + '</label>';
            }).join('');
            zeigeTopic();
        } catch (e) { /* still */ }
    }

    function benachrichtigungAusFormular() {
        var ereignisse = [];
        el('bn-ereignisse').querySelectorAll('input[data-ereignis]:checked').forEach(function (i) {
            ereignisse.push(i.getAttribute('data-ereignis'));
        });
        return {
            aktiv: el('bn-aktiv').value === '1',
            ziel_typ: el('bn-typ').value,
            url: el('bn-url').value.trim(),
            topic: el('bn-topic').value.trim(),
            ereignisse: ereignisse
        };
    }

    window.speichereBenachrichtigung = async function () {
        var r = await fetch('/api/benachrichtigung', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(benachrichtigungAusFormular()) });
        var d = await r.json();
        feedback(r.ok ? '✓ Gespeichert' : '✗ ' + tr(d.error || 'Fehler'), r.ok ? 'success' : 'error');
    };

    window.testeBenachrichtigung = async function () {
        feedback('Probenachricht geht raus …');
        var r = await fetch('/api/benachrichtigung/test', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(benachrichtigungAusFormular()) });
        var d = await r.json();
        feedback(r.ok ? '✓ Zugestellt' : '✗ ' + tr(d.error || 'Nicht zugestellt'), r.ok ? 'success' : 'error');
    };

    document.addEventListener('DOMContentLoaded', function () {
        if (!el('card-monitor')) return;
        el('bn-typ').addEventListener('change', zeigeTopic);
        var heute = new Date();
        var vor = new Date(heute.getTime() - 6 * 86400000);
        el('pop-bis').value = heute.toISOString().slice(0, 10);
        el('pop-von').value = vor.toISOString().slice(0, 10);
        ladeAnzeigen();
        ladeSystem();
        ladeBenachrichtigung();
        ladeWiedergabe();
        setInterval(ladeAnzeigen, 5000);
        setInterval(ladeSystem, 15000);
    });

    // Die Aufbewahrung steht in der Konfiguration, die app.js im Status
    // mitfuehrt (`config`) — von dort ins Feld, solange niemand darin tippt.
    setInterval(function () {
        var feld = el('cfg-wiedergabe-tage');
        var c = window.config;
        if (feld && c && document.activeElement !== feld && c.wiedergabe_aufbewahrung_tage != null) {
            feld.value = c.wiedergabe_aufbewahrung_tage;
        }
    }, 2000);
})();

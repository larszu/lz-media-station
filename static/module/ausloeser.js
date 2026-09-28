/* Ausloeser — die Verwaltungsseite (Welle 2). „Wenn … dann …"

   Laeuft nach app.js (static/module/): `el()`, `esc()`, `escAttr()`, `tr()`,
   `config`, `allMedia`, `layoutsStand` stehen bereit. Redet mit
   /api/ausloeser, /api/ausloeser/protokoll, /api/ausloeser/<id>/test. */
(function () {
    'use strict';

    var TAGE = ['mo', 'di', 'mi', 'do', 'fr', 'sa', 'so'];
    var TAG_NAMEN = { mo: 'Mo', di: 'Di', mi: 'Mi', do: 'Do', fr: 'Fr', sa: 'Sa', so: 'So' };
    var ZONEN = { near: 'Nah', mid: 'Mitte', far: 'Fern' };
    var QUELLEN = { webhook: 'Webhook', taster: 'Taster', zeit: 'Uhrzeit', video_ende: 'Video zu Ende', zone: 'Zonenwechsel' };
    var AKTIONEN = { zeige_layout: 'Layout einblenden', zurueck: 'Layout beenden', meldung: 'Sofortmeldung',
                     display_aus: 'Schirm schwarz', display_an: 'Schirm an', start: 'Steuerung starten', stop: 'Steuerung anhalten' };

    var stand = { ausloeser: [], belegte_pins: {}, gpio: false };
    var bearbeitet = null;

    function tr_(t) { return (typeof tr === 'function') ? tr(t) : t; }
    function layouts() { return (window.layoutsStand && layoutsStand.layouts) || {}; }
    function layoutName(id) { return (layouts()[id] || {}).name || id || ''; }

    /* ---- Daten ---- */

    async function lade() {
        try {
            var r = await fetch('/api/ausloeser');
            if (r.ok) stand = await r.json();
        } catch (e) { /* alter Stand bleibt */ }
        zeichne();
        ladeProtokoll();
    }

    async function speichere(liste, text) {
        try {
            var r = await fetch('/api/ausloeser', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(liste) });
            var d = await r.json();
            if (!r.ok) { rueck(d.error || 'Fehler', true); return false; }
            stand.ausloeser = d.ausloeser;
            rueck(text || '✓ Gespeichert', false);
            zeichne();
            return true;
        } catch (e) { rueck(tr_('Station nicht erreichbar'), true); return false; }
    }

    function rueck(text, fehler) {
        var fb = el('aus-feedback');
        fb.textContent = text;
        fb.className = 'feedback ' + (fehler ? 'error' : 'success');
        if (!fehler) setTimeout(function () { if (fb.textContent === text) fb.textContent = ''; }, 3000);
    }

    /* ---- Liste ---- */

    function wenn(q) {
        q = q || {};
        if (q.typ === 'webhook') return tr_('Webhook') + ' ' + (q.token ? '🔒' : '');
        if (q.typ === 'taster') return tr_('Taster an BCM') + ' ' + q.pin;
        if (q.typ === 'zeit') return (q.tage || []).map(function (t) { return TAG_NAMEN[t]; }).join(', ') + ' ' + q.zeit;
        if (q.typ === 'video_ende') return tr_('Video zu Ende') + (q.datei ? ': ' + q.datei : '');
        if (q.typ === 'zone') return tr_('Zone wechselt zu') + ' ' + tr_(ZONEN[q.zone] || q.zone);
        return q.typ || '';
    }
    function dann(a) {
        a = a || {};
        if (a.typ === 'zeige_layout') return tr_('Layout einblenden') + ': ' + layoutName(a.layout_id) + (a.dauer_s ? ' (' + a.dauer_s + ' s)' : '');
        if (a.typ === 'meldung') return tr_('Sofortmeldung') + ': „' + (a.text || '') + '"';
        return tr_(AKTIONEN[a.typ] || a.typ || '');
    }

    function zeichne() {
        var wurzel = el('aus-liste');
        if (!wurzel) return;
        var liste = stand.ausloeser || [];
        if (!liste.length) { wurzel.innerHTML = '<div class="empty">' + tr_('Noch kein Auslöser.') + '</div>'; return; }
        wurzel.innerHTML = liste.map(function (e) {
            return '<div class="aus-zeile' + (e.aktiv === false ? ' inaktiv' : '') + '">' +
                '<label class="checkbox-label" style="padding:0"><input type="checkbox"' + (e.aktiv !== false ? ' checked' : '') + ' onchange="ausAktiv(\'' + escAttr(e.id) + '\', this.checked)"></label>' +
                '<div class="wenn-dann"><strong>' + esc(e.name) + '</strong><small>' + tr_('Wenn') + ' ' + esc(wenn(e.quelle)) + ' → ' + esc(dann(e.aktion)) + '</small>' +
                (e.status ? '<span class="status">' + esc(e.status) + '</span>' : '') + '</div>' +
                '<button class="btn btn-small btn-secondary" onclick="ausTest(\'' + escAttr(e.id) + '\')">' + tr_('Test') + '</button>' +
                '<button class="btn btn-small btn-secondary" onclick="ausBearbeiten(\'' + escAttr(e.id) + '\')">' + tr_('Bearbeiten') + '</button>' +
                '</div>';
        }).join('');
    }

    /* ---- Formular ---- */

    function fuelleTage(gewaehlt) {
        el('aus-tage').innerHTML = TAGE.map(function (t) {
            return '<label><input type="checkbox" value="' + t + '"' + (gewaehlt.indexOf(t) >= 0 ? ' checked' : '') + '>' + TAG_NAMEN[t] + '</label>';
        }).join('');
    }
    function fuelleLayouts(gewaehlt) {
        var ids = Object.keys(layouts());
        el('aus-layout').innerHTML = ids.map(function (id) {
            return '<option value="' + escAttr(id) + '"' + (id === gewaehlt ? ' selected' : '') + '>' + esc(layoutName(id)) + '</option>';
        }).join('');
    }
    function fuelleVideos(gewaehlt) {
        var videos = (window.allMedia && allMedia.videos) || [];
        el('aus-datei').innerHTML = '<option value="">' + tr_('jedes Video') + '</option>' + videos.map(function (v) {
            var n = v.name || v;
            return '<option value="' + escAttr(n) + '"' + (n === gewaehlt ? ' selected' : '') + '>' + esc(n) + '</option>';
        }).join('');
    }

    window.ausQuelleFelder = function () {
        var typ = el('aus-quelle-typ').value;
        document.querySelectorAll('#aus-form .aus-q').forEach(function (n) {
            n.style.display = n.classList.contains('aus-q-' + typ) ? '' : 'none';
        });
        if (typ === 'webhook') webhookInfo();
        if (typ === 'taster' && !stand.gpio) {
            el('aus-webhook-info').style.display = '';
            el('aus-webhook-info').innerHTML = '<span style="color:var(--warning)">' + tr_('Auf diesem Rechner gibt es kein GPIO (gpiozero fehlt) — der Taster löst hier nicht aus.') + '</span>';
        }
    };
    window.ausAktionFelder = function () {
        var typ = el('aus-aktion-typ').value;
        document.querySelectorAll('#aus-form .aus-a').forEach(function (n) {
            n.style.display = n.classList.contains('aus-a-' + typ) ? '' : 'none';
        });
    };

    function webhookInfo() {
        var id = (el('aus-id').value || 'kennung').trim();
        var host = (config && config.display_ip) || location.host.split(':')[0];
        var port = (config && config.web_port) || location.port || 80;
        var url = 'http://' + host + ':' + port + '/api/trigger/' + id;
        var token = (el('aus-token').value || '').trim();
        var curl = 'curl -X POST ' + (token ? '-H "X-LZ-Token: ' + token + '" ' : '') + url;
        el('aus-webhook-info').innerHTML =
            '<div>' + tr_('Adresse für Home Assistant, Node-RED, ioBroker oder einen Taster mit WLAN:') + '</div>' +
            '<code id="aus-webhook-url">' + esc(url) + '</code>' +
            '<button type="button" class="btn btn-small btn-secondary" onclick="ausKopieren(\'aus-webhook-url\')">' + tr_('Adresse kopieren') + '</button> ' +
            '<div style="margin-top:6px">' + tr_('Beispiel:') + '</div><code>' + esc(curl) + '</code>';
    }
    window.ausKopieren = function (id) {
        var t = el(id).textContent;
        if (navigator.clipboard) navigator.clipboard.writeText(t).then(function () { rueck('✓ ' + tr_('Kopiert'), false); });
    };

    function zeigeForm(e) {
        bearbeitet = e.id || null;
        el('aus-form-titel').textContent = bearbeitet ? tr_('Auslöser bearbeiten') : tr_('Neuer Auslöser');
        el('aus-name').value = e.name || '';
        el('aus-id').value = e.id || '';
        el('aus-id').disabled = !!bearbeitet;
        el('aus-aktiv').checked = e.aktiv !== false;
        var q = e.quelle || { typ: 'webhook' };
        el('aus-quelle-typ').value = q.typ || 'webhook';
        el('aus-token').value = q.token || '';
        el('aus-pin').value = q.pin || 27;
        el('aus-zeit').value = q.zeit || '18:00';
        fuelleTage(q.tage || TAGE);
        fuelleVideos(q.datei || '');
        el('aus-zone').value = q.zone || 'near';
        var a = e.aktion || { typ: 'zeige_layout' };
        el('aus-aktion-typ').value = a.typ || 'zeige_layout';
        fuelleLayouts(a.layout_id || Object.keys(layouts())[0]);
        el('aus-dauer').value = a.dauer_s || '';
        el('aus-meldung-text').value = a.text || '';
        el('aus-meldung-untertext').value = a.untertext || '';
        el('aus-meldung-farbe').value = a.farbe || '#B04A3F';
        el('aus-meldung-ton').checked = !!a.ton;
        el('aus-loeschen').hidden = !bearbeitet;
        el('aus-form').hidden = false;
        ausQuelleFelder();
        ausAktionFelder();
        el('aus-name').focus();
    }

    function kennung(name, vergeben) {
        var g = (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 36) || 'ausloeser';
        if (!/^[a-z0-9]/.test(g)) g = 'a-' + g;
        var k = g, n = 2;
        while (vergeben.indexOf(k) >= 0) k = g + '-' + (n++);
        return k;
    }

    window.ausNeu = function () { zeigeForm({}); };
    window.ausBearbeiten = function (id) {
        var e = (stand.ausloeser || []).filter(function (x) { return x.id === id; })[0];
        if (e) zeigeForm(e);
    };
    window.ausFormSchliessen = function () { el('aus-form').hidden = true; bearbeitet = null; };

    window.ausSpeichern = function () {
        var name = (el('aus-name').value || '').trim();
        if (!name) { rueck(tr_('Bitte einen Namen eingeben.'), true); el('aus-name').focus(); return; }
        var liste = (stand.ausloeser || []).map(function (x) { var k = {}; Object.keys(x).forEach(function (f) { if (f !== 'status') k[f] = x[f]; }); return k; });
        var ids = liste.map(function (x) { return x.id; });
        var id = bearbeitet || (el('aus-id').value || '').trim() || kennung(name, ids);
        var qt = el('aus-quelle-typ').value;
        var quelle = { typ: qt };
        if (qt === 'webhook') quelle.token = (el('aus-token').value || '').trim();
        if (qt === 'taster') quelle.pin = parseInt(el('aus-pin').value, 10);
        if (qt === 'zeit') { quelle.zeit = el('aus-zeit').value; quelle.tage = Array.prototype.map.call(el('aus-tage').querySelectorAll('input:checked'), function (i) { return i.value; }); }
        if (qt === 'video_ende') quelle.datei = el('aus-datei').value;
        if (qt === 'zone') quelle.zone = el('aus-zone').value;
        var at = el('aus-aktion-typ').value;
        var aktion = { typ: at };
        var dauer = el('aus-dauer').value;
        if (at === 'zeige_layout') { aktion.layout_id = el('aus-layout').value; aktion.dauer_s = dauer ? Number(dauer) : null; }
        if (at === 'meldung') {
            aktion.text = (el('aus-meldung-text').value || '').trim();
            aktion.untertext = (el('aus-meldung-untertext').value || '').trim();
            aktion.farbe = el('aus-meldung-farbe').value;
            aktion.ton = el('aus-meldung-ton').checked;
            aktion.dauer_s = dauer ? Number(dauer) : null;
        }
        var e = { id: id, name: name, aktiv: el('aus-aktiv').checked, quelle: quelle, aktion: aktion };
        var i = ids.indexOf(id);
        if (i >= 0) liste[i] = e; else liste.push(e);
        speichere(liste).then(function (ok) { if (ok) ausFormSchliessen(); });
    };
    window.ausLoeschen = function () {
        if (!bearbeitet) return;
        var liste = (stand.ausloeser || []).filter(function (x) { return x.id !== bearbeitet; });
        speichere(liste, '✓ Gelöscht').then(function (ok) { if (ok) ausFormSchliessen(); });
    };
    window.ausAktiv = function (id, an) {
        var liste = (stand.ausloeser || []).map(function (x) {
            var k = {}; Object.keys(x).forEach(function (f) { if (f !== 'status') k[f] = x[f]; });
            if (k.id === id) k.aktiv = an;
            return k;
        });
        speichere(liste);
    };
    window.ausTest = async function (id) {
        try {
            var r = await fetch('/api/ausloeser/' + encodeURIComponent(id) + '/test', { method: 'POST' });
            var d = await r.json();
            rueck(r.ok ? '✓ ' + (d.ergebnis || '') : (d.error || 'Fehler'), !r.ok);
            ladeProtokoll();
        } catch (e) { rueck(tr_('Station nicht erreichbar'), true); }
    };

    /* ---- Protokoll ---- */

    async function ladeProtokoll() {
        var wurzel = el('aus-protokoll');
        if (!wurzel) return;
        try {
            var r = await fetch('/api/ausloeser/protokoll');
            var liste = await r.json();
            if (!liste.length) { wurzel.innerHTML = '<div class="empty">' + tr_('Noch nichts ausgelöst.') + '</div>'; return; }
            wurzel.innerHTML = liste.slice(0, 30).map(function (p) {
                return '<div><span class="zeit">' + esc((p.zeit || '').replace('T', ' ')) + '</span><strong>' + esc(p.name || p.id) + '</strong>' +
                    '<span>' + esc(p.anlass || '') + '</span><span class="ergebnis">' + esc(p.ergebnis || '') + '</span></div>';
            }).join('');
        } catch (e) { /* naechstes Mal */ }
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (!el('aus-liste')) return;
        lade();
        setInterval(ladeProtokoll, 5000);
        ['aus-id', 'aus-token'].forEach(function (id) { el(id).addEventListener('input', function () { if (el('aus-quelle-typ').value === 'webhook') webhookInfo(); }); });
        if (window.EventSource) {
            var q = new EventSource('/api/events');
            q.addEventListener('config', function () { if (el('aus-form').hidden) lade(); });
        }
    });
})();

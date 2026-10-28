/* IPTV-Kanal (Karte templates/admin/zusatz/50-multicast.html).

   Einstellungen stehen im Config-Abschnitt `multicast` und gehen als Ganzes
   per POST /api/config; Senden/Stopp ueber /api/multicast/*. „Senden"
   speichert vorher, damit der Kanal mit dem laeuft, was im Formular steht.
   Rueckgrat aus app.js: el(), esc(), tr(). */
(function () {
    'use strict';
    if (!el('card-multicast')) return;

    var ZAHLEN = { port: 'mc-port', ttl: 'mc-ttl', tsid: 'mc-tsid', pid_video: 'mc-pid-video', pid_audio: 'mc-pid-audio' };

    function meldung(text, fehler) {
        var fb = el('mc-feedback');
        fb.textContent = text;
        fb.className = 'feedback ' + (fehler ? 'error' : 'success');
    }

    function zeigeModus() {
        var datei = el('mc-modus').value === 'datei';
        el('mc-datei-feld').hidden = !datei;
        document.querySelectorAll('#card-multicast .mc-nur-anzeige').forEach(function (f) { f.hidden = datei; });
    }

    function fuelle(c) {
        el('mc-modus').value = c.modus;
        el('mc-name').value = c.name;
        el('mc-gruppe').value = c.gruppe;
        el('mc-aufloesung').value = c.breite + 'x' + c.hoehe;
        el('mc-fps').value = String(c.fps);
        el('mc-bitrate').value = c.bitrate_k / 1000;
        el('mc-sprache').value = c.sprache;
        el('mc-sap').checked = !!c.sap;
        el('mc-aktiv').checked = !!c.aktiv;
        Object.keys(ZAHLEN).forEach(function (k) { el(ZAHLEN[k]).value = c[k]; });
        zeigeModus();
    }

    function formular() {
        var a = el('mc-aufloesung').value.split('x');
        var c = {
            modus: el('mc-modus').value, name: el('mc-name').value.trim(),
            gruppe: el('mc-gruppe').value.trim(), breite: Number(a[0]), hoehe: Number(a[1]),
            fps: Number(el('mc-fps').value), bitrate_k: Math.round(Number(el('mc-bitrate').value) * 1000),
            sprache: el('mc-sprache').value, sap: el('mc-sap').checked, aktiv: el('mc-aktiv').checked,
        };
        Object.keys(ZAHLEN).forEach(function (k) { c[k] = Number(el(ZAHLEN[k]).value); });
        return c;
    }

    async function speichern() {
        var r = await fetch('/api/config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ multicast: formular() }),
        });
        var j = await r.json();
        if (!r.ok) throw new Error(j.error || r.status);
        return j;
    }

    async function ladeStatus() {
        try {
            var s = await (await fetch('/api/multicast/status')).json();
            var box = el('mc-status');
            if (s.laeuft) {
                box.innerHTML = '<strong>' + esc(tr('Sendet')) + '</strong> · ' + esc(s.name) + ' · <code>' + esc(s.url) + '</code>' +
                    (s.modus === 'anzeige' ? ' · ' + esc(s.aufloesung) : ' · ' + esc(s.datei || ''));
            } else {
                box.innerHTML = esc(tr('Sendet nicht')) + (s.fehler ? ' — <span class="wg-dim">' + esc(s.fehler) + '</span>' : '');
            }
        } catch (e) { /* naechster Versuch */ }
    }

    async function ladeVideos() {
        try {
            var liste = await (await fetch('/api/media/videos')).json();
            el('mc-datei').innerHTML = liste.map(function (f) {
                return '<option value="' + esc(f.name) + '">' + esc(f.name) + '</option>';
            }).join('');
        } catch (e) { /* bleibt leer */ }
    }

    el('mc-modus').addEventListener('change', zeigeModus);
    el('mc-speichern').addEventListener('click', async function () {
        try { await speichern(); meldung(tr('Gespeichert.')); } catch (e) { meldung(tr('Fehler: ') + e.message, true); }
    });
    el('mc-start').addEventListener('click', async function () {
        meldung(tr('Starte den Kanal …'));
        try {
            await speichern();
            var body = el('mc-modus').value === 'datei' ? { datei: el('mc-datei').value } : {};
            var r = await fetch('/api/multicast/start', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
            });
            var j = await r.json();
            if (!r.ok) throw new Error(j.error || r.status);
            meldung(tr('Kanal läuft.'));
        } catch (e) { meldung(tr('Fehler: ') + e.message, true); }
        ladeStatus();
    });
    el('mc-stop').addEventListener('click', async function () {
        await fetch('/api/multicast/stop', { method: 'POST' });
        meldung(tr('Gestoppt.'));
        ladeStatus();
    });

    fetch('/api/status').then(function (r) { return r.json(); }).then(function (d) {
        if (d.config && d.config.multicast) fuelle(d.config.multicast);
    }).catch(function () {});
    ladeVideos();
    ladeStatus();
    setInterval(ladeStatus, 10000);
})();

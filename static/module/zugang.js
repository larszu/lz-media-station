/* Zugang-Karte (3.0): PIN setzen, aendern, aufheben, abmelden.
   Vorlage: templates/admin/zusatz/90-zugang.html */
(function () {
    'use strict';

    function feedback(text, cls) {
        var f = el('zugang-feedback');
        f.textContent = text;
        f.className = 'feedback' + (cls ? ' ' + cls : '');
    }

    async function ladeStand() {
        try {
            var r = await fetch('/api/zugang');
            var d = await r.json();
            el('zugang-stand').textContent = d.gesetzt
                ? (d.angemeldet ? 'PIN ist gesetzt — du bist angemeldet.' : 'PIN ist gesetzt.')
                : 'Keine PIN gesetzt — die Verwaltung ist für jeden im Netz offen.';
            el('zugang-alt-gruppe').hidden = !d.gesetzt || d.lokal;
            el('zugang-aufheben').hidden = !d.gesetzt;
            el('zugang-abmelden').hidden = !d.angemeldet;
            el('zugang-dauer').value = d.sitzungsdauer_h || 24;
            var knopf = document.querySelector('#card-zugang .btn-save');
            if (knopf) knopf.textContent = d.gesetzt ? 'PIN ändern' : 'PIN setzen';
        } catch (e) { /* still */ }
    }

    window.setzePin = async function () {
        var pin = el('zugang-pin').value, pin2 = el('zugang-pin2').value;
        if (pin !== pin2) { feedback('✗ ' + tr('Die beiden PINs stimmen nicht überein'), 'error'); return; }
        var koerper = { pin: pin, sitzungsdauer_h: parseInt(el('zugang-dauer').value, 10) || 24 };
        if (!el('zugang-alt-gruppe').hidden) koerper.alt = el('zugang-alt').value;
        var r = await fetch('/api/zugang', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(koerper) });
        var d = await r.json();
        if (r.ok) {
            feedback('✓ PIN gesetzt — ab jetzt verlangt die Verwaltung eine Anmeldung', 'success');
            el('zugang-pin').value = el('zugang-pin2').value = el('zugang-alt').value = '';
        } else {
            feedback('✗ ' + tr(d.error || 'Fehler'), 'error');
        }
        ladeStand();
    };

    window.hebePinAuf = async function () {
        if (!confirm(tr('PIN aufheben? Die Verwaltung ist dann wieder für jeden im Netz offen.'))) return;
        var r = await fetch('/api/zugang', { method: 'DELETE' });
        var d = await r.json();
        feedback(r.ok ? '✓ PIN aufgehoben' : '✗ ' + tr(d.error || 'Fehler'), r.ok ? 'success' : 'error');
        ladeStand();
    };

    window.abmelden = async function () {
        await fetch('/api/zugang/logout', { method: 'POST' });
        window.location.href = '/login?weiter=/admin';
    };

    document.addEventListener('DOMContentLoaded', function () {
        if (el('card-zugang')) ladeStand();
    });

    // Antwortet die Station mit 401, ist die Sitzung abgelaufen: zur Anmeldung.
    var urspruenglich = window.fetch;
    window.fetch = function () {
        return urspruenglich.apply(this, arguments).then(function (r) {
            if (r.status === 401 && location.pathname === '/admin') {
                r.clone().json().then(function (d) {
                    if (d && d.zugang === 'pin') window.location.href = '/login?weiter=/admin';
                }).catch(function () { /* keine JSON-Antwort */ });
            }
            return r;
        });
    };
})();

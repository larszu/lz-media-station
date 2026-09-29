/* Puls der Anzeigeseite: melden, was hier laeuft — und auf Abruf ein Bild.

   Laeuft VOR display.js (static/anzeige/*.js) und hoert deshalb auf die
   Ereignisse am document, die der Kern der Anzeige ausloest:
     lz-szene    — eine Szene wurde angewandt
     lz-eintrag  — ein Playlist-Eintrag startet {region, item, idx}
     lz-befehl   — ein Befehl von /api/befehl, hier: {typ: 'screenshot'}

   DREI DINGE:
   1. Alle 10 s POST /api/anzeige/puls — Kennung dieses Tabs, Layout, Zone,
      was je Region laeuft, die letzten JS-Fehler. Bleibt das aus, meldet die
      Zustandspruefung „Keine Anzeige verbunden".
   2. Jeden Eintragsstart puffern und alle 30 s an POST /api/wiedergabe
      schicken (Proof-of-Play). Der Puffer bleibt bei Netzfehler stehen und
      geht beim naechsten Mal mit; der Kern dedupliziert.
   3. Auf den Befehl `screenshot` die Buehne in ein Canvas zeichnen und als
      JPEG an POST /api/anzeige/screenshot geben.

   IN DER VORSCHAU (Editor) meldet die Seite ihren Puls mit `vorschau: true`
   und KEINE Starts — ein Layout, das jemand im Editor probiert, ist nicht
   gespielt worden. */
(function () {
    'use strict';

    var PULS_S = 10, LOG_S = 30, FEHLER_MAX = 5;

    var kennung = (function () {
        try {
            var k = sessionStorage.getItem('lz-anzeige-kennung');
            if (!k) {
                k = 'a-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
                sessionStorage.setItem('lz-anzeige-kennung', k);
            }
            return k;
        } catch (e) {
            return 'a-' + Math.random().toString(36).slice(2, 10);
        }
    })();

    var seit = jetztIso();
    var szene = null;
    var fehler = [];
    var puffer = [];

    window.addEventListener('error', function (e) {
        fehler.push((e.message || 'Fehler') + (e.filename ? ' @' + e.filename.split('/').pop() + ':' + e.lineno : ''));
        if (fehler.length > FEHLER_MAX) fehler.shift();
    });

    function anzeige() { return window.LZ_ANZEIGE || null; }
    function inVorschau() { var a = anzeige(); return !!(a && a.vorschau && a.vorschau()); }

    // `keepalive` nur fuer den letzten Puffer beim Verlassen der Seite: der
    // Browser deckelt keepalive-Koerper bei 64 KiB und wirft groessere
    // Anfragen weg, bevor sie das Netz sehen — ein Screenshot (bis 2 MB)
    // oder ein voller Puffer kaeme so nie an.
    var KEEPALIVE_MAX_B = 60 * 1024;
    function post(url, daten, keepalive) {
        var body = JSON.stringify(daten);
        return fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: body, keepalive: !!keepalive && body.length <= KEEPALIVE_MAX_B
        });
    }

    // Zeitstempel voll nach ISO mit `Z`: der Kern rechnet sie in seine Ortszeit
    // um. Ohne das Z gilt eine UTC-Uhrzeit dort als Ortszeit — um den
    // Zeitzonenversatz falsch.
    function jetztIso() { return new Date().toISOString(); }

    document.addEventListener('lz-szene', function (e) { szene = e.detail || null; });

    document.addEventListener('lz-eintrag', function (e) {
        if (inVorschau() || !e.detail || !e.detail.item) return;
        var item = e.detail.item;
        puffer.push({
            zeit: jetztIso(),
            region: e.detail.region,
            typ: item.typ,
            name: item.name || item.url || '',
            layout_id: szene ? szene.layout_id : null,
            zone: szene ? szene.zone : null
        });
        if (puffer.length > 500) puffer.splice(0, puffer.length - 500);
    });

    function puls() {
        var a = anzeige();
        post('/api/anzeige/puls', {
            kennung: kennung,
            seit: seit,
            layout_id: szene ? szene.layout_id : null,
            zone: szene ? szene.zone : null,
            vorschau: inVorschau(),
            regionen: a ? a.regionen() : [],
            fehler: fehler
        }).catch(function () { /* Station nicht erreichbar — naechster Puls */ });
    }

    function logSenden(beimVerlassen) {
        if (!puffer.length) return;
        // Beim Verlassen nur, was in eine keepalive-Anfrage passt — die
        // juengsten Eintraege; der Rest ist in dieser Sitzung verloren.
        var eintraege = beimVerlassen ? puffer.slice(-40) : puffer.slice();
        var anzahl = eintraege.length;
        post('/api/wiedergabe', { kennung: kennung, eintraege: eintraege }, !!beimVerlassen)
            .then(function (r) { if (r.ok) puffer.splice(puffer.length - anzahl, anzahl); })
            .catch(function () { /* bleibt im Puffer */ });
    }

    /* ---- Screenshot: die Buehne in ein Canvas ---- */

    function zeichne() {
        var a = anzeige();
        var buehne = a && a.buehne ? a.buehne() : document.getElementById('buehne');
        var W = window.innerWidth, H = window.innerHeight;
        var f = Math.min(1, 1280 / Math.max(W, 1));
        var c = document.createElement('canvas');
        c.width = Math.max(1, Math.round(W * f));
        c.height = Math.max(1, Math.round(H * f));
        var ctx = c.getContext('2d');
        ctx.fillStyle = (buehne && buehne.style.background) || '#000';
        ctx.fillRect(0, 0, c.width, c.height);
        if (!buehne) return c;
        var regionen = buehne.querySelectorAll('.region');
        for (var i = 0; i < regionen.length; i++) {
            var reg = regionen[i];
            var b = reg.getBoundingClientRect();
            var x = b.left * f, y = b.top * f, w = b.width * f, h = b.height * f;
            var ebene = reg.querySelector('.layer.active');
            var gezeichnet = false;
            if (ebene && (ebene.tagName === 'VIDEO' || ebene.tagName === 'IMG')) {
                try {
                    // object-fit: cover nachbilden — Bild fuellt die Region, Rest beschnitten.
                    var qw = ebene.tagName === 'VIDEO' ? ebene.videoWidth : ebene.naturalWidth;
                    var qh = ebene.tagName === 'VIDEO' ? ebene.videoHeight : ebene.naturalHeight;
                    if (qw && qh) {
                        var s = Math.max(w / qw, h / qh);
                        var zw = qw * s, zh = qh * s;
                        ctx.save();
                        ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
                        ctx.drawImage(ebene, x + (w - zw) / 2, y + (h - zh) / 2, zw, zh);
                        ctx.restore();
                        gezeichnet = true;
                    }
                } catch (e) { gezeichnet = false; }
            }
            if (!gezeichnet) {
                // Webseite, Widget oder nichts Ladbares: eine beschriftete
                // Flaeche. Ein fremdes iframe laesst sich nicht auslesen.
                ctx.fillStyle = '#1D324F';
                ctx.fillRect(x, y, w, h);
                ctx.strokeStyle = '#8C9CB3';
                ctx.lineWidth = 1;
                ctx.strokeRect(x + 0.5, y + 0.5, Math.max(0, w - 1), Math.max(0, h - 1));
                ctx.fillStyle = '#E1ECEF';
                ctx.font = Math.max(10, Math.round(14 * f)) + 'px system-ui, sans-serif';
                ctx.textBaseline = 'top';
                var name = reg.getAttribute('data-region') || '';
                var art = reg.querySelector('iframe.layer.active') ? 'Webseite' : (ebene ? '' : 'Widget');
                ctx.fillText((name + (art ? ' · ' + art : '')).trim(), x + 6, y + 6);
            }
        }
        return c;
    }

    function screenshot() {
        var bild;
        try { bild = zeichne().toDataURL('image/jpeg', 0.7); }
        catch (e) { return; }
        post('/api/anzeige/screenshot', { kennung: kennung, bild: bild })
            .catch(function () { /* naechstes Mal */ });
    }

    document.addEventListener('lz-befehl', function (e) {
        if (e.detail && e.detail.typ === 'screenshot') screenshot();
    });

    // display.js registriert LZ_ANZEIGE erst nach uns — der erste Puls wartet
    // deshalb einen Augenblick, damit er schon Regionen nennen kann.
    setTimeout(puls, 1500);
    setInterval(puls, PULS_S * 1000);
    setInterval(function () { logSenden(false); }, LOG_S * 1000);
    window.addEventListener('pagehide', function () { logSenden(true); });
})();

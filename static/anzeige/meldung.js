/* Sofortmeldung und schwarzer Schirm auf der Anzeige (Welle 2).

   Laeuft VOR display.js (static/anzeige/) und hoert auf dessen Ereignisse am
   document: `lz-szene` (jede angewandte Szene traegt `meldung` und `schwarz`)
   und `lz-befehl` (typ `meldung` bzw. `schwarz` — sofort, ohne auf die
   naechste Szene zu warten).

   Zwei Ebenen ueber der Buehne: `#schwarz` (deckt alles ab, wenn die Station
   den Schirm ausschaltet) und `#meldung` (grosse Schrift, Farbe frei). Die
   Meldung endet von selbst zu `bis`; die Anzeige braucht dafuer keinen Server. */
(function () {
    'use strict';

    var schwarzEl = null, meldungEl = null, timer = null, gezeigt = '';

    function ebene(id, z) {
        var n = document.getElementById(id);
        if (n) return n;
        n = document.createElement('div');
        n.id = id;
        n.style.cssText = 'position:fixed;inset:0;z-index:' + z + ';display:none;';
        document.body.appendChild(n);
        return n;
    }

    function schwarz(an) {
        if (!schwarzEl) { schwarzEl = ebene('schwarz', 50); schwarzEl.style.background = '#000'; }
        schwarzEl.style.display = an ? 'block' : 'none';
    }

    function piep() {
        try {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            var ctx = new AC();
            for (var i = 0; i < 3; i++) {
                var o = ctx.createOscillator(), g = ctx.createGain();
                o.type = 'square'; o.frequency.value = 880;
                g.gain.value = 0.15;
                o.connect(g); g.connect(ctx.destination);
                o.start(ctx.currentTime + i * 0.5);
                o.stop(ctx.currentTime + i * 0.5 + 0.25);
            }
        } catch (e) { /* kein Ton moeglich — die Meldung steht trotzdem */ }
    }

    function zeige(m) {
        if (!meldungEl) {
            meldungEl = ebene('meldung', 60);
            meldungEl.style.cssText += 'display:none;flex-direction:column;align-items:center;justify-content:center;text-align:center;' +
                'padding:6vh 6vw;font-family:"Public Sans",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;';
            meldungEl.innerHTML = '<div id="meldung-text" style="font-size:8vmin;font-weight:700;line-height:1.15"></div>' +
                '<div id="meldung-untertext" style="font-size:4vmin;margin-top:3vmin;opacity:0.9"></div>';
        }
        if (timer) { clearTimeout(timer); timer = null; }
        var aktiv = m && m.aktiv;
        if (aktiv && m.bis) {
            var rest = new Date(m.bis).getTime() - Date.now();
            if (rest <= 0) aktiv = false;
            else timer = setTimeout(function () { zeige({ aktiv: false }); }, rest);
        }
        if (!aktiv) { meldungEl.style.display = 'none'; gezeigt = ''; return; }
        meldungEl.style.background = m.farbe || '#B04A3F';
        meldungEl.style.color = m.textfarbe || '#FFFFFF';
        document.getElementById('meldung-text').textContent = m.text || '';
        document.getElementById('meldung-untertext').textContent = m.untertext || '';
        meldungEl.style.display = 'flex';
        var kennung = JSON.stringify([m.text, m.untertext, m.bis]);
        if (m.ton && kennung !== gezeigt) piep();
        gezeigt = kennung;
    }

    document.addEventListener('lz-szene', function (e) {
        var s = e.detail || {};
        if (s.vorschau) return;
        if ('schwarz' in s) schwarz(!!s.schwarz);
        if ('meldung' in s) zeige(s.meldung);
    });
    document.addEventListener('lz-befehl', function (e) {
        var b = e.detail || {};
        if (b.typ === 'schwarz') schwarz(!!b.an);
        if (b.typ === 'meldung') zeige(b);
    });
})();

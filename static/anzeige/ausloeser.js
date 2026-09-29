/* Die Anzeige meldet der Station, wenn ein Video zu Ende ist (Welle 2).

   Quelle `video_ende` der Ausloeser: „nach dem Film kommt das Menue zurueck".
   Gemeldet wird nur, wenn die Szene sagt, dass es einen solchen Ausloeser gibt
   (`ausloeser_video_ende`) — sonst waere jedes Videoende ein Aufruf ins Leere.
   Nicht in der Vorschau: ein Editor-Fenster darf keine Ausloeser feuern. */
(function () {
    'use strict';

    var melden = false, vorschau = false;

    document.addEventListener('lz-szene', function (e) {
        var s = e.detail || {};
        vorschau = !!s.vorschau;
        melden = !!s.ausloeser_video_ende;
    });

    // `ended` steigt nicht auf; als Capture-Listener am document kommt es
    // trotzdem hier an — fuer jedes <video>, das display.js je anlegt.
    document.addEventListener('ended', function (e) {
        if (!melden || vorschau) return;
        var v = e.target;
        if (!v || v.tagName !== 'VIDEO') return;
        var region = v.closest ? v.closest('.region') : null;
        var datei = '';
        try { datei = decodeURIComponent((v.currentSrc || v.src || '').split('/').pop().split('?')[0]); } catch (err) { /* egal */ }
        try {
            fetch('/api/trigger/_video_ende', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ datei: datei, region: region ? region.getAttribute('data-region') : '' })
            });
        } catch (err) { /* Station nicht erreichbar */ }
    }, true);
})();

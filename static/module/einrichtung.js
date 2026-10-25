/* Ersteinrichtung (3.0): die Karte „In 3 Schritten" steht oben, solange
   keine Zone etwas zu zeigen hat, und verschwindet von selbst, sobald
   Inhalt da ist. „Inhalt" misst genau wie der Autostart der Startseite
   (templates/launch.html): Ton der Zone, eine Region mit Playlist oder ein
   Widget im Layout der Zone. */
(function () {
    'use strict';
    var karte = document.getElementById('card-einrichtung');
    if (!karte) return;
    // Oben in der Lande-Ansicht „Abspielen" platzieren (nicht in `main`
    // selbst — sonst stuende die Karte ausserhalb der Ansichten und waere in
    // jeder sichtbar). Faellt auf `main` zurueck, falls es keine Ansichten
    // gibt (aeltere Oberflaeche).
    var ziel = document.querySelector('.view[data-view="abspielen"]') || karte.closest('main');
    if (ziel && ziel.firstElementChild !== karte) ziel.insertBefore(karte, ziel.firstElementChild);

    function hatInhalt(cfg) {
        if (!cfg) return true;  // ohne Daten nichts behaupten
        var zonen = Number(cfg.zonen_stufen) === 3 ? ['near', 'mid', 'far'] : ['near', 'far'];
        var layouts = cfg.layouts || {};
        return zonen.some(function (name) {
            var z = cfg[name] || {};
            if ((z.audio || []).length) return true;
            var l = layouts[z.layout || ('zone-' + name)] || layouts['zone-' + name] || {};
            return (l.regionen || []).some(function (r) {
                return r.typ === 'widget' || (r.playlist || []).length;
            });
        });
    }

    function pruefe(cfg) { karte.hidden = hatInhalt(cfg); }

    document.addEventListener('lz-status', function (e) { if (e.detail) pruefe(e.detail.config); });
    fetch('/api/status').then(function (r) { return r.json(); })
        .then(function (d) { pruefe(d.config); }).catch(function () {});
})();

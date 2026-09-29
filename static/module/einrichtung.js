/* Ersteinrichtung (3.0): die Karte „In 3 Schritten" steht oben, solange
   keine Zone etwas zu zeigen hat, und verschwindet von selbst, sobald
   Inhalt da ist. „Inhalt" misst genau wie der Autostart der Startseite
   (templates/launch.html): Ton der Zone, eine Region mit Playlist oder ein
   Widget im Layout der Zone. */
(function () {
    'use strict';
    var karte = document.getElementById('card-einrichtung');
    if (!karte) return;
    var main = karte.closest('main');
    if (main && main.firstElementChild !== karte) main.insertBefore(karte, main.firstElementChild);

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

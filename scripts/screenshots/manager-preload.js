/* Nachbildung von station-manager/preload.js fuer die Screenshots: der
   Renderer laeuft im Browser, `window.station` fragt die Demo-Stationen ueber
   die von aufnehmen.py bereitgestellte Funktion `lzHolen` ab — dieselben drei
   GETs wie `pollStation` in main.js. */
(function () {
    var basis = function (s) { return 'http://' + s.host + ':' + s.port; };
    var stationen = (window.__LZ_STATIONEN || []).map(function (s, i) {
        return Object.assign({ id: 'demo-' + i, source: 'manual', online: false, stumm: false }, s);
    });

    async function abfragen(s) {
        var st = await lzHolen(basis(s) + '/api/status');
        if (st.status !== 200) { s.online = false; return; }
        s.online = true;
        s.state = st.body.state; s.active = st.body.active;
        s.geschlossen = !!st.body.geschlossen; s.anzeige = st.body.anzeige || null;
        var sz = await lzHolen(basis(s) + '/api/scene');
        if (sz.status === 200 && sz.body) {
            s.zone = sz.body.zone || null; s.layoutId = sz.body.layout_id || null;
            s.layoutName = (sz.body.layout && sz.body.layout.name) || null;
        }
        var id = await lzHolen(basis(s) + '/api/identity');
        if (id.status === 200 && id.body) {
            s.health = id.body.health || null; s.healthAnzahl = id.body.health_anzahl || 0;
            s.version = id.body.version; s.name = id.body.name || s.name;
        }
    }
    var bereit = Promise.all(stationen.map(abfragen));
    var finde = function (id) { return stationen.find(function (s) { return s.id === id; }); };
    var nichts = function () { return Promise.resolve(null); };

    window.station = {
        version: function () { return Promise.resolve(window.__LZ_VERSION || ''); },
        listStations: function () { return bereit.then(function () { return stationen; }); },
        onStations: function () {}, onUploadProgress: function () {}, onAlarme: function () {},
        alarme: function () { return Promise.resolve([]); },
        api: async function (id, action, method, body) {
            var s = finde(id);
            var r = await lzHolen(basis(s) + '/api/' + action, method || 'POST', body || null);
            return { ok: r.status >= 200 && r.status < 300, status: r.status, body: r.body };
        },
        screenshot: async function (id, anfordern) {
            var s = finde(id);
            if (!s || !s.online) return { error: 'offline' };
            var pfad = '/api/anzeige/screenshot';
            if (anfordern) {
                var a = await lzHolen(basis(s) + '/api/anzeige/screenshot/anfordern', 'POST', {});
                if (a.status === 200 && a.body && a.body.url) pfad = a.body.url;
            }
            var b = await lzHolen(basis(s) + pfad, 'GET', null, true);
            if (b.status !== 200) return { fehlt: true };
            return { ok: true, bild: 'data:' + (b.typ || 'image/jpeg') + ';base64,' + b.b64, zeit: b.zeit };
        },
        hasPin: function () { return Promise.resolve(false); },
        accessInfo: nichts, adminUrl: nichts, openAdmin: nichts, addStation: nichts,
        removeStation: nichts, rescan: nichts, pickFiles: nichts, uploadTo: nichts,
        pushConfig: nichts, setPin: nichts, setOrdnung: nichts, setStumm: nichts,
        alarmeLeeren: nichts,
    };
})();

/* Wochenprogramm und Sofortmeldung — die Verwaltungsseite (Welle 2).

   Laeuft nach app.js (static/module/), darf also `el()`, `esc()`, `escAttr()`,
   `tr()`, `config` und `layoutsStand` benutzen. Redet nur mit
   /api/programm, /api/programm/jetzt, /api/meldung und /api/layouts.

   DER KALENDER: sieben Spalten (Mo–So), 24 Stunden je Spalte, 20 px je Stunde.
   Ein Eintrag ist ein Block; laeuft er ueber Mitternacht, sind es zwei
   (heute bis 24:00, morgen ab 00:00). Ziehen ueber Stunden legt einen
   Eintrag an — mit Vorgaben, die in den meisten Faellen stimmen (alle
   Zonen, Prioritaet 5, aktiv), damit es zwei Klicks sind und nicht zehn. */
(function () {
    'use strict';

    var TAGE = ['mo', 'di', 'mi', 'do', 'fr', 'sa', 'so'];
    var TAG_NAMEN = { mo: 'Mo', di: 'Di', mi: 'Mi', do: 'Do', fr: 'Fr', sa: 'Sa', so: 'So' };
    var ZONEN = { near: 'Nah', mid: 'Mitte', far: 'Fern' };
    var PX_JE_STUNDE = 20;
    // Zehn deutlich unterscheidbare, gedeckte Toene auf Deep Navy — je
    // Layout einer, stabil ueber die Kennung.
    var FARBEN = ['#8C9CB3', '#2F7D5C', '#C8892B', '#6B7FB3', '#B04A3F', '#5E8F7A', '#A67C52', '#7B6FA6', '#4E8CA8', '#9C7B8C'];

    var programm = { eintraege: [], ausnahmen: [] };
    var zone = 'near';
    var bearbeitet = null;      // id des Eintrags im Formular, null = neu
    var ziehen = null;          // {tag, von, bis, el}
    var jetztSichtbar = false;

    function tr_(t) { return (typeof tr === 'function') ? tr(t) : t; }

    /* ---- Daten ---- */

    async function lade() {
        try {
            var r = await fetch('/api/programm');
            if (r.ok) programm = await r.json();
        } catch (e) { /* Station nicht erreichbar — der alte Stand bleibt */ }
        if (!window.layoutsStand || !Object.keys(layoutsStand.layouts || {}).length) {
            try {
                var l = await fetch('/api/layouts');
                if (l.ok) window.layoutsStand = await l.json();
            } catch (e) { /* s. o. */ }
        }
        fuelleZonenWahl();
        zeichne();
        zeichneAusnahmen();
        fuelleLayoutWahl(el('prog-layout'), null);
        fuelleLayoutWahl(el('prog-ausnahme-layout'), '');
    }

    async function speichere(neu, feedbackText) {
        try {
            var r = await fetch('/api/programm', {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(neu)
            });
            var d = await r.json();
            if (!r.ok) { rueckmeldung(d.error || 'Fehler', true); return false; }
            programm = d.programm;
            rueckmeldung(feedbackText || '✓ Gespeichert', false);
            zeichne();
            zeichneAusnahmen();
            if (jetztSichtbar) ladeJetzt();
            return true;
        } catch (e) {
            rueckmeldung('Station nicht erreichbar', true);
            return false;
        }
    }

    function rueckmeldung(text, fehler) {
        var fb = el('prog-feedback');
        if (!fb) return;
        fb.textContent = text;
        fb.className = 'feedback ' + (fehler ? 'error' : 'success');
        if (!fehler) setTimeout(function () { if (fb.textContent === text) fb.textContent = ''; }, 3000);
    }

    /* ---- Hilfen ---- */

    function layouts() { return (window.layoutsStand && layoutsStand.layouts) || {}; }
    function layoutName(id) { return (layouts()[id] || {}).name || id || ''; }
    function farbe(id) {
        var ids = Object.keys(layouts()).sort();
        var i = ids.indexOf(id);
        if (i < 0) { i = 0; for (var k = 0; k < (id || '').length; k++) i = (i * 31 + id.charCodeAt(k)) % 997; }
        return FARBEN[i % FARBEN.length];
    }
    function minuten(hhmm) {
        var t = (hhmm || '00:00').split(':');
        return (parseInt(t[0], 10) || 0) * 60 + (parseInt(t[1], 10) || 0);
    }
    function hhmm(min) {
        min = Math.max(0, Math.min(1440, min));
        var h = Math.floor(min / 60), m = min % 60;
        return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
    }
    function heuteKuerzel() { return TAGE[(new Date().getDay() + 6) % 7]; }
    function aktiveZonen() {
        return (config && Number(config.zonen_stufen) >= 3) ? ['near', 'mid', 'far'] : ['near', 'far'];
    }

    function fuelleZonenWahl() {
        var sel = el('prog-zone');
        if (!sel) return;
        var zonen = aktiveZonen();
        if (zonen.indexOf(zone) < 0) zone = zonen[0];
        sel.innerHTML = zonen.map(function (z) {
            return '<option value="' + z + '"' + (z === zone ? ' selected' : '') + '>' + ZONEN[z] + '</option>';
        }).join('');
    }

    function fuelleLayoutWahl(sel, gewaehlt) {
        if (!sel) return;
        var ids = Object.keys(layouts());
        var html = '';
        if (sel.id === 'prog-ausnahme-layout') html += '<option value="">' + tr_('Standard der Zone (kein Programm)') + '</option>';
        html += ids.map(function (id) {
            return '<option value="' + escAttr(id) + '"' + (id === gewaehlt ? ' selected' : '') + '>' + esc(layoutName(id)) + '</option>';
        }).join('');
        sel.innerHTML = html;
        if (gewaehlt !== null && gewaehlt !== undefined) sel.value = gewaehlt;
    }

    /* ---- Kalender ---- */

    function zeichne() {
        var wurzel = el('prog-kalender');
        if (!wurzel) return;
        var heute = heuteKuerzel();
        var html = '<div class="prog-tagkopf"></div>';
        TAGE.forEach(function (t) {
            html += '<div class="prog-tagkopf' + (t === heute ? ' heute' : '') + '">' + TAG_NAMEN[t] + '</div>';
        });
        html += '<div class="prog-stunden">';
        for (var h = 0; h < 24; h += 2) html += '<span style="top:' + (h * PX_JE_STUNDE) + 'px">' + (h < 10 ? '0' : '') + h + '</span>';
        html += '</div>';
        TAGE.forEach(function (t) {
            html += '<div class="prog-tag" data-tag="' + t + '">';
            for (var s = 0; s < 24; s++) html += '<div class="stunde' + (s % 6 === 0 ? ' voll' : '') + '" style="top:' + (s * PX_JE_STUNDE) + 'px"></div>';
            html += bloeckeFuer(t);
            if (t === heute) {
                var n = new Date();
                html += '<div class="prog-jetzt" style="top:' + ((n.getHours() * 60 + n.getMinutes()) / 60 * PX_JE_STUNDE) + 'px"></div>';
            }
            html += '</div>';
        });
        wurzel.innerHTML = html;
        wurzel.querySelectorAll('.prog-tag').forEach(bindeZiehen);
        zeichneLegende();
    }

    function bloeckeFuer(tag) {
        var html = '';
        (programm.eintraege || []).forEach(function (e) {
            if ((e.tage || []).indexOf(tag) < 0) return;
            if (e.zonen && e.zonen.length && e.zonen.indexOf(zone) < 0) return;
            var von = minuten(e.von), bis = minuten(e.bis);
            if (bis === 0) bis = 1440;
            if (von < bis) {
                html += block(e, von, bis, false);
            } else {
                html += block(e, von, 1440, false);
                // Der Teil nach Mitternacht steht in der Spalte des naechsten Tages.
                html += '<!--folgetag:' + tag + '-->';
            }
        });
        // Ueberlaeufe aus dem Vortag
        var vortag = TAGE[(TAGE.indexOf(tag) + 6) % 7];
        (programm.eintraege || []).forEach(function (e) {
            if ((e.tage || []).indexOf(vortag) < 0) return;
            if (e.zonen && e.zonen.length && e.zonen.indexOf(zone) < 0) return;
            var von = minuten(e.von), bis = minuten(e.bis);
            if (bis !== 0 && von > bis) html += block(e, 0, bis, true);
        });
        return html;
    }

    function block(e, von, bis, fortsetzung) {
        var top = von / 60 * PX_JE_STUNDE, hoehe = Math.max(6, (bis - von) / 60 * PX_JE_STUNDE - 1);
        var klasse = 'prog-block' + (e.aktiv === false ? ' inaktiv' : '') + (bearbeitet === e.id ? ' markiert' : '');
        return '<div class="' + klasse + '" data-id="' + escAttr(e.id) + '" style="top:' + top + 'px;height:' + hoehe +
            'px;z-index:' + (e.prioritaet || 5) + ';background:' + farbe(e.layout_id) + '" title="' + escAttr(e.name + ' · ' + layoutName(e.layout_id)) + '">' +
            (fortsetzung ? '↳ ' : '') + esc(e.name) + '<span class="prio">' + (e.prioritaet || 5) + '</span></div>';
    }

    function zeichneLegende() {
        var leg = el('prog-legende');
        if (!leg) return;
        var benutzt = {};
        (programm.eintraege || []).forEach(function (e) { benutzt[e.layout_id] = true; });
        leg.innerHTML = Object.keys(benutzt).map(function (id) {
            return '<span><i style="background:' + farbe(id) + '"></i>' + esc(layoutName(id)) + '</span>';
        }).join('') + (Object.keys(benutzt).length ? '' : '<span>' + tr_('Noch kein Eintrag — im Kalender ziehen oder „+ Eintrag".') + '</span>');
    }

    /* ---- Ziehen (Maus und Finger) ---- */

    function bindeZiehen(spalte) {
        var tag = spalte.getAttribute('data-tag');

        function position(ev) {
            var p = ev.touches ? ev.touches[0] : ev;
            var r = spalte.getBoundingClientRect();
            var min = Math.round((p.clientY - r.top) / PX_JE_STUNDE * 60 / 15) * 15;
            return Math.max(0, Math.min(1440, min));
        }
        function start(ev) {
            var blockEl = ev.target.closest && ev.target.closest('.prog-block');
            if (blockEl) {
                ev.preventDefault();
                oeffneEintrag(blockEl.getAttribute('data-id'));
                return;
            }
            if (ev.type === 'mousedown' && ev.button !== 0) return;
            ev.preventDefault();
            var m = Math.floor(position(ev) / 60) * 60;
            ziehen = { tag: tag, von: m, bis: m + 60, el: document.createElement('div') };
            ziehen.el.className = 'prog-auswahl';
            spalte.appendChild(ziehen.el);
            male();
        }
        function bewege(ev) {
            if (!ziehen || ziehen.tag !== tag) return;
            ev.preventDefault();
            var m = Math.ceil(position(ev) / 60) * 60;
            ziehen.bis = Math.max(ziehen.von + 60, Math.min(1440, m));
            male();
        }
        function male() {
            ziehen.el.style.top = (ziehen.von / 60 * PX_JE_STUNDE) + 'px';
            ziehen.el.style.height = ((ziehen.bis - ziehen.von) / 60 * PX_JE_STUNDE) + 'px';
        }
        function ende(ev) {
            if (!ziehen || ziehen.tag !== tag) return;
            ev.preventDefault();
            var z = ziehen; ziehen = null;
            if (z.el.parentNode) z.el.parentNode.removeChild(z.el);
            progNeuerEintrag({ tage: [tag], von: hhmm(z.von), bis: hhmm(z.bis) });
        }
        spalte.addEventListener('mousedown', start);
        spalte.addEventListener('mousemove', bewege);
        spalte.addEventListener('mouseup', ende);
        spalte.addEventListener('mouseleave', function () {
            if (ziehen && ziehen.tag === tag) { if (ziehen.el.parentNode) ziehen.el.parentNode.removeChild(ziehen.el); ziehen = null; }
        });
        spalte.addEventListener('touchstart', start, { passive: false });
        spalte.addEventListener('touchmove', bewege, { passive: false });
        spalte.addEventListener('touchend', ende, { passive: false });
    }

    /* ---- Formular ---- */

    function fuelleTage(wurzel, gewaehlt) {
        wurzel.innerHTML = TAGE.map(function (t) {
            return '<label><input type="checkbox" value="' + t + '"' + (gewaehlt.indexOf(t) >= 0 ? ' checked' : '') + '>' + TAG_NAMEN[t] + '</label>';
        }).join('');
    }
    function fuelleZonen(wurzel, gewaehlt) {
        wurzel.innerHTML = aktiveZonen().map(function (z) {
            return '<label><input type="checkbox" value="' + z + '"' + (gewaehlt.indexOf(z) >= 0 ? ' checked' : '') + '>' + ZONEN[z] + '</label>';
        }).join('');
    }
    function gewaehlte(wurzel) {
        return Array.prototype.map.call(wurzel.querySelectorAll('input:checked'), function (i) { return i.value; });
    }

    function zeigeForm(e) {
        bearbeitet = e.id || null;
        el('prog-form-titel').textContent = bearbeitet ? tr_('Eintrag bearbeiten') : tr_('Neuer Eintrag');
        el('prog-name').value = e.name || '';
        var ids = Object.keys(layouts());
        var vorgabe = e.layout_id || ids.filter(function (id) { return id.indexOf('zone-') !== 0; })[0] || ids[0] || '';
        fuelleLayoutWahl(el('prog-layout'), vorgabe);
        fuelleTage(el('prog-tage'), e.tage || TAGE);
        fuelleZonen(el('prog-zonen'), e.zonen || []);
        el('prog-von').value = e.von || '09:00';
        el('prog-bis').value = (e.bis === '24:00' ? '00:00' : e.bis) || '12:00';
        el('prog-prio').value = e.prioritaet || 5;
        el('prog-gueltig-von').value = e.gueltig_von || '';
        el('prog-gueltig-bis').value = e.gueltig_bis || '';
        el('prog-aktiv').checked = e.aktiv !== false;
        el('prog-loeschen').hidden = !bearbeitet;
        el('prog-form').hidden = false;
        zeichne();
        el('prog-name').focus();
    }

    function oeffneEintrag(id) {
        var e = (programm.eintraege || []).filter(function (x) { return x.id === id; })[0];
        if (e) zeigeForm(e);
    }

    function kennung(name, vergeben) {
        var g = (name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 36) || 'eintrag';
        if (!/^[a-z0-9]/.test(g)) g = 'e-' + g;
        var k = g, n = 2;
        while (vergeben.indexOf(k) >= 0) k = g + '-' + (n++);
        return k;
    }

    window.progNeuerEintrag = function (vorgaben) {
        zeigeForm(vorgaben && vorgaben.tage ? vorgaben : {});
    };
    window.progFormSchliessen = function () {
        el('prog-form').hidden = true;
        bearbeitet = null;
        zeichne();
    };
    window.progEintragSpeichern = function () {
        var name = (el('prog-name').value || '').trim();
        if (!name) { rueckmeldung(tr_('Bitte einen Namen eingeben.'), true); el('prog-name').focus(); return; }
        var bis = el('prog-bis').value || '00:00';
        if (bis === '00:00') bis = '24:00';
        var liste = (programm.eintraege || []).slice();
        var ids = liste.map(function (x) { return x.id; });
        var e = {
            id: bearbeitet || kennung(name, ids),
            name: name,
            layout_id: el('prog-layout').value,
            zonen: gewaehlte(el('prog-zonen')),
            tage: gewaehlte(el('prog-tage')),
            von: el('prog-von').value || '00:00',
            bis: bis,
            prioritaet: parseInt(el('prog-prio').value, 10) || 5,
            gueltig_von: el('prog-gueltig-von').value || null,
            gueltig_bis: el('prog-gueltig-bis').value || null,
            aktiv: el('prog-aktiv').checked
        };
        var i = ids.indexOf(e.id);
        if (i >= 0) liste[i] = e; else liste.push(e);
        speichere({ eintraege: liste, ausnahmen: programm.ausnahmen || [] }).then(function (ok) {
            if (ok) progFormSchliessen();
        });
    };
    window.progEintragLoeschen = function () {
        if (!bearbeitet) return;
        var liste = (programm.eintraege || []).filter(function (x) { return x.id !== bearbeitet; });
        speichere({ eintraege: liste, ausnahmen: programm.ausnahmen || [] }, '✓ Gelöscht').then(function (ok) {
            if (ok) progFormSchliessen();
        });
    };

    /* ---- Ausnahmetage ---- */

    function zeichneAusnahmen() {
        var wurzel = el('prog-ausnahmen');
        if (!wurzel) return;
        var liste = programm.ausnahmen || [];
        if (!liste.length) { wurzel.innerHTML = '<div class="empty">' + tr_('Keine Ausnahmetage.') + '</div>'; return; }
        wurzel.innerHTML = liste.map(function (a) {
            return '<div class="prog-zeile"><strong>' + esc(a.datum) + '</strong> ' + esc(a.name || '') +
                '<span class="meta">' + esc(a.layout_id ? layoutName(a.layout_id) : tr_('Standard der Zone (kein Programm)')) + '</span>' +
                '<button class="del-btn" title="' + escAttr(tr_('Löschen')) + '" onclick="progAusnahmeWeg(\'' + escAttr(a.datum) + '\')">✕</button></div>';
        }).join('');
    }
    window.progAusnahmeHinzu = function () {
        var datum = el('prog-ausnahme-datum').value;
        if (!datum) { rueckmeldung(tr_('Bitte ein Datum wählen.'), true); return; }
        var liste = (programm.ausnahmen || []).filter(function (a) { return a.datum !== datum; });
        liste.push({ datum: datum, layout_id: el('prog-ausnahme-layout').value || null, name: (el('prog-ausnahme-name').value || '').trim() });
        speichere({ eintraege: programm.eintraege || [], ausnahmen: liste }).then(function (ok) {
            if (ok) { el('prog-ausnahme-datum').value = ''; el('prog-ausnahme-name').value = ''; }
        });
    };
    window.progAusnahmeWeg = function (datum) {
        var liste = (programm.ausnahmen || []).filter(function (a) { return a.datum !== datum; });
        speichere({ eintraege: programm.eintraege || [], ausnahmen: liste }, '✓ Gelöscht');
    };

    /* ---- Was laeuft jetzt ---- */

    async function ladeJetzt() {
        var wurzel = el('prog-jetzt');
        try {
            var r = await fetch('/api/programm/jetzt');
            var d = await r.json();
            wurzel.innerHTML = Object.keys(d.zonen).map(function (z) {
                var s = d.zonen[z];
                var woher = s.quelle === 'programm' ? tr_('laut Programm') + (s.eintrag ? ' „' + esc(s.eintrag.name) + '"' : '')
                    : s.quelle === 'ausnahme' ? tr_('Ausnahmetag') + (s.eintrag && s.eintrag.name ? ' „' + esc(s.eintrag.name) + '"' : '')
                    : tr_('Layout der Zone');
                return '<div><span class="badge ' + z + '">' + ZONEN[z] + '</span> <strong>' + esc(s.layout_name || s.layout_id || '–') + '</strong> <span class="meta">— ' + woher + '</span></div>';
            }).join('');
        } catch (e) { wurzel.textContent = tr_('Station nicht erreichbar'); }
    }
    window.progJetztUmschalten = function () {
        jetztSichtbar = !jetztSichtbar;
        el('prog-jetzt').hidden = !jetztSichtbar;
        if (jetztSichtbar) ladeJetzt();
    };

    /* ---- Sofortmeldung ---- */

    var VORLAGEN = {
        raeumung: { text: 'Bitte verlassen Sie das Gebäude', untertext: 'Folgen Sie den Fluchtwegen zum Sammelplatz', farbe: '#B04A3F', textfarbe: '#FFFFFF', ton: true },
        hinweis: { text: 'Hinweis', untertext: 'Die Veranstaltung beginnt in 5 Minuten', farbe: '#C8892B', textfarbe: '#132040', ton: false },
        pause: { text: 'Pause', untertext: 'Es geht um 14:00 Uhr weiter', farbe: '#1D324F', textfarbe: '#E1ECEF', ton: false }
    };

    window.meldungVorlage = function (name) {
        var v = VORLAGEN[name];
        if (!v) return;
        el('meldung-text').value = tr_(v.text);
        el('meldung-untertext').value = tr_(v.untertext);
        el('meldung-farbe').value = v.farbe;
        el('meldung-textfarbe').value = v.textfarbe;
        el('meldung-ton').checked = v.ton;
        meldungVorschau();
    };

    function meldungVorschau() {
        var v = el('meldung-vorschau');
        var text = el('meldung-text').value;
        if (!text) { v.hidden = true; return; }
        v.hidden = false;
        v.style.background = el('meldung-farbe').value;
        v.style.color = el('meldung-textfarbe').value;
        v.innerHTML = esc(text) + (el('meldung-untertext').value ? '<small>' + esc(el('meldung-untertext').value) + '</small>' : '');
    }

    function meldungRueck(text, fehler) {
        var fb = el('meldung-feedback');
        fb.textContent = text;
        fb.className = 'feedback ' + (fehler ? 'error' : 'success');
        if (!fehler) setTimeout(function () { if (fb.textContent === text) fb.textContent = ''; }, 3000);
    }

    async function meldungStatus() {
        var s = el('meldung-status');
        if (!s) return;
        try {
            var r = await fetch('/api/meldung');
            var m = await r.json();
            if (m.aktiv) {
                s.className = 'meldung-status aktiv';
                s.textContent = tr_('Aktiv:') + ' „' + m.text + '"' + (m.bis ? ' — ' + tr_('bis') + ' ' + new Date(m.bis).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');
            } else {
                s.className = 'meldung-status';
                s.textContent = tr_('Keine Meldung aktiv.');
            }
        } catch (e) { /* naechstes Mal */ }
    }

    window.meldungEinblenden = async function () {
        var text = (el('meldung-text').value || '').trim();
        if (!text) { meldungRueck(tr_('Bitte einen Text eingeben.'), true); el('meldung-text').focus(); return; }
        var dauer = el('meldung-dauer').value;
        var body = {
            text: text, untertext: (el('meldung-untertext').value || '').trim(),
            farbe: el('meldung-farbe').value, textfarbe: el('meldung-textfarbe').value,
            ton: el('meldung-ton').checked, dauer_s: dauer ? Number(dauer) : null
        };
        try {
            var r = await fetch('/api/meldung', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            var d = await r.json();
            if (!r.ok) { meldungRueck(d.error || 'Fehler', true); return; }
            meldungRueck('✓ ' + tr_('Eingeblendet auf') + ' ' + d.empfaenger + ' ' + tr_('Anzeige(n)'), false);
            meldungStatus();
        } catch (e) { meldungRueck(tr_('Station nicht erreichbar'), true); }
    };
    window.meldungBeenden = async function () {
        try {
            var r = await fetch('/api/meldung', { method: 'DELETE' });
            if (r.ok) { meldungRueck('✓ ' + tr_('Beendet'), false); meldungStatus(); }
        } catch (e) { meldungRueck(tr_('Station nicht erreichbar'), true); }
    };

    /* ---- Start ---- */

    document.addEventListener('DOMContentLoaded', function () {
        if (!el('prog-kalender')) return;
        lade();
        meldungStatus();
        setInterval(meldungStatus, 5000);
        // Die Jetzt-Linie wandert, die Layouts koennen sich aendern.
        setInterval(function () { if (el('prog-form').hidden) zeichne(); }, 60000);
        el('prog-zone').addEventListener('change', function (e) { zone = e.target.value; zeichne(); });
        ['meldung-text', 'meldung-untertext', 'meldung-farbe', 'meldung-textfarbe'].forEach(function (id) {
            el(id).addEventListener('input', meldungVorschau);
        });
        // Jemand anderes hat geschrieben (Manager, zweites Handy): neu holen.
        if (window.EventSource) {
            var q = new EventSource('/api/events');
            q.addEventListener('config', function () { if (el('prog-form').hidden) lade(); meldungStatus(); });
        }
    });
})();

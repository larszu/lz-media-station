/* Layout-Editor (Karte „Layouts", seit 3.0).

   WAS ER TUT. Ein Layout teilt den Schirm in Regionen; hier werden sie
   gezeichnet: auf einer Leinwand im Seitenverhaeltnis des Schirms ziehen,
   verschieben und an den Ecken skalieren — mit der Maus wie mit dem Finger
   (Pointer Events, `touch-action: none`). Jede Region hat ein Panel:
   Name, Inhalt (Medien-Playlist oder Widget), Ton, Uebergang, Schalter.
   Die Playlist wird aus der Medienbibliothek zusammengeklickt oder gezogen,
   je Eintrag Standzeit und Gueltigkeit.

   WIE ER SPEICHERT. Der Editor arbeitet auf einer KOPIE (`entwurf`) und
   schreibt sie erst mit „Layout speichern" als Ganzes per
   `PUT /api/layouts/<id>`. Lehnt der Kern ab (400), steht der Grund mit
   Feldnamen unter dem Knopf — dieselbe Politik wie ueberall: ablehnen und
   sagen, was. Zwischendurch geht nichts an die Station; ein halb gezogenes
   Rechteck soll nicht auf dem Schirm im Foyer aufblitzen.

   VORSCHAU. Rechts unten laeuft `/display?vorschau=1&layout=<id>` — die
   Anzeigeseite selbst, nicht eine Nachbildung. Nach dem Speichern zeigt sie
   den neuen Stand; mit „Zeitpunkt simulieren" den Dienstag 18:00, wenn die
   Gueltigkeit eines Eintrags geprueft werden soll.

   Rueckgrat aus app.js: el(), esc(), escAttr(), tr(), config, allMedia,
   layoutsStand, layoutVorlagen, ladeLayouts(); app.js meldet jede neue Liste
   als Ereignis `lz-layouts` am document. */
(function () {
    'use strict';

    var RASTER = 5;          // Prozent — Raster beim Ziehen
    var MIN = 5;             // Prozent — kleinste Kantenlaenge
    var ZONEN = ['near', 'mid', 'far'];
    var SYMBOL = { video: '🎬', image: '🖼', audio: '🎵', web: '🌐' };
    var ART_ZU_TYP = { videos: 'video', images: 'image', audio: 'audio' };

    var stand = { layouts: {}, zonen: {} };
    var vorlagen = [];
    var aktuell = null;      // Kennung des Layouts im Editor
    var entwurf = null;      // Arbeitskopie
    var gewaehlt = null;     // Kennung der gewaehlten Region
    var schmutzig = false;
    var format = 'quer';
    var tabArt = 'videos';
    var vorschauSrc = '';
    var zug = null;          // laufender Zieh-Vorgang auf der Leinwand
    var zugEintrag = null;   // laufender Zieh-Vorgang in der Playlist
    var wahlHtml = '';       // zuletzt in #le-wahl geschriebene Optionen

    /* ---- Anbindung an app.js ---- */

    document.addEventListener('lz-layouts', uebernimm);

    // Die Medienbibliothek meldet neue Dateien nicht als Ereignis; nach jedem
    // Neuzeichnen der Listen zeichnen wir unsere Auswahl ebenfalls neu.
    if (typeof window.renderMediaLists === 'function') {
        var altRender = window.renderMediaLists;
        window.renderMediaLists = function () {
            altRender.apply(this, arguments);
            renderMedien();
        };
    }

    function uebernimm() {
        // Waehrend eines Zugs oder einer Eingabe im Panel wird NICHTS
        // uebernommen — weder Zeichnung noch Zustand. `config`-Ereignisse
        // kommen bei jedem Schreibzugriff irgendeines Admins; stand/entwurf
        // unter einem laufenden Zug oder einem halb getippten Feld zu tauschen,
        // liesse die Eingabe ins neue Modell laufen (oder ins Leere). Der
        // Tausch wird nachgeholt, sobald Zug oder Eingabe enden.
        if (zugHaengt()) zugEnde();
        if (zug || eingabeLaeuft()) { nachholen = true; return; }
        stand = window.layoutsStand || stand;
        vorlagen = window.layoutVorlagen || vorlagen;
        var ids = Object.keys(stand.layouts || {});
        if (!ids.length) return;
        if (!aktuell || !stand.layouts[aktuell]) {
            aktuell = stand.zonen.near && stand.layouts[stand.zonen.near] ? stand.zonen.near : ids[0];
            schmutzig = false;
        }
        // Waehrend jemand hier arbeitet, wird sein Entwurf nicht ueberschrieben —
        // auch nicht, wenn ein zweites Handy dasselbe Layout aendert.
        if (!schmutzig) {
            entwurf = kopie(stand.layouts[aktuell]);
            if (gewaehlt && !region(gewaehlt)) gewaehlt = null;
        }
        renderAlles();
    }

    var nachholen = false;
    // Eingabe laeuft: ein Feld im Region-Panel oder die offene Layout-Auswahl
    // hat den Fokus.
    function eingabeLaeuft() {
        var a = document.activeElement;
        if (!a || a === document.body) return false;
        if (a.id === 'le-wahl') return true;
        var panel = el('le-region-panel');
        return !!(panel && panel.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
    }
    // Ein Zug, dessen Element nicht mehr im Dokument haengt, kann kein
    // pointerup mehr bekommen — er darf Aktualisierungen nicht ewig sperren.
    function zugHaengt() { return !!(zug && zug.el && !zug.el.isConnected); }

    // Nachholen, sobald der Fokus das Panel bzw. die Auswahl verlaesst. Der
    // Fokus wechselt erst NACH focusout — deshalb ein Takt spaeter pruefen.
    document.addEventListener('focusout', function (e) {
        var t = e.target;
        var panel = el('le-region-panel');
        if (!t || !(t.id === 'le-wahl' || (panel && panel.contains(t)))) return;
        setTimeout(function () { if (nachholen && !zug && !eingabeLaeuft()) { nachholen = false; uebernimm(); } }, 0);
    });
    // Rueckfall fuer Browser ohne Pointer-Capture: das Loslassen ausserhalb
    // der Region kommt nur am Dokument an.
    document.addEventListener('pointerup', function () { if (zug) zugEnde(); });
    document.addEventListener('pointercancel', function () { if (zug) zugEnde(); });

    function kopie(o) { return JSON.parse(JSON.stringify(o)); }
    function region(id) {
        if (!entwurf) return null;
        for (var i = 0; i < entwurf.regionen.length; i++) if (entwurf.regionen[i].id === id) return entwurf.regionen[i];
        return null;
    }
    function markiere() {
        schmutzig = true;
        var s = el('le-schmutzig');
        if (s) s.hidden = false;
    }
    function sauber() {
        schmutzig = false;
        var s = el('le-schmutzig');
        if (s) s.hidden = true;
    }
    function rueckmeldung(text, fehler) {
        var fb = el('layouts-feedback');
        if (!fb) return;
        fb.textContent = text;
        fb.className = 'feedback ' + (fehler ? 'error' : 'success');
        clearTimeout(rueckmeldung.t);
        rueckmeldung.t = setTimeout(function () { fb.textContent = ''; }, fehler ? 8000 : 4000);
    }
    function snap(v) { return Math.round(v / RASTER) * RASTER; }
    function klemme(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    // Lokales Datum, nicht UTC: der Kern filtert mit `datetime.now().date()`,
    // und um 00:30 in Berlin waere `toISOString()` noch beim Vortag.
    function heute() {
        var d = new Date();
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    /* ---- Zeichnen ---- */

    function renderAlles() {
        renderWahl();
        renderLeinwand();
        renderPanel();
        var hg = el('le-hintergrund');
        if (hg && entwurf) hg.value = entwurf.hintergrund || '#000000';
        vorschauNeu();
    }

    function nutzerVon(id) {
        var n = [];
        ZONEN.forEach(function (z) { if (stand.zonen[z] === id) n.push(tr((window.ZONEN_NAMEN || {})[z] || z)); });
        return n;
    }

    function renderWahl() {
        var sel = el('le-wahl');
        if (!sel) return;
        var ids = Object.keys(stand.layouts || {});
        var html = ids.map(function (id) {
            return '<option value="' + escAttr(id) + '"' + (id === aktuell ? ' selected' : '') + '>' +
                esc(stand.layouts[id].name) + ' (' + esc(id) + ')</option>';
        }).join('');
        // Verglichen wird mit dem zuletzt ERZEUGTEN String, nicht mit
        // sel.innerHTML — der Browser serialisiert `selected` anders, der
        // Vergleich ginge nie auf und die Liste wuerde bei jedem Ereignis neu
        // gebaut, auch unter der offenen Auswahl (wie fuelleLayoutWahl in app.js).
        if (document.activeElement !== sel && html !== wahlHtml) { wahlHtml = html; sel.innerHTML = html; }
        if (document.activeElement !== sel) sel.value = aktuell || '';
        var nutzer = nutzerVon(aktuell);
        var badge = el('le-zonen');
        if (badge) {
            badge.textContent = nutzer.length ? 'Zonen: ' + nutzer.join(', ') : '';
            badge.hidden = !nutzer.length;
        }
        var del = el('le-loeschen');
        if (del) {
            del.disabled = !!nutzer.length;
            del.title = nutzer.length ? 'Wird von einer Zone gespielt – erst dort ein anderes Layout wählen' : '';
        }
        var vs = el('layout-neu-vorlage');
        if (vs && !vs.options.length && vorlagen.length) {
            vs.innerHTML = vorlagen.map(function (v) {
                return '<option value="' + escAttr(v.id) + '" title="' + escAttr(v.beschreibung) + '">' +
                    esc((window.VORLAGEN_NAMEN || {})[v.id] || v.id) + '</option>';
            }).join('');
        }
    }

    function renderLeinwand() {
        var lw = el('le-leinwand');
        if (!lw || !entwurf) return;
        lw.style.background = entwurf.hintergrund || '#000000';
        lw.innerHTML = '';
        entwurf.regionen.slice().sort(function (a, b) { return (a.z || 0) - (b.z || 0); }).forEach(function (r) {
            var d = document.createElement('div');
            d.className = 'le-region' + (r.typ === 'widget' ? ' widget' : '') + (r.id === gewaehlt ? ' gewaehlt' : '');
            d.style.left = r.x + '%'; d.style.top = r.y + '%';
            d.style.width = r.w + '%'; d.style.height = r.h + '%';
            d.style.zIndex = String(10 + (r.z || 0));
            d.setAttribute('data-region', r.id);
            var info = r.typ === 'widget'
                ? ((r.widget && r.widget.typ) ? 'Widget: ' + widgetName(r.widget.typ) : 'Widget')
                : anzahlText(r.playlist.length);
            // Das Ton-Zeichen in einem eigenen Knoten: haengt es am Text,
            // passt „2 Einträge ♫" auf kein Uebersetzungsmuster mehr.
            d.innerHTML = '<span class="le-region-name">' + esc(r.name) + '</span>' +
                '<span class="le-region-info"><span>' + esc(info) + '</span>' + (r.ton ? '<span> ♫</span>' : '') + '</span>' +
                ['nw', 'ne', 'sw', 'se'].map(function (g) { return '<span class="le-griff ' + g + '" data-griff="' + g + '"></span>'; }).join('');
            d.addEventListener('pointerdown', zugStart);
            lw.appendChild(d);
        });
    }

    function anzahlText(n) { return n === 1 ? '1 Eintrag' : n + ' Einträge'; }

    // Anzeigename aus dem Widget-Katalog („Uhr" statt „uhr"); ohne Katalog
    // die Kennung.
    function widgetName(typ) {
        var kat = (window.LZ_WIDGETS && window.LZ_WIDGETS.katalog) ? window.LZ_WIDGETS.katalog() : [];
        for (var i = 0; i < kat.length; i++) if (kat[i].typ === typ) return kat[i].name;
        return typ;
    }

    /* ---- Ziehen und Skalieren (Maus und Finger gleich) ---- */

    function zugStart(e) {
        var d = e.currentTarget;
        var id = d.getAttribute('data-region');
        var r = region(id);
        if (!r) return;
        if (gewaehlt !== id) {
            // Nur die Klassen tauschen — die Leinwand darf unter dem Finger
            // nicht neu gezeichnet werden, sonst reisst der Zieh-Vorgang ab.
            gewaehlt = id;
            el('le-leinwand').querySelectorAll('.le-region.gewaehlt').forEach(function (n) { n.classList.remove('gewaehlt'); });
            d.classList.add('gewaehlt');
            renderPanel();
        }
        var griff = e.target.getAttribute && e.target.getAttribute('data-griff');
        var rect = el('le-leinwand').getBoundingClientRect();
        zug = {
            id: id, el: d, modus: griff || 'move', rect: rect,
            px: e.clientX, py: e.clientY, x: r.x, y: r.y, w: r.w, h: r.h, bewegt: false,
        };
        try { d.setPointerCapture(e.pointerId); } catch (err) { /* alter Browser */ }
        d.addEventListener('pointermove', zugBewegung);
        d.addEventListener('pointerup', zugEnde);
        d.addEventListener('pointercancel', zugEnde);
        d.addEventListener('lostpointercapture', zugEnde);
        e.preventDefault();
    }

    function zugBewegung(e) {
        if (!zug) return;
        var r = region(zug.id);
        if (!r) return;
        var dx = (e.clientX - zug.px) / zug.rect.width * 100;
        var dy = (e.clientY - zug.py) / zug.rect.height * 100;
        if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && !zug.bewegt) return;
        zug.bewegt = true;
        var g = geometrie(zug, dx, dy);
        r.x = g.x; r.y = g.y; r.w = g.w; r.h = g.h;
        zug.el.style.left = r.x + '%'; zug.el.style.top = r.y + '%';
        zug.el.style.width = r.w + '%'; zug.el.style.height = r.h + '%';
        fuelleGeo(r);
    }

    // Die neue Geometrie aus Startlage und Verschiebung — im Raster, in der
    // Leinwand, nie kleiner als MIN. Beim Skalieren an einer Ecke bleibt die
    // gegenueberliegende Ecke stehen.
    function geometrie(z, dx, dy) {
        var x = z.x, y = z.y, w = z.w, h = z.h;
        if (z.modus === 'move') {
            x = klemme(snap(z.x + dx), 0, 100 - w);
            y = klemme(snap(z.y + dy), 0, 100 - h);
            return { x: x, y: y, w: w, h: h };
        }
        var rechts = z.x + z.w, unten = z.y + z.h;
        if (z.modus.indexOf('e') >= 0) w = klemme(snap(z.w + dx), MIN, 100 - z.x);
        if (z.modus.indexOf('s') >= 0) h = klemme(snap(z.h + dy), MIN, 100 - z.y);
        if (z.modus.indexOf('w') >= 0) { x = klemme(snap(z.x + dx), 0, rechts - MIN); w = rechts - x; }
        if (z.modus.indexOf('n') >= 0) { y = klemme(snap(z.y + dy), 0, unten - MIN); h = unten - y; }
        return { x: x, y: y, w: w, h: h };
    }

    function zugEnde() {
        if (!zug) return;
        var d = zug.el;
        d.removeEventListener('pointermove', zugBewegung);
        d.removeEventListener('pointerup', zugEnde);
        d.removeEventListener('pointercancel', zugEnde);
        d.removeEventListener('lostpointercapture', zugEnde);
        if (zug.bewegt) markiere();
        zug = null;
        if (nachholen) { nachholen = false; uebernimm(); return; }
        renderLeinwand();
    }

    /* ---- Panel der gewaehlten Region ---- */

    function renderPanel() {
        var leer = el('le-region-leer'), panel = el('le-region-panel');
        if (!leer || !panel) return;
        var r = region(gewaehlt);
        leer.hidden = !!r;
        panel.hidden = !r;
        if (!r) return;
        el('le-region-titel').textContent = r.name;
        el('le-r-name').value = r.name;
        el('le-r-typ').value = r.typ;
        el('le-r-uebergang').value = r.uebergang || 'blende';
        el('le-r-ton').checked = !!r.ton;
        el('le-r-shuffle').checked = !!r.shuffle;
        el('le-r-einmal').checked = !!r.einmal;
        fuelleGeo(r);
        var medien = r.typ === 'medien';
        panel.querySelectorAll('.le-nur-medien').forEach(function (n) { n.hidden = !medien; });
        panel.querySelectorAll('.le-nur-widget').forEach(function (n) { n.hidden = medien; });
        if (medien) { renderPlaylist(); renderMedien(); renderTabs(); }
        else renderWidget(r);
    }

    function fuelleGeo(r) {
        ['x', 'y', 'w', 'h'].forEach(function (k) {
            var f = el('le-r-' + k);
            if (f && document.activeElement !== f) f.value = Math.round(r[k]);
        });
    }

    function renderTabs() {
        document.querySelectorAll('[data-le-tab]').forEach(function (b) {
            b.classList.toggle('active', b.getAttribute('data-le-tab') === tabArt);
        });
        var web = el('le-web'), med = el('le-medien');
        if (web) web.hidden = tabArt !== 'web';
        if (med) med.hidden = tabArt === 'web';
    }

    function eintragName(item) {
        return item.typ === 'web' ? item.url : item.name;
    }

    function renderPlaylist() {
        var box = el('le-playlist');
        var r = region(gewaehlt);
        if (!box || !r) return;
        if (!r.playlist.length) {
            box.innerHTML = '<div class="zone-empty">Noch keine Einträge — unten aus der Bibliothek hinzufügen.</div>';
            return;
        }
        var h = heute();
        box.innerHTML = r.playlist.map(function (item, i, liste) {
            var stand = item.typ === 'image' || item.typ === 'web';
            var abgelaufen = item.bis && item.bis < h;
            var hoch = i > 0 ? '<button type="button" class="ord-btn" onclick="LZ_EDITOR.verschiebe(' + i + ',-1)" title="nach oben">▲</button>' : '<span class="ord-btn leer"></span>';
            var runter = i < liste.length - 1 ? '<button type="button" class="ord-btn" onclick="LZ_EDITOR.verschiebe(' + i + ',1)" title="nach unten">▼</button>' : '<span class="ord-btn leer"></span>';
            return '<div class="le-eintrag ziehbar' + (abgelaufen ? ' ungueltig' : '') + '" draggable="true" data-i="' + i + '">' +
                '<span class="le-eintrag-griff" title="Ziehen zum Umsortieren">☰</span>' +
                '<span class="le-eintrag-name" title="' + escAttr(eintragName(item)) + '">' + SYMBOL[item.typ] + ' ' + esc(eintragName(item)) + '</span>' +
                '<span class="le-eintrag-felder">' +
                    (stand ? '<input type="number" class="bildzeit" min="1" max="86400" step="1" placeholder="Std." value="' + (item.dauer_s ? escAttr(String(item.dauer_s)) : '') + '"' +
                        ' title="Standzeit in Sekunden (leer = allgemeiner Bildwechsel)" onchange="LZ_EDITOR.eintrag(' + i + ',\'dauer_s\',this.value)">' : '') +
                    '<input type="date" value="' + escAttr(item.von || '') + '" title="gültig von" onchange="LZ_EDITOR.eintrag(' + i + ',\'von\',this.value)">' +
                    '<input type="date" value="' + escAttr(item.bis || '') + '" title="gültig bis" onchange="LZ_EDITOR.eintrag(' + i + ',\'bis\',this.value)">' +
                    hoch + runter +
                    '<button type="button" class="del-btn" onclick="LZ_EDITOR.entferne(' + i + ')" title="Aus der Playlist entfernen">✕</button>' +
                '</span></div>';
        }).join('');
        box.querySelectorAll('.le-eintrag').forEach(function (z) {
            z.addEventListener('dragstart', function (e) {
                zugEintrag = { von: Number(z.getAttribute('data-i')) };
                e.dataTransfer.effectAllowed = 'move';
                try { e.dataTransfer.setData('text/plain', 'eintrag'); } catch (err) { /* IE */ }
            });
            // Ein ausserhalb losgelassener Zug hinterlaesst sonst einen Rest,
            // den der naechste Ablage-Vorgang als Umsortierung missversteht.
            z.addEventListener('dragend', function () { zugEintrag = null; });
            z.addEventListener('dragover', function (e) { e.preventDefault(); z.classList.add('ziel'); });
            z.addEventListener('dragleave', function () { z.classList.remove('ziel'); });
            z.addEventListener('drop', function (e) {
                e.preventDefault(); z.classList.remove('ziel');
                var nach = Number(z.getAttribute('data-i'));
                // Was abgelegt wird, sagt der Transfer selbst — nicht ein Merker.
                var datei = e.dataTransfer.getData('lz-datei');
                if (datei) { var t = datei.split('|'); fuegeHinzu(t[0], t[1], nach); zugEintrag = null; return; }
                if (zugEintrag) { bewegeEintrag(zugEintrag.von, nach); zugEintrag = null; }
            });
        });
    }

    // Die Playlist als Ganzes ist Ablageflaeche fuer Dateien aus der
    // Bibliothek — einmal gebunden, nicht bei jedem Neuzeichnen.
    (function () {
        var box = el('le-playlist');
        if (!box) return;
        box.addEventListener('dragover', function (e) { e.preventDefault(); });
        box.addEventListener('drop', function (e) {
            e.preventDefault();
            var datei = e.dataTransfer.getData('lz-datei');
            if (datei && !e.target.closest('.le-eintrag')) { var t = datei.split('|'); fuegeHinzu(t[0], t[1]); }
            zugEintrag = null;
        });
    })();

    function renderMedien() {
        var box = el('le-medien');
        var r = region(gewaehlt);
        if (!box || !r || tabArt === 'web') return;
        var dateien = (window.allMedia || {})[tabArt] || [];
        if (!dateien.length) { box.innerHTML = '<div class="empty">Keine Dateien</div>'; return; }
        var typ = ART_ZU_TYP[tabArt];
        var drin = {};
        r.playlist.forEach(function (it) { if (it.typ === typ) drin[it.name] = (drin[it.name] || 0) + 1; });
        box.innerHTML = dateien.map(function (f) {
            return '<div class="media-item" draggable="true" data-typ="' + typ + '" data-name="' + escAttr(f.name) + '" title="Klick fügt hinzu">' +
                '<div class="media-info"><span class="media-name">' + SYMBOL[typ] + ' ' + esc(f.name) + '</span>' +
                '<span class="media-size">' + esc(String(f.size_mb)) + ' MB</span></div>' +
                '<div class="media-actions">' + (drin[f.name] ? '<span class="badge">' + drin[f.name] + '×</span>' : '') +
                '<button type="button" class="zone-btn" onclick="LZ_EDITOR.fuegeHinzu(\'' + typ + '\',\'' + escAttr(f.name) + '\')">+ Hinzufügen</button></div></div>';
        }).join('');
        box.querySelectorAll('.media-item').forEach(function (z) {
            z.addEventListener('click', function (e) {
                if (e.target.closest('button')) return;
                fuegeHinzu(z.getAttribute('data-typ'), z.getAttribute('data-name'));
            });
            z.addEventListener('dragstart', function (e) {
                zugEintrag = null;
                e.dataTransfer.setData('lz-datei', z.getAttribute('data-typ') + '|' + z.getAttribute('data-name'));
                e.dataTransfer.effectAllowed = 'copy';
            });
        });
    }

    /* ---- Widget-Region ---- */

    function katalog() {
        try {
            if (window.LZ_WIDGETS && typeof window.LZ_WIDGETS.katalog === 'function') {
                var k = window.LZ_WIDGETS.katalog();
                if (Array.isArray(k)) return k;
            }
        } catch (e) { /* Katalog kaputt — dann das freie Formular */ }
        return null;
    }

    function renderWidget(r) {
        var kat = katalog();
        var sel = el('le-widget-typ'), frei = el('le-widget-typ-frei');
        var felder = el('le-widget-felder'), jsonBlock = el('le-widget-json-block');
        r.widget = r.widget || {};
        if (kat && kat.length) {
            sel.hidden = false; frei.hidden = true;
            var opts = ['<option value="">– bitte wählen –</option>'].concat(kat.map(function (w) {
                return '<option value="' + escAttr(w.typ) + '"' + (w.typ === r.widget.typ ? ' selected' : '') + '>' + esc(w.name || w.typ) + '</option>';
            }));
            sel.innerHTML = opts.join('');
            sel.value = r.widget.typ || '';
            var def = null;
            kat.forEach(function (w) { if (w.typ === r.widget.typ) def = w; });
            if (def) {
                jsonBlock.hidden = true;
                felder.innerHTML = (def.felder || []).map(function (f) { return widgetFeld(f, r.widget[f.key]); }).join('');
            } else {
                felder.innerHTML = '';
                jsonBlock.hidden = !r.widget.typ;
                el('le-widget-json').value = JSON.stringify(ohneTyp(r.widget), null, 2);
            }
        } else {
            // Kein Katalog (Widgets noch nicht installiert): Typ frei, Rest als JSON.
            sel.hidden = true; frei.hidden = false;
            frei.value = r.widget.typ || '';
            felder.innerHTML = '';
            jsonBlock.hidden = false;
            el('le-widget-json').value = JSON.stringify(ohneTyp(r.widget), null, 2);
        }
    }

    function ohneTyp(w) {
        var o = {};
        Object.keys(w).forEach(function (k) { if (k !== 'typ') o[k] = w[k]; });
        return o;
    }

    function widgetFeld(f, wert) {
        var id = 'le-wf-' + f.key;
        var v = (wert === undefined || wert === null) ? (f.default === undefined ? '' : f.default) : wert;
        var on = ' onchange="LZ_EDITOR.widgetWert(\'' + escAttr(f.key) + '\',\'' + escAttr(f.typ || 'text') + '\',this)"';
        var eingabe;
        switch (f.typ) {
            case 'zahl': eingabe = '<input type="number" id="' + id + '" step="any" value="' + escAttr(String(v)) + '"' + on + '>'; break;
            case 'farbe': eingabe = '<input type="color" id="' + id + '" value="' + escAttr(String(v || '#ffffff')) + '"' + on + '>'; break;
            case 'bool': return '<div class="form-group span-2"><label class="checkbox-label"><input type="checkbox" id="' + id + '"' + (v ? ' checked' : '') + on + '><span>' + esc(f.label || f.key) + '</span></label></div>';
            case 'url': eingabe = '<input type="url" id="' + id + '" value="' + escAttr(String(v)) + '"' + on + '>'; break;
            case 'textarea': eingabe = '<textarea id="' + id + '" rows="3"' + on + '>' + esc(String(v)) + '</textarea>'; break;
            case 'auswahl':
                eingabe = '<select id="' + id + '"' + on + '>' + (f.optionen || []).map(function (o) {
                    var w = (o && typeof o === 'object') ? o.wert : o;
                    var l = (o && typeof o === 'object') ? (o.label || o.wert) : o;
                    return '<option value="' + escAttr(String(w)) + '"' + (String(w) === String(v) ? ' selected' : '') + '>' + esc(String(l)) + '</option>';
                }).join('') + '</select>';
                break;
            default: eingabe = '<input type="text" id="' + id + '" value="' + escAttr(String(v)) + '"' + on + '>';
        }
        var breit = f.typ === 'textarea' || f.typ === 'url' ? ' span-2' : '';
        return '<div class="form-group' + breit + '"><label for="' + id + '">' + esc(f.label || f.key) + '</label>' + eingabe + '</div>';
    }

    /* ---- Oeffentliche Aktionen (aus dem Template) ---- */

    var API = {};

    API.waehleLayout = function (id) {
        if (id === aktuell) return;
        if (schmutzig && !confirm(tr('Nicht gespeicherte Änderungen verwerfen?'))) {
            el('le-wahl').value = aktuell;
            return;
        }
        aktuell = id;
        gewaehlt = null;
        sauber();
        entwurf = kopie(stand.layouts[aktuell]);
        renderAlles();
    };

    API.neuAnzeigen = function (zeigen) {
        var box = el('le-neu');
        if (!box) return;
        box.hidden = zeigen === false ? true : !box.hidden;
        if (!box.hidden) el('layout-neu-name').focus();
    };

    API.anlegen = async function () {
        var name = (el('layout-neu-name').value || '').trim();
        if (!name) { rueckmeldung('Bitte einen Namen eingeben.', true); return; }
        try {
            var r = await fetch('/api/layouts', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, vorlage: el('layout-neu-vorlage').value || 'vollbild' }),
            });
            var d = await r.json();
            if (!r.ok) throw new Error(d.error || 'Fehler');
            el('layout-neu-name').value = '';
            API.neuAnzeigen(false);
            aktuell = d.id; gewaehlt = null; sauber();
            rueckmeldung('✓ Angelegt');
            ladeLayouts();
        } catch (e) { rueckmeldung('✗ ' + e.message, true); }
    };

    API.umbenennen = function () {
        if (!entwurf) return;
        var box = el('le-umbenennen');
        if (!box) return;
        box.hidden = !box.hidden;
        if (!box.hidden) { el('le-name-neu').value = entwurf.name; el('le-name-neu').focus(); }
    };

    API.nameUebernehmen = function () {
        var neu = (el('le-name-neu').value || '').trim();
        if (!neu) { rueckmeldung('Bitte einen Namen eingeben.', true); return; }
        entwurf.name = neu.slice(0, 64);
        el('le-umbenennen').hidden = true;
        markiere();
        // Der neue Name steht erst nach „Layout speichern" auf der Station.
        var opt = el('le-wahl').querySelector('option[value="' + aktuell.replace(/"/g, '\\"') + '"]');
        if (opt) opt.textContent = entwurf.name + ' (' + aktuell + ')';
    };

    API.duplizieren = async function () {
        if (!aktuell) return;
        try {
            var r = await fetch('/api/layouts/' + encodeURIComponent(aktuell) + '/duplizieren', { method: 'POST' });
            var d = await r.json();
            if (!r.ok) throw new Error(d.error || 'Fehler');
            aktuell = d.id; gewaehlt = null; sauber();
            rueckmeldung('✓ Kopiert');
            ladeLayouts();
        } catch (e) { rueckmeldung('✗ ' + e.message, true); }
    };

    API.loeschen = async function () {
        if (!aktuell || !entwurf) return;
        if (!confirm(tr('Layout "' + entwurf.name + '" löschen? Die Medien bleiben erhalten.'))) return;
        try {
            var r = await fetch('/api/layouts/' + encodeURIComponent(aktuell), { method: 'DELETE' });
            var d = await r.json();
            // 409: eine Zone spielt es noch — der Kern sagt, welche.
            if (!r.ok) throw new Error(d.error || 'Fehler');
            aktuell = null; gewaehlt = null; sauber();
            rueckmeldung('✓ Gelöscht');
            ladeLayouts();
        } catch (e) { rueckmeldung('✗ ' + e.message, true); }
    };

    API.setzeFormat = function (f) {
        format = f === 'hoch' ? 'hoch' : 'quer';
        ['le-leinwand', 'le-vorschau-rahmen'].forEach(function (id) {
            var n = el(id);
            if (n) { n.classList.toggle('hoch', format === 'hoch'); n.classList.toggle('quer', format === 'quer'); }
        });
        el('le-format-quer').classList.toggle('active', format === 'quer');
        el('le-format-hoch').classList.toggle('active', format === 'hoch');
    };

    API.setzeHintergrund = function (v) {
        if (!entwurf || !/^#[0-9a-fA-F]{6}$/.test(v)) return;
        entwurf.hintergrund = v.toLowerCase();
        el('le-leinwand').style.background = v;
        markiere();
    };

    API.regionHinzu = function () {
        if (!entwurf) return;
        if (entwurf.regionen.length >= 12) { rueckmeldung('Höchstens 12 Regionen je Layout.', true); return; }
        var n = 1, id;
        do { id = 'region-' + n; n++; } while (region(id));
        var hatTon = entwurf.regionen.some(function (r) { return r.typ === 'medien' && r.ton; });
        var z = entwurf.regionen.reduce(function (m, r) { return Math.max(m, r.z || 0); }, -1) + 1;
        entwurf.regionen.push({
            id: id, name: 'Region ' + (n - 1), x: 25, y: 25, w: 50, h: 50, z: z,
            typ: 'medien', ton: !hatTon, playlist: [], shuffle: false, einmal: false, uebergang: 'blende', widget: {},
        });
        gewaehlt = id;
        markiere();
        renderLeinwand(); renderPanel();
    };

    API.regionEntfernen = function () {
        var r = region(gewaehlt);
        if (!r) return;
        entwurf.regionen = entwurf.regionen.filter(function (x) { return x.id !== gewaehlt; });
        gewaehlt = null;
        markiere();
        renderLeinwand(); renderPanel();
    };

    API.ebene = function (delta) {
        var r = region(gewaehlt);
        if (!r) return;
        r.z = (r.z || 0) + delta;
        markiere();
        renderLeinwand();
    };

    API.feld = function (name, wert) {
        var r = region(gewaehlt);
        if (!r) return;
        if (name === 'name') {
            wert = String(wert || '').trim().slice(0, 64);
            if (!wert) { el('le-r-name').value = r.name; return; }
        }
        r[name] = wert;
        markiere();
        if (name === 'typ' || name === 'name') { renderLeinwand(); renderPanel(); }
        else if (name === 'ton') renderLeinwand();
    };

    API.geo = function (k, wert) {
        var r = region(gewaehlt);
        if (!r) return;
        var v = Number(wert);
        if (!isFinite(v)) { fuelleGeo(r); return; }
        if (k === 'x') r.x = klemme(v, 0, 100 - MIN);
        if (k === 'y') r.y = klemme(v, 0, 100 - MIN);
        if (k === 'w') r.w = klemme(v, MIN, 100);
        if (k === 'h') r.h = klemme(v, MIN, 100);
        // Ragt die Region jetzt hinaus, wird sie eingekuerzt — der Kern
        // lehnte es sonst ab, und der Nutzer saehe erst beim Speichern, warum.
        if (r.x + r.w > 100) { if (k === 'x') r.w = 100 - r.x; else r.x = 100 - r.w; }
        if (r.y + r.h > 100) { if (k === 'y') r.h = 100 - r.y; else r.y = 100 - r.h; }
        markiere();
        renderLeinwand(); fuelleGeo(r);
    };

    API.tab = function (art) {
        tabArt = art;
        renderTabs(); renderMedien();
    };

    API.fuegeHinzu = fuegeHinzu;
    function fuegeHinzu(typ, name, an) {
        var r = region(gewaehlt);
        if (!r || !name) return;
        var item = { typ: typ, name: name, dauer_s: null, von: null, bis: null };
        if (an === undefined || an === null || an >= r.playlist.length) r.playlist.push(item);
        else r.playlist.splice(an, 0, item);
        markiere();
        renderPlaylist(); renderMedien(); renderLeinwand();
    }

    API.webHinzu = function () {
        var r = region(gewaehlt);
        var feld = el('le-web-url');
        if (!r || !feld) return;
        var url = (feld.value || '').trim();
        if (!/^https?:\/\//i.test(url)) { rueckmeldung('Adresse muss mit http:// oder https:// beginnen.', true); return; }
        r.playlist.push({ typ: 'web', url: url, dauer_s: null, von: null, bis: null });
        feld.value = '';
        markiere();
        renderPlaylist(); renderLeinwand();
    };

    API.eintrag = function (i, k, wert) {
        var r = region(gewaehlt);
        if (!r || !r.playlist[i]) return;
        var item = r.playlist[i];
        if (k === 'dauer_s') {
            var v = Number(wert);
            item.dauer_s = (wert === '' || !isFinite(v) || v <= 0) ? null : v;
        } else {
            item[k] = wert || null;
            if (item.von && item.bis && item.von > item.bis) {
                rueckmeldung('Das Ende liegt vor dem Anfang — bitte prüfen.', true);
            }
        }
        markiere();
        renderPlaylist();
    };

    API.verschiebe = function (i, richtung) { bewegeEintrag(i, i + richtung); };
    function bewegeEintrag(von, nach) {
        var r = region(gewaehlt);
        if (!r || von === nach || von < 0 || nach < 0 || von >= r.playlist.length || nach >= r.playlist.length) return;
        var it = r.playlist.splice(von, 1)[0];
        r.playlist.splice(nach, 0, it);
        markiere();
        renderPlaylist();
    }

    API.entferne = function (i) {
        var r = region(gewaehlt);
        if (!r) return;
        r.playlist.splice(i, 1);
        markiere();
        renderPlaylist(); renderMedien(); renderLeinwand();
    };

    API.widgetTyp = function (typ) {
        var r = region(gewaehlt);
        if (!r) return;
        typ = String(typ || '').trim();
        var alt = r.widget || {};
        r.widget = typ ? { typ: typ } : {};
        var kat = katalog() || [];
        var def = null;
        kat.forEach(function (w) { if (w.typ === typ) def = w; });
        if (def) {
            // Vorgaben aus dem Katalog, damit ein neues Widget sofort etwas zeigt.
            (def.felder || []).forEach(function (f) {
                if (f.default !== undefined) r.widget[f.key] = f.default;
                if (alt.typ === typ && alt[f.key] !== undefined) r.widget[f.key] = alt[f.key];
            });
        } else if (typ) {
            // Ohne Katalogeintrag (Widgets nicht installiert, fremder Typ) sind
            // die Einstellungen aus dem JSON-Feld das Einzige, was der Nutzer
            // hat — sie bleiben; nur der Typ wechselt.
            Object.keys(alt).forEach(function (k) { if (k !== 'typ') r.widget[k] = alt[k]; });
        }
        markiere();
        renderWidget(r); renderLeinwand();
    };

    API.widgetWert = function (key, typ, feld) {
        var r = region(gewaehlt);
        if (!r) return;
        r.widget = r.widget || {};
        if (typ === 'bool') r.widget[key] = !!feld.checked;
        else if (typ === 'zahl') { var v = Number(feld.value); r.widget[key] = isFinite(v) && feld.value !== '' ? v : null; }
        else r.widget[key] = feld.value;
        markiere();
    };

    API.widgetJson = function (text) {
        var r = region(gewaehlt);
        if (!r) return;
        try {
            var o = text.trim() ? JSON.parse(text) : {};
            if (!o || typeof o !== 'object' || Array.isArray(o)) throw new Error('Objekt erwartet');
            var typ = (r.widget && r.widget.typ) || '';
            r.widget = o;
            if (typ) r.widget.typ = typ;
            markiere();
        } catch (e) {
            rueckmeldung('Einstellungen sind kein gültiges JSON: ' + e.message, true);
        }
    };

    API.speichern = async function () {
        if (!aktuell || !entwurf) return;
        var knopf = el('le-speichern');
        knopf.disabled = true;
        try {
            var r = await fetch('/api/layouts/' + encodeURIComponent(aktuell), {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(entwurf),
            });
            var d = await r.json();
            if (!r.ok) throw new Error(d.error || 'Fehler');
            sauber();
            rueckmeldung('✓ Gespeichert');
            ladeLayouts();
            vorschauNeu(true);
        } catch (e) { rueckmeldung('✗ ' + e.message, true); }
        knopf.disabled = false;
    };

    /* ---- Vorschau ---- */

    API.vorschauNeu = vorschauNeu;
    function vorschauNeu(erzwingen) {
        var frame = el('le-vorschau'), zoneSel = el('le-vorschau-zone'), zeit = el('le-zeit'), voll = el('le-vollbild');
        if (!frame || !aktuell) return;
        // Die Mitte gibt es nur mit drei Stufen.
        var drei = Number((window.config || {}).zonen_stufen) === 3;
        var mid = zoneSel.querySelector('option[value="mid"]');
        if (mid) mid.hidden = !drei;
        if (!zoneSel.value || (zoneSel.value === 'mid' && !drei)) {
            var spielt = ZONEN.filter(function (z) { return stand.zonen[z] === aktuell && (z !== 'mid' || drei); });
            zoneSel.value = spielt[0] || 'near';
        }
        var q = '/display?vorschau=1&layout=' + encodeURIComponent(aktuell) + '&zone=' + encodeURIComponent(zoneSel.value);
        if (zeit.value) q += '&zeit=' + encodeURIComponent(zeit.value);
        if (voll) voll.href = q;
        if (q !== vorschauSrc || erzwingen) {
            vorschauSrc = q;
            frame.src = q + (erzwingen ? '&_=' + Date.now() : '');
        }
    }

    API.zeitJetzt = function () {
        el('le-zeit').value = '';
        vorschauNeu();
    };

    /* ---- „Was laeuft gerade" in der Status-Karte ---- */

    API.zeigeLaeuftGerade = function () {
        var box = el('laeuft-gerade');
        if (!box) return;
        if (!box.hidden) { box.innerHTML = ''; box.hidden = true; return; }
        // `zuschauen=1`: dieselbe Seite wie auf dem Schirm, aber stumm und
        // ohne den Auto-Start, der die Steuerung anwerfen wuerde.
        box.innerHTML = '<div class="le-vorschau quer"><iframe title="Was gerade auf dem Schirm läuft" src="/display?zuschauen=1"></iframe></div>';
        box.hidden = false;
    };

    window.LZ_EDITOR = API;
})();

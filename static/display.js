/* Die Anzeige: spielt das Layout der aktiven Zone.

   SEIT 3.0 IN REGIONEN. Ein Layout teilt den Schirm in Rechtecke (Prozent);
   jede Medien-Region spielt ihre eigene, gemischte Playlist (Video, Bild,
   Webseite, Audio) mit Blende, eine Widget-Region ueberlaesst die Flaeche
   `window.LZ_WIDGETS` (Welle 2). Der Ton der Zone laeuft parallel dazu.

   EREIGNISSE STATT POLLING. Die Seite hoert `/api/events` (SSE) und wendet
   eine neue Szene sofort an; `/api/scene` wird nur noch alle 5 s als
   Rueckfall gefragt. Faellt die Verbindung aus, spielt die letzte Szene
   weiter — und unten steht dezent, dass die Station nicht antwortet.

   KEINE UMLEITUNG ZUM ADMIN. Bis 3.0 sprang die Seite bei einer leeren Zone
   oder einem nicht ladbaren Video nach `/admin`. Ein Schirm im Foyer zeigte
   dann die Verwaltungsoberflaeche, bis jemand vorbeikam. Jetzt bleibt er
   schwarz und sagt in einer Zeile, was fehlt. ESC fuehrt weiterhin zum Admin.

   VORSCHAU. `/display?vorschau=1&layout=<id>[&zone=near][&zeit=JJJJ-MM-TTTHH:MM]`
   zeigt ein Layout ohne Sensor, ohne Auto-Start und ohne Zonenwechsel —
   dieselbe Seite, die auch auf dem Schirm laeuft. `zeit` reicht die Seite
   an Widgets weiter (ctx.zeit), und der Kern filtert damit die Eintraege. */
(function () {
    'use strict';

    var buehne = document.getElementById('buehne');
    var audioEl = document.getElementById('audio-player');
    var hintEl = document.getElementById('hint');
    var dezentEl = document.getElementById('dezent');

    var params = new URLSearchParams(location.search);
    var vorschau = params.get('vorschau') === '1';
    var vorschauLayout = params.get('layout') || '';
    var vorschauZone = params.get('zone') || '';
    var vorschauZeit = params.get('zeit') || '';

    var currentHash = '';
    // Kennung der laufenden Regionen (der Name stammt aus der Zeit, in der
    // es nur EINE Videoliste gab; er bleibt, weil Tests ihn kennen). Die
    // Regionen werden NUR neu aufgesetzt, wenn sich diese Kennung aendert —
    // sonst spraenge jede Szene, die der Kern erneut schickt, auf Anfang.
    var currentVideoSet = '';
    var currentAudioSet = '';
    var currentAudioFile = null;
    var zoneAudioList = [];
    var audioIndex = 0;
    // Wiedergabe-Optionen der Hauptregion — sie gelten fuer den Ton der Zone.
    var zoneEinmal = false;
    var zoneShuffle = false;
    var imageInterval = 5;
    var regionen = {};          // id -> Zustand einer Region
    var regionReihe = [];
    var lautstaerke = { video: 1, audio: 1 };
    var stationsname = '';
    // Untertitel: die Sprachliste und die Zuordnung aus `/api/scene`, dazu die
    // gerade gewaehlte Sprache.
    var sprachen = [];
    var untertitel = {};
    var aktiveSprache = null;
    var sprachwahlStand = '';

    var startAttempted = false;
    var resumeEnabled = false;
    var videoPositions = {}; // { filename: seconds }
    var letzterKontakt = Date.now();
    var expectedPlayable = false;
    var lastPlayableAt = Date.now();
    var leerSeit = null;
    // Ein per `/api/befehl` eingeblendetes Layout: {layout_id} oder null.
    var ueberblendung = null;
    var ueberblendungTimer = null;

    // ESC -> zur Admin-Seite (bewusst der einzige Weg dorthin)
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.keyCode === 27) {
            window.location.href = '/admin';
        }
    });

    /* ---- Verbindung: Ereignisse zuerst, Polling als Rueckfall ---- */

    function verbinde() {
        if (!window.EventSource) return;
        var quelle = new EventSource('/api/events');
        quelle.addEventListener('scene', function (e) {
            letzterKontakt = Date.now();
            // In der Vorschau und waehrend einer Ueberblendung zaehlt nicht
            // die Zone, sondern das gewaehlte Layout — also neu holen.
            if (vorschau || ueberblendung) { hole(); return; }
            try { verarbeite(JSON.parse(e.data)); } catch (err) { /* naechste */ }
        });
        quelle.addEventListener('config', function () {
            letzterKontakt = Date.now();
            if (vorschau || ueberblendung) hole();
        });
        quelle.addEventListener('befehl', function (e) {
            try { befehl(JSON.parse(e.data)); } catch (err) { /* unlesbar */ }
        });
        // Bei einem Abriss verbindet der Browser von selbst neu.
    }

    function szenenAdresse() {
        var q = [];
        if (vorschau && vorschauLayout) {
            q.push('layout=' + encodeURIComponent(vorschauLayout));
            if (vorschauZone) q.push('zone=' + encodeURIComponent(vorschauZone));
            if (vorschauZeit) q.push('zeit=' + encodeURIComponent(vorschauZeit));
        } else if (ueberblendung) {
            q.push('layout=' + encodeURIComponent(ueberblendung.layout_id));
        }
        return '/api/scene' + (q.length ? '?' + q.join('&') : '');
    }

    async function hole() {
        try {
            var resp = await fetch(szenenAdresse());
            if (resp.ok) {
                var scene = await resp.json();
                letzterKontakt = Date.now();
                verarbeite(scene);
            } else if (ueberblendung && resp.status === 404) {
                // Das eingeblendete Layout gibt es nicht mehr — zurueck.
                ueberblendung = null;
            }
        } catch (e) { /* Station nicht erreichbar: letzte Szene laeuft weiter */ }
        waechter();
    }

    setInterval(hole, 5000);
    hole();
    verbinde();

    /* ---- Befehle von /api/befehl ---- */

    function befehl(b) {
        if (!b || !b.typ) return;
        if (b.typ === 'reload') { window.location.reload(); return; }
        if (b.typ === 'zeige_layout') {
            if (ueberblendungTimer) { clearTimeout(ueberblendungTimer); ueberblendungTimer = null; }
            ueberblendung = b.layout_id ? { layout_id: b.layout_id } : null;
            if (ueberblendung && b.dauer_s > 0) {
                ueberblendungTimer = setTimeout(function () {
                    ueberblendung = null;
                    ueberblendungTimer = null;
                    hole();
                }, b.dauer_s * 1000);
            }
            hole();
        }
        // `screenshot` wird mit Welle 2 ausgewertet.
    }

    /* ---- Hinweise ---- */

    function showHint(html) {
        if (!hintEl) return;
        hintEl.innerHTML = html;
        hintEl.classList.add('show');
    }
    function hideHint() {
        if (hintEl) hintEl.classList.remove('show');
    }
    function zeigeDezent(text) {
        if (!dezentEl) return;
        if (!text) { dezentEl.classList.remove('show'); return; }
        if (dezentEl.textContent !== text) dezentEl.textContent = text;
        dezentEl.classList.add('show');
    }

    // Der Waechter sagt, was fehlt — er leitet nirgendwohin um. Erst nach
    // 30 s: ein kurzer Aussetzer beim Laden ist kein Grund fuer eine Meldung.
    function waechter() {
        var jetzt = Date.now();
        if (jetzt - letzterKontakt > 30000) {
            zeigeDezent('Verbindung zur Station unterbrochen – läuft weiter');
            return;
        }
        if (currentHash && !expectedPlayable) {
            if (leerSeit === null) leerSeit = jetzt;
            if (jetzt - leerSeit > 30000) { zeigeDezent('Kein Inhalt zugewiesen'); return; }
        } else {
            leerSeit = null;
        }
        if (expectedPlayable && (jetzt - lastPlayableAt) > 30000) {
            zeigeDezent('Inhalt konnte nicht geladen werden – Medien im Admin prüfen');
            return;
        }
        zeigeDezent('');
    }

    /* ---- Szene anwenden ---- */

    function verarbeite(scene) {
        if (!scene) return;
        stationsname = scene.stationsname || stationsname;

        // Der Wochenplan steht VOR allem anderen: ausserhalb der
        // Oeffnungszeit bleibt der Schirm schwarz und der Ton aus — kein
        // Hinweistext ("Warte auf Sensor" waere nachts schlicht falsch)
        // und vor allem KEIN Auto-Start, der die Steuerung wieder
        // anwerfen wuerde.
        if (scene.geschlossen && !vorschau) {
            if (currentHash) { fadeAllOut(); currentHash = ''; }
            hideHint();
            return;
        }

        if (!scene.active && !vorschau) {
            if (currentHash) { fadeAllOut(); currentHash = ''; }
            if (!startAttempted) {
                startAttempted = true;
                fetch('/api/start', { method: 'POST' }).catch(function () {});
            }
            showHint('<strong>Starte Sensor-Steuerung...</strong>');
            return;
        }

        var zone = scene.zone;
        if (!zone) {
            showHint('<strong>Warte auf Sensor</strong><br><br>Bewege etwas vor den Sensor um eine Zone auszuwählen.');
            return;
        }
        var zd = scene[zone] || { videos: [], images: [], audio: [] };
        // Ein Kern von vor 3.0 liefert kein Layout — dann wird eines aus den
        // Zonenlisten gebaut, und die Seite spielt wie frueher im Vollbild.
        var layout = scene.layout || layoutAusZone(zd);

        // Die Lautstaerken kommen FERTIG aus `/api/scene`:
        // `Controller.get_scene()` setzt die Vorgaben aus `DEFAULT_CONFIG`
        // bereits ein. Hier stand trotzdem `(scene.master_volume || 100)`
        // -- dieselbe Vorgabe ein zweites Mal, und in einer Form, die die
        // Null nicht kennt: `0 || 100` ist 100. Wer den Gesamt-Regler auf
        // 0 % zog, bekam volle Lautstaerke; der Regler geht bis 0, und er
        // ist der einzige Stumm-Schalter, den die Station hat. Fuer Video
        // und Audio galt dasselbe.
        var master = anteil(scene.master_volume);
        var vid = anteil(scene.video_volume);
        var aud = anteil(scene.audio_volume);
        if (master !== null && vid !== null) {
            lautstaerke.video = vid * master;
            regionReihe.forEach(function (r) {
                if (r.videoA) { r.videoA.volume = lautstaerke.video; r.videoB.volume = lautstaerke.video; }
            });
        }
        if (master !== null && aud !== null) {
            lautstaerke.audio = aud * master;
            audioEl.volume = lautstaerke.audio;
        }

        resumeEnabled = !!scene.video_resume;
        // VOR der Hash-Abkuerzung: die Sprachliste haengt nicht an der
        // Zone. Stuende sie dahinter, erschienen die Knoepfe erst beim
        // naechsten Zonenwechsel — also womoeglich nie.
        uebernimmSprachen(scene);
        hideHint();

        var hash = zone + '|' + (scene.layout_id || '') + '|' + JSON.stringify(layout) +
            '|' + JSON.stringify(zd.audio || []) + '|' + scene.image_interval_s;
        if (hash === currentHash) return;
        currentHash = hash;
        var iv = Number(scene.image_interval_s);
        imageInterval = (isFinite(iv) && iv > 0) ? iv : 5;
        expectedPlayable = hatInhalt(layout, zd);
        lastPlayableAt = Date.now();
        applyScene(layout, zd);
        waechter();
    }

    // ---------------------------------------------------------------------
    // Zahlen aus `/api/scene` uebernehmen, ohne eine zweite Vorgabe zu
    // erfinden. `null` heisst hier „der Kern hat nichts Brauchbares gesagt" --
    // dann wird der vorhandene Wert nicht angefasst, statt einen zu raten.
    // ---------------------------------------------------------------------
    function anteil(wert) {
        var n = Number(wert);
        if (!isFinite(n)) return null;
        return Math.min(100, Math.max(0, n)) / 100;
    }

    // Zufaellige Reihenfolge auf einer KOPIE (Fisher-Yates). Die Liste aus
    // `/api/scene` wird bei jedem Poll neu geliefert; sie an Ort und Stelle zu
    // mischen waere wirkungslos und verwirrend.
    function mischen(liste) {
        var k = liste.slice();
        for (var i = k.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = k[i]; k[i] = k[j]; k[j] = t;
        }
        return k;
    }

    // Ein Layout aus den alten Zonenlisten — fuer einen Kern von vor 3.0.
    function layoutAusZone(zd) {
        var zeiten = zd.bildzeiten || {};
        var playlist = (zd.videos || []).map(function (n) {
            return { typ: 'video', name: n, dauer_s: null };
        }).concat((zd.images || []).map(function (n) {
            return { typ: 'image', name: n, dauer_s: zeiten[n] || null };
        }));
        return {
            name: 'Vollbild', hintergrund: '#000000',
            regionen: [{ id: 'haupt', name: 'Hauptbild', x: 0, y: 0, w: 100, h: 100, z: 0,
                         typ: 'medien', ton: true, playlist: playlist,
                         shuffle: !!zd.shuffle, einmal: !!zd.einmal, uebergang: 'blende' }],
        };
    }

    function hauptregion(layout) {
        var regs = layout.regionen || [];
        for (var i = 0; i < regs.length; i++) if (regs[i].typ === 'medien') return regs[i];
        return null;
    }

    function hatInhalt(layout, zd) {
        if ((zd.audio || []).length) return true;
        return (layout.regionen || []).some(function (r) {
            return r.typ === 'widget' || (r.playlist && r.playlist.length);
        });
    }

    function regionKennung(reg) {
        return JSON.stringify([reg.id, reg.x, reg.y, reg.w, reg.h, reg.z, reg.typ, reg.ton,
                               reg.playlist, reg.shuffle, reg.einmal, reg.uebergang, reg.widget]);
    }

    function applyScene(layout, zd) {
        buehne.style.background = layout.hintergrund || '#000000';
        var haupt = hauptregion(layout) || {};
        zoneShuffle = !!haupt.shuffle;
        zoneEinmal = !!haupt.einmal;

        var kennungen = {};
        (layout.regionen || []).forEach(function (reg) { kennungen[reg.id] = regionKennung(reg); });
        var gesamt = JSON.stringify(kennungen);
        if (gesamt !== currentVideoSet) {
            currentVideoSet = gesamt;
            // Nur die Regionen anfassen, die sich geaendert haben: eine
            // laufende Seitenleiste soll nicht von vorn beginnen, weil im
            // Hauptbild ein Video dazukam.
            Object.keys(regionen).forEach(function (id) {
                if (!kennungen[id] || kennungen[id] !== regionen[id].kennung) entferneRegion(id);
            });
            (layout.regionen || []).slice().sort(function (a, b) {
                return (a.z || 0) - (b.z || 0);
            }).forEach(function (reg) {
                if (!regionen[reg.id]) baueRegion(reg, layout);
            });
            regionReihe = Object.keys(regionen).map(function (id) { return regionen[id]; });
        }

        // Der Ton der Zone laeuft parallel zu allen Regionen.
        var audio = zd.audio || [];
        if (audio.length > 0) {
            var audSet = JSON.stringify(audio) + '|' + zoneShuffle;
            if (audSet !== currentAudioSet) {
                currentAudioSet = audSet;
                zoneAudioList = zoneShuffle ? mischen(audio) : audio.slice();
                audioIndex = 0;
                playAudio(zoneAudioList[0]);
            }
        } else if (currentAudioFile) {
            currentAudioSet = '';
            fadeOutAudio();
        }
    }

    /* ---- Regionen ---- */

    function mache(tag, el) {
        var n = document.createElement(tag);
        n.className = 'layer';
        if (tag === 'video') { n.setAttribute('playsinline', ''); n.preload = 'auto'; }
        if (tag === 'img') n.alt = '';
        if (tag === 'iframe') { n.setAttribute('allow', 'autoplay; fullscreen'); n.src = 'about:blank'; }
        el.appendChild(n);
        return n;
    }

    function baueRegion(reg, layout) {
        var el = document.createElement('div');
        el.className = 'region' + (reg.uebergang === 'keiner' ? ' sofort' : '');
        el.style.left = (reg.x || 0) + '%';
        el.style.top = (reg.y || 0) + '%';
        el.style.width = (reg.w || 100) + '%';
        el.style.height = (reg.h || 100) + '%';
        el.style.zIndex = String(10 + (reg.z || 0));
        el.setAttribute('data-region', reg.id);
        buehne.appendChild(el);

        var r = {
            id: reg.id, def: reg, kennung: regionKennung(reg), el: el,
            typ: reg.typ, ton: !!reg.ton, einmal: !!reg.einmal,
            playlist: [], idx: 0, timer: null, aktiv: null, fehler: 0,
            currentVideoFile: null, widget: null,
        };
        regionen[reg.id] = r;

        if (reg.typ === 'widget') {
            r.widget = starteWidget(el, reg, layout);
            return;
        }
        r.videoA = mache('video', el);
        r.videoB = mache('video', el);
        r.imgA = mache('img', el);
        r.imgB = mache('img', el);
        r.web = mache('iframe', el);
        r.audio = document.createElement('audio');
        el.appendChild(r.audio);
        r.activeVideo = r.videoA;
        r.standbyVideo = r.videoB;
        r.activeImg = r.imgA;
        r.standbyImg = r.imgB;
        [r.videoA, r.videoB].forEach(function (v) {
            v.volume = lautstaerke.video;
            v.muted = !r.ton;
        });
        r.audio.volume = lautstaerke.video;
        r.audio.muted = !r.ton;

        var liste = (reg.playlist || []).slice();
        r.playlist = reg.shuffle ? mischen(liste) : liste;
        if (r.playlist.length) spieleItem(r, 0);
    }

    function entferneRegion(id) {
        var r = regionen[id];
        if (!r) return;
        stopSlideshow(r);
        if (r.widget && typeof r.widget.stop === 'function') {
            try { r.widget.stop(); } catch (e) { /* Widget-Fehler bleiben beim Widget */ }
        }
        if (r.videoA) {
            merkePosition(r);
            [r.videoA, r.videoB].forEach(function (v) { v.pause(); v.removeAttribute('src'); v.load(); });
            r.audio.pause();
        }
        if (r.el.parentNode) r.el.parentNode.removeChild(r.el);
        delete regionen[id];
    }

    function starteWidget(el, reg, layout) {
        if (!window.LZ_WIDGETS || typeof window.LZ_WIDGETS.render !== 'function') return null;
        var ctx = {
            zeit: vorschauZeit ? new Date(vorschauZeit) : new Date(),
            jetzt: function () { return vorschauZeit ? new Date(vorschauZeit) : new Date(); },
            sprache: (window.LZ && window.LZ.sprache) ? window.LZ.sprache() : 'de',
            region: reg, layout: layout, stationsname: stationsname, vorschau: vorschau,
        };
        try {
            var ergebnis = window.LZ_WIDGETS.render(el, reg.widget || {}, ctx);
            touchPlayable();
            return ergebnis || null;
        } catch (e) {
            return null;
        }
    }

    /* ---- Playlist einer Region ---- */

    function spieleItem(r, idx) {
        stopSlideshow(r);
        if (!r.playlist.length) return;
        r.idx = ((idx % r.playlist.length) + r.playlist.length) % r.playlist.length;
        var item = r.playlist[r.idx];
        if (item.typ === 'video') { crossfadeVideo(r, item); return; }
        if (item.typ === 'image') { zeigeBild(r, item); startSlideshow(r); return; }
        if (item.typ === 'web') { zeigeWeb(r, item); startSlideshow(r); return; }
        if (item.typ === 'audio') { spieleRegionAudio(r, item); return; }
        naechstes(r);
    }

    function naechstes(r) {
        var einmal = (r.einmal !== undefined) ? r.einmal : zoneEinmal;
        // „einmal": nach dem letzten Eintrag stehen bleiben statt von vorn.
        if (einmal && r.idx >= r.playlist.length - 1) return;
        if (r.playlist.length <= 1) return;
        spieleItem(r, r.idx + 1);
    }

    // Ungueltige oder fehlende Datei: den naechsten Eintrag probieren. Ist
    // keiner abspielbar, bleibt die Region dunkel und probiert es in 30 s
    // wieder — vielleicht kopiert gerade jemand die Dateien nach.
    function fehler(r, item) {
        r.fehler++;
        if (r.fehler >= r.playlist.length) {
            r.fehler = 0;
            stopSlideshow(r);
            r.timer = setTimeout(function () { r.timer = null; spieleItem(r, r.idx); }, 30000);
            return;
        }
        spieleItem(r, r.idx + 1);
    }

    // Die neue Ebene zeigen, die alte ausblenden — egal welcher Art beide sind.
    function zeige(r, neu) {
        var alt = r.aktiv;
        if (alt && alt !== neu) alt.classList.remove('active');
        neu.classList.add('active');
        r.aktiv = neu;
        touchPlayable();
        r.fehler = 0;
        if (alt && alt !== neu) {
            setTimeout(function () {
                if (r.aktiv === alt) return;
                if (alt.tagName === 'VIDEO') { alt.pause(); alt.removeAttribute('src'); alt.load(); }
                if (alt.tagName === 'IFRAME') alt.src = 'about:blank';
            }, 900);
        }
    }

    /* ---- Untertitel und Sprachwahl ---- */

    function uebernimmSprachen(scene) {
        sprachen = scene.sprachen || [];
        untertitel = scene.untertitel || {};
        if (aktiveSprache === null || sprachen.indexOf(aktiveSprache) < 0) {
            aktiveSprache = sprachen.length ? sprachen[0] : null;
        }
        zeichneSprachwahl();
    }

    function zeichneSprachwahl() {
        var box = document.getElementById('sprachwahl');
        if (!box) return;
        // Nur neu zeichnen, wenn sich etwas geaendert hat: ein Neubau bei
        // jeder Szene wuerde einen gerade beruehrten Knopf unter dem Finger
        // wegziehen.
        var stand = sprachen.join(',') + '|' + aktiveSprache;
        if (stand === sprachwahlStand) return;
        sprachwahlStand = stand;
        if (sprachen.length < 2) {
            // Eine einzige Sprache ist keine Wahl.
            box.innerHTML = '';
            box.classList.remove('sichtbar');
            return;
        }
        box.innerHTML = sprachen.map(function (code) {
            return '<button class="sprach-knopf' + (code === aktiveSprache ? ' aktiv' : '') +
                '" data-code="' + code + '">' + code.toUpperCase() + '</button>';
        }).join('');
        box.classList.add('sichtbar');
        Array.prototype.forEach.call(box.querySelectorAll('.sprach-knopf'), function (k) {
            k.addEventListener('click', function () {
                aktiveSprache = k.getAttribute('data-code');
                sprachwahlStand = '';
                zeichneSprachwahl();
                regionReihe.forEach(function (r) { if (r.activeVideo) wendeSpracheAn(r.activeVideo); });
            });
        });
    }

    function setzeUntertitel(el, datei) {
        // Alte Spuren entfernen: das Element wird wiederverwendet (A/B-Paar),
        // und uebrig gebliebene <track> eines anderen Films wuerden mitlaufen.
        Array.prototype.forEach.call(el.querySelectorAll('track'), function (t) {
            el.removeChild(t);
        });
        var spuren = untertitel[datei] || {};
        sprachen.forEach(function (code) {
            if (!spuren[code]) return;
            var track = document.createElement('track');
            track.kind = 'subtitles';
            track.srclang = code;
            track.label = code.toUpperCase();
            track.src = '/media/subtitles/' + encodeURIComponent(spuren[code]);
            el.appendChild(track);
        });
    }

    function wendeSpracheAn(el) {
        if (!el || !el.textTracks) return;
        for (var i = 0; i < el.textTracks.length; i++) {
            el.textTracks[i].mode =
                (el.textTracks[i].language === aktiveSprache) ? 'showing' : 'disabled';
        }
    }

    /* ---- Video ---- */

    function merkePosition(r) {
        // Aktuelle Position des laufenden Videos merken (Resume beim Zonenwechsel)
        if (resumeEnabled && r.currentVideoFile && r.activeVideo && !r.activeVideo.paused) {
            var t = r.activeVideo.currentTime;
            if (isFinite(t) && t > 0) videoPositions[r.currentVideoFile] = t;
        }
    }

    function crossfadeVideo(r, item) {
        var file = item.name;
        merkePosition(r);
        r.currentVideoFile = file;
        var el = r.standbyVideo;
        el.onerror = null;
        el.onended = null;
        el.src = '/media/videos/' + encodeURIComponent(file);
        // Ein einzelnes Video lief bisher immer in der Schleife. Mit „einmal"
        // soll es stehen bleiben — sonst laesst sich eine Praesentation nicht
        // von einer Endlosschleife unterscheiden.
        var einmal = (r.einmal !== undefined) ? r.einmal : zoneEinmal;
        el.loop = r.playlist.length <= 1 && !einmal;
        el.muted = !r.ton;
        el.volume = lautstaerke.video;
        setzeUntertitel(el, file);
        el.load();

        function onReady() {
            el.removeEventListener('canplay', onReady);
            el.onerror = null;
            if (resumeEnabled && videoPositions[file]) {
                try { el.currentTime = videoPositions[file]; } catch (e) { /* ignore */ }
            }
            el.play().catch(function () {});
            // Erst nach `canplay`: vorher sind die Spuren dem Element zwar
            // angehaengt, aber `textTracks` ist noch leer.
            wendeSpracheAn(el);
            zeige(r, el);
            var tmp = r.activeVideo;
            r.activeVideo = r.standbyVideo;
            r.standbyVideo = tmp;
        }
        el.addEventListener('canplay', onReady);
        el.onerror = function () {
            el.removeEventListener('canplay', onReady);
            fehler(r, item);
        };
        el.onended = function () {
            // Komplett durchgespielt -> Position vergessen, damit beim naechsten Mal von vorn
            delete videoPositions[file];
            // „einmal": nach dem letzten Video stehen bleiben statt von vorn
            // zu beginnen.
            if (einmal && r.idx >= r.playlist.length - 1) return;
            if (r.playlist.length > 1) naechstes(r);
        };
    }

    /* ---- Bilder und Webseiten ---- */

    function zeigeBild(r, item) {
        var el = (r.aktiv === r.imgA) ? r.imgB : r.imgA;
        el.onload = function () { zeige(r, el); };
        el.onerror = function () { fehler(r, item); };
        el.src = '/media/images/' + encodeURIComponent(item.name);
    }

    function zeigeWeb(r, item) {
        var el = r.web;
        el.onload = function () { zeige(r, el); };
        // Ein Fehler in einer fremden Seite ist von aussen nicht sichtbar —
        // der Rahmen bleibt stehen, die Standzeit schaltet weiter.
        el.src = item.url;
        touchPlayable();
    }

    // Kette aus `setTimeout` statt eines festen `setInterval`: nur so kann
    // jeder Eintrag seine EIGENE Standzeit haben (ein Titelbild 3 s, eine
    // Detailtafel 20 s, eine Webseite 60 s). Mit einem Intervall waere die
    // Schrittweite fuer alle dieselbe.
    function startSlideshow(r) {
        stopSlideshow(r);
        if (r.playlist.length <= 1) return;   // ein Bild steht, es gibt kein Naechstes
        var item = r.playlist[r.idx];
        // „einmal": am letzten Eintrag stehen bleiben, statt von vorn zu
        // beginnen. Das ist der Unterschied zwischen einer Praesentation
        // und einer Endlosschleife.
        var einmal = (r.einmal !== undefined) ? r.einmal : zoneEinmal;
        if (einmal && r.idx >= r.playlist.length - 1) return;

        function standzeit(it) {
            var s = Number(it.dauer_s);
            if (isFinite(s) && s > 0) return s;
            return it.typ === 'web' ? 30 : imageInterval;
        }

        r.timer = setTimeout(function () {
            r.timer = null;
            naechstes(r);
        }, standzeit(item) * 1000);
    }

    function stopSlideshow(r) {
        if (r.timer) {
            clearTimeout(r.timer);
            r.timer = null;
        }
    }

    /* ---- Audio in einer Region ---- */

    function spieleRegionAudio(r, item) {
        var el = r.audio;
        el.src = '/media/audio/' + encodeURIComponent(item.name);
        el.loop = r.playlist.length <= 1 && !r.einmal;
        el.onloadeddata = touchPlayable;
        el.onerror = function () { fehler(r, item); };
        el.onended = function () { naechstes(r); };
        el.play().catch(function () {});
    }

    /* ---- Ton der Zone ---- */

    function playAudio(file) {
        currentAudioFile = file;
        audioEl.src = '/media/audio/' + encodeURIComponent(file);
        audioEl.loop = zoneAudioList.length <= 1 && !zoneEinmal;
        audioEl.onloadeddata = touchPlayable;
        audioEl.onerror = function () {
            if (zoneAudioList.length > 1) {
                audioIndex = (audioIndex + 1) % zoneAudioList.length;
                if (zoneAudioList[audioIndex] !== file) {
                    playAudio(zoneAudioList[audioIndex]);
                    return;
                }
            }
            // Nichts abspielbar: still bleiben. Der Waechter sagt es unten.
            currentAudioFile = null;
        };
        audioEl.play().catch(function () {});
        audioEl.onended = function () {
            if (zoneEinmal && audioIndex >= zoneAudioList.length - 1) return;
            if (zoneAudioList.length > 1) {
                audioIndex = (audioIndex + 1) % zoneAudioList.length;
                // Ueber `playAudio`, nicht die `src` direkt setzen: sonst
                // bleibt `currentAudioFile` auf dem alten Titel stehen, und
                // die Fehlerbehandlung des neuen Titels fehlt ganz.
                playAudio(zoneAudioList[audioIndex]);
            }
        };
    }

    function fadeOutAudio() {
        currentAudioFile = null;
        var startVol = audioEl.volume;
        var step = 0;
        var iv = setInterval(function () {
            step++;
            audioEl.volume = Math.max(0, startVol * (1 - step / 10));
            if (step >= 10) {
                clearInterval(iv);
                audioEl.pause();
                audioEl.removeAttribute('src');
                audioEl.volume = startVol;
            }
        }, 50);
    }

    function fadeAllOut() {
        Object.keys(regionen).forEach(entferneRegion);
        regionReihe = [];
        currentVideoSet = '';
        currentAudioSet = '';
        fadeOutAudio();
        expectedPlayable = false;
        leerSeit = null;
    }

    function touchPlayable() {
        lastPlayableAt = Date.now();
    }
})();

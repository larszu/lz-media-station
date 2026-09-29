/* Widgets der Anzeige (3.0, Welle 2) — `window.LZ_WIDGETS`.

   Eine Region mit `typ: "widget"` ueberlaesst ihre Flaeche diesem Skript:
   display.js ruft `LZ_WIDGETS.render(el, widget, ctx)` und bekommt ein
   Objekt mit `stop()` zurueck, das beim Abbau der Region gerufen wird.
   `widget.typ` waehlt das Widget, die uebrigen Felder sind seine
   Einstellungen; `LZ_WIDGETS.katalog()` beschreibt jedes Feld, damit der
   Layout-Editor daraus ein Formular bauen kann, ohne die Widgets zu kennen.

   WARUM ALLES IN EINER DATEI. Die Anzeige laeuft auf einem Pi, der jedes
   Skript einzeln ueber das LAN laedt; display.html bindet `static/anzeige/*.js`
   automatisch ein. Zehn Dateien waeren zehn Anfragen beim Start — und die
   Widgets teilen sich Hilfsfunktionen (Groesse, Zeit, Netz), die sonst
   zehnmal da waeren.

   REGELN:
   * Kein Netz aus dem Browser. RSS, Kalender und Wetter kommen ueber die
     Proxys in `api_widgets.py`. Faellt der Abruf aus, zeigt das Widget den
     letzten Stand oder eine dezente Zeile — nie einen Fehler in der Konsole,
     nie eine leere weisse Flaeche.
   * Deutsch ist die Quelle. Sichtbare Texte stehen hier deutsch; der
     Beobachter aus i18n.js uebersetzt sie ueber `static/i18n/widgets.en.js`.
     Datum und Uhrzeit folgen `ctx.sprache` ueber `toLocale…`.
   * `ctx.zeit` ist die Zeit der Vorschau: Uhr, Kalender und Zaehler rechnen
     von dort weiter, nicht von der Uhr des Rechners.
   * Marke: kein border-radius, kein box-shadow, kein Verlauf (widgets.css).
   * Unter Node ohne DOM importierbar (`module.exports`) — so testet die CI
     den QR-Code gegen eine Referenz, ohne einen Browser zu starten. */
(function (global) {
    'use strict';

    /* ======================================================================
       QR-Code — Byte-Modus, Fehlerkorrektur M, Versionen 1–10.
       Eigenbau statt Fremdskript: 4 kB, keine Abhaengigkeit, laeuft offline.
       Aufbau nach ISO/IEC 18004; die Struktur folgt der Referenz von Nayuki
       (MIT), weil sie nachlesbar ist und sich gegen `segno` pruefen laesst.
       ====================================================================== */
    var QR = (function () {
        var MAX_VERSION = 10;
        // Je Version (Index 1..10), Fehlerkorrektur M:
        var EC_JE_BLOCK = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26];
        var BLOECKE = [0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5];
        var AUSRICHTUNG = [null, [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34],
                           [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]];

        // GF(256) mit dem QR-Polynom 0x11D.
        var EXP = [], LOG = [];
        (function () {
            var x = 1;
            for (var i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11D; }
            for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
        })();
        function gmul(a, b) { return (a === 0 || b === 0) ? 0 : EXP[LOG[a] + LOG[b]]; }

        function rsTeiler(grad) {
            var r = [];
            for (var i = 0; i < grad - 1; i++) r.push(0);
            r.push(1);
            var wurzel = 1;
            for (var k = 0; k < grad; k++) {
                for (var j = 0; j < r.length; j++) {
                    r[j] = gmul(r[j], wurzel);
                    if (j + 1 < r.length) r[j] ^= r[j + 1];
                }
                wurzel = gmul(wurzel, 2);
            }
            return r;
        }
        function rsRest(daten, teiler) {
            var r = teiler.map(function () { return 0; });
            daten.forEach(function (b) {
                var faktor = b ^ r.shift();
                r.push(0);
                for (var i = 0; i < teiler.length; i++) r[i] ^= gmul(teiler[i], faktor);
            });
            return r;
        }

        function rohModule(ver) {
            var n = (16 * ver + 128) * ver + 64;
            if (ver >= 2) {
                var a = Math.floor(ver / 7) + 2;
                n -= (25 * a - 10) * a - 55;
                if (ver >= 7) n -= 36;
            }
            return n;
        }
        function datenCodewoerter(ver) {
            return Math.floor(rohModule(ver) / 8) - EC_JE_BLOCK[ver] * BLOECKE[ver];
        }

        function utf8(text) {
            if (typeof TextEncoder !== 'undefined') return Array.prototype.slice.call(new TextEncoder().encode(text));
            var s = unescape(encodeURIComponent(text)), out = [];
            for (var i = 0; i < s.length; i++) out.push(s.charCodeAt(i));
            return out;
        }

        function bitsAnhaengen(bits, wert, laenge) {
            for (var i = laenge - 1; i >= 0; i--) bits.push((wert >>> i) & 1);
        }

        /* Text -> Liste der Codewoerter (Daten + Fehlerkorrektur, verschraenkt). */
        function kodieren(bytes) {
            var ver = 1;
            for (; ver <= MAX_VERSION; ver++) {
                if (4 + (ver <= 9 ? 8 : 16) + 8 * bytes.length <= 8 * datenCodewoerter(ver)) break;
            }
            if (ver > MAX_VERSION) return null;
            var bits = [];
            bitsAnhaengen(bits, 4, 4);                       // Byte-Modus
            bitsAnhaengen(bits, bytes.length, ver <= 9 ? 8 : 16);
            bytes.forEach(function (b) { bitsAnhaengen(bits, b, 8); });
            var kapazitaet = datenCodewoerter(ver) * 8;
            bitsAnhaengen(bits, 0, Math.min(4, kapazitaet - bits.length));
            while (bits.length % 8) bits.push(0);
            for (var pad = 0xEC; bits.length < kapazitaet; pad ^= 0xEC ^ 0x11) bitsAnhaengen(bits, pad, 8);
            var daten = [];
            for (var i = 0; i < bits.length; i += 8) {
                var b = 0;
                for (var j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
                daten.push(b);
            }
            // Bloecke und Verschraenkung
            var anzahl = BLOECKE[ver], ec = EC_JE_BLOCK[ver];
            var roh = Math.floor(rohModule(ver) / 8);
            var kurze = anzahl - roh % anzahl, kurzLaenge = Math.floor(roh / anzahl);
            var bloecke = [], k = 0, teiler = rsTeiler(ec);
            for (var n = 0; n < anzahl; n++) {
                var len = kurzLaenge - ec + (n < kurze ? 0 : 1);
                var dat = daten.slice(k, k + len);
                k += len;
                var rest = rsRest(dat, teiler);
                if (n < kurze) dat.push(-1);                 // Platzhalter, wird uebersprungen
                bloecke.push(dat.concat(rest));
            }
            var ergebnis = [];
            for (var i2 = 0; i2 < bloecke[0].length; i2++) {
                for (var j2 = 0; j2 < bloecke.length; j2++) {
                    if (i2 !== kurzLaenge - ec || j2 >= kurze) ergebnis.push(bloecke[j2][i2]);
                }
            }
            return { version: ver, codewoerter: ergebnis };
        }

        function Symbol(ver) {
            this.version = ver;
            this.groesse = ver * 4 + 17;
            this.module = [];
            this.funktion = [];
            for (var y = 0; y < this.groesse; y++) {
                this.module.push(new Array(this.groesse).fill(false));
                this.funktion.push(new Array(this.groesse).fill(false));
            }
        }
        Symbol.prototype.setzeFunktion = function (x, y, dunkel) {
            this.module[y][x] = !!dunkel;
            this.funktion[y][x] = true;
        };
        Symbol.prototype.funktionsmuster = function () {
            var g = this.groesse, i;
            for (i = 0; i < g; i++) { this.setzeFunktion(6, i, i % 2 === 0); this.setzeFunktion(i, 6, i % 2 === 0); }
            this.sucher(3, 3); this.sucher(g - 4, 3); this.sucher(3, g - 4);
            var pos = AUSRICHTUNG[this.version];
            for (var a = 0; a < pos.length; a++) {
                for (var b = 0; b < pos.length; b++) {
                    if ((a === 0 && b === 0) || (a === 0 && b === pos.length - 1) || (a === pos.length - 1 && b === 0)) continue;
                    this.ausrichtung(pos[a], pos[b]);
                }
            }
            this.formatBits(0);
            this.versionBits();
        };
        Symbol.prototype.sucher = function (x, y) {
            for (var dy = -4; dy <= 4; dy++) for (var dx = -4; dx <= 4; dx++) {
                var d = Math.max(Math.abs(dx), Math.abs(dy)), xx = x + dx, yy = y + dy;
                if (xx >= 0 && xx < this.groesse && yy >= 0 && yy < this.groesse) this.setzeFunktion(xx, yy, d !== 2 && d !== 4);
            }
        };
        Symbol.prototype.ausrichtung = function (x, y) {
            for (var dy = -2; dy <= 2; dy++) for (var dx = -2; dx <= 2; dx++) {
                this.setzeFunktion(x + dx, y + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
            }
        };
        Symbol.prototype.formatBits = function (maske) {
            var daten = (0 << 3) | maske;                    // Fehlerkorrektur M = 00
            var rest = daten;
            for (var i = 0; i < 10; i++) rest = (rest << 1) ^ ((rest >>> 9) * 0x537);
            var bits = ((daten << 10) | rest) ^ 0x5412, g = this.groesse, b;
            function bit(i) { return ((bits >>> i) & 1) !== 0; }
            for (b = 0; b <= 5; b++) this.setzeFunktion(8, b, bit(b));
            this.setzeFunktion(8, 7, bit(6)); this.setzeFunktion(8, 8, bit(7)); this.setzeFunktion(7, 8, bit(8));
            for (b = 9; b < 15; b++) this.setzeFunktion(14 - b, 8, bit(b));
            for (b = 0; b < 8; b++) this.setzeFunktion(g - 1 - b, 8, bit(b));
            for (b = 8; b < 15; b++) this.setzeFunktion(8, g - 15 + b, bit(b));
            this.setzeFunktion(8, g - 8, true);              // das immer dunkle Modul
        };
        Symbol.prototype.versionBits = function () {
            if (this.version < 7) return;
            var rest = this.version;
            for (var i = 0; i < 12; i++) rest = (rest << 1) ^ ((rest >>> 11) * 0x1F25);
            var bits = (this.version << 12) | rest, g = this.groesse;
            for (var k = 0; k < 18; k++) {
                var bit = ((bits >>> k) & 1) !== 0, a = g - 11 + k % 3, b = Math.floor(k / 3);
                this.setzeFunktion(a, b, bit); this.setzeFunktion(b, a, bit);
            }
        };
        Symbol.prototype.codewoerter = function (daten) {
            var g = this.groesse, i = 0, gesamt = daten.length * 8;
            for (var rechts = g - 1; rechts >= 1; rechts -= 2) {
                if (rechts === 6) rechts = 5;             // die senkrechte Taktspur ueberspringen
                for (var v = 0; v < g; v++) {
                    for (var j = 0; j < 2; j++) {
                        var x = rechts - j, aufwaerts = ((rechts + 1) & 2) === 0, y = aufwaerts ? g - 1 - v : v;
                        if (!this.funktion[y][x] && i < gesamt) {
                            this.module[y][x] = ((daten[i >>> 3] >>> (7 - (i & 7))) & 1) !== 0;
                            i++;
                        }
                    }
                }
            }
        };
        Symbol.prototype.maskiere = function (m) {
            for (var y = 0; y < this.groesse; y++) for (var x = 0; x < this.groesse; x++) {
                var inv;
                switch (m) {
                case 0: inv = (x + y) % 2 === 0; break;
                case 1: inv = y % 2 === 0; break;
                case 2: inv = x % 3 === 0; break;
                case 3: inv = (x + y) % 3 === 0; break;
                case 4: inv = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; break;
                case 5: inv = x * y % 2 + x * y % 3 === 0; break;
                case 6: inv = (x * y % 2 + x * y % 3) % 2 === 0; break;
                default: inv = ((x + y) % 2 + x * y % 3) % 2 === 0;
                }
                if (!this.funktion[y][x] && inv) this.module[y][x] = !this.module[y][x];
            }
        };
        Symbol.prototype.strafe = function () {
            var g = this.groesse, m = this.module, s = 0, x, y, self = this;
            function zaehleMuster(h) {
                var n = h[1], kern = n > 0 && h[2] === n && h[3] === n * 3 && h[4] === n && h[5] === n;
                return (kern && h[0] >= n * 4 && h[6] >= n ? 1 : 0) + (kern && h[6] >= n * 4 && h[0] >= n ? 1 : 0);
            }
            function merke(len, h) { if (h[0] === 0) len += g; h.pop(); h.unshift(len); }
            function abschluss(farbe, len, h) {
                if (farbe) { merke(len, h); len = 0; }
                len += g; merke(len, h);
                return zaehleMuster(h);
            }
            function lauf(hol) {
                for (var a = 0; a < g; a++) {
                    var farbe = false, len = 0, h = [0, 0, 0, 0, 0, 0, 0];
                    for (var b = 0; b < g; b++) {
                        if (hol(a, b) === farbe) {
                            len++;
                            if (len === 5) s += 3; else if (len > 5) s++;
                        } else {
                            merke(len, h);
                            if (!farbe) s += zaehleMuster(h) * 40;
                            farbe = hol(a, b); len = 1;
                        }
                    }
                    s += abschluss(farbe, len, h) * 40;
                }
            }
            lauf(function (a, b) { return m[a][b]; });
            lauf(function (a, b) { return m[b][a]; });
            for (y = 0; y < g - 1; y++) for (x = 0; x < g - 1; x++) {
                var c = m[y][x];
                if (c === m[y][x + 1] && c === m[y + 1][x] && c === m[y + 1][x + 1]) s += 3;
            }
            var dunkel = 0;
            m.forEach(function (zeile) { zeile.forEach(function (d) { if (d) dunkel++; }); });
            var gesamt = g * g, k = Math.ceil(Math.abs(dunkel * 20 - gesamt * 10) / gesamt) - 1;
            s += k * 10;
            void self;
            return s;
        };

        /* Text -> { version, maske, groesse, module[][] (true = dunkel) } oder null,
           wenn der Text fuer Version 10 zu lang ist (> 213 Byte). */
        function matrix(text, optionen) {
            var kod = kodieren(utf8(String(text == null ? '' : text)));
            if (!kod) return null;
            var maske = optionen && typeof optionen.maske === 'number' ? optionen.maske : null;
            var beste = null;
            var kandidaten = maske === null ? [0, 1, 2, 3, 4, 5, 6, 7] : [maske];
            kandidaten.forEach(function (mk) {
                var s = new Symbol(kod.version);
                s.funktionsmuster();
                s.codewoerter(kod.codewoerter);
                s.formatBits(mk);
                s.maskiere(mk);
                var strafe = maske === null ? s.strafe() : 0;
                if (!beste || strafe < beste.strafe) beste = { symbol: s, strafe: strafe, maske: mk };
            });
            return { version: kod.version, maske: beste.maske, groesse: beste.symbol.groesse, module: beste.symbol.module };
        }

        function svg(text, optionen) {
            var q = matrix(text, optionen);
            if (!q) return null;
            var rand = 4, n = q.groesse + rand * 2, pfad = [];
            for (var y = 0; y < q.groesse; y++) for (var x = 0; x < q.groesse; x++) {
                if (q.module[y][x]) pfad.push('M' + (x + rand) + ' ' + (y + rand) + 'h1v1h-1z');
            }
            var vorn = (optionen && optionen.farbe) || '#132040', hinten = (optionen && optionen.hintergrund) || '#F6F5F0';
            return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + n + ' ' + n + '" shape-rendering="crispEdges">' +
                '<rect width="' + n + '" height="' + n + '" fill="' + hinten + '"/>' +
                '<path d="' + pfad.join('') + '" fill="' + vorn + '"/></svg>';
        }

        return { matrix: matrix, svg: svg, MAX_VERSION: MAX_VERSION };
    })();

    /* ======================================================================
       Hilfen
       ====================================================================== */
    var CSS_GELADEN = false;
    function ladeCss() {
        if (CSS_GELADEN || typeof document === 'undefined') return;
        CSS_GELADEN = true;
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/anzeige/widgets.css';
        document.head.appendChild(link);
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function zahl(w, vorgabe, min, max) {
        var n = parseFloat(w);
        if (isNaN(n)) n = vorgabe;
        if (min !== undefined && n < min) n = min;
        if (max !== undefined && n > max) n = max;
        return n;
    }
    function farbe(w, vorgabe) {
        return (typeof w === 'string' && /^#[0-9a-fA-F]{6}$/.test(w)) ? w : (vorgabe || '');
    }
    function locale(ctx) { return ctx && ctx.sprache === 'en' ? 'en-GB' : 'de-DE'; }

    /* Die Zeit des Widgets: in der Vorschau laeuft sie ab `ctx.zeit` weiter,
       sonst ist es die Uhr. So zeigt „Dienstag 18:00" wirklich Dienstag 18:00
       — und die Uhr tickt trotzdem. */
    function zeitgeber(ctx) {
        var basis = (ctx && ctx.zeit instanceof Date && !isNaN(ctx.zeit)) ? ctx.zeit.getTime() : Date.now();
        var start = Date.now();
        return function () { return new Date(basis + (Date.now() - start)); };
    }

    /* Grundschrift aus der Groesse der Region: die kleinere Kante geteilt
       durch 12, mal dem Faktor `schrift` (Prozent). Ein Ticker unten ist
       damit lesbar und eine Vollbild-Uhr gross, ohne dass jemand Pixel setzt. */
    function passeAn(el, w, faktorFeld, nachHoehe) {
        var faktor = zahl(w[faktorFeld || 'schrift'], 100, 25, 400) / 100;
        function rechne() {
            var b = el.clientWidth || 400, h = el.clientHeight || 300;
            // Ein Laufband ist breit und flach: dort zaehlt die Hoehe, sonst
            // stuende in einer 10 %-Zeile eine Schrift von wenigen Pixeln.
            var basis = nachHoehe ? h / 2.4 : Math.min(b, h) / 12;
            el.style.setProperty('--wg-basis', (basis * faktor) + 'px');
            el.style.setProperty('--wg-breite', b + 'px');
        }
        rechne();
        var ro = null;
        if (typeof ResizeObserver !== 'undefined') {
            ro = new ResizeObserver(rechne);
            ro.observe(el);
        }
        return function () { if (ro) ro.disconnect(); };
    }

    function huelle(el, w, klasse) {
        el.innerHTML = '';
        el.classList.add('wg');
        var box = document.createElement('div');
        box.className = 'wg-box ' + (klasse || '');
        var hg = farbe(w.hintergrund, '');
        box.style.background = hg || 'transparent';
        box.style.color = farbe(w.farbe, '#E1ECEF');
        el.appendChild(box);
        return box;
    }

    function dezent(box, text) {
        var z = box.querySelector('.wg-dezent');
        if (!text) { if (z) z.remove(); return; }
        if (!z) { z = document.createElement('div'); z.className = 'wg-dezent'; box.appendChild(z); }
        z.textContent = text;
    }

    /* Abruf ueber einen Kern-Proxy mit Wiederholung. Ein Fehler wird gemeldet,
       nie geworfen — die Anzeige laeuft auf einem Schirm, den niemand liest. */
    function pollend(url, intervallMs, beiDaten, beiFehler) {
        var timer = null, laeuft = true;
        function hole() {
            if (!laeuft) return;
            fetch(url).then(function (r) {
                return r.json().then(function (d) { return { ok: r.ok, daten: d }; });
            }).then(function (a) {
                if (!laeuft) return;
                if (a.ok) beiDaten(a.daten); else beiFehler((a.daten && a.daten.fehler) || 'Abruf gescheitert');
            }).catch(function () {
                if (laeuft) beiFehler('Station nicht erreichbar');
            }).then(function () {
                if (laeuft) timer = setTimeout(hole, intervallMs);
            });
        }
        hole();
        return function () { laeuft = false; if (timer) clearTimeout(timer); };
    }

    function stationsStatus(beiDaten) {
        return fetch('/api/status').then(function (r) { return r.json(); }).then(beiDaten).catch(function () { /* still */ });
    }

    /* Sichtbare deutsche Texte mit Werten: gehen durch den Beobachter aus
       i18n.js (Muster in widgets.en.js). */
    var TAGE_KURZ = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

    function uhrzeit(d, ctx, sekunden, zeitzone, zwoelf) {
        var opt = { hour: '2-digit', minute: '2-digit' };
        if (sekunden) opt.second = '2-digit';
        if (zwoelf) opt.hour12 = true;
        if (zeitzone) opt.timeZone = zeitzone;
        try { return d.toLocaleTimeString(locale(ctx), opt); } catch (e) {
            delete opt.timeZone;
            return d.toLocaleTimeString(locale(ctx), opt);
        }
    }
    function datum(d, ctx, zeitzone, lang) {
        var opt = lang ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
                       : { weekday: 'short', day: '2-digit', month: '2-digit' };
        if (zeitzone) opt.timeZone = zeitzone;
        try { return d.toLocaleDateString(locale(ctx), opt); } catch (e) {
            delete opt.timeZone;
            return d.toLocaleDateString(locale(ctx), opt);
        }
    }

    /* ======================================================================
       Die Widgets. Jeder Eintrag: name, beschreibung, felder, render.
       `katalog()` leitet sich daraus ab — es kann kein Widget ohne Katalog
       und keinen Katalogeintrag ohne Widget geben.
       ====================================================================== */
    var FARBFELDER = [
        { key: 'farbe', label: 'Textfarbe', typ: 'farbe', default: '#E1ECEF' },
        { key: 'hintergrund', label: 'Hintergrund (leer = durchsichtig)', typ: 'farbe', default: '' },
        { key: 'schrift', label: 'Schriftgröße (%)', typ: 'zahl', default: 100, min: 25, max: 400 },
    ];

    var WIDGETS = {};

    /* ---- Uhr ---- */
    WIDGETS.uhr = {
        name: 'Uhr',
        beschreibung: 'Digital oder analog, mit Datum, Sekunden und Zeitzone.',
        felder: [
            { key: 'stil', label: 'Darstellung', typ: 'auswahl', default: 'digital',
              optionen: [{ wert: 'digital', label: 'Digital' }, { wert: 'analog', label: 'Analog' }] },
            { key: 'sekunden', label: 'Sekunden anzeigen', typ: 'bool', default: false },
            { key: 'datum', label: 'Datum anzeigen', typ: 'bool', default: true },
            { key: 'zwoelf', label: '12-Stunden-Format', typ: 'bool', default: false },
            { key: 'zeitzone', label: 'Zeitzone (leer = Station)', typ: 'text', default: '' },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-uhr wg-mitte');
            var jetzt = zeitgeber(ctx), tz = (w.zeitzone || '').trim() || null;
            var sekunden = !!w.sekunden, analog = w.stil === 'analog';
            var stopGroesse = passeAn(el, w);
            var timer;
            if (analog) {
                box.innerHTML = '<div class="wg-analog"><svg viewBox="0 0 100 100">' +
                    '<circle cx="50" cy="50" r="48" class="wg-ziffernblatt"/>' +
                    Array.apply(null, Array(12)).map(function (_, i) {
                        var a = i * Math.PI / 6, r1 = i % 3 === 0 ? 40 : 43;
                        return '<line x1="' + (50 + r1 * Math.sin(a)) + '" y1="' + (50 - r1 * Math.cos(a)) + '" x2="' + (50 + 46 * Math.sin(a)) + '" y2="' + (50 - 46 * Math.cos(a)) + '" class="wg-strich"/>';
                    }).join('') +
                    '<line id="h" x1="50" y1="50" x2="50" y2="24" class="wg-zeiger wg-stunde"/>' +
                    '<line id="m" x1="50" y1="50" x2="50" y2="14" class="wg-zeiger wg-minute"/>' +
                    (sekunden ? '<line id="s" x1="50" y1="50" x2="50" y2="10" class="wg-zeiger wg-sekunde"/>' : '') +
                    '<circle cx="50" cy="50" r="2.5" class="wg-nabe"/></svg></div>' +
                    (w.datum !== false ? '<div class="wg-datum"></div>' : '');
            } else {
                box.innerHTML = '<div class="wg-zeit"></div>' + (w.datum !== false ? '<div class="wg-datum"></div>' : '');
            }
            function teile(d) {
                // Stunden/Minuten/Sekunden in der gewuenschten Zeitzone.
                try {
                    var p = new Intl.DateTimeFormat('en-GB', { hour: 'numeric', minute: 'numeric', second: 'numeric', hourCycle: 'h23', timeZone: tz || undefined }).formatToParts(d);
                    var o = {};
                    p.forEach(function (x) { o[x.type] = parseInt(x.value, 10); });
                    return o;
                } catch (e) { return { hour: d.getHours(), minute: d.getMinutes(), second: d.getSeconds() }; }
            }
            function tick() {
                var d = jetzt();
                if (analog) {
                    var t = teile(d), s = t.second, m = t.minute + s / 60, h = (t.hour % 12) + m / 60;
                    box.querySelector('#h').setAttribute('transform', 'rotate(' + (h * 30) + ' 50 50)');
                    box.querySelector('#m').setAttribute('transform', 'rotate(' + (m * 6) + ' 50 50)');
                    var sz = box.querySelector('#s');
                    if (sz) sz.setAttribute('transform', 'rotate(' + (s * 6) + ' 50 50)');
                } else {
                    box.querySelector('.wg-zeit').textContent = uhrzeit(d, ctx, sekunden, tz, !!w.zwoelf);
                }
                var dat = box.querySelector('.wg-datum');
                if (dat) dat.textContent = datum(d, ctx, tz, true);
            }
            tick();
            timer = setInterval(tick, sekunden ? 250 : 1000);
            return { stop: function () { clearInterval(timer); stopGroesse(); } };
        }
    };

    /* ---- Text-Folie ---- */
    var VORLAGEN = {
        frei: {},
        willkommen: { ueberschrift: 'Herzlich willkommen', text: '', ausrichtung: 'mitte' },
        wegweiser: { ueberschrift: 'Ausstellung', pfeil: '→', ausrichtung: 'mitte' },
        menuekarte: { ueberschrift: 'Speisekarte', text: 'Tagessuppe | 4,50 €\nHausgericht | 9,80 €\nKaffee | 2,40 €', ausrichtung: 'links' },
        hinweis: { ueberschrift: 'Hinweis', text: 'Bitte Fotografieren ohne Blitz.', ausrichtung: 'mitte' },
        oeffnungszeiten: { ueberschrift: 'Öffnungszeiten', ausrichtung: 'mitte' },
    };
    WIDGETS.text = {
        name: 'Text-Folie',
        beschreibung: 'Überschrift, Text und Fußzeile — mit Vorlagen für Willkommen, Wegweiser, Speisekarte, Hinweis und Öffnungszeiten.',
        felder: [
            { key: 'vorlage', label: 'Vorlage', typ: 'auswahl', default: 'frei', optionen: [
                { wert: 'frei', label: 'Frei' }, { wert: 'willkommen', label: 'Willkommen' },
                { wert: 'wegweiser', label: 'Wegweiser' }, { wert: 'menuekarte', label: 'Speisekarte' },
                { wert: 'hinweis', label: 'Hinweis' }, { wert: 'oeffnungszeiten', label: 'Öffnungszeiten (aus der Zeitsteuerung)' }] },
            { key: 'ueberschrift', label: 'Überschrift', typ: 'text', default: '' },
            { key: 'text', label: 'Text (Speisekarte: eine Zeile je Gericht, „Gericht | Preis")', typ: 'textarea', default: '' },
            { key: 'fusszeile', label: 'Fußzeile', typ: 'text', default: '' },
            { key: 'pfeil', label: 'Pfeil (Wegweiser)', typ: 'auswahl', default: '', optionen: [
                { wert: '', label: 'kein Pfeil' }, { wert: '←', label: '← links' }, { wert: '→', label: '→ rechts' },
                { wert: '↑', label: '↑ geradeaus' }, { wert: '↓', label: '↓ zurück' }, { wert: '↖', label: '↖' },
                { wert: '↗', label: '↗' }, { wert: '↙', label: '↙' }, { wert: '↘', label: '↘' }] },
            { key: 'ausrichtung', label: 'Ausrichtung', typ: 'auswahl', default: 'mitte', optionen: [
                { wert: 'links', label: 'links' }, { wert: 'mitte', label: 'mittig' }, { wert: 'rechts', label: 'rechts' }] },
            { key: 'akzent', label: 'Akzentfarbe (Überschrift, Pfeil)', typ: 'farbe', default: '#F6F5F0' },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var v = VORLAGEN[w.vorlage] || {};
            function wert(k) { return (w[k] != null && String(w[k]).trim() !== '') ? String(w[k]) : (v[k] || ''); }
            var box = huelle(el, w, 'wg-text wg-' + (wert('ausrichtung') || 'mitte'));
            box.style.setProperty('--wg-akzent', farbe(w.akzent, '#F6F5F0'));
            var stopGroesse = passeAn(el, w);
            var ueberschrift = wert('ueberschrift'), text = wert('text'), fuss = wert('fusszeile'), pfeil = wert('pfeil');
            if (w.vorlage === 'willkommen' && !text) text = ctx && ctx.stationsname ? ctx.stationsname : '';
            var html = '';
            if (pfeil) html += '<div class="wg-pfeil">' + esc(pfeil) + '</div>';
            if (ueberschrift) html += '<h1 class="wg-h1">' + esc(ueberschrift) + '</h1>';
            if (w.vorlage === 'menuekarte' && text) {
                html += '<table class="wg-karte">' + text.split('\n').filter(function (z) { return z.trim(); }).map(function (z) {
                    var t = z.split('|');
                    return '<tr><td>' + esc(t[0].trim()) + '</td><td class="wg-preis">' + esc((t[1] || '').trim()) + '</td></tr>';
                }).join('') + '</table>';
            } else if (w.vorlage === 'oeffnungszeiten' && !text) {
                html += '<table class="wg-karte wg-zeiten"><tr><td class="wg-dezent">Öffnungszeiten werden geladen …</td></tr></table>';
            } else if (text) {
                html += '<div class="wg-fliess">' + text.split('\n').map(esc).join('<br>') + '</div>';
            }
            if (fuss) html += '<div class="wg-fuss">' + esc(fuss) + '</div>';
            box.innerHTML = html;
            if (w.vorlage === 'oeffnungszeiten' && !text) {
                var NAMEN = { mo: 'Montag', di: 'Dienstag', mi: 'Mittwoch', do: 'Donnerstag', fr: 'Freitag', sa: 'Samstag', so: 'Sonntag' };
                stationsStatus(function (st) {
                    var zp = st && st.config && st.config.zeitplan, tab = box.querySelector('.wg-zeiten');
                    if (!tab) return;
                    if (!zp || !zp.aktiv) {
                        tab.innerHTML = '<tr><td>Täglich geöffnet</td></tr>';
                        return;
                    }
                    tab.innerHTML = ['mo', 'di', 'mi', 'do', 'fr', 'sa', 'so'].map(function (t) {
                        var tag = zp.tage && zp.tage[t];
                        var z = (tag && tag.an) ? (esc(tag.von) + ' – ' + esc(tag.bis === '24:00' ? '24:00' : tag.bis) + ' Uhr') : 'geschlossen';
                        return '<tr><td>' + NAMEN[t] + '</td><td class="wg-preis">' + z + '</td></tr>';
                    }).join('');
                });
            }
            return { stop: stopGroesse };
        }
    };

    /* ---- Ticker ---- */
    WIDGETS.ticker = {
        name: 'Laufschrift',
        beschreibung: 'Eigener Text oder die Schlagzeilen eines RSS-Feeds als Laufband.',
        felder: [
            { key: 'text', label: 'Text (leer, wenn RSS)', typ: 'textarea', default: 'Herzlich willkommen in der Ausstellung' },
            { key: 'rss_url', label: 'RSS-/Atom-Feed (optional)', typ: 'url', default: '' },
            { key: 'geschwindigkeit', label: 'Geschwindigkeit (Pixel/s)', typ: 'zahl', default: 80, min: 10, max: 600 },
            { key: 'trenner', label: 'Trennzeichen', typ: 'text', default: '  •  ' },
            { key: 'richtung', label: 'Richtung', typ: 'auswahl', default: 'links',
              optionen: [{ wert: 'links', label: 'nach links' }, { wert: 'rechts', label: 'nach rechts' }] },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-ticker');
            var stopGroesse = passeAn(el, w, 'schrift', true);
            var band = document.createElement('div');
            band.className = 'wg-band';
            box.appendChild(band);
            var trenner = (w.trenner != null && w.trenner !== '') ? String(w.trenner) : '  •  ';
            var tempo = zahl(w.geschwindigkeit, 80, 10, 600), nachRechts = w.richtung === 'rechts';
            var inhalt = String(w.text || '').replace(/\s*\n\s*/g, trenner);
            var pos = 0, raf = null, letzte = null, breite = 0;
            function setze(text) {
                inhalt = text || '';
                band.innerHTML = '';
                // Zweimal hintereinander, damit die Schleife nahtlos ist.
                for (var i = 0; i < 2; i++) {
                    var s = document.createElement('span');
                    s.className = 'wg-band-teil';
                    s.textContent = inhalt + trenner;
                    band.appendChild(s);
                }
                breite = band.firstChild ? band.firstChild.getBoundingClientRect().width : 0;
            }
            setze(inhalt);
            function schritt(ts) {
                if (letzte !== null) {
                    var dt = (ts - letzte) / 1000;
                    if (!breite) breite = band.firstChild ? band.firstChild.getBoundingClientRect().width : 0;
                    if (breite > 0) {
                        pos += tempo * dt * (nachRechts ? -1 : 1);
                        if (pos >= breite) pos -= breite;
                        if (pos < 0) pos += breite;
                        band.style.transform = 'translateX(' + (-pos) + 'px)';
                    }
                }
                letzte = ts;
                raf = requestAnimationFrame(schritt);
            }
            raf = requestAnimationFrame(schritt);
            var stopPoll = null;
            if (w.rss_url) {
                stopPoll = pollend('/api/widgets/rss?anzahl=20&url=' + encodeURIComponent(w.rss_url), 10 * 60 * 1000,
                    function (d) {
                        var titel = (d.eintraege || []).map(function (e) { return e.titel; }).filter(Boolean);
                        if (titel.length) { pos = 0; setze(titel.join(trenner)); }
                        else if (!inhalt) setze('Keine Meldungen');
                    },
                    function (grund) { if (!inhalt) setze('Feed nicht erreichbar: ' + grund); });
            }
            return { stop: function () { if (raf) cancelAnimationFrame(raf); if (stopPoll) stopPoll(); stopGroesse(); } };
        }
    };

    /* ---- Wetter ---- */
    function wetterSymbol(code) {
        if (code === 0) return '☀';
        if (code === 1 || code === 2) return '🌤';
        if (code === 3) return '☁';
        if (code === 45 || code === 48) return '🌫';
        if (code >= 51 && code <= 57) return '🌦';
        if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return '🌧';
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return '🌨';
        if (code >= 95) return '⛈';
        return '·';
    }
    WIDGETS.wetter = {
        name: 'Wetter',
        beschreibung: 'Aktuelles Wetter und drei Tage Vorschau (Open-Meteo, ohne Schlüssel).',
        felder: [
            { key: 'ort', label: 'Ortsname (nur Anzeige)', typ: 'text', default: '' },
            { key: 'lat', label: 'Breitengrad', typ: 'zahl', default: 52.52, min: -90, max: 90 },
            { key: 'lon', label: 'Längengrad', typ: 'zahl', default: 13.405, min: -180, max: 180 },
            { key: 'einheit', label: 'Einheit', typ: 'auswahl', default: 'c',
              optionen: [{ wert: 'c', label: '°C' }, { wert: 'f', label: '°F' }] },
            { key: 'tage', label: 'Vorschau-Tage (0–3)', typ: 'zahl', default: 3, min: 0, max: 3 },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-wetter wg-mitte');
            var stopGroesse = passeAn(el, w);
            box.innerHTML = '<div class="wg-dezent">Wetter wird geladen …</div>';
            var tage = zahl(w.tage, 3, 0, 3);
            var url = '/api/widgets/wetter?lat=' + encodeURIComponent(zahl(w.lat, 52.52)) + '&lon=' + encodeURIComponent(zahl(w.lon, 13.405)) + '&einheit=' + (w.einheit === 'f' ? 'f' : 'c');
            var stopPoll = pollend(url, 15 * 60 * 1000, function (d) {
                var a = d.aktuell || {}, einheit = d.einheit || '°C';
                var html = '<div class="wg-wetter-jetzt"><span class="wg-wetter-symbol">' + wetterSymbol(a.code) + '</span>' +
                    '<span class="wg-wetter-temp">' + (a.temperatur != null ? Math.round(a.temperatur) + einheit : '–') + '</span></div>' +
                    '<div class="wg-wetter-text">' + esc(a.text || '') + (w.ort ? ' · ' + esc(w.ort) : '') + '</div>';
                if (tage > 0) {
                    html += '<div class="wg-wetter-tage">' + (d.tage || []).slice(1, 1 + tage).map(function (t) {
                        var dt = new Date(t.datum + 'T12:00:00');
                        return '<div class="wg-wetter-tag"><div>' + esc(dt.toLocaleDateString(locale(ctx), { weekday: 'short' })) + '</div>' +
                            '<div class="wg-wetter-symbol-klein">' + wetterSymbol(t.code) + '</div>' +
                            '<div>' + (t.max != null ? Math.round(t.max) + '°' : '–') + ' <span class="wg-dim">' + (t.min != null ? Math.round(t.min) + '°' : '–') + '</span></div></div>';
                    }).join('') + '</div>';
                }
                box.innerHTML = html;
                dezent(box, d.veraltet ? 'Stand: älter, Wetterdienst gerade nicht erreichbar' : '');
            }, function (grund) {
                if (box.querySelector('.wg-wetter-jetzt')) dezent(box, 'Wetterdienst nicht erreichbar');
                else box.innerHTML = '<div class="wg-dezent">Wetter nicht verfügbar: ' + esc(grund) + '</div>';
            });
            return { stop: function () { stopPoll(); stopGroesse(); } };
        }
    };

    /* ---- RSS-Liste ---- */
    WIDGETS.rss = {
        name: 'Nachrichten (RSS)',
        beschreibung: 'Die neuesten Einträge eines RSS-/Atom-Feeds als Liste — oder einzeln im Wechsel.',
        felder: [
            { key: 'url', label: 'Feed-Adresse', typ: 'url', default: '' },
            { key: 'anzahl', label: 'Anzahl Einträge', typ: 'zahl', default: 6, min: 1, max: 20 },
            { key: 'wechsel_s', label: 'Einzeln zeigen, Sekunden je Eintrag (0 = alle als Liste)', typ: 'zahl', default: 0, min: 0, max: 600 },
            { key: 'quelle', label: 'Quelle anzeigen', typ: 'bool', default: true },
            { key: 'zeit', label: 'Zeit anzeigen', typ: 'bool', default: true },
            { key: 'vorschau_text', label: 'Kurztext anzeigen', typ: 'bool', default: false },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-rss');
            var stopGroesse = passeAn(el, w);
            if (!w.url) { box.innerHTML = '<div class="wg-dezent">Keine Feed-Adresse eingetragen</div>'; return { stop: stopGroesse }; }
            box.innerHTML = '<div class="wg-dezent">Nachrichten werden geladen …</div>';
            var wechsel = zahl(w.wechsel_s, 0, 0, 600), eintraege = [], idx = 0, wechselTimer = null;
            function zeile(e) {
                var meta = [];
                if (w.quelle !== false && e.quelle) meta.push(esc(e.quelle));
                if (w.zeit !== false && e.zeit) {
                    var d = new Date(e.zeit);
                    if (!isNaN(d)) meta.push(esc(d.toLocaleString(locale(ctx), { weekday: 'short', hour: '2-digit', minute: '2-digit' })));
                }
                return '<div class="wg-rss-eintrag"><div class="wg-rss-titel">' + esc(e.titel) + '</div>' +
                    (w.vorschau_text && e.text ? '<div class="wg-rss-text">' + esc(e.text) + '</div>' : '') +
                    (meta.length ? '<div class="wg-rss-meta">' + meta.join(' · ') + '</div>' : '') + '</div>';
            }
            function zeige() {
                if (!eintraege.length) { box.innerHTML = '<div class="wg-dezent">Keine Meldungen</div>'; return; }
                if (wechsel > 0) {
                    box.innerHTML = '<div class="wg-rss-einzeln">' + zeile(eintraege[idx % eintraege.length]) + '</div>';
                } else {
                    box.innerHTML = eintraege.map(zeile).join('');
                }
            }
            var stopPoll = pollend('/api/widgets/rss?anzahl=' + zahl(w.anzahl, 6, 1, 20) + '&url=' + encodeURIComponent(w.url), 10 * 60 * 1000,
                function (d) {
                    eintraege = d.eintraege || [];
                    zeige();
                    if (d.veraltet) dezent(box, 'Stand: älter, Feed gerade nicht erreichbar');
                },
                function (grund) {
                    if (eintraege.length) dezent(box, 'Feed nicht erreichbar');
                    else box.innerHTML = '<div class="wg-dezent">Feed nicht erreichbar: ' + esc(grund) + '</div>';
                });
            if (wechsel > 0) wechselTimer = setInterval(function () { idx++; zeige(); }, wechsel * 1000);
            return { stop: function () { stopPoll(); if (wechselTimer) clearInterval(wechselTimer); stopGroesse(); } };
        }
    };

    /* ---- Kalender ---- */
    WIDGETS.kalender = {
        name: 'Kalender (ICS)',
        beschreibung: 'Termine aus einem iCalendar-Abo: heute, die nächsten Tage oder als Raumbelegung.',
        felder: [
            { key: 'url', label: 'ICS-Adresse', typ: 'url', default: '' },
            { key: 'ansicht', label: 'Ansicht', typ: 'auswahl', default: 'heute', optionen: [
                { wert: 'heute', label: 'Heute' }, { wert: 'woche', label: 'Nächste 7 Tage' }, { wert: 'raum', label: 'Raumbelegung (Jetzt / Danach)' }] },
            { key: 'anzahl', label: 'Höchstens Termine', typ: 'zahl', default: 8, min: 1, max: 30 },
            { key: 'zwoelf', label: '12-Stunden-Format', typ: 'bool', default: false },
            { key: 'titel', label: 'Überschrift (leer = Kalendername)', typ: 'text', default: '' },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-kalender');
            var stopGroesse = passeAn(el, w);
            if (!w.url) { box.innerHTML = '<div class="wg-dezent">Keine ICS-Adresse eingetragen</div>'; return { stop: stopGroesse }; }
            box.innerHTML = '<div class="wg-dezent">Termine werden geladen …</div>';
            var jetzt = zeitgeber(ctx), daten = null, timer = null;
            var anzahl = zahl(w.anzahl, 8, 1, 30), ansicht = w.ansicht || 'heute';
            function zeit(iso) { return uhrzeit(new Date(iso), ctx, false, null, !!w.zwoelf); }
            function tagVon(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
            function zeige() {
                if (!daten) return;
                var now = jetzt(), heute = tagVon(now), termine = daten.termine || [];
                var kopf = '<div class="wg-kal-kopf">' + esc(w.titel || daten.name || 'Termine') + '</div>';
                var html = '';
                function eintrag(t, mitTag) {
                    var s = new Date(t.start), e = new Date(t.ende);
                    var zeitText = t.ganztags ? 'ganztägig' : zeit(t.start) + (e > s ? ' – ' + zeit(t.ende) : '');
                    return '<div class="wg-kal-termin' + (s <= now && e > now ? ' wg-kal-jetzt' : '') + '">' +
                        '<div class="wg-kal-zeit">' + (mitTag ? esc(datum(s, ctx)) + ' · ' : '') + zeitText + '</div>' +
                        '<div class="wg-kal-titel">' + esc(t.titel) + (t.ort ? ' <span class="wg-dim">' + esc(t.ort) + '</span>' : '') + '</div></div>';
                }
                if (ansicht === 'raum') {
                    var laufend = termine.filter(function (t) { return new Date(t.start) <= now && new Date(t.ende) > now && !t.ganztags; })[0];
                    var kommend = termine.filter(function (t) { return new Date(t.start) > now && !t.ganztags; })[0];
                    html += '<div class="wg-kal-raum"><div class="wg-kal-label">Jetzt</div>' +
                        (laufend ? '<div class="wg-kal-gross">' + esc(laufend.titel) + '</div><div class="wg-dim">bis ' + zeit(laufend.ende) + ' Uhr</div>'
                                 : '<div class="wg-kal-gross wg-kal-frei">Frei</div>') +
                        '<div class="wg-kal-label">Danach</div>' +
                        (kommend ? '<div>' + esc(kommend.titel) + '</div><div class="wg-dim">' + esc(datum(new Date(kommend.start), ctx)) + ' · ' + zeit(kommend.start) + ' Uhr</div>'
                                 : '<div class="wg-dim">Keine weiteren Termine</div>') + '</div>';
                } else {
                    var bis = new Date(heute.getTime() + (ansicht === 'woche' ? 7 : 1) * 86400000);
                    var liste = termine.filter(function (t) { return new Date(t.ende) > now && new Date(t.start) < bis; }).slice(0, anzahl);
                    html += liste.length ? liste.map(function (t) { return eintrag(t, ansicht === 'woche'); }).join('')
                                         : '<div class="wg-dezent">' + (ansicht === 'woche' ? 'Keine Termine in den nächsten 7 Tagen' : 'Heute keine Termine') + '</div>';
                }
                box.innerHTML = kopf + html;
                if (daten.veraltet) dezent(box, 'Stand: älter, Kalender gerade nicht erreichbar');
            }
            var stopPoll = pollend('/api/widgets/ics?tage=14&url=' + encodeURIComponent(w.url), 10 * 60 * 1000,
                function (d) { daten = d; zeige(); },
                function (grund) {
                    if (daten) dezent(box, 'Kalender nicht erreichbar');
                    else box.innerHTML = '<div class="wg-dezent">Kalender nicht erreichbar: ' + esc(grund) + '</div>';
                });
            timer = setInterval(zeige, 30000);
            return { stop: function () { stopPoll(); clearInterval(timer); stopGroesse(); } };
        }
    };

    /* ---- QR-Code ---- */
    WIDGETS.qr = {
        name: 'QR-Code',
        beschreibung: 'QR-Code aus Text oder Adresse — leer zeigt er die Verwaltung dieser Station.',
        felder: [
            { key: 'inhalt', label: 'Inhalt (leer = Adresse der Verwaltung)', typ: 'text', default: '' },
            { key: 'beschriftung', label: 'Beschriftung', typ: 'text', default: '' },
            { key: 'modulfarbe', label: 'Farbe der Module', typ: 'farbe', default: '#132040' },
            { key: 'codegrund', label: 'Grund des Codes', typ: 'farbe', default: '#F6F5F0' },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-qr wg-mitte');
            var stopGroesse = passeAn(el, w);
            function zeichne(inhalt) {
                var s = QR.svg(inhalt, { farbe: farbe(w.modulfarbe, '#132040'), hintergrund: farbe(w.codegrund, '#F6F5F0') });
                box.innerHTML = (s ? '<div class="wg-qr-code">' + s + '</div>'
                                   : '<div class="wg-dezent">Inhalt zu lang für einen QR-Code (höchstens 213 Zeichen)</div>') +
                    (w.beschriftung ? '<div class="wg-qr-text">' + esc(w.beschriftung) + '</div>' : '');
            }
            if (w.inhalt && String(w.inhalt).trim()) {
                zeichne(String(w.inhalt).trim());
            } else {
                box.innerHTML = '<div class="wg-dezent">Adresse wird ermittelt …</div>';
                stationsStatus(function (st) { zeichne((st && st.remote_url) || location.origin + '/admin'); });
            }
            return { stop: stopGroesse };
        }
    };

    /* ---- Webseite ---- */
    WIDGETS.webseite = {
        name: 'Webseite',
        beschreibung: 'Eine Webseite im Rahmen, mit Zoom und Neuladen — samt Hinweis, wenn sie sich nicht einbetten lässt.',
        felder: [
            { key: 'url', label: 'Adresse', typ: 'url', default: 'https://' },
            { key: 'reload_s', label: 'Neu laden alle … Sekunden (0 = nie)', typ: 'zahl', default: 0, min: 0, max: 86400 },
            { key: 'zoom', label: 'Zoom (%)', typ: 'zahl', default: 100, min: 25, max: 300 },
            { key: 'interaktiv', label: 'Berührung durchlassen', typ: 'bool', default: false },
            { key: 'hintergrund', label: 'Hintergrund', typ: 'farbe', default: '' },
        ],
        render: function (el, w) {
            var box = huelle(el, w, 'wg-web');
            var url = String(w.url || '').trim();
            if (!/^https?:\/\/./.test(url)) { box.innerHTML = '<div class="wg-dezent">Keine gültige Adresse (http:// oder https://)</div>'; return { stop: function () {} }; }
            var zoom = zahl(w.zoom, 100, 25, 300) / 100;
            var rahmen = document.createElement('iframe');
            rahmen.className = 'wg-web-rahmen';
            rahmen.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms');
            rahmen.style.width = (100 / zoom) + '%';
            rahmen.style.height = (100 / zoom) + '%';
            rahmen.style.transform = 'scale(' + zoom + ')';
            rahmen.style.pointerEvents = w.interaktiv ? 'auto' : 'none';
            rahmen.src = url;
            box.appendChild(rahmen);
            var timer = null, reload = zahl(w.reload_s, 0, 0, 86400);
            if (reload > 0) timer = setInterval(function () { rahmen.src = url; }, reload * 1000);
            // Ob die Seite sich einbetten laesst, sagt uns der Kern anhand der
            // Kopfzeilen — der Rahmen selbst schweigt dazu.
            fetch('/api/widgets/einbettbar?url=' + encodeURIComponent(url)).then(function (r) { return r.json(); }).then(function (d) {
                if (d && d.einbettbar === false) dezent(box, 'Seite lässt sich nicht einbetten (' + (d.grund || 'vom Anbieter untersagt') + ')');
            }).catch(function () { /* dann eben ohne Hinweis */ });
            return { stop: function () { if (timer) clearInterval(timer); rahmen.src = 'about:blank'; } };
        }
    };

    /* ---- Eigenes HTML-Widget ---- */
    WIDGETS.html = {
        name: 'Eigenes Widget (HTML)',
        beschreibung: 'Ein Ordner unter widgets/ mit index.html — die Einstellungen kommen als Query und window.LZ_WIDGET_EINSTELLUNGEN an.',
        felder: [
            { key: 'name', label: 'Ordnername unter widgets/', typ: 'text', default: 'beispiel' },
            { key: 'einstellungen', label: 'Einstellungen (eine Zeile je schluessel=wert)', typ: 'textarea', default: '' },
            { key: 'reload_s', label: 'Neu laden alle … Sekunden (0 = nie)', typ: 'zahl', default: 0, min: 0, max: 86400 },
        ],
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-html');
            var name = String(w.name || '').trim();
            if (!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(name)) { box.innerHTML = '<div class="wg-dezent">Ungültiger Widget-Ordner</div>'; return { stop: function () {} }; }
            var einst = {};
            String(w.einstellungen || '').split('\n').forEach(function (z) {
                var i = z.indexOf('=');
                if (i > 0) einst[z.slice(0, i).trim()] = z.slice(i + 1).trim();
            });
            var q = Object.keys(einst).map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(einst[k]); });
            q.push('sprache=' + encodeURIComponent((ctx && ctx.sprache) || 'de'));
            q.push('station=' + encodeURIComponent((ctx && ctx.stationsname) || ''));
            if (ctx && ctx.zeit instanceof Date && !isNaN(ctx.zeit)) q.push('zeit=' + encodeURIComponent(ctx.zeit.toISOString()));
            var src = '/widgets/' + name + '/index.html?' + q.join('&');
            var rahmen = document.createElement('iframe');
            rahmen.className = 'wg-web-rahmen';
            rahmen.style.pointerEvents = 'none';
            rahmen.onload = function () {
                try { rahmen.contentWindow.LZ_WIDGET_EINSTELLUNGEN = einst; } catch (e) { /* fremd */ }
            };
            rahmen.src = src;
            box.appendChild(rahmen);
            var timer = null, reload = zahl(w.reload_s, 0, 0, 86400);
            if (reload > 0) timer = setInterval(function () { rahmen.src = src; }, reload * 1000);
            return { stop: function () { if (timer) clearInterval(timer); rahmen.src = 'about:blank'; } };
        }
    };

    /* ---- Zaehler ---- */
    WIDGETS.zaehler = {
        name: 'Zähler',
        beschreibung: 'Countdown bis zu einem Zeitpunkt — oder die Zeit, die seit einem Zeitpunkt vergangen ist.',
        felder: [
            { key: 'ziel', label: 'Zeitpunkt (JJJJ-MM-TTTHH:MM)', typ: 'text', default: '' },
            { key: 'beschriftung', label: 'Beschriftung', typ: 'text', default: 'Noch' },
            { key: 'danach', label: 'Text, wenn erreicht', typ: 'text', default: 'Es ist soweit' },
            { key: 'modus', label: 'Richtung', typ: 'auswahl', default: 'countdown',
              optionen: [{ wert: 'countdown', label: 'Herunterzählen' }, { wert: 'countup', label: 'Hochzählen (seit)' }] },
            { key: 'sekunden', label: 'Sekunden anzeigen', typ: 'bool', default: true },
        ].concat(FARBFELDER),
        render: function (el, w, ctx) {
            var box = huelle(el, w, 'wg-zaehler wg-mitte');
            var stopGroesse = passeAn(el, w);
            var ziel = new Date(String(w.ziel || '').trim());
            if (isNaN(ziel)) { box.innerHTML = '<div class="wg-dezent">Kein gültiger Zeitpunkt (JJJJ-MM-TTTHH:MM)</div>'; return { stop: stopGroesse }; }
            var jetzt = zeitgeber(ctx), hoch = w.modus === 'countup';
            box.innerHTML = '<div class="wg-zaehler-label">' + esc(w.beschriftung || '') + '</div><div class="wg-zaehler-zahl"></div><div class="wg-zaehler-bis wg-dim"></div>';
            var zahlEl = box.querySelector('.wg-zaehler-zahl'), bisEl = box.querySelector('.wg-zaehler-bis'), labelEl = box.querySelector('.wg-zaehler-label');
            bisEl.textContent = (hoch ? 'seit ' : 'bis ') + datum(ziel, ctx, null, true) + ', ' + uhrzeit(ziel, ctx, false) + ' Uhr';
            function zwei(n) { return (n < 10 ? '0' : '') + n; }
            function tick() {
                var diff = hoch ? jetzt() - ziel : ziel - jetzt();
                if (diff < 0) {
                    labelEl.textContent = '';
                    zahlEl.textContent = w.danach || 'Es ist soweit';
                    zahlEl.classList.add('wg-zaehler-fertig');
                    return;
                }
                var s = Math.floor(diff / 1000), tage = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), sek = s % 60;
                var teile = [];
                if (tage > 0) teile.push('<span class="wg-zaehler-block"><b>' + tage + '</b><small>' + (tage === 1 ? 'Tag' : 'Tage') + '</small></span>');
                teile.push('<span class="wg-zaehler-block"><b>' + zwei(h) + '</b><small>Std.</small></span>');
                teile.push('<span class="wg-zaehler-block"><b>' + zwei(m) + '</b><small>Min.</small></span>');
                if (w.sekunden !== false) teile.push('<span class="wg-zaehler-block"><b>' + zwei(sek) + '</b><small>Sek.</small></span>');
                zahlEl.innerHTML = teile.join('');
            }
            tick();
            var timer = setInterval(tick, 500);
            return { stop: function () { clearInterval(timer); stopGroesse(); } };
        }
    };

    /* ======================================================================
       Schnittstelle
       ====================================================================== */
    var AKTIVE = [];

    function katalog() {
        return Object.keys(WIDGETS).map(function (typ) {
            var w = WIDGETS[typ];
            return { typ: typ, name: w.name, beschreibung: w.beschreibung, felder: w.felder.map(function (f) { return Object.assign({}, f); }) };
        });
    }

    function render(el, widget, ctx) {
        ladeCss();
        widget = widget || {};
        ctx = ctx || {};
        var def = WIDGETS[widget.typ];
        if (!def) {
            el.innerHTML = '<div class="wg wg-box"><div class="wg-dezent">' +
                (widget.typ ? 'Unbekanntes Widget: ' + esc(widget.typ) : 'Kein Widget gewählt') + '</div></div>';
            return { stop: function () {} };
        }
        var ergebnis;
        try {
            ergebnis = def.render(el, widget, ctx) || {};
        } catch (e) {
            el.innerHTML = '<div class="wg wg-box"><div class="wg-dezent">Widget „' + esc(def.name) + '" konnte nicht dargestellt werden</div></div>';
            ergebnis = {};
        }
        var eintrag = { stop: function () {
            try { if (typeof ergebnis.stop === 'function') ergebnis.stop(); } catch (e) { /* beim Widget */ }
            var i = AKTIVE.indexOf(eintrag);
            if (i >= 0) AKTIVE.splice(i, 1);
        } };
        AKTIVE.push(eintrag);
        return eintrag;
    }

    function stopAll() {
        AKTIVE.slice().forEach(function (a) { a.stop(); });
    }

    var LZ_WIDGETS = { render: render, katalog: katalog, stopAll: stopAll, qr: QR, typen: Object.keys(WIDGETS) };

    if (typeof module !== 'undefined' && module.exports) module.exports = LZ_WIDGETS;
    if (typeof window !== 'undefined') {
        window.LZ_WIDGETS = LZ_WIDGETS;
        if (typeof document !== 'undefined' && document.head) ladeCss();
    }
})(typeof window !== 'undefined' ? window : this);

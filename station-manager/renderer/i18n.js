/* Oberflaechensprache Deutsch / Englisch.

   Deutsch ist die Quellsprache: im HTML, im JavaScript und in den Meldungen
   des Servers steht Deutsch. Dieser Kern uebersetzt ins Englische, indem er
   jeden Textknoten und die Attribute placeholder/title/alt/aria-label mit dem
   Woerterbuch abgleicht (`window.LZ_I18N_EN`, aus `i18n-en.js`).

   WARUM EIN BEOBACHTER UND NICHT t() AN JEDER STELLE. Ein grosser Teil der
   Texte kommt nicht aus der Oberflaeche, sondern vom Server: Sensor-Zustand,
   Befunde der Zustandspruefung, Hinweise des Medien-Checks. Die API bleibt
   deutsch, weil der Station Manager und Skripte sie lesen. Der
   MutationObserver erwischt alles, was ins DOM kommt — ob aus dem Template,
   aus app.js oder aus einer API-Antwort. Meldungen mit Werten darin
   (Dateinamen, Zahlen) deckt `muster` ab: regulaere Ausdruecke, deren
   Gruppen selbst wieder uebersetzt werden.

   Absaetze mit Auszeichnung darin (<strong>, <code>) tragen
   `data-i18n="schluessel"` und stehen als Ganzes in `html` — sonst zerfielen
   sie in Bruchstuecke, die sich einzeln nicht sinnvoll uebersetzen lassen.

   Die Wahl gilt je Browser (localStorage) und faellt ohne Wahl auf die
   Sprache des Browsers zurueck. Umgeschaltet wird mit #lang-switch.

   Dieselbe Datei liegt als station-manager/renderer/i18n.js im Station
   Manager; tests/test_i18n.py haelt beide gleich. */
(function () {
    'use strict';

    var SCHLUESSEL = 'lz-sprache';
    var ATTRIBUTE = ['placeholder', 'title', 'alt', 'aria-label'];
    var UEBERSPRINGEN = { SCRIPT: 1, STYLE: 1, CODE: 1, TEXTAREA: 1 };

    function gespeichert() {
        try { return localStorage.getItem(SCHLUESSEL); } catch (e) { return null; }
    }

    function startSprache() {
        // `?lang=en` in der Adresse gewinnt und wird gemerkt — so laesst sich
        // auch ein Kiosk ohne Tastatur auf eine Sprache festlegen.
        var url = (location.search.match(/[?&]lang=(de|en)\b/) || [])[1];
        if (url) {
            try { localStorage.setItem(SCHLUESSEL, url); } catch (e) { /* nur jetzt */ }
            return url;
        }
        var s = gespeichert();
        if (s === 'de' || s === 'en') return s;
        var nav = (navigator.language || 'de').toLowerCase();
        return nav.indexOf('de') === 0 ? 'de' : 'en';
    }

    var sprache = startSprache();
    /* Das Kern-Woerterbuch plus alle, die Erweiterungen mitbringen
       (`static/i18n/<modul>.en.js` legt seines in `window.LZ_I18N_EN_EXTRA`
       ab). Spaetere Eintraege gewinnen; Muster werden angehaengt. */
    var wb = zusammen(window.LZ_I18N_EN, window.LZ_I18N_EN_EXTRA);
    var muster = (wb.muster || []).map(function (m) { return [new RegExp(m[0]), m[1]]; });

    function norm(s) { return s.replace(/\s+/g, ' ').trim(); }

    function zusammen(kern, extras) {
        var w = { texte: {}, muster: [], html: {} };
        [kern].concat(extras || []).forEach(function (t) {
            if (!t) return;
            Object.keys(t.texte || {}).forEach(function (k) { w.texte[k] = t.texte[k]; });
            // Nur echte Paare [Regex, Ersatz]: ein falsch geformtes
            // Woerterbuch darf die Uebersetzung der ganzen Seite nicht kippen.
            (Array.isArray(t.muster) ? t.muster : []).forEach(function (m) {
                if (Array.isArray(m) && typeof m[0] === 'string' && typeof m[1] === 'string') w.muster.push(m);
            });
            Object.keys(t.html || {}).forEach(function (k) { w.html[k] = t.html[k]; });
        });
        return w;
    }

    /* Uebersetzen: erst exakt, dann nach Muster. Gruppen eines Musters werden
       rekursiv uebersetzt — „Keine Messung ({Sensor-Zustand})" bekommt so
       auch den eingebetteten Zustand auf Englisch. */
    function t(de) {
        if (sprache !== 'en' || de == null) return de;
        var s = String(de);
        var kern = norm(s);
        if (!kern) return s;
        var en = uebersetze(kern, 0);
        if (en === null) return s;
        // Fuehrende und folgende Leerzeichen erhalten: sie trennen den
        // Textknoten von seinen Nachbarn (<strong>X</strong> auf …).
        var vorn = s.match(/^\s*/)[0], hinten = s.match(/\s*$/)[0];
        return vorn + en + hinten;
    }

    function uebersetze(kern, tiefe) {
        if (Object.prototype.hasOwnProperty.call(wb.texte, kern)) return wb.texte[kern];
        if (tiefe > 3) return null;
        for (var i = 0; i < muster.length; i++) {
            var m = kern.match(muster[i][0]);
            if (m) {
                return muster[i][1].replace(/\{(\d)\}/g, function (_, n) {
                    var g = m[Number(n)] || '';
                    var u = uebersetze(norm(g), tiefe + 1);
                    return u === null ? g : u;
                });
            }
        }
        return null;
    }

    /* ---- DOM ---- */

    /* Original merken, damit der Rueckweg nach Deutsch verlustfrei ist.
       Weicht der Wert von dem ab, was hier zuletzt gesetzt wurde, hat die
       Seite ihn neu geschrieben — dann ist ER das neue Original. */
    function knotenText(n) {
        if (n.__lzGesetzt === undefined || n.nodeValue !== n.__lzGesetzt) n.__lzDe = n.nodeValue;
        var ziel = t(n.__lzDe);
        n.__lzGesetzt = ziel;
        if (n.nodeValue !== ziel) n.nodeValue = ziel;
    }

    function knotenAttribute(e) {
        ATTRIBUTE.forEach(function (a) {
            if (!e.hasAttribute(a)) return;
            var de = e.__lzAttrDe = e.__lzAttrDe || {};
            var gesetzt = e.__lzAttr = e.__lzAttr || {};
            var aktuell = e.getAttribute(a);
            if (de[a] === undefined || aktuell !== gesetzt[a]) de[a] = aktuell;
            var ziel = t(de[a]);
            gesetzt[a] = ziel;
            if (aktuell !== ziel) e.setAttribute(a, ziel);
        });
    }

    function knotenHtml(e) {
        if (e.__lzHtmlDe === undefined) e.__lzHtmlDe = e.innerHTML;
        var ziel = (sprache === 'en' && wb.html[e.getAttribute('data-i18n')]) || e.__lzHtmlDe;
        if (e.innerHTML !== ziel) e.innerHTML = ziel;
    }

    function wende(wurzel) {
        if (!wurzel) return;
        if (wurzel.nodeType === 3) {
            var p = wurzel.parentNode;
            if (p && !UEBERSPRINGEN[p.nodeName] && !(p.closest && p.closest('[data-i18n]'))) knotenText(wurzel);
            return;
        }
        if (wurzel.nodeType !== 1 || UEBERSPRINGEN[wurzel.nodeName]) return;
        if (wurzel.hasAttribute('data-i18n')) { knotenHtml(wurzel); return; }
        var eltern = wurzel.parentNode;
        if (eltern && eltern.closest && eltern.closest('[data-i18n]')) return;
        knotenAttribute(wurzel);
        var kind = wurzel.firstChild;
        while (kind) { wende(kind); kind = kind.nextSibling; }
    }

    var beobachter = new MutationObserver(function (liste) {
        beobachter.disconnect();
        liste.forEach(function (m) {
            if (m.type === 'characterData') wende(m.target);
            else if (m.type === 'attributes') { if (m.target.nodeType === 1) knotenAttribute(m.target); }
            else m.addedNodes.forEach(wende);
        });
        beobachte();
    });

    function beobachte() {
        beobachter.observe(document.body, {
            childList: true, subtree: true, characterData: true,
            attributes: true, attributeFilter: ATTRIBUTE,
        });
    }

    function alles() {
        document.documentElement.lang = sprache;
        if (document.title) {
            if (document.__lzTitel === undefined) document.__lzTitel = document.title;
            document.title = t(document.__lzTitel);
        }
        beobachter.disconnect();
        wende(document.body);
        var knopf = document.getElementById('lang-switch');
        if (knopf) {
            // Der Knopf nennt die ANDERE Sprache — dorthin fuehrt der Klick.
            knopf.textContent = sprache === 'en' ? 'DE' : 'EN';
            knopf.title = sprache === 'en' ? 'Deutsch' : 'English';
            knopf.setAttribute('aria-label', knopf.title);
        }
        beobachte();
    }

    function setzeSprache(s) {
        sprache = (s === 'en') ? 'en' : 'de';
        try { localStorage.setItem(SCHLUESSEL, sprache); } catch (e) { /* nur fuer diese Sitzung */ }
        // Ein `?lang=` in der Adresse wuerde die Wahl beim Neuladen ueberstimmen.
        if (/[?&]lang=/.test(location.search) && history.replaceState) {
            var rest = location.search.replace(/([?&])lang=(de|en)\b&?/, '$1').replace(/[?&]$/, '');
            history.replaceState(null, '', location.pathname + rest + location.hash);
        }
        alles();
        document.dispatchEvent(new CustomEvent('lz-sprache', { detail: sprache }));
    }

    window.LZ = window.LZ || {};
    window.LZ.t = t;
    window.LZ.sprache = function () { return sprache; };
    window.LZ.setzeSprache = setzeSprache;

    document.addEventListener('DOMContentLoaded', function () {
        var knopf = document.getElementById('lang-switch');
        if (knopf) knopf.addEventListener('click', function () {
            setzeSprache(sprache === 'en' ? 'de' : 'en');
        });
        alles();
    });
})();

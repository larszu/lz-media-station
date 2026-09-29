/* Bringt den Widget-Katalog in den Admin (3.0, Welle 2).

   `static/anzeige/widgets.js` gehoert zur Anzeige und wird nur dort
   automatisch eingebunden. Der Layout-Editor (static/module/layout-editor.js)
   fragt aber `window.LZ_WIDGETS.katalog()`, um fuer eine Widget-Region ein
   Formular statt eines rohen JSON-Felds zu bauen. Dieses Modul laedt die
   Datei im Admin nach — als Datei unter static/module/, ohne admin.html oder
   web_ui.py anzufassen. Bis sie da ist, zeigt der Editor sein freies
   Formular; er fragt den Katalog erst, wenn jemand eine Widget-Region
   anklickt. */
(function () {
    'use strict';
    if (window.LZ_WIDGETS) return;
    var s = document.createElement('script');
    s.src = '/static/anzeige/widgets.js';
    s.async = true;
    document.head.appendChild(s);
})();

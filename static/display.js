(function () {
    'use strict';

    var videoA = document.getElementById('video-a');
    var videoB = document.getElementById('video-b');
    var imgA = document.getElementById('img-a');
    var imgB = document.getElementById('img-b');
    var audioEl = document.getElementById('audio-player');

    var activeVideoEl = videoA, standbyVideoEl = videoB;
    var activeImgEl = imgA, standbyImgEl = imgB;

    var currentHash = '';
    var currentVideoFile = null;
    var currentAudioFile = null;
    var currentImageSet = '';
    // Kennung der aktuell laufenden Liste (Dateien + Shuffle-Schalter). Die
    // Wiedergabe wird NUR neu aufgesetzt, wenn sich diese Kennung aendert.
    //
    // Vorher stand hier `currentVideoFile !== videos[0]`, und das war ein
    // echter Defekt bei mehr als einer Datei: sobald das erste Video endete
    // und auf das zweite weiterschaltete, war `currentVideoFile` nicht mehr
    // `videos[0]` — der naechste Poll (500 ms spaeter) sprang deshalb zurueck
    // auf das erste. Eine Playlist mit mehreren Videos spielte faktisch nur
    // das erste, immer wieder. Fuer Audio galt dasselbe.
    var currentVideoSet = '';
    var currentAudioSet = '';
    var zoneVideos = [];
    var videoIndex = 0;
    var slideshowTimer = null;
    var audioIndex = 0;
    var zoneAudioList = [];
    // Wiedergabe-Optionen der laufenden Zone.
    var zoneEinmal = false;

    var hintEl = document.getElementById('hint');
    var startAttempted = false;
    var resumeEnabled = false;
    var videoPositions = {}; // { filename: seconds }
    var redirectTimer = null;
    var redirected = false;
    var expectedPlayable = false;
    var lastPlayableAt = Date.now();

    // ESC -> zurück zur Admin-Seite
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.keyCode === 27) {
            window.location.href = '/admin';
        }
    });

    setInterval(poll, 500);
    poll();

    function showHint(html) {
        if (!hintEl) return;
        hintEl.innerHTML = html;
        hintEl.classList.add('show');
    }
    function hideHint() {
        if (hintEl) hintEl.classList.remove('show');
    }

    async function poll() {
        try {
            var resp = await fetch('/api/scene');
            var scene = await resp.json();

            // Der Wochenplan steht VOR allem anderen: ausserhalb der
            // Oeffnungszeit bleibt der Schirm schwarz und der Ton aus — kein
            // Hinweistext ("Warte auf Sensor" waere nachts schlicht falsch)
            // und vor allem KEIN Auto-Start, der die Steuerung wieder
            // anwerfen wuerde.
            if (scene.geschlossen) {
                if (currentHash) { fadeAllOut(); currentHash = ''; }
                clearRedirect();
                hideHint();
                return;
            }

            if (!scene.active) {
                if (currentHash) { fadeAllOut(); currentHash = ''; }
                if (!startAttempted) {
                    startAttempted = true;
                    fetch('/api/start', { method: 'POST' }).catch(function () {});
                }
                clearRedirect();
                showHint('<strong>Starte Sensor-Steuerung...</strong>');
                return;
            }

            var zone = scene.zone;
            if (!zone) {
                clearRedirect();
                showHint('<strong>Warte auf Sensor</strong><br><br>Bewege etwas vor den Sensor um eine Zone auszuwählen.');
                return;
            }
            var zd = scene[zone] || { videos: [], images: [], audio: [] };
            var hasMedia = (zd.videos && zd.videos.length) || (zd.images && zd.images.length) || (zd.audio && zd.audio.length);
            if (!hasMedia) {
                showHint('<strong>Zone "' + zone + '" ist leer</strong><br><br>Konfiguriere Medien im Admin-Panel:<br><code>/admin</code>');
                scheduleAdminRedirect(5000);
                return;
            }
            hideHint();
            clearRedirect();
            var hash = zone + JSON.stringify(zd);

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
                videoA.volume = vid * master;
                videoB.volume = vid * master;
            }
            if (master !== null && aud !== null) {
                audioEl.volume = aud * master;
            }

            resumeEnabled = !!scene.video_resume;

            if (hash === currentHash) return;
            currentHash = hash;
            expectedPlayable = true;
            lastPlayableAt = Date.now();
            applyScene(zd, scene.image_interval_s || 5);
        } catch (e) { /* server unreachable */ }

        // Watchdog: es gibt Medien-Zuweisung, aber es wurde nichts abspielbar geladen.
        if (expectedPlayable && (Date.now() - lastPlayableAt) > 12000) {
            showHint('<strong>Medien konnten nicht geladen werden</strong><br><br>Zur Admin-Seite...');
            scheduleAdminRedirect(1200);
        }
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

    function applyScene(zd, imgInterval) {
        var videos = zd.videos || [];
        var images = zd.images || [];
        var audio = zd.audio || [];
        var shuffle = !!zd.shuffle;
        zoneEinmal = !!zd.einmal;
        var bildzeiten = zd.bildzeiten || {};

        if (videos.length > 0) {
            hideImages();
            // Der Shuffle-Schalter gehoert in die Kennung: wird er umgelegt,
            // soll neu gemischt werden — sonst liefe die alte Reihenfolge bis
            // zum naechsten Zonenwechsel weiter.
            var vidSet = JSON.stringify(videos) + '|' + shuffle;
            if (vidSet !== currentVideoSet) {
                currentVideoSet = vidSet;
                zoneVideos = shuffle ? mischen(videos) : videos.slice();
                videoIndex = 0;
                crossfadeVideo(zoneVideos[0]);
            }
        } else {
            currentVideoSet = '';
            if (images.length > 0) {
                hideVideos();
                var imgSet = JSON.stringify(images) + '|' + shuffle + '|' +
                    JSON.stringify(bildzeiten) + '|' + imgInterval;
                if (imgSet !== currentImageSet) {
                    currentImageSet = imgSet;
                    startSlideshow(shuffle ? mischen(images) : images.slice(),
                                   imgInterval, bildzeiten);
                }
            } else {
                hideVideos();
                hideImages();
            }
        }

        if (audio.length > 0) {
            var audSet = JSON.stringify(audio) + '|' + shuffle;
            if (audSet !== currentAudioSet) {
                currentAudioSet = audSet;
                zoneAudioList = shuffle ? mischen(audio) : audio.slice();
                audioIndex = 0;
                playAudio(zoneAudioList[0]);
            }
        } else if (currentAudioFile) {
            currentAudioSet = '';
            fadeOutAudio();
        }
    }

    /* ---- Video ---- */

    function crossfadeVideo(file) {
        // Aktuelle Position des laufenden Videos merken (für Resume bei Zonenwechsel)
        if (resumeEnabled && currentVideoFile && activeVideoEl && !activeVideoEl.paused) {
            var t = activeVideoEl.currentTime;
            if (isFinite(t) && t > 0) videoPositions[currentVideoFile] = t;
        }
        currentVideoFile = file;
        var el = standbyVideoEl;
        el.src = '/media/videos/' + encodeURIComponent(file);
        // Ein einzelnes Video lief bisher immer in der Schleife. Mit „einmal"
        // soll es stehen bleiben — sonst laesst sich eine Praesentation nicht
        // von einer Endlosschleife unterscheiden.
        el.loop = zoneVideos.length <= 1 && !zoneEinmal;
        el.load();

        function onReady() {
            el.removeEventListener('canplay', onReady);
            el.onerror = null;
            touchPlayable();
            if (resumeEnabled && videoPositions[file]) {
                try { el.currentTime = videoPositions[file]; } catch (e) { /* ignore */ }
            }
            el.play().catch(function () {});
            el.classList.add('active');
            activeVideoEl.classList.remove('active');
            var old = activeVideoEl;
            setTimeout(function () {
                old.pause();
                old.removeAttribute('src');
                old.load();
            }, 900);
            var tmp = activeVideoEl;
            activeVideoEl = standbyVideoEl;
            standbyVideoEl = tmp;
        }
        el.addEventListener('canplay', onReady);
        el.onerror = function () {
            // Ungültige/fehlende Datei -> nächsten Kandidaten testen.
            if (zoneVideos.length > 1) {
                videoIndex = (videoIndex + 1) % zoneVideos.length;
                if (zoneVideos[videoIndex] !== file) {
                    crossfadeVideo(zoneVideos[videoIndex]);
                    return;
                }
            }
            showHint('<strong>Video nicht abspielbar</strong><br><br>Zur Admin-Seite...');
            scheduleAdminRedirect(1200);
        };

        el.onended = function () {
            // Komplett durchgespielt -> Position vergessen, damit beim nächsten Mal von vorn
            delete videoPositions[file];
            // „einmal": nach dem letzten Video stehen bleiben statt von vorn
            // zu beginnen.
            if (zoneEinmal && videoIndex >= zoneVideos.length - 1) return;
            if (zoneVideos.length > 1) {
                videoIndex = (videoIndex + 1) % zoneVideos.length;
                crossfadeVideo(zoneVideos[videoIndex]);
            }
        };
    }

    function hideVideos() {
        // Position merken bevor wir das Video stoppen
        if (resumeEnabled && currentVideoFile && activeVideoEl && !activeVideoEl.paused) {
            var t = activeVideoEl.currentTime;
            if (isFinite(t) && t > 0) videoPositions[currentVideoFile] = t;
        }
        [videoA, videoB].forEach(function (v) {
            v.classList.remove('active');
            v.pause();
            v.removeAttribute('src');
            v.load();
        });
        currentVideoFile = null;
    }

    /* ---- Images ---- */

    function bildFehler() {
        showHint('<strong>Bild nicht ladbar</strong><br><br>Zur Admin-Seite...');
        scheduleAdminRedirect(1200);
    }

    function zeigeBild(name, sofort) {
        var el = sofort ? activeImgEl : standbyImgEl;
        el.src = '/media/images/' + encodeURIComponent(name);
        el.onload = function () {
            touchPlayable();
            el.classList.add('active');
            if (!sofort) {
                activeImgEl.classList.remove('active');
                var tmp = activeImgEl;
                activeImgEl = standbyImgEl;
                standbyImgEl = tmp;
            }
        };
        el.onerror = bildFehler;
        if (sofort) standbyImgEl.classList.remove('active');
    }

    // Kette aus `setTimeout` statt eines festen `setInterval`: nur so kann
    // jedes Bild seine EIGENE Standzeit haben (ein Titelbild 3 s, eine
    // Detailtafel 20 s). Mit einem Intervall waere die Schrittweite fuer alle
    // Bilder dieselbe.
    function startSlideshow(images, interval, bildzeiten) {
        stopSlideshow();
        var idx = 0;
        zeigeBild(images[idx], true);

        function standzeit(name) {
            var s = Number((bildzeiten || {})[name]);
            return (isFinite(s) && s > 0) ? s : interval;
        }

        function plane() {
            if (images.length <= 1) return;
            // „einmal": am letzten Bild stehen bleiben, statt von vorn zu
            // beginnen. Das ist der Unterschied zwischen einer Praesentation
            // und einer Endlosschleife.
            if (zoneEinmal && idx === images.length - 1) return;
            slideshowTimer = setTimeout(function () {
                idx = (idx + 1) % images.length;
                zeigeBild(images[idx], false);
                plane();
            }, standzeit(images[idx]) * 1000);
        }
        plane();
    }

    function stopSlideshow() {
        if (slideshowTimer) {
            clearTimeout(slideshowTimer);
            slideshowTimer = null;
        }
    }

    function hideImages() {
        stopSlideshow();
        [imgA, imgB].forEach(function (i) {
            i.classList.remove('active');
            i.removeAttribute('src');
        });
        currentImageSet = '';
    }

    /* ---- Audio ---- */

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
            showHint('<strong>Audio nicht abspielbar</strong><br><br>Zur Admin-Seite...');
            scheduleAdminRedirect(1200);
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
        hideVideos();
        hideImages();
        fadeOutAudio();
        expectedPlayable = false;
        clearRedirect();
    }

    function touchPlayable() {
        lastPlayableAt = Date.now();
    }

    function scheduleAdminRedirect(ms) {
        if (redirected) return;
        if (redirectTimer) return;
        redirectTimer = setTimeout(function () {
            redirected = true;
            window.location.href = '/admin';
        }, ms || 1000);
    }

    function clearRedirect() {
        if (redirectTimer) {
            clearTimeout(redirectTimer);
            redirectTimer = null;
        }
    }
})();

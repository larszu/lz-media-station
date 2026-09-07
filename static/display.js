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
    var zoneVideos = [];
    var videoIndex = 0;
    var slideshowTimer = null;
    var audioIndex = 0;
    var zoneAudioList = [];

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

    function applyScene(zd, imgInterval) {
        var videos = zd.videos || [];
        var images = zd.images || [];
        var audio = zd.audio || [];

        if (videos.length > 0) {
            hideImages();
            zoneVideos = videos;
            if (currentVideoFile !== videos[0]) {
                videoIndex = 0;
                crossfadeVideo(videos[0]);
            }
        } else if (images.length > 0) {
            hideVideos();
            var imgSet = JSON.stringify(images);
            if (imgSet !== currentImageSet) {
                currentImageSet = imgSet;
                startSlideshow(images, imgInterval);
            }
        } else {
            hideVideos();
            hideImages();
        }

        if (audio.length > 0) {
            if (currentAudioFile !== audio[0]) {
                zoneAudioList = audio;
                audioIndex = 0;
                playAudio(audio[0]);
            }
        } else if (currentAudioFile) {
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
        el.loop = zoneVideos.length <= 1;
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

    function startSlideshow(images, interval) {
        if (slideshowTimer) clearInterval(slideshowTimer);
        var idx = 0;

        activeImgEl.src = '/media/images/' + encodeURIComponent(images[0]);
        activeImgEl.onload = function () { activeImgEl.classList.add('active'); touchPlayable(); };
        activeImgEl.onerror = function () {
            showHint('<strong>Bild nicht ladbar</strong><br><br>Zur Admin-Seite...');
            scheduleAdminRedirect(1200);
        };
        standbyImgEl.classList.remove('active');

        if (images.length > 1) {
            slideshowTimer = setInterval(function () {
                idx = (idx + 1) % images.length;
                var el = standbyImgEl;
                el.src = '/media/images/' + encodeURIComponent(images[idx]);
                el.onload = function () {
                    touchPlayable();
                    el.classList.add('active');
                    activeImgEl.classList.remove('active');
                    var tmp = activeImgEl;
                    activeImgEl = standbyImgEl;
                    standbyImgEl = tmp;
                };
                el.onerror = function () {
                    showHint('<strong>Bild nicht ladbar</strong><br><br>Zur Admin-Seite...');
                    scheduleAdminRedirect(1200);
                };
            }, interval * 1000);
        }
    }

    function hideImages() {
        if (slideshowTimer) { clearInterval(slideshowTimer); slideshowTimer = null; }
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
        audioEl.loop = zoneAudioList.length <= 1;
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
            if (zoneAudioList.length > 1) {
                audioIndex = (audioIndex + 1) % zoneAudioList.length;
                audioEl.src = '/media/audio/' + encodeURIComponent(zoneAudioList[audioIndex]);
                audioEl.play().catch(function () {});
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

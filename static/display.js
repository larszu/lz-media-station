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

    setInterval(poll, 500);
    poll();

    async function poll() {
        try {
            var resp = await fetch('/api/scene');
            var scene = await resp.json();

            if (!scene.active) {
                if (currentHash) { fadeAllOut(); currentHash = ''; }
                return;
            }

            var zone = scene.zone;
            if (!zone) return;
            var zd = scene[zone] || { videos: [], images: [], audio: [] };
            var hash = zone + JSON.stringify(zd);

            audioEl.volume = (scene.audio_volume || 80) / 100;

            if (hash === currentHash) return;
            currentHash = hash;
            applyScene(zd, scene.image_interval_s || 5);
        } catch (e) { /* server unreachable */ }
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
        currentVideoFile = file;
        var el = standbyVideoEl;
        el.src = '/media/videos/' + encodeURIComponent(file);
        el.loop = zoneVideos.length <= 1;
        el.load();

        function onReady() {
            el.removeEventListener('canplay', onReady);
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

        el.onended = function () {
            if (zoneVideos.length > 1) {
                videoIndex = (videoIndex + 1) % zoneVideos.length;
                crossfadeVideo(zoneVideos[videoIndex]);
            }
        };
    }

    function hideVideos() {
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
        activeImgEl.onload = function () { activeImgEl.classList.add('active'); };
        standbyImgEl.classList.remove('active');

        if (images.length > 1) {
            slideshowTimer = setInterval(function () {
                idx = (idx + 1) % images.length;
                var el = standbyImgEl;
                el.src = '/media/images/' + encodeURIComponent(images[idx]);
                el.onload = function () {
                    el.classList.add('active');
                    activeImgEl.classList.remove('active');
                    var tmp = activeImgEl;
                    activeImgEl = standbyImgEl;
                    standbyImgEl = tmp;
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
    }
})();

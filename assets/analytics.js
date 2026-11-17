/* Privacy-conscious aggregate review engagement; no account IDs or personal details. */
(function () {
  'use strict';
  const page = document.querySelector('[data-review-slug]');
  if (!page) return;
  const review = page.dataset.reviewSlug;
  const sent = new Set();

  // No error or blocked request should ever interfere with reading or listening.
  function once(name, key, data = {}) {
    if (sent.has(key) || typeof window.umami?.track !== 'function') return;
    sent.add(key);
    try {
      const result = window.umami.track(name, { review, ...data });
      if (result && typeof result.catch === 'function') result.catch(() => {});
    } catch (_) {}
  }

  const prose = page.querySelector('.prose');
  if (prose) {
    let scheduled = false;
    function measureScroll() {
      scheduled = false;
      if (document.visibilityState !== 'visible') return;
      const rect = prose.getBoundingClientRect();
      if (rect.height <= 0) return;
      // Percentage of article body reached by the bottom of the viewport.
      // Scroll depth is not proof that the text was read.
      const reached = Math.max(0, Math.min(100, (window.innerHeight - rect.top) / rect.height * 100));
      for (const milestone of [25, 50, 75, 100]) {
        if (reached >= milestone) once('review-scroll', 'scroll-' + milestone, { percent: milestone });
      }
    }
    window.addEventListener('scroll', () => {
      if (!scheduled) {
        scheduled = true;
        window.requestAnimationFrame(measureScroll);
      }
    }, { passive: true });
  }

  const audio = page.querySelector('audio');
  if (audio) {
    function measureAudio() {
      if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
      // TimeRanges.played counts media that was played, not the playhead's
      // position. Seeking to the end does not earn completion.
      let seconds = 0;
      for (let i = 0; i < audio.played.length; i++) {
        seconds += Math.max(0, audio.played.end(i) - audio.played.start(i));
      }
      const percent = Math.min(100, seconds / audio.duration * 100);
      if (seconds <= 0) return;
      once('audio-play', 'audio-play');
      for (const milestone of [25, 50, 75]) {
        if (percent >= milestone) once('audio-progress', 'audio-' + milestone, { percent: milestone });
      }
      if (percent >= 95) once('audio-complete', 'audio-complete', { percent: 95 });
    }
    audio.addEventListener('playing', () => once('audio-play', 'audio-play'));
    for (const event of ['timeupdate', 'pause', 'ended']) {
      audio.addEventListener(event, measureAudio);
    }
  }
})();

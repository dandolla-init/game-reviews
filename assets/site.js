(function () {
  const progress = document.getElementById('reading-progress');
  const article = document.querySelector('.prose');
  if (progress && article) {
    const update = () => {
      const top = article.getBoundingClientRect().top + window.scrollY;
      const end = top + article.offsetHeight - window.innerHeight * .4;
      progress.style.width = Math.max(0, Math.min(100, (window.scrollY - top) * 100 / Math.max(1, end - top))) + '%';
    };
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  }
  document.querySelectorAll('img[data-fallback]').forEach(img => {
    const onError = () => {
      const fallback = img.getAttribute('data-fallback');
      if (fallback && img.src !== new URL(fallback, window.location.href).href) {
        img.src = fallback;
      }
    };
    img.addEventListener('error', onError);
    if (img.complete && img.naturalWidth === 0) onError();
  });
  document.querySelectorAll('[data-copy-link]').forEach(button => button.addEventListener('click', async () => {
    const url = button.getAttribute('data-copy-link') || window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      const original = button.textContent;
      button.textContent = 'Copied ✓';
      setTimeout(() => { button.textContent = original; }, 1600);
    } catch { window.prompt('Copy this link:', url); }
  }));
})();

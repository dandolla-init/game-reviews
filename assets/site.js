(function () {
  // Initial preference is applied before CSS by the inline head script.
  const themeToggle = document.getElementById('theme-toggle');
  const setTheme = (theme) => {
    const dark = theme === 'dark';
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    if (themeToggle) {
      themeToggle.setAttribute('aria-label', dark ? 'Enable light mode' : 'Enable dark mode');
      themeToggle.setAttribute('aria-pressed', String(dark));
      themeToggle.querySelector('.theme-toggle-icon').textContent = dark ? '☀' : '☾';
      themeToggle.querySelector('.theme-toggle-text').textContent = dark ? 'Light mode' : 'Dark mode';
    }
  };
  setTheme(document.documentElement.dataset.theme);
  themeToggle?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try { localStorage.setItem('dandolla-theme', next); } catch (e) { /* Storage can be disabled. */ }
  });
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

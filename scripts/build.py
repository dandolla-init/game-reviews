#!/usr/bin/env python3
"""Build Dandolla: static GitHub Pages catalogue + Markdown reviews."""
import datetime as dt
from email.utils import format_datetime
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote, urlparse
from xml.sax.saxutils import escape as xml_escape

import mistune
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '_site'


def E(value):
    return html.escape(str(value), quote=True)


def get_site_url():
    explicit = os.getenv('SITE_URL', '').strip().rstrip('/')
    if explicit:
        if not explicit.startswith(('https://', 'http://')):
            raise ValueError('SITE_URL must begin with https:// or http://')
        return explicit
    repo = os.getenv('GITHUB_REPOSITORY', '') if os.getenv('GITHUB_ACTIONS') else ''
    if '/' in repo:
        owner, name = repo.split('/', 1)
        suffix = '' if name.lower() == f'{owner}.github.io'.lower() else '/' + name
        return f'https://{owner}.github.io{suffix}'
    return ''


class HeadingsRenderer(mistune.HTMLRenderer):
    def __init__(self):
        super().__init__(escape=True)
        self.toc = []
        self.used = set()

    def heading(self, text, level, **attrs):
        plain = html.unescape(re.sub(r'<[^>]+>', '', text))
        slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', plain.lower())).strip('-') or 'section'
        base_slug, number = slug, 2
        while slug in self.used:
            slug = f'{base_slug}-{number}'
            number += 1
        self.used.add(slug)
        if level == 2:
            self.toc.append((slug, plain))
        return f'<h{level} id="{E(slug)}">{text}</h{level}>\n'


def validate_local_asset(path):
    """Safely verify site-relative file exists before embedding audio or a local cover."""
    if not path.startswith('/assets/') or '..' in Path(path).parts:
        raise ValueError(f'Local media must use /assets/... with no parent traversal: {path}')
    real = (ROOT / path.lstrip('/')).resolve()
    if not real.is_relative_to((ROOT / 'assets').resolve()) or not real.is_file():
        raise ValueError(f'Missing asset: {path}. Upload the file to that location first.')
    return path


def media_src(src, base, *, must_exist=False):
    if not src:
        return ''
    src = str(src).strip()
    if src.startswith('https://'):
        return src
    if src.startswith('/assets/'):
        if must_exist:
            validate_local_asset(src)
        return base + src
    raise ValueError(f'Invalid media URL: {src}. Use /assets/filename or https:// URL.')


def youtube_link(value):
    if not value:
        return ''
    url = str(value).strip()
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}:
        raise ValueError(f'YouTube link must be a https://youtube.com or https://youtu.be URL: {url}')
    return url


def parse_post(path):
    source = path.read_text(encoding='utf-8')
    match = re.match(r'\A---\s*\n(.*?)\n---\s*\n(.*)\Z', source, flags=re.S)
    if not match:
        raise ValueError(f'{path.name}: missing YAML front matter')
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f'{path.name}: invalid YAML front matter')
    for key in ('title', 'slug', 'date', 'game', 'description'):
        if not meta.get(key):
            raise ValueError(f'{path.name}: missing {key}')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', str(meta['slug'])):
        raise ValueError(f'{path.name}: invalid slug')
    if meta.get('published', True) is False:
        return None
    date = str(meta['date'])
    dt.date.fromisoformat(date)
    meta['audio'] = str(meta.get('audio') or '').strip()
    meta['narration'] = str(meta.get('narration') or 'manual').strip().lower()
    if meta['narration'] not in {'manual', 'elevenlabs'}:
        raise ValueError(f'{path.name}: narration must be manual or elevenlabs')
    meta['narration_source'] = 'manual'
    # The generated file is optional until a GitHub workflow creates it.
    # A manually specified audio file always takes precedence.
    auto_mp3 = ROOT / 'assets' / 'audio' / (str(meta['slug']) + '.mp3')
    if not meta['audio'] and meta['narration'] == 'elevenlabs' and auto_mp3.is_file():
        meta['audio'] = '/assets/audio/' + str(meta['slug']) + '.mp3'
        meta['narration_source'] = 'elevenlabs'
    meta['youtube'] = youtube_link(meta.get('youtube'))
    meta['cover_image'] = str(meta.get('cover_image') or '/assets/cover.svg').strip()
    meta['cover_alt'] = str(meta.get('cover_alt') or f"Cover art for {meta['game']}")
    meta['cover_fallback'] = str(meta.get('cover_fallback') or '/assets/cover.svg')
    # A chosen theme accent is optional. The base site remains blue/black.
    accent = str(meta.get('accent') or '').strip()
    if accent and not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ValueError(f'{path.name}: accent must be a 6-digit hex colour')
    meta['accent'] = accent
    # Validate local links now to prevent broken published pages.
    for field in ('audio', 'cover_image', 'cover_fallback'):
        media = meta.get(field, '')
        if media and media.startswith('/assets/'):
            validate_local_asset(media)
    renderer = HeadingsRenderer()
    markdown = mistune.create_markdown(renderer=renderer, plugins=['strikethrough', 'table', 'url'])
    body = match.group(2).strip()
    words = len(re.findall(r'\b\S+\b', body))
    return {**meta, 'date': date,
            'date_formatted': dt.date.fromisoformat(date).strftime('%d %B %Y'),
            'html': markdown(body), 'toc': renderer.toc,
            'reading_time': max(1, round(words / 215)),
            'word_count': words, 'path': path}


def load_catalogue(all_posts):
    data = json.loads((ROOT / 'catalogue.json').read_text(encoding='utf-8'))
    order = data.get('review_order', [])
    if not isinstance(order, list) or any(not isinstance(s, str) for s in order):
        raise ValueError('catalogue.json: review_order must be an array of review slugs')
    if len(order) != len(set(order)):
        raise ValueError('catalogue.json contains duplicate slugs')
    available = {post['slug']: post for post in all_posts}
    missing = [slug for slug in order if slug not in available]
    if missing:
        raise ValueError('catalogue.json refers to unpublished or unknown review(s): ' + ', '.join(missing))
    return [available[slug] for slug in order]


def post_url(base, post):
    return f"{base}/reviews/{quote(str(post['slug']))}/"


def cover(post, base, *, css_class='cover-image'):
    image_url = media_src(post['cover_image'], base)
    fallback_url = media_src(post['cover_fallback'], base)
    return f'<img class="{css_class}" loading="lazy" src="{E(image_url)}" alt="{E(post["cover_alt"])}" data-fallback="{E(fallback_url)}">'


def page(*, title, description, content, site, url, base, og_image='', article=False):
    canonical = url.rstrip('/') + '/' if url else ''
    if not og_image:
        og_image = (urlparse(url).scheme + '://' + urlparse(url).netloc + base + '/assets/home-banner.png') if url else ''
    return f'''<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#121320">
  <title>{E(title)} | {E(site['title'])}</title><meta name="description" content="{E(description)}">
  {f'<link rel="canonical" href="{E(canonical)}">' if canonical else ''}
  <meta property="og:type" content="{'article' if article else 'website'}">
  <meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(description)}">
  {f'<meta property="og:url" content="{E(canonical)}">' if canonical else ''}
  {f'<meta property="og:image" content="{E(og_image)}">' if og_image else ''}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="{E(base)}/assets/favicon.svg">
  <script>try{{document.documentElement.dataset.theme=localStorage.getItem('dandolla-theme')==='dark'?'dark':'light';}}catch(e){{document.documentElement.dataset.theme='light';}}</script>
  <link rel="stylesheet" href="{E(base)}/assets/styles.css">
  <link rel="alternate" type="application/rss+xml" href="{E(base)}/feed.xml" title="RSS">
</head><body>
  <div class="progress" id="reading-progress" aria-hidden="true"></div>
  <header class="site-header"><div class="container header-inner">
    <a class="wordmark" href="{E(base)}/">{E(site['title'])}</a>
    <nav class="top-links" aria-label="Main navigation"><a href="{E(base)}/#catalogue">Reviews</a><a href="{E(base)}/archive/">Archive</a><a href="{E(base)}/feed.xml">RSS ↗</a><button type="button" id="theme-toggle" class="theme-toggle" aria-label="Enable dark mode" aria-pressed="false"><span class="theme-toggle-icon" aria-hidden="true">☾</span><span class="theme-toggle-text">Dark mode</span></button></nav>
  </div></header>
  <main id="main-content">{content}</main>
  <footer class="site-footer"><div class="container footer-inner"><div>{E(site['title'])}<span class="footer-note"> · {E(site['footer_note'])}</span></div><span>© {dt.date.today().year} {E(site['author'])}</span></div></footer>
  <script src="{E(base)}/assets/site.js" defer></script>
</body></html>'''


def review_item(post, base, index):
    tags = ''.join(f'<span class="tag">{E(t)}</span>' for t in post.get('tags', [])[:3])
    return f'''<a class="review-item" href="{E(post_url(base, post))}">
      <div class="review-art">{cover(post, base)}</div>
      <div class="review-copy"><div class="eyebrow">{index:02d} / {E(post['game'])} / {E(post['date_formatted'])}</div>
      <h3>{E(post['title'])}</h3><p>{E(post['description'])}</p>
      <div class="review-bottom"><span class="tags">{tags}</span><span class="read-time">{post['reading_time']} MIN READ</span></div></div>
      <span class="review-arrow" aria-hidden="true">↗</span>
    </a>'''


def render_index(posts, site, base, site_url):
    items = ''.join(review_item(p, base, n) for n, p in enumerate(posts, 1))
    count = f'{len(posts):02d}'
    content = f'''<section class="hero-banner" aria-label="DANDOLLA header artwork">
      <img src="{E(base)}/assets/home-banner.png" alt="Blue illustrated banner with a black cat and a seated man" class="banner-art" fetchpriority="high">
      <div class="banner-copy container"><span class="banner-kicker">Dandolla</span>
        <h1>Plentiful effort<br><em>backed by</em><br><em>poor opinions.</em></h1>
        <p>{E(site['subtitle'])}</p></div>
    </section>
    <section class="catalogue container" id="catalogue">
      <div class="catalogue-top"><div><div class="eyebrow">Hand-curated Collection</div><h2>Written reviews<span class="period">.</span></h2></div><div class="catalogue-count">{count} <span>ON THE SHELF</span></div></div>
      <div class="catalogue-list">{items if items else '<p class="empty-state">No published reviews have been added to the catalogue yet.</p>'}</div>
      <div class="catalogue-tail">A growing catalogue of personal interpretations, obsessions, and occasionally questionable opinions.</div>
    </section>'''
    return page(title='Written reviews', description=site['description'], content=content, site=site, url=site_url, base=base)


def render_archive(posts, site, base, site_url):
    items = ''.join(review_item(p, base, n) for n, p in enumerate(posts, 1))
    content = f'''<section class="container archive-layout"><div class="eyebrow">ALL REVIEWS / {len(posts):02d} ENTRIES</div>
    <h1>The archive<span class="period">.</span></h1><p>Everything in the collection, in your chosen order.</p>
    <div class="catalogue-list">{items or '<p>No reviews yet.</p>'}</div></section>'''
    return page(title='Archive', description='All game reviews from Dandolla', content=content, site=site,
                url=site_url + '/archive' if site_url else '', base=base)


def render_media(post, base):
    """Keep any rejected audio off the public review pages."""
    if post['youtube']:
        video_inner = f'<a class="media-action" href="{E(post["youtube"])}" target="_blank" rel="noopener noreferrer">Watch on YouTube <span aria-hidden="true">↗</span></a>'
    else:
        video_inner = '<p class="media-pending">Video essay to follow.</p>'
    return f'''<section class="companion-section" aria-label="Companion video">
      <div class="companion-card"><div class="eyebrow">WATCH</div><h2>Video review</h2><p>Watch the companion video on YouTube.</p>{video_inner}</div>
    </section>'''


def render_post(post, site, base, site_url, next_post):
    url = post_url(base, post)
    toc = ''.join(f'<a href="#{E(anchor)}">{E(text)}</a>' for anchor, text in post['toc'])
    tags = ''.join(f'<span class="tag">{E(t)}</span>' for t in post.get('tags', []))
    next_url = post_url(base, next_post) if next_post else f'{base}/#catalogue'
    next_title = next_post['title'] if next_post else 'Return to the catalogue'
    copy_url = f"{site_url}/reviews/{post['slug']}/" if site_url else url
    accent = f' style="--article-accent:{E(post["accent"])}"' if post['accent'] else ''
    content = f'''<article class="review-page"{accent}>
      <section class="article-masthead"><div class="container article-masthead-inner">
        <div class="article-intro"><a class="back-link" href="{E(base)}/#catalogue">← All reviews</a>
          <div class="eyebrow article-category">{E(post['game'])} / WRITTEN REVIEW / FULL SPOILERS</div>
          <h1>{E(post['title'])}</h1><p>{E(post['description'])}</p>
          <div class="article-meta"><span>BY {E(site['author']).upper()}</span><span>{E(post['date_formatted'])}</span><span>{post['reading_time']} MIN READ</span></div></div>
        <div class="article-poster">{cover(post, base, css_class='poster-image')}</div>
      </div></section>
      <div class="container reading-layout">
        <aside class="toc" aria-label="Table of contents"><div class="toc-sticky"><div class="eyebrow">IN THIS REVIEW</div>{toc}</div></aside>
        <div class="article-content"><div class="spoiler-notice"><span aria-hidden="true">◇</span><span><strong>Full spoilers ahead.</strong> The story, characters, and endings are discussed openly.</span></div>
          {render_media(post, base)}
          <div class="prose">{post['html']}</div>
          <div class="article-outro"><div class="tags">{tags}</div><div class="share-row"><span>Share this review</span><button class="copy-link" type="button" data-copy-link="{E(copy_url)}">Copy link ↗</button></div></div>
          <a class="next-card" href="{E(next_url)}"><span class="eyebrow">KEEP READING</span><strong>{E(next_title)}</strong><span>Explore ↗</span></a>
        </div></div></article>'''
    cover_url = media_src(post['cover_image'], base)
    og_image = cover_url if cover_url.startswith('http') else (f'{urlparse(site_url).scheme}://{urlparse(site_url).netloc}{cover_url}' if site_url else '')
    return page(title=post['title'], description=post['description'], content=content, site=site,
                url=site_url + f"/reviews/{post['slug']}" if site_url else '', base=base,
                og_image=og_image, article=True)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def make_feed(posts, site, site_url):
    if not site_url:
        return '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel></channel></rss>'
    items = []
    for post in posts[:20]:
        url = f"{site_url}/reviews/{post['slug']}/"
        day = dt.date.fromisoformat(post['date'])
        stamp = format_datetime(dt.datetime.combine(day, dt.time(12), dt.timezone.utc))
        items.append(f'<item><title>{xml_escape(post["title"])}</title><link>{xml_escape(url)}</link><guid>{xml_escape(url)}</guid><pubDate>{stamp}</pubDate><description>{xml_escape(post["description"])}</description></item>')
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{xml_escape(site["title"])}</title><link>{xml_escape(site_url)}</link><description>{xml_escape(site["description"])}</description>{"".join(items)}</channel></rss>'


def main():
    site = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    site_url = get_site_url()
    base = urlparse(site_url).path.rstrip('/') if site_url else ''
    all_posts = [post for file in sorted((ROOT / 'posts').glob('*.md')) if (post := parse_post(file)) is not None]
    if len({p['slug'] for p in all_posts}) != len(all_posts):
        raise ValueError('Duplicate review slugs')
    posts = load_catalogue(all_posts)
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / 'assets', OUT / 'assets')
    write(OUT / 'index.html', render_index(posts, site, base, site_url))
    write(OUT / 'archive' / 'index.html', render_archive(posts, site, base, site_url))
    for i, post in enumerate(posts):
        next_post = posts[i + 1] if i + 1 < len(posts) else None
        write(OUT / 'reviews' / post['slug'] / 'index.html', render_post(post, site, base, site_url, next_post))
    write(OUT / '.nojekyll', '')
    write(OUT / 'feed.xml', make_feed(posts, site, site_url))
    if site_url:
        write(OUT / 'robots.txt', f'User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n')
        urls = [site_url + '/', site_url + '/archive/'] + [f"{site_url}/reviews/{p['slug']}/" for p in posts]
        write(OUT / 'sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{xml_escape(u)}</loc></url>' for u in urls) + '</urlset>')
    print(f'Built {len(posts)} catalogue review(s) to {OUT}. Site URL: {site_url or "local preview"}')
    for post in posts:
        print(f"  {post['slug']} — {post['word_count']} words | {post['reading_time']} minute read")


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Site build failed: {exc}', file=sys.stderr)
        raise

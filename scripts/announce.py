#!/usr/bin/env python3
"""Announce newly added reviews after a successful Pages deploy. Never stores secrets."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import re
import yaml
from urllib import request, error

from build import ROOT, parse_post, get_site_url, load_catalogue


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def published_slugs_at(commit):
    """Public slugs in a historical commit: both published AND listed in catalogue."""
    if not commit or set(commit) == {'0'}:
        return set()
    try:
        catalogue = json.loads(git('show', commit + ':catalogue.json'))
        order = set(catalogue.get('review_order', []))
        names = git('ls-tree', '-r', '--name-only', commit, '--', 'posts').splitlines()
    except (subprocess.CalledProcessError, ValueError, TypeError):
        return set()
    public = set()
    for name in names:
        if not name.startswith('posts/') or not name.endswith('.md') or Path(name).name.startswith('_'):
            continue
        try:
            source = git('show', commit + ':' + name)
            match = re.match(r'\A---\s*\n(.*?)\n---', source, flags=re.S)
            if not match:
                continue
            data = yaml.safe_load(match.group(1)) or {}
            if data.get('published', True) is not False and data.get('slug') in order:
                public.add(str(data['slug']))
        except (subprocess.CalledProcessError, ValueError, AttributeError):
            continue
    return public


def new_post_paths():
    """Only announce reviews newly public in this push, including newly published drafts."""
    old = os.getenv('GITHUB_EVENT_BEFORE', '').strip()
    new = os.getenv('GITHUB_SHA', '').strip() or 'HEAD'
    if not old:
        print('No push comparison available. Skipping automatic announcement.')
        return []
    if set(old) != {'0'}:
        try:
            git('cat-file', '-e', old + '^{commit}')
        except subprocess.CalledProcessError:
            print('Push base commit unavailable; skipping to avoid duplicate announcements.')
            return []
    before, after = published_slugs_at(old), published_slugs_at(new)
    changed = after - before
    # One-shot announcement markers let an article be announced after a
    # failed deployment, or later, without replaying announcements on edits.
    def marker_slugs(commit):
        if not commit or set(commit) == {'0'}:
            return set()
        try:
            filenames = git('ls-tree', '-r', '--name-only', commit, '--', 'publication-announcements').splitlines()
        except subprocess.CalledProcessError:
            return set()
        return {Path(name).stem for name in filenames
                if name.startswith('publication-announcements/')
                and name.endswith('.txt')
                and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', Path(name).stem)}
    changed |= (marker_slugs(new) - marker_slugs(old)) & after
    paths = []
    for file in sorted((ROOT / 'posts').glob('*.md')):
        post = parse_post(file)
        if post is not None and post['slug'] in changed:
            paths.append(file)
    return paths


def get_url():
    site_url = (os.getenv('SITE_URL') or os.getenv('DEPLOYED_URL') or '').strip().rstrip('/')
    return site_url or get_site_url()


def announce(post, webhook, site_url):
    link = f"{site_url}/reviews/{post['slug']}/"
    title = post['title'][:256]
    description = post['description'][:900]
    payload = {
        'username': 'Dandolla',
        'allowed_mentions': {'parse': []},
        'embeds': [{
            'title': title,
            'url': link,
            'description': description + '\n\n**Read the complete review ↗**',
            'color': int('91add8', 16),
            'fields': [
                {'name': 'GAME', 'value': str(post['game'])[:1024], 'inline': True},
                {'name': 'READ TIME', 'value': f"{post['reading_time']} min", 'inline': True},
            ],
            'footer': {'text': 'Written reviews · Full spoilers may follow'},
        }],
    }
    # Ping exactly one opt-in role, never @everyone or arbitrary mentions.
    # DISCORD_ROLE_ID is a repository variable, not the role's display name.
    role_id = os.getenv('DISCORD_ROLE_ID', '').strip()
    if role_id:
        if not re.fullmatch(r'[0-9]{15,22}', role_id):
            raise ValueError('DISCORD_ROLE_ID must be the numeric Discord role ID, not its name')
        payload['content'] = f'<@&{role_id}>'
        payload['allowed_mentions'] = {'roles': [role_id]}
    if post.get('cover_image'):
        cover = str(post['cover_image'])
        if cover.startswith('/assets/'):
            cover = site_url + cover
        if cover.startswith('https://'):
            payload['embeds'][0]['thumbnail'] = {'url': cover}
    if os.getenv('DISCORD_FORUM_MODE', '').strip().lower() == 'true':
        payload['thread_name'] = title[:100]
    encoded = json.dumps(payload).encode('utf-8')
    webhook_url = webhook + ('&' if '?' in webhook else '?') + 'wait=true'
    for attempt in range(4):
        req = request.Request(webhook_url, data=encoded, headers={'Content-Type': 'application/json', 'User-Agent': 'GameReviewPublisher/1.0'}, method='POST')
        try:
            with request.urlopen(req, timeout=25) as response:
                print(f"Announced {post['slug']} (HTTP {response.status})")
                return
        except error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                retry = 2
                try:
                    detail = json.loads(exc.read().decode('utf-8'))
                    retry = min(30, max(1, float(detail.get('retry_after', 2))))
                except Exception: pass
                time.sleep(retry)
                continue
            raise RuntimeError(f'Discord webhook rejected announcement: HTTP {exc.code}') from exc
    raise RuntimeError('Discord announcement failed after retries')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--post', help='Explicit post path for a one-off announcement')
    parser.add_argument('--slug', help='Publish an existing review by its front-matter slug')
    parser.add_argument('--dry-run', action='store_true', help='Print target articles without calling Discord')
    args = parser.parse_args()
    if args.post and args.slug:
        parser.error('Choose --post or --slug, not both')
    if args.slug:
        if not __import__('re').fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
            parser.error('Slug must contain only lowercase letters, numbers and hyphens')
        paths = [path for path in (ROOT / 'posts').glob('*.md') if path.name != '_TEMPLATE.md']
        available_posts = [p for file in paths if (p := parse_post(file)) is not None]
        listed = {post['slug'] for post in load_catalogue(available_posts)}
        paths = [path for path in paths if (post := parse_post(path)) is not None and post['slug'] == args.slug and post['slug'] in listed]
        if not paths:
            parser.error('No published review found with that slug')
    else:
        paths = [ROOT / args.post] if args.post else new_post_paths()
    posts = [p for path in paths if path.is_file() and (p := parse_post(path)) is not None]
    if not posts:
        print('No newly added published reviews; no announcement needed.')
        return
    site_url = get_url()
    if not site_url:
        raise RuntimeError('Provide SITE_URL or DEPLOYED_URL for public article links.')
    if args.dry_run:
        for p in posts:
            print(f"Would announce {p['title']}: {site_url}/reviews/{p['slug']}/")
        return
    webhook = os.getenv('DISCORD_WEBHOOK_URL', '').strip()
    if not webhook:
        print('No DISCORD_WEBHOOK_URL configured; deployment succeeds without Discord notifications.')
        return
    if not webhook.startswith('https://discord.com/api/webhooks/') and not webhook.startswith('https://discordapp.com/api/webhooks/'):
        raise ValueError('Discord webhook URL is not a standard Discord HTTPS webhook URL')
    for p in posts:
        announce(p, webhook, site_url)

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'Announcement failed: {exc}', file=sys.stderr)
        sys.exit(1)

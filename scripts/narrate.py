#!/usr/bin/env python3
"""Turn opted-in Markdown reviews into static ElevenLabs MP3 narration.

Never place an API key in a public page. This runs inside GitHub Actions with
repository secrets, and commits only the finished MP3 to the repository.

Examples:
  python scripts/narrate.py --slug signalis-alatyr --dry-run
  python scripts/narrate.py --slug signalis-alatyr
  python scripts/narrate.py --new-publications
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib import error, parse, request

import mistune
import yaml

import announce
from build import ROOT, parse_post, load_catalogue

MODEL_LIMITS = {
    'eleven_multilingual_v2': 10000,
    'eleven_v3': 5000,
    'eleven_v4': 10000,
    'eleven_flash_v2_5': 40000,
    'eleven_turbo_v2_5': 40000,
}
# A conservative cap for stitching and natural pauses, even for longer models.
DEFAULT_MODEL = 'eleven_multilingual_v2'
MAX_TOTAL_CHARS = 120_000


def source_and_metadata(path):
    source = Path(path).read_text(encoding='utf-8')
    m = re.match(r'\A---\s*\n(.*?)\n---\s*\n(.*)\Z', source, re.S)
    if not m:
        raise ValueError(f'No front matter in {path}')
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def spoken_text(markdown):
    """Extract natural reading text without reading Markdown punctuation or URLs."""
    md = mistune.create_markdown(renderer='ast', plugins=['strikethrough', 'table'])
    nodes = md(markdown)

    def inline(nodes):
        parts = []
        for n in nodes or []:
            t = n.get('type')
            if t in ('text', 'codespan'):
                parts.append(n.get('raw', ''))
            elif t in ('softbreak', 'linebreak'):
                parts.append(' ')
            elif t in ('image', 'inline_html', 'block_html'):
                pass
            elif n.get('children'):
                parts.append(inline(n['children']))
        return ''.join(parts)

    lines = []

    def walk(nodes):
        for n in nodes:
            t = n.get('type')
            if t in ('heading', 'paragraph', 'block_text'):
                x = inline(n.get('children', [])).strip()
                if x:
                    lines.append(' '.join(x.split()))
            elif t == 'block_quote':
                walk(n.get('children', []))
            elif t in ('list', 'list_item', 'table', 'table_head', 'table_body', 'table_row'):
                walk(n.get('children', []))
            elif t in ('table_cell',):
                x = inline(n.get('children', [])).strip()
                if x:
                    lines.append(x)

    walk(nodes)
    result = '\n\n'.join(lines)
    if not result.strip():
        raise ValueError('No readable content found in Markdown')
    return result


def split_for_tts(text, limit):
    """Keep paragraphs intact when possible; split long paragraphs at sentences."""
    chunks = []
    current = ''

    def push(fragment):
        nonlocal current
        if not fragment:
            return
        if len(fragment) > limit:
            raise ValueError(f'Single TTS fragment too long: {len(fragment)} > {limit}')
        combined = current + ('\n\n' if current else '') + fragment
        if len(combined) > limit:
            if current:
                chunks.append(current)
            current = fragment
        else:
            current = combined

    for paragraph in text.split('\n\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= limit:
            push(paragraph)
            continue
        # Split only exceptionally long paragraphs, preferring sentence boundaries.
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        buffer = ''
        for sentence in sentences:
            if len(sentence) > limit:
                if buffer:
                    push(buffer)
                    buffer = ''
                words = sentence.split()
                piece = ''
                for word in words:
                    if len(word) > limit:
                        raise ValueError('Unbroken word exceeds model limit')
                    merged = (piece + ' ' + word).strip()
                    if len(merged) > limit:
                        push(piece)
                        piece = word
                    else:
                        piece = merged
                if piece:
                    push(piece)
                continue
            merged = (buffer + ' ' + sentence).strip()
            if len(merged) > limit:
                push(buffer)
                buffer = sentence
            else:
                buffer = merged
        if buffer:
            push(buffer)
    if current:
        chunks.append(current)
    assert chunks and all(len(c) <= limit for c in chunks)
    return chunks


def request_audio(text, voice_id, model, api_key, output):
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{parse.quote(voice_id, safe="")}?output_format=mp3_44100_128'
    data = json.dumps({'text': text, 'model_id': model}).encode('utf-8')
    for attempt in range(3):
        req = request.Request(url, data=data, headers={
            'xi-api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'audio/mpeg',
            'User-Agent': 'DandollaReviewPublisher/1.0',
        }, method='POST')
        try:
            with request.urlopen(req, timeout=180) as response:
                body = response.read()
                if not body:
                    raise RuntimeError('Empty audio response from ElevenLabs')
                output.write_bytes(body)
                return
        except error.HTTPError as exc:
            # Only retry explicit rate limits. Other failures might have used credits.
            if exc.code == 429 and attempt < 2:
                delay = min(60, max(2, int(exc.headers.get('Retry-After', '5'))))
                print(f'ElevenLabs rate limited; retrying after {delay}s.')
                time.sleep(delay)
                continue
            msg = exc.read(450).decode('utf-8', errors='replace')
            raise RuntimeError(f'ElevenLabs HTTP {exc.code}: {msg}') from None
    raise RuntimeError('ElevenLabs generation retry limit exceeded')


def concat_mp3(paths, destination):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg is required to combine long-form narration segments')
    with tempfile.TemporaryDirectory() as folder:
        concat_list = Path(folder) / 'parts.txt'
        # inputs are all generated in a private temporary directory.
        concat_list.write_text(''.join(f"file '{p.as_posix()}'\n" for p in paths), encoding='utf-8')
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
            '-f', 'concat', '-safe', '0', '-i', str(concat_list), '-c', 'copy', str(destination)
        ], check=True)


def find_post(slug):
    posts = [p for f in sorted((ROOT / 'posts').glob('*.md')) if (p := parse_post(f)) is not None]
    listed = load_catalogue(posts)
    match = next((p for p in listed if p['slug'] == slug), None)
    if not match:
        raise ValueError(f'No published catalogue review with slug: {slug}')
    return match


def generate(post, *, force=False, dry_run=False):
    slug = post['slug']
    if post.get('narration', 'manual') != 'elevenlabs':
        print(f'Skipping {slug}: narration must be elevenlabs in the front matter.')
        return False
    source_meta, source_md = source_and_metadata(post['path'])
    if source_meta.get('audio'):
        print(f'Skipping {slug}: a manually specified audio file takes precedence.')
        return False
    destination = ROOT / 'assets' / 'audio' / f'{slug}.mp3'
    if destination.exists() and not force:
        print(f'Skipping {slug}: existing generated MP3 will not be charged again.')
        return False
    model = os.getenv('ELEVENLABS_MODEL_ID', DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if model not in MODEL_LIMITS:
        raise ValueError(f'Unsupported ELEVENLABS_MODEL_ID: {model}; supported: {", ".join(MODEL_LIMITS)}')
    # Allow room for future API overhead and to avoid long individual requests.
    limit = min(MODEL_LIMITS[model] - 500, 9000)
    text = spoken_text(source_md)
    if len(text) > MAX_TOTAL_CHARS:
        raise ValueError(f'Review would use {len(text)} characters; above the {MAX_TOTAL_CHARS} configured safety ceiling')
    chunks = split_for_tts(text, limit)
    print(f'{slug}: {len(text):,} characters across {len(chunks)} segments with {model}.')
    if dry_run:
        return False
    api_key = os.getenv('ELEVENLABS_API_KEY', '').strip()
    voice_id = os.getenv('ELEVENLABS_VOICE_ID', '').strip()
    if not (api_key and voice_id):
        raise RuntimeError('Set ELEVENLABS_API_KEY (Actions secret) and ELEVENLABS_VOICE_ID (Actions variable) before generating audio')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', voice_id):
        raise ValueError('ELEVENLABS_VOICE_ID must be an ElevenLabs voice ID, not a URL')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg is required on the runner; install it before making paid requests')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        segments = []
        for i, chunk in enumerate(chunks):
            output = Path(folder) / f'part-{i:03d}.mp3'
            print(f'Generating paid segment {i+1}/{len(chunks)} ({len(chunk)} characters)...', flush=True)
            request_audio(chunk, voice_id, model, api_key, output)
            segments.append(output)
        temp_final = Path(folder) / 'narration.mp3'
        concat_mp3(segments, temp_final)
        if temp_final.stat().st_size > 95 * 1024 * 1024:
            raise RuntimeError('MP3 exceeds 95 MB; reduce bitrate or host audio externally')
        shutil.copy2(temp_final, destination)
    print(f'Generated {destination.relative_to(ROOT)} ({destination.stat().st_size / 1024 / 1024:.1f} MB).')
    return True


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--slug', help='Generate narration for this review')
    mode.add_argument('--new-publications', action='store_true', help='Generate opted-in newly public reviews in the GitHub push')
    parser.add_argument('--force', action='store_true', help='Replace an already generated MP3 (will use credits again)')
    parser.add_argument('--dry-run', action='store_true', help='Preview character usage and chunk count without any API call')
    args = parser.parse_args()
    if args.slug:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
            parser.error('Invalid review slug')
        posts = [find_post(args.slug)]
    else:
        # One-time requests introduced by a new GitHub commit. Existing
        # markers are deliberately ignored so later commits cannot re-charge.
        before = os.getenv('GITHUB_EVENT_BEFORE', '').strip()
        after = os.getenv('GITHUB_SHA', '').strip()
        marker_paths = []
        if before and after and set(before) != {'0'}:
            changed = subprocess.check_output(
                ['git', 'diff', '--diff-filter=A', '--name-only', before, after,
                 '--', '.narration-requests/'], cwd=ROOT, text=True)
            marker_paths = changed.splitlines()
        preflight = any(re.fullmatch(r'\\.narration-requests/preflight-[0-9]+\\.txt', p)
                        for p in marker_paths)
        if preflight:
            if not os.getenv('ELEVENLABS_API_KEY') or not os.getenv('ELEVENLABS_VOICE_ID'):
                raise RuntimeError('ElevenLabs API key or voice ID missing from GitHub Actions')
            if not shutil.which('ffmpeg'):
                raise RuntimeError('ffmpeg missing from GitHub Actions runner')
            print('PREFLIGHT_CREDENTIALS_AND_FFMPEG_OK')
            for check_slug in ('danganronpa-trigger-happy-havoc', 'signalis-alatyr'):
                generate(find_post(check_slug), dry_run=True)
            print('PREFLIGHT_COMPLETE_NO_CREDITS_USED')
        approved = []
        for item in marker_paths:
            matched = re.fullmatch(r'\\.narration-requests/(danganronpa-trigger-happy-havoc|signalis-alatyr)\\.approved', item)
            if matched:
                marker = ROOT / item
                if marker.read_text(encoding='utf-8').strip() != 'AUTHORIZE_ONE_TIME_ELEVENLABS_GENERATION':
                    raise ValueError('Unapproved narration marker: ' + item)
                approved.append(matched.group(1))
        if len(approved) > 1:
            raise ValueError('Generate one approved review per commit to control costs')
        for approved_slug in approved:
            generate(find_post(approved_slug))
        paths = announce.new_post_paths()
        posts = [p for path in paths if (p := parse_post(path)) is not None]
    if not posts:
        print('No newly published reviews to narrate.')
    for post in posts:
        if post.get('narration') != 'elevenlabs':
            continue
        if not args.dry_run and (not os.getenv('ELEVENLABS_API_KEY') or not os.getenv('ELEVENLABS_VOICE_ID')):
            if args.new_publications:
                print('No ElevenLabs credentials configured; skipping optional narration without affecting deployment.')
                return
        generate(post, force=args.force, dry_run=args.dry_run)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Narration error: {exc}', file=sys.stderr)
        sys.exit(1)

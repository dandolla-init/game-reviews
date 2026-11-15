#!/usr/bin/env python3
"""Long-form, emotionally guided Dandolla1 narration approved by one-time Git markers.

No review prose is modified. Emotion tags affect only ElevenLabs synthesis.
No Discord or publication messages are sent.
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
from urllib import error, request

from build import ROOT
from narrate import source_and_metadata, spoken_text, split_for_tts, concat_mp3, find_post
from voice_samples import resolve_voice_id

AUTH = 'AUTHORIZE_ONE_TIME_EXPRESSIVE_DANDOLLA1_V4'
PROFILES = {
    'danganronpa-trigger-happy-havoc': {
        'stability': 0.30, 'similarity_boost': 0.75,
        'moods': ('[British accent] [incredulous]', '[exasperated]', '[sarcastic]', '[dryly amused]'),
    },
    'signalis-alatyr': {
        'stability': 0.30, 'similarity_boost': 0.80,
        'moods': ('[British accent] [wistfully]', '[softly]', '[with growing sadness]', '[thoughtfully]'),
    },
}

def performance_text(slug, spoken):
    """Add performance cues while keeping every word of article text unchanged."""
    if slug not in PROFILES:
        raise ValueError('No approved expressive voice profile for ' + slug)
    lines = spoken.split('\n\n')
    out = []
    for idx, para in enumerate(lines):
        if not para.strip():
            continue
        lower = para.lower()
        if slug == 'danganronpa-trigger-happy-havoc':
            if 'chapter 6' in lower or 'unnecessary amount of exposition' in lower:
                cue = '[exasperated]'
            elif 'true ending' in lower or 'hope versus' in lower:
                cue = '[sarcastic]'
            elif 'alternative ending' in lower:
                cue = '[mischievously]'
            elif any(term in lower for term in ('death', 'murder', 'sadness', 'tragedy')):
                cue = '[with restrained sadness]'
            else:
                cue = PROFILES[slug]['moods'][idx % 4]
        else:
            if any(term in lower for term in ('promise', 'elster', 'ariane', 'love', 'yuri')):
                cue = '[softly, wistfully]'
            elif any(term in lower for term in ('adler', 'sisyphus', 'camus')):
                cue = '[wistfully]'
            elif any(term in lower for term in ('eldritch', 'horror becomes', 'supernatural')):
                cue = '[disappointed]'
            else:
                cue = PROFILES[slug]['moods'][idx % 4]
        if idx == 0:
            cue = '[British accent] ' + cue
        # Reproduce Sample 4's emotional turn on the Adler line.
        if slug == 'signalis-alatyr' and 'One must imagine Adler happy. Because I certainly cannot.' in para:
            para = para.replace('One must imagine Adler happy. Because I certainly cannot.',
                                'One must imagine Adler happy. [quietly] Because I certainly cannot.')
        out.append(cue + ' ' + para)
    return '\n\n'.join(out)

def new_request():
    before, after = os.getenv('GITHUB_EVENT_BEFORE', ''), os.getenv('GITHUB_SHA', '')
    if not before or not after or set(before) == {'0'}:
        return None
    paths = subprocess.check_output(
        ['git','diff','--diff-filter=A','--name-only',before,after,'--','.narration-requests/'],
        cwd=ROOT, text=True).splitlines()
    chosen = []
    for path in paths:
        m = re.fullmatch(r'\.narration-requests/expressive-(danganronpa-trigger-happy-havoc|signalis-alatyr)-v4\.request',path)
        if m:
            if (ROOT/path).read_text(encoding='utf-8').strip() != AUTH:
                raise RuntimeError('An expressive narration request has invalid approval')
            chosen.append(m.group(1))
    if len(chosen) > 1:
        raise RuntimeError('Only one paid full review is permitted per commit')
    return chosen[0] if chosen else None

def speech_request(text, voice_id, settings, key, target):
    body = json.dumps({
        'text': text, 'model_id': 'eleven_v4', 'language_code': 'en',
        'voice_settings': {
           'stability': settings['stability'],
           'similarity_boost': settings['similarity_boost']
        },
    }).encode('utf-8')
    req = request.Request('https://api.elevenlabs.io/v1/text-to-speech/'+voice_id+'?output_format=mp3_44100_128',
        data=body, method='POST', headers={
            'xi-api-key':key, 'Content-Type':'application/json', 'Accept':'audio/mpeg'})
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=210) as r:
                data = r.read()
            if len(data) < 1000 or not data.startswith((b'ID3',bytes([255,251]),bytes([255,243]),bytes([255,242]))):
                raise RuntimeError('Invalid MP3 received from ElevenLabs')
            target.write_bytes(data)
            return
        except error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(6 * (attempt + 1))
                continue
            detail = exc.read(600).decode('utf-8','replace')
            raise RuntimeError(f'ElevenLabs HTTP {exc.code}: {detail}') from None
    raise RuntimeError('ElevenLabs rate limit persisted')

def generate(slug, dry_run=False):
    profile = PROFILES[slug]
    post = find_post(slug)
    if post.get('narration') != 'elevenlabs':
        raise RuntimeError('Article not opted in to expressive narration')
    metadata, article = source_and_metadata(post['path'])
    if metadata.get('audio'):
        raise RuntimeError('Manual audio specified; refusing to overwrite')
    target = ROOT / 'assets' / 'audio' / (slug+'.mp3')
    if target.is_file():
        print('EXISTING_MP3_SKIPPED ' + slug)
        return False
    speech = performance_text(slug, spoken_text(article))
    segments = split_for_tts(speech, 8500)
    print(f'EXPRESSIVE_PREVIEW {slug}: {len(speech)} total characters, {len(segments)} v4 segments, stability={profile["stability"]}, similarity={profile["similarity_boost"]}', flush=True)
    if dry_run:
        return False
    key = os.getenv('ELEVENLABS_API_KEY', '').strip()
    if not key.startswith('sk_'):
        raise RuntimeError('ElevenLabs secret API key is not configured')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg is required to combine narration segments')
    voice_id = resolve_voice_id(key)  # Checks current voice name and British accent.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        parts = []
        for index, text in enumerate(segments):
            part=Path(temp)/f'part-{index:03d}.mp3'
            print(f'EXPRESSIVE_SEGMENT {slug}: {index+1}/{len(segments)} ({len(text)} characters)', flush=True)
            speech_request(text, voice_id, profile, key, part)
            parts.append(part)
        assembled=Path(temp)/'narration.mp3'
        concat_mp3(parts,assembled)
        if assembled.stat().st_size > 95*1024*1024:
            raise RuntimeError('Audio exceeds repository size limit')
        shutil.copy2(assembled,target)
    print(f'EXPRESSIVE_DONE {slug}: {target.stat().st_size} bytes',flush=True)
    return True

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only-new-request',action='store_true')
    parser.add_argument('--preview',choices=sorted(PROFILES))
    args=parser.parse_args()
    if args.preview:
        generate(args.preview,dry_run=True)
        return
    if not args.only_new_request:
        parser.error('Full narration requires an explicit one-time Git request')
    chosen=new_request()
    if chosen:
        generate(chosen)
    else:
        print('No expressive full-review generation requested in this commit.')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('EXPRESSIVE_ERROR:',e,file=sys.stderr)
        sys.exit(1)

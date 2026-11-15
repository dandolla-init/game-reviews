import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build
import announce


class SiteTests(unittest.TestCase):
    def test_original_article_preserved(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md')
        self.assertGreater(post['word_count'], 5900)
        self.assertEqual(len(post['toc']), 10)
        self.assertIn('One Must Imagine Adler Happy', post['html'])
        self.assertIn('Camus', post['html'])
        self.assertIn('The Promise Is the Point', post['html'])
        self.assertEqual(post['audio'], '')
        self.assertEqual(post['youtube'], '')

    def test_catalogue_manual_order_and_renders(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md')
        dan = build.parse_post(ROOT / 'posts' / 'danganronpa-trigger-happy-havoc.md')
        listing = build.load_catalogue([post, dan])
        self.assertEqual([x['slug'] for x in listing], ['danganronpa-trigger-happy-havoc', 'signalis-alatyr'])
        home = build.render_index(listing, json.loads((ROOT / 'site.json').read_text()), '/game-reviews', 'https://example.github.io/game-reviews')
        self.assertIn('home-banner.png', home)
        self.assertIn('Plentiful effort', home)
        self.assertIn('backed by', home)
        self.assertIn('poor opinions.', home)
        self.assertIn('Games that refuse to leave my head.', home)
        self.assertIn('Hand-curated Collection', home)
        self.assertNotIn('DANDOLLA / WRITTEN', home)
        self.assertNotIn('✳', home)
        self.assertIn('catalogue', home)
        self.assertIn('library_600x900.jpg', home)
        article = build.render_post(post, json.loads((ROOT / 'site.json').read_text()), '/game-reviews', 'https://example.github.io/game-reviews', None)
        self.assertIn('Audio narration', article)
        self.assertIn('Video review', article)
        self.assertIn('Narrated edition coming soon', article)
        self.assertIn('Video essay to follow', article)
        self.assertIn('28 MIN READ', article)
        self.assertIn('Camus', article)
        self.assertIn('/game-reviews/assets/styles.css', home)

    def test_media_fields_generate_functional_controls(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md').copy()
        post['audio'] = '/assets/audio/voiceover.mp3'
        post['youtube'] = 'https://www.youtube.com/watch?v=abcdefghijk'
        with patch.object(build, 'ROOT', ROOT), patch.object(build, 'validate_local_asset', return_value='/assets/audio/voiceover.mp3'):
            html = build.render_media(post, '/reviews')
        self.assertIn('<audio controls', html)
        self.assertIn('/reviews/assets/audio/voiceover.mp3', html)
        self.assertIn('https://www.youtube.com/watch?v=abcdefghijk', html)
        self.assertNotIn('coming soon', html)

    def test_missing_local_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing asset'):
            build.validate_local_asset('/assets/audio/not-uploaded.mp3')
        with self.assertRaises(ValueError):
            build.youtube_link('https://other.example/video')

    def test_project_pages_and_custom_domains(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'example/reviews'}, clear=True):
            self.assertEqual(build.get_site_url(), 'https://example.github.io/reviews')
        with patch.dict(os.environ, {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'example/example.github.io'}, clear=True):
            self.assertEqual(build.get_site_url(), 'https://example.github.io')
        with patch.dict(os.environ, {'SITE_URL':'https://reviews.example.com/'}, clear=True):
            self.assertEqual(build.get_site_url(), 'https://reviews.example.com')

    def test_discord_only_newly_public_reviews(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / 'posts').mkdir()
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
            def post(name, published):
                (repo / 'posts' / (name + '.md')).write_text(f'''---
title: {name}
slug: {name}
date: '2026-11-14'
game: Test
description: Test article
published: {'true' if published else 'false'}
---
Review text
''')
            def catalogue(names):
                (repo / 'catalogue.json').write_text(json.dumps({'review_order': names}))
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.com')
            post('one',True); post('two',False);catalogue(['one'])
            git('add','.');git('commit','-qm','initial')
            first=git('rev-parse','HEAD')
            with patch.object(announce,'ROOT',repo),patch.dict(os.environ, {'GITHUB_EVENT_BEFORE':'0'*40,'GITHUB_SHA':first}):
                self.assertEqual([x.stem for x in announce.new_post_paths()], ['one'])
            # An edit to the first review + publication of the second announces only second.
            post('one',True); post('two',True);catalogue(['two','one'])
            git('add','.');git('commit','-qm','publish second')
            second=git('rev-parse','HEAD')
            with patch.object(announce,'ROOT',repo),patch.dict(os.environ, {'GITHUB_EVENT_BEFORE':first,'GITHUB_SHA':second}):
                self.assertEqual([x.stem for x in announce.new_post_paths()], ['two'])
            # Changing the listing order, art, or body doesn't reannounce anything.
            catalogue(['one','two']);git('add','.');git('commit','-qm','reorder catalogue')
            third=git('rev-parse','HEAD')
            with patch.object(announce,'ROOT',repo),patch.dict(os.environ, {'GITHUB_EVENT_BEFORE':second,'GITHUB_SHA':third}):
                self.assertEqual(announce.new_post_paths(), [])


if __name__ == '__main__':
    unittest.main()

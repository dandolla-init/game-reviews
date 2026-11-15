"""All narration tests are offline; no real API key or paid requests are used."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import narrate
import build


class NarrationTests(unittest.TestCase):
    def test_signalis_narration_ready_for_approved_generation(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md')
        self.assertEqual(post['narration'], 'elevenlabs')
        self.assertIn(post['audio'], ('', '/assets/audio/signalis-alatyr.mp3'))

    def test_plain_text_from_markdown(self):
        sample = '''# Review\n\n*A long* **opinion** about [the game](https://example.com).\n\n![Poster](poster.jpg)\n\n## Final thought\n\nOne must imagine Adler happy.''' 
        actual = narrate.spoken_text(sample)
        self.assertIn('A long opinion about the game.', actual)
        self.assertIn('Final thought', actual)
        self.assertNotIn('https://', actual)
        self.assertNotIn('Poster', actual)
        self.assertNotIn('**', actual)

    def test_chunker_respects_limit_and_keeps_all_text(self):
        speech = '\n\n'.join('Sentence number %s. This is a fairly long paragraph.' % i for i in range(60))
        chunks = narrate.split_for_tts(speech, 210)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(c) <= 210 for c in chunks))
        self.assertEqual('\n\n'.join(chunks), speech)

    def test_signalis_dry_run_no_network(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md')
        # Simulate opt-in without modifying the review currently awaiting approval.
        post['narration'] = 'elevenlabs'
        with patch.object(narrate, 'request_audio', side_effect=AssertionError('Network not allowed')):
            result = narrate.generate(post, dry_run=True)
        self.assertFalse(result)
        meta, body = narrate.source_and_metadata(post['path'])
        self.assertTrue(len(narrate.spoken_text(body)) > 30000)

    def test_existing_audio_requires_force_to_regenerate(self):
        post = build.parse_post(ROOT / 'posts' / 'signalis-alatyr.md')
        post['narration'] = 'elevenlabs'
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(narrate, 'ROOT', Path(tmp)):
                target = Path(tmp) / 'assets' / 'audio' / 'signalis-alatyr.mp3'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'preserved audio')
                with patch.object(narrate, 'request_audio', side_effect=AssertionError('Would spend credits')):
                    self.assertFalse(narrate.generate(post))
                self.assertEqual(target.read_bytes(), b'preserved audio')

    def test_rejected_recording_is_not_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            cloned = Path(tmp)
            (cloned / 'assets' / 'audio').mkdir(parents=True)
            (cloned / 'assets' / 'audio' / 'signalis-alatyr.mp3').write_bytes(b'rejected')
            (cloned / 'posts').mkdir()
            source = (ROOT / 'posts' / 'signalis-alatyr.md').read_text(encoding='utf-8').replace('narration: elevenlabs', 'narration: manual', 1)
            (cloned / 'posts' / 'signalis-alatyr.md').write_text(source, encoding='utf-8')
            with patch.object(build, 'ROOT', cloned), patch.object(build, 'validate_local_asset', lambda p: p):
                post = build.parse_post(cloned / 'posts' / 'signalis-alatyr.md')
                page = build.render_media(post, '/game-reviews')
            self.assertEqual(post['audio'], '')
            self.assertNotIn('<audio', page)
            self.assertNotIn('Audio narration', page)


if __name__ == '__main__':
    unittest.main()

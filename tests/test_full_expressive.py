import re
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import full_expressive
from narrate import source_and_metadata, spoken_text, split_for_tts

class FullExpressiveTests(unittest.TestCase):
    def test_preserve_spoken_words(self):
        for slug in full_expressive.PROFILES:
            md=source_and_metadata(ROOT/'posts'/(slug+'.md'))[1]
            plain=spoken_text(md)
            guided=full_expressive.performance_text(slug,plain)
            clean=re.sub(r'\[[^\]]+\]\s*','',guided)
            self.assertEqual(clean,plain)
            self.assertIn('[British accent]',guided)
            self.assertGreater(len(split_for_tts(guided,8500)),1)
            self.assertTrue(all(len(s)<=8500 for s in split_for_tts(guided,8500)))
    def test_selected_samples(self):
        self.assertEqual(full_expressive.PROFILES['danganronpa-trigger-happy-havoc']['stability'],0.30)
        self.assertEqual(full_expressive.PROFILES['danganronpa-trigger-happy-havoc']['similarity_boost'],0.75)
        self.assertEqual(full_expressive.PROFILES['signalis-alatyr']['stability'],0.30)
        self.assertEqual(full_expressive.PROFILES['signalis-alatyr']['similarity_boost'],0.80)
        self.assertIn('[quietly] Because I certainly cannot.', full_expressive.performance_text(
            'signalis-alatyr','One must imagine Adler happy. Because I certainly cannot.'))

if __name__=='__main__':
    unittest.main()

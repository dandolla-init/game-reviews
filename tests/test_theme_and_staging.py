import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build

class ThemeAndDraftTests(unittest.TestCase):
    def test_toggle_on_home_article_archive(self):
        site = json.loads((ROOT/'site.json').read_text())
        all_posts=[p for f in (ROOT/'posts').glob('*.md') if (p:=build.parse_post(f))]
        catalogue=build.load_catalogue(all_posts)
        home=build.render_index(catalogue,site,'','')
        archive=build.render_archive(catalogue,site,'','')
        article=build.render_post(catalogue[0],site,'','',None)
        for page in [home,archive,article]:
            self.assertIn('id="theme-toggle"',page)
            self.assertIn('dandolla-theme',page)
        self.assertIn('data-theme="dark"',(ROOT/'assets/styles.css').read_text())
        self.assertIn("localStorage.setItem('dandolla-theme'",(ROOT/'assets/site.js').read_text())
    def test_danganronpa_draft_stays_hidden(self):
        self.assertIsNone(build.parse_post(ROOT/'posts/danganronpa-trigger-happy-havoc.md'))
        self.assertNotIn('danganronpa-trigger-happy-havoc', json.loads((ROOT/'catalogue.json').read_text())['review_order'])

if __name__ == '__main__': unittest.main()

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
    def test_danganronpa_is_published_first(self):
        self.assertIsNotNone(build.parse_post(ROOT/'posts/danganronpa-trigger-happy-havoc.md'))
        self.assertEqual('danganronpa-trigger-happy-havoc', json.loads((ROOT/'catalogue.json').read_text())['review_order'][0])

if __name__ == '__main__': unittest.main()

class ArticleImportTests(unittest.TestCase):
    def test_danganronpa_imported_and_staged(self):
        source = (ROOT/'posts/danganronpa-trigger-happy-havoc.md').read_text(encoding='utf-8')
        self.assertIn('Danganronpa: Trigger Happy Havoc - A Flawed, Red-Pilled Foundation', source)
        self.assertIn('Chapter 6 - Hope, Despair', source)
        self.assertIn('The Ultimate Hope was inside Aoi all along. Literally.', source)
        self.assertIn('published: true', source)
        self.assertNotIn('—', source)
        self.assertNotIn('–', source)
    def test_signalis_hyphen_standard(self):
        source = (ROOT/'posts/signalis-alatyr.md').read_text(encoding='utf-8')
        self.assertNotIn('—', source)
        self.assertNotIn('–', source)
        self.assertIn('narration: elevenlabs', source)
    def test_role_default_in_workflow(self):
        workflow = (ROOT/'.github/workflows/publish.yml').read_text()
        self.assertIn('884385448410087455', workflow)
        self.assertIn('DISCORD_ROLE_ID', workflow)

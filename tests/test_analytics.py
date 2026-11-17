import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build

class AnalyticsTests(unittest.TestCase):
    def test_tracking_shared_by_all_pages(self):
        site = json.loads((ROOT / 'site.json').read_text())
        posts = build.load_catalogue([p for f in (ROOT/'posts').glob('*.md') if (p := build.parse_post(f))])
        home = build.render_index(posts, site, '/game-reviews', '')
        archive = build.render_archive(posts, site, '/game-reviews', '')
        article = build.render_post(posts[0], site, '/game-reviews', '', posts[1])
        for page in (home, archive, article):
            self.assertEqual(page.count('https://cloud.umami.is/script.js'), 1)
            self.assertIn('data-website-id="53ef5c68-a0d7-4829-9424-ab49d790505d"', page)
            self.assertIn('data-do-not-track="true"', page)
            self.assertIn('/game-reviews/assets/analytics.js', page)
        self.assertIn('data-umami-event="review-click"', home)
        self.assertIn('data-umami-event="chapter-click"', article)
        self.assertIn('data-umami-event="share-click"', article)
        self.assertIn('data-umami-event="next-review-click"', article)
        self.assertIn('data-review-slug=', article)

    @unittest.skipUnless(shutil.which('node'), 'Node.js not available')
    def test_analytics_javascript(self):
        subprocess.run(['node', str(ROOT/'tests'/'analytics_test.js')], check=True)

if __name__ == '__main__':
    unittest.main()

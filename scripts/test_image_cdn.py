"""Build real site templates with CDN enabled and disabled, without external APIs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]


class Images(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.images = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images.append(dict(attrs))


class ImageCDNTests(unittest.TestCase):
    def test_site_builds(self):
        with tempfile.TemporaryDirectory(prefix='beachside-image-cdn-') as folder:
            site = Path(folder)
            for name in ['layouts', 'themes', 'content', 'data']:
                shutil.copytree(ROOT / name, site / name)
            for name in ['assets', 'static']:
                shutil.copytree(ROOT / name, site / name)
            shutil.copy(ROOT / 'hugo.toml', site / 'hugo.toml')
            # Live event API availability is covered separately in test_events.py.
            override = site / 'layouts/partials/church-center/events.html'
            override.parent.mkdir(parents=True, exist_ok=True)
            override.write_text('{{ return slice }}')
            for enabled in [False, True]:
                env = dict(os.environ, HUGO_PARAMS_NETLIFYIMAGECDN=str(enabled).lower())
                result = subprocess.run(['hugo', '--source', folder, '--minify'],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                home = (site / 'public/index.html').read_text()
                images = Images(home).images
                self.assertGreater(len(images), 5)
                for image in images:
                    src = image['src']
                    if enabled:
                        self.assertTrue(src.startswith('/.netlify/images?'), src)
                        query = parse_qs(urlparse(src).query)
                        self.assertEqual(query['q'], ['80'])
                        self.assertTrue((site / 'public' / query['url'][0].lstrip('/')).is_file(), query['url'][0])
                        self.assertIn('srcset', image)
                        self.assertNotIn('ZgotmplZ', home)
                        for candidate in image['srcset'].split(', '):
                            url, width = candidate.rsplit(' ', 1)
                            self.assertEqual(parse_qs(urlparse(url).query)['w'], [width[:-1]])
                    else:
                        self.assertNotIn('/.netlify/images', src)
                        self.assertNotIn('srcset', image)
                page = (site / 'public/visit/index.html').read_text()
                self.assertEqual('/.netlify/images?' in page, enabled)


if __name__ == '__main__':
    unittest.main()

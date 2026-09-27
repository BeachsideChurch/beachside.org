"""Check live-link validation and the actual landing template with offline Hugo builds."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VIDEO = 'waa1ouN5Aao'


class YouTubeLiveTests(unittest.TestCase):
    def test_urls_and_layout(self):
        valid = [
            f'https://www.youtube.com/watch?v={VIDEO}',
            f'https://youtube.com/watch?v={VIDEO}&feature=share',
            f'https://www.youtube.com/watch?feature=share&v={VIDEO}',
            f'https://www.youtube.com/live/{VIDEO}?si=abc',
            f'https://www.youtube.com/embed/{VIDEO}',
            f'https://www.youtube-nocookie.com/embed/{VIDEO}',
            f'https://youtu.be/{VIDEO}?si=abc',
            f'  https://youtu.be/{VIDEO}  ',
        ]
        invalid = [
            'not a URL',
            'https://www.youtube.com/@beachside/live',
            f'https://example.com/watch?v={VIDEO}',
            f'https://youtube.com.evil.example/watch?v={VIDEO}',
            'https://youtu.be/too-short',
            f'https://youtu.be/{VIDEO}x',
            f'https://www.youtube.com/watch?feature=share#&v={VIDEO}',
        ]
        with tempfile.TemporaryDirectory(prefix='beachside-youtube-test-') as directory:
            site = Path(directory)
            for folder in ['layouts/_default', 'layouts/partials', 'content', 'data']:
                (site / folder).mkdir(parents=True)
            templates = ROOT / 'themes/beachside/layouts'
            for file in ['_default/landing.html', 'partials/youtube-live-video.html']:
                shutil.copyfile(templates / file, site / 'layouts' / file)
            shutil.copyfile(ROOT / 'static/admin/config.yml', site / 'data/cms.yaml')
            (site / 'layouts/partials/content-section.html').write_text('')
            # Parse the actual CMS YAML and exercise its pattern as well as rendering.
            (site / 'layouts/_default/baseof.html').write_text('''
{{ range site.Data.cms.collections }}{{ if eq .name "watch_live" }}
  {{ range .files }}{{ range .fields }}{{ if eq .name "youtube_live_url" }}
    {{ if not (findRE (index .pattern 0) $.Params.youtube_live_url) }}
      {{ errorf "CMS rejected URL" }}
    {{ end }}
  {{ end }}{{ end }}{{ end }}
{{ end }}{{ end }}
{{ block "main" . }}{{ end }}
''')
            (site / 'hugo.toml').write_text('baseURL = "https://example.test/"\n')
            for url in valid + invalid:
                with self.subTest(url=url):
                    metadata = json.dumps({'title': 'Watch Live', 'layout': 'landing',
                                           'youtube_live_url': url})
                    (site / 'content/watch-live.md').write_text(metadata + '\n\n## Watch live\n')
                    result = subprocess.run(['hugo', '--source', str(site), '--noBuildLock'],
                                            capture_output=True, text=True)
                    output = result.stdout + result.stderr
                    if url in valid:
                        self.assertEqual(result.returncode, 0, output)
                        html = (site / 'public/watch-live/index.html').read_text()
                        self.assertIn(f'https://www.youtube-nocookie.com/embed/{VIDEO}', html)
                        self.assertRegex(html, r'(?s)<div class="prose wrap">\s*<h2[^>]*>Watch live</h2>\s*<div class="video-frame">')
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('CMS rejected URL', output)
                        self.assertIn('invalid Watch Live YouTube URL', output)


if __name__ == '__main__':
    unittest.main()

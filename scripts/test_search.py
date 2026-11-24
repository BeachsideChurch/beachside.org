"""Verify real Hugo/Pagefind indexing boundaries and build failure propagation."""
import gzip
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import build

ROOT = Path(__file__).resolve().parents[1]


class SearchBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='beachside-search-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.site = Path(cls.temp.name)
        shutil.copytree(ROOT / 'themes', cls.site / 'themes')
        shutil.copytree(ROOT / 'data', cls.site / 'data')
        shutil.copytree(ROOT / 'layouts/landing-pages', cls.site / 'layouts/landing-pages')
        shutil.copyfile(ROOT / 'hugo.toml', cls.site / 'hugo.toml')
        cls.output = cls.site / 'public'

        files = {
            'layouts/home.html': '{{ define "main" }}<h1>Welcome</h1>{{ end }}',
            'layouts/partials/footer.html': '<footer>Footeruniqueterm</footer>',
            'content/search/_index.md': (ROOT / 'content/search/_index.md').read_text(encoding='utf-8'),
            'content/visible.md': '---\ntitle: Visible Page\n---\nBodyonlyuniqueterm lives here.',
            'content/messages/example.md': '---\ntitle: Message Title\npart_number: 7\nseries: Finding Hope\ndate: 2026-10-18\n---\nMessageuniqueterm',
            'content/messages/hope/_index.md': '---\ntitle: Hope Series\nlayout: series\nseries: Finding Hope\n---\n',
            'content/messages/hope/inherited.md': '---\ntitle: Inherited Series\n---\nMessage body.',
            'content/discipleship-guide/example.md': '---\ntitle: Example Guide\nseries: Finding Hope\ndate: 2026-11-15\n---\nGuide body.',
            'content/students/example.md': '---\ntitle: Example Ministry\n---\nMinistry body.',
            'content/children/waumba-land.md': (ROOT / 'content/children/waumba-land.md').read_text(encoding='utf-8'),
            'content/students/transit.md': (ROOT / 'content/students/transit.md').read_text(encoding='utf-8'),
            'content/hidden.md': '---\ntitle: Hidden\nnoindex: true\n---\nHiddenuniqueterm',
            'content/draft.md': '---\ntitle: Draft\ndraft: true\n---\nDraftuniqueterm',
            'content/landing-pages/_index.md': (ROOT / 'content/landing-pages/_index.md').read_text(encoding='utf-8'),
            'content/landing-pages/unlisted/index.md': '---\ntitle: Unlisted\nnoindex: false\n---\nUnlisteduniqueterm',
            'content/landing-pages/unlisted/style.css': 'body { color: black; }',
            'static/admin/index.html': '<html lang="en"><body>Adminuniqueterm</body></html>',
        }
        for filename, text in files.items():
            target = cls.site / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
        result = subprocess.run([
            sys.executable, str(ROOT / 'scripts/build.py'), '--source', str(cls.site),
            '--destination', str(cls.output), '--minify', '--cleanDestinationDir',
        ], capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.fragments = []
        for file in (cls.output / 'pagefind/fragment').glob('*.pf_fragment'):
            raw = gzip.decompress(file.read_bytes())
            cls.fragments.append(json.loads(raw.removeprefix(b'pagefind_dcd')))

    def test_body_content_and_computed_message_url_are_indexed(self):
        by_url = {fragment['url']: fragment for fragment in self.fragments}
        self.assertIn('Bodyonlyuniqueterm', by_url['/visible/']['content'])
        self.assertIn('Messageuniqueterm', by_url['/messages/part-7/']['content'])
        self.assertEqual(by_url['/visible/']['meta']['title'], 'Visible Page')

    def test_nonpublic_and_shared_content_are_excluded(self):
        indexed = json.dumps(self.fragments).lower()
        for term in ('footeruniqueterm', 'hiddenuniqueterm', 'draftuniqueterm',
                     'unlisteduniqueterm', 'adminuniqueterm'):
            with self.subTest(term=term):
                self.assertNotIn(term, indexed)
        urls = {fragment['url'] for fragment in self.fragments}
        self.assertNotIn('/search/', urls)
        self.assertNotIn('/404.html', urls)
        self.assertTrue((self.output / 'landing-pages/unlisted/index.html').exists())

    def test_result_type_and_series_metadata(self):
        by_url = {fragment['url']: fragment['meta'] for fragment in self.fragments}
        for url, expected in (
            ('/visible/', 'page'),
            ('/', 'home'),
            ('/messages/part-7/', 'message'),
            ('/messages/hope/', 'series'),
            ('/discipleship-guide/example/', 'guide'),
            ('/students/example/', 'ministry'),
        ):
            with self.subTest(url=url):
                self.assertEqual(by_url[url]['type'], expected)
        for url in ('/messages/part-7/', '/messages/hope/',
                    '/messages/hope/inherited-series/', '/discipleship-guide/example/'):
            with self.subTest(url=url):
                self.assertEqual(by_url[url]['series'], 'Finding Hope')
        self.assertNotIn('series', by_url['/visible/'])

    def test_related_ministries_stay_visible_but_are_not_indexed(self):
        by_url = {fragment['url']: fragment for fragment in self.fragments}
        waumba = by_url['/children/waumba-land/']['content'].lower()
        self.assertIn('waumba land', waumba)
        self.assertNotIn('transit', waumba)
        self.assertNotIn('environments for every age', waumba)
        self.assertIn('transit', by_url['/students/transit/']['content'].lower())
        html = (self.output / 'children/waumba-land/index.html').read_text(encoding='utf-8')
        self.assertIn('Environments for every age.', html)
        self.assertIn('/students/transit/', html)

    def test_filter_groups_and_date_sort_preserve_undated_pages(self):
        by_url = {fragment['url']: fragment for fragment in self.fragments}
        for url, category in (
            ('/messages/part-7/', 'messages'),
            ('/messages/hope/', 'messages'),
            ('/discipleship-guide/example/', 'guides'),
            ('/students/example/', 'ministries'),
            ('/visible/', 'other'),
        ):
            with self.subTest(url=url):
                self.assertEqual(by_url[url]['filters']['category'], [category])
        self.assertEqual(by_url['/messages/part-7/']['meta']['date'], '2026-10-18')
        self.assertEqual(by_url['/discipleship-guide/example/']['meta']['date'], '2026-11-15')
        self.assertNotIn('date', by_url['/visible/']['meta'])

        class SortParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('data-pagefind-sort') == 'date[content]':
                    self.values.append(int(attrs['content']))

        values = {}
        for url in by_url:
            parser = SortParser()
            parser.feed((self.output / url.strip('/') / 'index.html').read_text(encoding='utf-8'))
            self.assertEqual(len(parser.values), 1, url)
            values[url] = parser.values[0]
        self.assertGreater(values['/discipleship-guide/example/'], values['/messages/part-7/'])
        self.assertGreater(values['/messages/part-7/'], values['/visible/'])
        self.assertEqual(values['/visible/'], 0)

    def test_search_page_and_local_engine_are_published(self):
        html = (self.output / 'search/index.html').read_text(encoding='utf-8')
        self.assertIn('name=q', html)
        self.assertIn('role=status', html)
        self.assertIn('data-pagefind-url=/pagefind/pagefind.js', html)
        self.assertNotIn('data-pagefind-body', html)
        self.assertIn('name=type', html)
        self.assertIn('name=sort', html)
        self.assertIn('Most relevant', html)
        self.assertIn('Newest first', html)
        self.assertTrue((self.output / 'pagefind/pagefind.js').exists())
        self.assertFalse((self.output / 'index.json').exists())


class BuildFailureTests(unittest.TestCase):
    def test_hugo_failure_stops_indexing(self):
        with patch.object(sys, 'argv', ['build.py']), patch.object(build.subprocess, 'call', return_value=3) as call:
            self.assertEqual(build.main(), 3)
            self.assertEqual(call.call_count, 1)

    def test_index_failure_fails_build(self):
        with patch.object(sys, 'argv', ['build.py']), patch.object(build.subprocess, 'call', side_effect=[0, 5]) as call:
            self.assertEqual(build.main(), 5)
            self.assertIn('pagefind', call.call_args.args[0])


if __name__ == '__main__':
    unittest.main()

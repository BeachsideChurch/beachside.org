"""Run with Python plus PyYAML and beautifulsoup4; requires Hugo on PATH."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bs4 import BeautifulSoup
import yaml

from import_discipleship_guide import render_doc

ROOT = Path(__file__).resolve().parents[1]


class GuideTests(unittest.TestCase):
    def test_import_keeps_markdown_readable_and_lossless(self):
        for prose in ['First paragraph.\n\nSecond paragraph.',
                      '**Heading**  \nA hard break.', 'Indented\n    code\n',
                      '\nLeading blank line\n\n', 'Quotes: "yes" and Unicode: café']:
            with self.subTest(prose=prose):
                output = render_doc({'title': 'Readable', 'fields': {
                    'spiritual_practice': prose,
                    'daily_devotions': {'monday': {'reflection': prose}},
                }})
                data = yaml.safe_load(output.split('---', 2)[1])
                self.assertEqual(data['spiritual_practice'], prose)
                self.assertEqual(data['daily_devotions'][0]['reflection'], prose)
                self.assertNotIn(r'\n', output)
                self.assertIn('  - day: Monday', output)

    def test_existing_guides_match_cms_schema(self):
        config = yaml.safe_load((ROOT / 'static/admin/config.yml').read_text())
        collection = next(c for c in config['collections'] if c['name'] == 'discipleship_guides')
        fields = {f['name']: f for f in collection['fields']}
        self.assertTrue(collection['create'])
        for path in (ROOT / collection['folder']).glob('*.md'):
            data = yaml.safe_load(path.read_text().split('---', 2)[1])
            if path.name == '_index.md':
                self.assertNotEqual(data.get('guide_format'), 'structured')
                continue
            self.assertEqual(data['guide_format'], 'structured', path.name)
            self.assertFalse(set(data) - set(fields), path.name)
            for key, value in data.items():
                if fields[key]['widget'] == 'list':
                    self.assertIsInstance(value, list)
                    names = {f['name'] for f in fields[key]['fields']}
                    for item in value:
                        self.assertFalse(set(item) - names, (path.name, key))
                        for child in fields[key]["fields"]:
                            if child.get("required", True):
                                self.assertTrue(item.get(child["name"]), (path.name, key, child["name"]))

    def test_import_and_render_sections(self):
        payload = json.loads((ROOT / 'imports/discipleship-guide/example-discipleship-guide-import.json').read_text())
        payload['title'] = 'CMS regression guide'
        fields = payload['fields']
        fields['message_recap'] = '**Editable recap**'
        fields['daily_devotions'] = {
            'tuesday': {'scripture': 'John 3:16', 'scripture_url': 'https://www.bible.com/test', 'reflection': '**Tuesday reflection**'},
            'friday': {'reflection': '<p>Friday reflection</p>'},
        }
        imported = render_doc(payload)
        data = yaml.safe_load(imported.split('---', 2)[1])
        self.assertTrue(data['draft'])
        self.assertEqual(data['daily_devotions'][0]['day'], 'Tuesday')
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / 'content', temp / 'content')
            guides = temp / 'content/discipleship-guide'
            (guides / 'cms-regression-guide.md').write_text(imported)
            (guides / 'cms-empty-guide.md').write_text('---\ntitle: Empty\nguide_format: structured\n---\n')
            subprocess.run(['hugo', '--buildDrafts', '--contentDir', str(temp / 'content'), '--destination', str(temp / 'public')], cwd=ROOT, check=True, capture_output=True)
            page = BeautifulSoup((temp / 'public/discipleship-guide/cms-regression-guide/index.html').read_text(), 'html.parser')
            self.assertEqual(len(page.select('.dg-label')), 9)
            self.assertEqual(page.select_one('.dg-prose strong').text, 'Editable recap')
            self.assertEqual(page.select_one('.dg-devo-tab.active').text, 'Tuesday')
            self.assertEqual(len(page.select('.dg-devo-panel.active')), 1)
            self.assertEqual(page.select_one('.dg-devo-scripture-pill')['href'], 'https://www.bible.com/test')
            for tab in page.select('.dg-devo-tab'):
                self.assertIsNotNone(page.find(id='devo-' + tab['data-day']))
            self.assertIn('youtube-nocookie.com/embed/example', page.select_one('.dg-video iframe')['src'])
            empty = BeautifulSoup((temp / 'public/discipleship-guide/cms-empty-guide/index.html').read_text(), 'html.parser')
            self.assertFalse(empty.select('.dg-label, .dg-devo-tab, iframe'))


if __name__ == '__main__':
    unittest.main()

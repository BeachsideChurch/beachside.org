"""Check that the page editors can represent every existing content field."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ContentEditorTests(unittest.TestCase):
    def check_fields(self, fields, data, location):
        names = {field['name'] for field in fields}
        self.assertFalse(set(data) - names, (location, set(data) - names))
        self.assertEqual(len(fields), len(names), location)
        for field in fields:
            name = field['name']
            if name not in data:
                self.assertFalse(field.get('required', True), (location, name))
                continue
            value = data[name]
            widget = field['widget']
            here = f'{location}.{name}'
            if widget == 'object':
                self.assertIsInstance(value, dict, here)
                self.check_fields(field['fields'], value, here)
            elif widget == 'list':
                self.assertIsInstance(value, list, here)
                for item in value:
                    if 'types' in field:
                        key = field.get('typeKey', 'type')
                        variants = {v['name']: v for v in field['types']}
                        self.assertIn(item[key], variants, here)
                        self.check_fields(variants[item[key]]['fields'],
                                          {k: v for k, v in item.items() if k != key}, here)
                    elif 'fields' in field:
                        self.check_fields(field['fields'], item, here)
                    else:
                        self.assertIsInstance(item, str, here)
            elif widget == 'boolean':
                self.assertIsInstance(value, bool, here)
            elif widget == 'number':
                self.assertIsInstance(value, int, here)
                self.assertGreaterEqual(value, field.get('min', value), here)
                self.assertLessEqual(value, field.get('max', value), here)
            else:
                self.assertIsInstance(value, str, here)
                if widget == 'select':
                    self.assertIn(value, field['options'], here)

    def test_existing_pages_have_complete_editor_fields(self):
        config = yaml.safe_load((ROOT / 'static/admin/config.yml').read_text())
        collections = {c['name']: c for c in config['collections']}
        covered = set()
        for name in ('homepage', 'site_pages', 'ministry_pages'):
            for entry in collections[name]['files']:
                path = ROOT / entry['file']
                covered.add(path)
                source = path.read_text()
                if path.suffix == '.md':
                    _, frontmatter, body = source.split('---', 2)
                    data = yaml.safe_load(frontmatter)
                    if body.strip():
                        data['body'] = body
                else:
                    data = yaml.safe_load(source)
                with self.subTest(file=entry['file']):
                    self.check_fields(entry['fields'], data, entry['file'])
        for path in (ROOT / 'content').rglob('*.md'):
            if any(part in path.parts for part in ('messages', 'discipleship-guide', 'landing-pages')):
                continue
            if path.name == 'watch-live.md':
                continue  # Existing dedicated live-video editor.
            data = yaml.safe_load(path.read_text().split('---', 2)[1])
            if data.get('layout') in ('landing', 'ministry'):
                self.assertIn(path, covered)


if __name__ == '__main__':
    unittest.main()

"""Verify computed message slugs and URLs; requires PyYAML and Hugo on PATH."""
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import urlopen

import yaml

from hugo import prepare_message, sync_content
import hugo as build

ROOT = Path(__file__).resolve().parents[1]


class MessageURLTests(unittest.TestCase):
    def test_title_punctuation(self):
        for title, expected in [
            ('Happy Birthday U.S.A.', 'happy-birthday-usa'),
            ("What's Next?", 'whats-next'),
            ('Hope: Now & Forever!', 'hope-now-forever'),
            ('Café — A New Beginning', 'café-a-new-beginning'),
        ]:
            with self.subTest(title=title):
                raw = ('---\n' + yaml.safe_dump({'title': title}) + '---\n').encode()
                result = yaml.safe_load(prepare_message(raw).decode().split('---', 2)[1])
                self.assertEqual(result['slug'], expected)
        raw = b'---\ntitle: U.S.A.\nslug: custom.slug\n---\n'
        self.assertEqual(prepare_message(raw), raw)

    def test_slug_defaults_preserve_content(self):
        for extra, expected in [
            ('part_number: 3', 'part-3'),
            ('part_number: "4"', 'part-4'),
            ('series: Example\npart_number: 3', 'part-3'),
            ('slug: ""\npart_number: 3', 'part-3'),
            ('slug: null\npart_number: 3', 'part-3'),
            ('slug:\npart_number: 3', 'part-3'),
            ('slug: custom\npart_number: 3', 'custom'),
            ('slug: custom', 'custom'),
            ('series: Example', 'hope'),
            ('part_number: 0', 'hope'),
            ('part_number: -1', 'hope'),
            ('part_number: true', 'hope'),
            ('part_number: 1.5', 'hope'),
            ('part_number: ""', 'hope'),
        ]:
            for newline in ('\n', '\r\n'):
                with self.subTest(extra=extra, newline=newline):
                    source = ('---\ntitle: Hope # Keep this comment\n' + extra
                              + '\ndescription: >-\n  Keep this text.\n---\n\n**Body**\n')
                    raw = source.replace('\n', newline).encode('utf-8')
                    result = prepare_message(raw)
                    data = yaml.safe_load(result.decode().split('---', 2)[1])
                    self.assertEqual(data.get('slug'), expected)
                    self.assertIn(b'# Keep this comment', result)
                    self.assertTrue(result.endswith((newline + '**Body**' + newline).encode()))
                    self.assertEqual(prepare_message(result), result)
                    if expected == 'custom':
                        self.assertEqual(result, raw)

    def test_preview_sync_updates_and_deletes_without_editing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, staged = root / 'source', root / 'staged'
            (source / 'messages/bundle').mkdir(parents=True)
            staged.mkdir()
            page = source / 'messages/bundle/index.md'
            raw = b'---\ntitle: Example\npart_number: 2\n---\n'
            page.write_bytes(raw)
            section = source / 'messages/_index.md'
            section.write_bytes(raw)
            resource = source / 'messages/bundle/image.jpg'
            resource.write_bytes(b'image bytes')
            snapshot = sync_content(source, staged)
            self.assertEqual(page.read_bytes(), raw)
            self.assertIn(b'slug: part-2', (staged / 'messages/bundle/index.md').read_bytes())
            self.assertEqual((staged / 'messages/_index.md').read_bytes(), raw)
            self.assertEqual((staged / 'messages/bundle/image.jpg').read_bytes(), b'image bytes')
            page.write_bytes(raw.replace(b'2', b'35'))
            snapshot = sync_content(source, staged, snapshot)
            self.assertIn(b'slug: part-35', (staged / 'messages/bundle/index.md').read_bytes())
            page.unlink()
            resource.unlink()
            sync_content(source, staged, snapshot)
            self.assertFalse((staged / 'messages/bundle').exists())

    def test_title_fallback_and_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            shutil.copyfile(ROOT / 'hugo.toml', site / 'hugo.toml')
            (site / 'themes/beachside').mkdir(parents=True)
            layouts = site / 'layouts/_default'
            layouts.mkdir(parents=True)
            for name in ('single.html', 'list.html'):
                (layouts / name).write_text('{{ .RelPermalink }}', encoding='utf-8')

            cases = [
                ('messages/_index.md', 'Watch Messages', '', '/messages/'),
                ('messages/a-series/source-name.md', 'Finding Hope', '',
                 '/messages/a-series/finding-hope/'),
                ('messages/a-series/blank.md', 'Another Title', 'slug: ""\n',
                 '/messages/a-series/another-title/'),
                ('messages/a-series/custom.md', 'Changed Title', 'slug: fixed-slug\n',
                 '/messages/a-series/fixed-slug/'),
                ('messages/standalone.md', 'Standalone Title', '',
                 '/messages/standalone-title/'),
                ('messages/bundle/index.md', 'Bundle Title', '',
                 '/messages/bundle-title/'),
                ('messages/explicit.md', 'Explicit URL', 'url: /custom-message/\n',
                 '/custom-message/'),
                ('messages/explicit-part.md', 'Explicit Part URL',
                 'part_number: 6\nurl: /custom-part/\n', '/custom-part/'),
                ('messages/a-series/numbered.md', 'Different Part Title',
                 'series: A Series\npart_number: 3\n', '/messages/a-series/part-3/'),
                ('messages/a-series/override.md', 'Override Part',
                 'part_number: 4\nslug: special-message\n', '/messages/a-series/special-message/'),
                ('messages/no-series.md', 'No Series', 'part_number: 5\n', '/messages/part-5/'),
                ('messages/a-series/_index.md', 'Different Series Title',
                 'series: A Series\npart_number: 1\n', '/messages/a-series/'),
                ('other/source.md', 'Other Title', '', '/other/source/'),
            ]
            for filename, title, extra, _ in cases:
                path = site / 'content' / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'---\ntitle: "{title}"\n{extra}---\n', encoding='utf-8')

            originals = {p: p.read_bytes() for p in (site / 'content').rglob('*.md')}
            subprocess.run([sys.executable, str(ROOT / 'scripts/hugo.py'), '--source', str(site)], check=True,
                           capture_output=True, text=True)
            for path, raw in originals.items():
                self.assertEqual(path.read_bytes(), raw)
            for filename, _, _, url in cases:
                with self.subTest(file=filename):
                    output = site / 'public' / url.strip('/') / 'index.html'
                    self.assertEqual(output.read_text(encoding='utf-8'), url)

    def test_live_preview_recomputes_after_source_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / 'content/messages').mkdir(parents=True)
            (site / 'layouts/_default').mkdir(parents=True)
            (site / 'hugo.toml').write_text(
                "baseURL = 'http://localhost/'\n[permalinks.page]\n"
                "messages = '/:sections/:slug/'\n", encoding='utf-8')
            (site / 'layouts/_default/single.html').write_text('{{ .RelPermalink }}')
            page = site / 'content/messages/source.md'
            page.write_text('---\ntitle: Example\npart_number: 2\n---\n')
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            original_popen, original_sleep = subprocess.Popen, time.sleep
            processes = []
            seen = []
            deadline = time.monotonic() + 20

            def start(command):
                process = original_popen(command, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                processes.append(process)
                return process

            def check_preview(_):
                original_sleep(0.2)
                self.assertLess(time.monotonic(), deadline, 'Live preview did not update')
                expected = '/messages/part-2/' if not seen else '/messages/part-35/'
                try:
                    with urlopen(f'http://127.0.0.1:{port}{expected}', timeout=0.5) as response:
                        self.assertIn(expected, response.read().decode())
                except (URLError, TimeoutError):
                    return
                seen.append(expected)
                if len(seen) == 1:
                    page.write_text('---\ntitle: Example\npart_number: 35\n---\n')
                else:
                    processes[0].terminate()

            arguments = ['hugo.py', '--source', str(site), 'server', '--port', str(port),
                         '--bind', '127.0.0.1', '--disableLiveReload', '--disableFastRender']
            with patch.object(sys, 'argv', arguments), patch.object(build.subprocess, 'Popen', start), \
                    patch.object(build.time, 'sleep', check_preview):
                build.main()
            self.assertEqual(seen, ['/messages/part-2/', '/messages/part-35/'])
            self.assertNotIn('slug:', page.read_text())


if __name__ == '__main__':
    unittest.main()

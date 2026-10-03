"""Exercise the actual Hugo event templates against a local Church Center fixture."""
import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class EventsBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='beachside-events-test-')
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        self.pages = {1: {'data': [], 'links': {}}}
        self.requests = []
        self.failure = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, value, status=200, content_type='application/json', cookies=False):
                body = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                if cookies:
                    self.send_header('Set-Cookie', 'session=fixture; Path=/; HttpOnly')
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                owner.requests.append(self.path)
                path = urlparse(self.path)
                if path.path == '/web_boot_props':
                    self.send({'configuration': {'csrfToken': 'fixture-csrf'}}, cookies=True)
                elif path.path == '/image.png':
                    if owner.failure == 'image':
                        self.send({}, 404)
                    else:
                        self.send(PNG, content_type='image/png')
                elif path.path == '/registrations/v2/events':
                    if self.headers.get('Authorization') != 'Bearer fixture-anonymous-token':
                        self.send({}, 401)
                        return
                    query = parse_qs(path.query)
                    if 'page' not in query:
                        if query.get('filter') != ['unarchived,published'] or query.get('order') != ['starts_at']:
                            self.send({}, 400)
                            return
                    if owner.failure == 'http':
                        self.send({}, 403)
                    elif owner.failure == 'json':
                        self.send(b'{bad json', content_type='application/vnd.api+json; charset=utf-8')
                    else:
                        self.send(owner.pages[int(query.get('page', ['1'])[0])],
                                  content_type='application/vnd.api+json; charset=utf-8')
                else:
                    self.send({}, 404)

            def do_POST(self):
                if (self.path != '/sessions/tokens'
                        or self.headers.get('X-CSRF-Token') != 'fixture-csrf'
                        or self.headers.get('Cookie') != 'session=fixture'):
                    self.send({}, 403)
                    return
                self.send({'data': {'attributes': {'token': 'fixture-anonymous-token'}}})

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.origin = f'http://127.0.0.1:{server.server_port}'
        self.api = self.origin + '/registrations/v2/events'
        templates = ROOT / 'themes/beachside/layouts'
        shutil.copytree(templates / 'partials/church-center', self.site / 'layouts/partials/church-center')
        for name in ['image-attrs.html', 'image-url.html']:
            shutil.copy(templates / 'partials' / name, self.site / 'layouts/partials' / name)
        (self.site / 'layouts/events').mkdir()
        shutil.copy(templates / 'events/list.html', self.site / 'layouts/events/list.html')
        integration = self.site / 'layouts/partials/church-center/events.html'
        integration.write_text(integration.read_text()
                               .replace('https://beachsidecc.churchcenter.com', self.origin)
                               .replace('https://api.churchcenter.com/registrations/v2/events', self.api))
        (self.site / 'layouts/_default').mkdir()
        (self.site / 'layouts/_default/baseof.html').write_text('{{ block "main" . }}{{ end }}')
        (self.site / 'content/events').mkdir(parents=True)
        shutil.copy(ROOT / 'content/events/_index.md', self.site / 'content/events/_index.md')
        config = tomllib.loads((ROOT / 'hugo.toml').read_text())
        # Retain production caching and media-type rules; allow only the fixture server.
        config['security']['http']['urls'] = ['^http://127\\.0\\.0\\.1:']
        minimal = {key: config[key] for key in ['caches', 'security']}
        minimal.update({'baseURL': 'https://site.test/', 'disableKinds': ['taxonomy', 'term', 'RSS', 'sitemap']})
        (self.site / 'hugo.json').write_text(json.dumps(minimal))

    def event(self, id, name, featured=False, image=True):
        return {'type': 'Event', 'id': str(id), 'attributes': {
            'name': name, 'featured': featured,
            'logo_url': self.origin + '/image.png' if image else None,
            'event_time': 'October 2–4, 2026', 'starts_at': '2026-10-02T22:00:00Z',
            'registration_state': 'closed',
        }}

    def build(self, success=True):
        result = subprocess.run(['hugo', '--source', str(self.site), '--cacheDir', str(self.site / 'cache')],
                                text=True, capture_output=True, timeout=45)
        output = result.stdout + result.stderr
        self.assertNotIn('fixture-anonymous-token', output)
        if success:
            self.assertEqual(result.returncode, 0, output)
            return (self.site / 'public/events/index.html').read_text()
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn('Church Center:', output)

    def test_pagination_featured_images_and_refresh(self):
        self.pages = {
            1: {'data': [self.event(1, 'First & Friends')], 'links': {'next': self.api + '?page=2'}},
            2: {'data': [self.event(2, 'Featured', featured=True, image=False)], 'links': {}},
        }
        html = self.build()
        self.assertLess(html.index('<strong>Featured'), html.index('<strong>First &amp; Friends'))
        self.assertEqual(html.count('class="event-card"'), 2)
        self.assertIn('https://beachsidecc.churchcenter.com/registrations/events/2', html)
        self.assertIn('October 2–4, 2026', html)
        self.assertIn('datetime="2026-10-02T22:00:00Z"', html)
        image = re.search(r'<img src="([^"]+)"', html).group(1)
        self.assertRegex(image, r'^/images/events/1\.[a-f0-9]+\.png$')
        self.assertEqual((self.site / 'public' / image.lstrip('/')).read_bytes(), PNG)
        self.assertNotIn(self.origin, html)
        self.pages = {1: {'data': [self.event(3, 'Replacement')], 'links': {}}}
        html = self.build()
        self.assertIn('<strong>Replacement', html)
        self.assertNotIn('<strong>Featured', html)
        self.assertNotIn('<strong>First', html)
        self.assertEqual(self.requests.count('/web_boot_props'), 2)

    def test_empty_listing(self):
        html = self.build()
        self.assertIn('No events are currently listed.', html)
        self.assertNotIn('class="event-card"', html)

    def test_failures_do_not_silently_publish_empty_events(self):
        for failure in ['http', 'json', 'image']:
            with self.subTest(failure=failure):
                self.failure = failure
                self.pages = {1: {'data': [self.event(1, 'Event')], 'links': {}}}
                self.build(success=False)

    def test_invalid_payload_and_pagination(self):
        for payload in [
            {'unexpected': []},
            {'data': [{'type': 'Event', 'id': 'invalid', 'attributes': {}}]},
            {'data': [], 'links': {'next': 'https://example.com/steal-token'}},
            {'data': [], 'links': {'next': self.api + '?page=2'}},
        ]:
            with self.subTest(payload=payload):
                self.pages = {1: payload, 2: {'data': [], 'links': {'next': self.api + '?page=2'}}}
                self.build(success=False)


if __name__ == '__main__':
    unittest.main()

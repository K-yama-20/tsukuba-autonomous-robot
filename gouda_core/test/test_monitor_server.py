"""HTTP/SSE smoke tests of monitor_server (ND-02) without ROS. Design test: TS-25 (stage 5-2).

Checked: the page and assets are served from web/; /api/state returns the provider's snapshot; commands are dispatched
and refusals come back as 409 with the message (never hidden); invalid JSON is rejected; /api/config round-trips;
the SSE stream sends the current state immediately and again when the revision changes (reconnect gets latched state).
"""
import json
import socket
import sys
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.monitor_server import MonitorServer  # noqa: E402
from gouda_core.monitor_core import MonitorCore  # noqa: E402

WEB = Path(__file__).resolve().parents[1] / 'web'


class MonitorServerTests(unittest.TestCase):
    def setUp(self):
        self.core = MonitorCore()
        self.commands = []
        def command(name, body):
            self.commands.append((name, body))
            if name == 'pause': return {'ok': False, 'message': 'refused: pause is not accepted in mode manual'}
            return {'ok': True, 'message': f'{name} accepted'}
        self.cfg = {'values': {'lidar_mount_z_m': 'UNKNOWN'}, 'kinds': {'lidar_mount_z_m': 'number'}, 'config_revision': 0, 'updated_at': None, 'path': 'x', 'unknown_count': 1}
        def config_update(body):
            self.cfg['values'].update(body); self.cfg['config_revision'] += 1
            return {'ok': True, 'message': 'saved', 'config': self.cfg}
        self.server = MonitorServer(WEB, self.core.snapshot, lambda: self.cfg, command, config_update, port=0, keepalive_s=0.5)
        self.url = self.server.start()

    def tearDown(self): self.server.stop()

    def get(self, path):
        with urllib.request.urlopen(self.url.rstrip('/') + path, timeout=5) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()

    def post(self, path, body):
        req = urllib.request.Request(self.url.rstrip('/') + path, data=body.encode('utf-8') if isinstance(body, str) else json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=5) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_page_and_assets(self):
        st, ct, body = self.get('/'); self.assertEqual(st, 200); self.assertIn('text/html', ct); self.assertIn(b'GOUDA', body)
        st, ct, _ = self.get('/static/app.js'); self.assertEqual(st, 200); self.assertIn('javascript', ct)
        st, _, _ = self.get('/static/style.css'); self.assertEqual(st, 200)
        with self.assertRaises(urllib.error.HTTPError): self.get('/static/../setup.py')

    def test_state_reflects_core(self):
        self.core.on_mode({'mode': 1, 'state_revision': 1})
        st, _, body = self.get('/api/state'); s = json.loads(body)
        self.assertEqual(st, 200); self.assertEqual(s['mode']['name'], 'MANUAL'); self.assertEqual(s['esp32']['freshness']['status'], 'NOT_RECEIVED')

    def test_commands_dispatch_and_refusal_is_visible(self):
        st, j = self.post('/api/command/record_log_start', {}); self.assertEqual(st, 200); self.assertTrue(j['ok'])
        st, j = self.post('/api/command/pause', {}); self.assertEqual(st, 409); self.assertFalse(j['ok']); self.assertIn('refused', j['message'])
        st, j = self.post('/api/command/pause', '{not json'); self.assertEqual(st, 400)
        self.assertEqual([c[0] for c in self.commands], ['record_log_start', 'pause'])

    def test_config_roundtrip(self):
        st, _, body = self.get('/api/config'); self.assertEqual(json.loads(body)['config_revision'], 0)
        st, j = self.post('/api/config', {'lidar_mount_z_m': 0.95}); self.assertEqual(st, 200); self.assertEqual(j['config']['config_revision'], 1)
        _, _, body = self.get('/api/config'); self.assertEqual(json.loads(body)['values']['lidar_mount_z_m'], 0.95)

    def test_sse_sends_current_state_then_updates(self):
        self.core.on_mode({'mode': 1, 'state_revision': 1})
        host, port = self.url[len('http://'):].rstrip('/').split(':')
        s = socket.create_connection((host, int(port)), timeout=5)
        s.sendall(b'GET /api/events HTTP/1.1\r\nHost: x\r\n\r\n')
        buf = b''
        def read_until(marker, limit=20):
            nonlocal buf
            for _ in range(limit):
                if marker in buf: return True
                try: chunk = s.recv(65536)
                except socket.timeout: return False
                if not chunk: return False
                buf += chunk
            return False
        self.assertTrue(read_until(b'event: state'))
        first = buf.split(b'data: ')[1].split(b'\n')[0]; self.assertEqual(json.loads(first)['mode']['name'], 'MANUAL')
        n_before = buf.count(b'event: state')
        self.core.on_mode({'mode': 4, 'state_revision': 2}); self.server.notify(self.core.connection_revision)
        self.assertTrue(read_until(b'"state_revision": 2'))
        self.assertGreater(buf.count(b'event: state'), n_before)
        s.close()


class ExtraRouteTests(unittest.TestCase):
    """Route hooks used by the waypoint_manager API (stage 5-4): a handler may return raw bytes or a JSON dict."""
    def test_get_and_post_hooks(self):
        core = MonitorCore()
        srv = MonitorServer(WEB, core.snapshot, lambda: {}, lambda n, b: {'ok': True, 'message': ''}, lambda b: {'ok': True}, port=0, keepalive_s=0.5,
                            get_routes={'/api/map/': lambda rest, q: (200, 'image/png', b'\x89PNG' + rest.encode()) if rest.endswith('map.png') else {'ok': False, 'message': 'no'}},
                            post_routes={'/api/waypoints/save': lambda rest, body: {'ok': bool(body.get('set')), 'message': 'saved' if body.get('set') else 'invalid'}})
        url = srv.start()
        try:
            with urllib.request.urlopen(url.rstrip('/') + '/api/map/o/1/map.png', timeout=5) as r:
                self.assertEqual(r.headers.get('Content-Type'), 'image/png'); self.assertTrue(r.read().startswith(b'\x89PNG'))
            try:
                urllib.request.urlopen(url.rstrip('/') + '/api/map/o/1/x', timeout=5); self.fail('expected 409')
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 409)
            req = urllib.request.Request(url.rstrip('/') + '/api/waypoints/save', data=json.dumps({'set': {'a': 1}}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5) as r: self.assertEqual(json.loads(r.read())['message'], 'saved')
        finally:
            srv.stop()


if __name__ == '__main__': unittest.main()

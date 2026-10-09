"""Local HTTP/SSE server of gouda_monitor (ND-02). Standard library only; no ROS dependency.

Serves the static page from the package's web/ directory and a small JSON API:
  GET  /                     the monitor page (16:9 operating screen, design/docs/gouda_gui_design_rules.md)
  GET  /static/<file>        page assets
  GET  /api/state            current snapshot (JSON)
  GET  /api/events           server-sent events: a snapshot whenever the revision changes, plus a keep-alive
  GET  /api/config           /config values
  POST /api/command/<name>   human operation; JSON body is passed to the command handler
  POST /api/config           update /config fields (JSON object of field: value)

Binds 127.0.0.1 only (RQ-I044: no screen forwarding; the page is opened on the PC's own desktop). With port 0 the OS
chooses a free port and the bound URL is written to url_file so that gouda.sh can print it. No port number is
hard-coded here (RQ-I076); a fixed port is a launch argument (PRM-26).
"""
from __future__ import annotations

import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse


class MonitorServer:
    def __init__(self, web_dir: Path, state_provider: Callable[[], dict], config_provider: Callable[[], dict],
                 command_handler: Callable[[str, dict], dict], config_handler: Callable[[dict], dict],
                 host: str = '127.0.0.1', port: int = 0, url_file: Optional[Path] = None, keepalive_s: float = None):
        if keepalive_s is None:
            raise ValueError('keepalive_s must be given by the node from its ROS parameter (PRM-28); the server has no default')
        self.web_dir = Path(web_dir); self.state_provider = state_provider; self.config_provider = config_provider
        self.command_handler = command_handler; self.config_handler = config_handler
        self.host, self.port, self.url_file, self.keepalive_s = host, port, url_file, keepalive_s
        self._cv = threading.Condition(); self._revision = -1
        self.httpd: Optional[ThreadingHTTPServer] = None; self._thread: Optional[threading.Thread] = None

    # ---- lifecycle ----
    def start(self) -> str:
        server = self
        handler = type('MonitorHandler', (_Handler,), {'server_ref': server})
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, name='gouda_monitor_http', daemon=True)
        self._thread.start()
        if self.url_file:
            self.url_file.parent.mkdir(parents=True, exist_ok=True)
            self.url_file.write_text(self.url + '\n', encoding='utf-8')
        return self.url

    @property
    def url(self) -> str:
        return f'http://{self.host}:{self.port}/'

    def stop(self):
        if self.httpd: self.httpd.shutdown(); self.httpd.server_close()
        if self._thread: self._thread.join(timeout=5)

    def notify(self, revision: int):
        """Wake SSE streams when the state revision changed."""
        with self._cv:
            if revision != self._revision:
                self._revision = revision; self._cv.notify_all()

    def wait_change(self, seen: int, timeout: float) -> bool:
        with self._cv:
            if self._revision != seen: return True
            return self._cv.wait_for(lambda: self._revision != seen, timeout=timeout)


class _Handler(BaseHTTPRequestHandler):
    server_ref: MonitorServer = None  # set per server instance
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):  # keep the node log clean; the page shows its own connection state
        pass

    # ---- helpers ----
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store'); self.end_headers()
        self.wfile.write(body)

    def _file(self, rel: str):
        root = self.server_ref.web_dir.resolve(); path = (root / rel).resolve()
        if root not in path.parents and path != root or not path.is_file():
            return self._json({'error': 'not found'}, 404)
        body = path.read_bytes(); ctype = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json'): ctype += '; charset=utf-8'
        self.send_response(200); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        if not raw: return {}
        try:
            obj = json.loads(raw.decode('utf-8'))
        except ValueError:
            return {'_invalid_json': True}
        return obj if isinstance(obj, dict) else {'_invalid_json': True}

    # ---- routes ----
    def do_GET(self):
        p = urlparse(self.path).path
        s = self.server_ref
        if p == '/': return self._file('index.html')
        if p.startswith('/static/'): return self._file(p[len('/static/'):])
        if p == '/api/state': return self._json(s.state_provider())
        if p == '/api/config': return self._json(s.config_provider())
        if p == '/api/events': return self._sse()
        return self._json({'error': 'not found'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        s = self.server_ref
        body = self._body()
        if body.get('_invalid_json'): return self._json({'ok': False, 'message': 'invalid JSON body'}, 400)
        if p.startswith('/api/command/'):
            name = p[len('/api/command/'):]
            try:
                result = s.command_handler(name, body)
            except Exception as e:  # a failing command is reported, never hidden
                result = {'ok': False, 'message': f'command {name} failed: {e}'}
            return self._json(result, 200 if result.get('ok') else 409)
        if p == '/api/config':
            result = s.config_handler(body)
            return self._json(result, 200 if result.get('ok') else 400)
        return self._json({'error': 'not found'}, 404)

    def _sse(self):
        s = self.server_ref
        self.send_response(200); self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-store'); self.send_header('Connection', 'keep-alive'); self.end_headers()
        seen = -1
        try:
            while True:
                snap = s.state_provider(); rev = snap.get('revision', 0)
                if rev != seen:
                    seen = rev
                    self.wfile.write(f'event: state\ndata: {json.dumps(snap, ensure_ascii=False, default=str)}\n\n'.encode('utf-8')); self.wfile.flush()
                if not s.wait_change(seen, s.keepalive_s):
                    self.wfile.write(f': keepalive {time.time():.0f}\n\n'.encode('utf-8')); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

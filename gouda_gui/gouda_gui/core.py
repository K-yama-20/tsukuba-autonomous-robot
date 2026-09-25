"""ROS-independent occupancy projection, map storage, and HTTP transport."""
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def compose_pose_transform(position, quaternion, translation, rotation):
    """Apply one parent-frame rigid transform to a 3D pose."""
    x,y,z=map(float,position);qx,qy,qz,qw=map(float,rotation)
    u=(qx,qy,qz);dot=qx*x+qy*y+qz*z
    cross=(qy*z-qz*y,qz*x-qx*z,qx*y-qy*x)
    rotated=[2*dot*u[i]+(qw*qw-sum(v*v for v in u))*(x,y,z)[i]+2*qw*cross[i] for i in range(3)]
    p=[rotated[0]+translation[0],rotated[1]+translation[1],rotated[2]+translation[2]]
    ax,ay,az,aw=map(float,quaternion)
    q=(qw*ax+qx*aw+qy*az-qz*ay,
       qw*ay-qx*az+qy*aw+qz*ax,
       qw*az+qx*ay-qy*ax+qz*aw,
       qw*aw-qx*ax-qy*ay-qz*az)
    return p,q


def glim_session_output_directory(session, requested):
    """Use GLIM's reported output path when set; otherwise keep the requested path."""
    output=getattr(session, 'map_output_directory', None)
    return Path(output) if output is not None else Path(requested)


def mapping_start_backend(saved, runtime, effective_backend, validation_errors=(), *, package_available=None, glim_active=False):
    """Return the only backend safe to start, or reject stale/missing runtime state."""
    if not isinstance(saved, dict) or not isinstance(runtime, dict):
        raise RuntimeError('SLAM設定を読み込めません')
    if saved != runtime or saved.get('backend') != effective_backend:
        raise RuntimeError('保存設定と処理起動時の方式が異なります。Mission Controlを再起動してください')
    if validation_errors:
        raise RuntimeError('SLAM設定を確認してください: '+' / '.join(map(str, validation_errors)))
    backend=runtime.get('backend')
    if backend=='glim_imu':
        if package_available is not True:
            raise RuntimeError('GLIMパッケージを利用できません')
        if not glim_active:
            raise RuntimeError('GLIMのLiDAR・IMU・オドメトリ入力が準備できていません')
    elif backend=='kiss_icp':
        if glim_active:
            raise RuntimeError('KISSとGLIMが同時に有効です。Mission Controlを再起動してください')
    else:
        raise RuntimeError('SLAM方式が不正です')
    return backend


def validate_autonomy_goal(data):
    """Validate a mapless relative goal and explicit requested speed references."""
    if not isinstance(data, dict) or not isinstance(data.get('goal'), dict):
        raise ValueError('相対目標を設定してください')
    goal=data['goal']
    values={name:goal.get(name) for name in ('forward_m','left_m','yaw_rad')}
    values.update(target_v_mps=data.get('target_v_mps'),target_w_rps=data.get('target_w_rps'))
    if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) for value in values.values()):
        raise ValueError('相対目標と要求速度には有限の数値を入力してください')
    if values['target_v_mps']<=0 or values['target_w_rps']<=0:
        raise ValueError('要求速度は0より大きい値を入力してください')
    return dict(goal={name:float(values[name]) for name in ('forward_m','left_m','yaw_rad')},
                target_v_mps=float(values['target_v_mps']),target_w_rps=float(values['target_w_rps']))


def autonomy_start_blocker(*, profile_enabled, config_ready, state, state_fresh, recording_active):
    """Return a concrete reason when the explicit autonomy start gate is closed."""
    if not profile_enabled:return '自動MVPプロファイルが起動していません。gouda.sh autonomy を使用してください。'
    if not config_ready:return 'シリアル接続と取付校正の設定を完了してください。'
    if not state_fresh or not isinstance(state,dict):return '自動制御状態が未受信または古くなっています。'
    if state.get('pose_fresh') is not True:return '位置推定が更新されていません。'
    if state.get('imu_fresh') is not True:return 'IMU入力が更新されていません。'
    if state.get('calibration_ready') is not True:return str(state.get('reason') or '取付変換または制御校正が未準備です。')
    if state.get('manual_override') is True:return '手動操作を優先中です。手動入力が中立になってから状態を確認してください。'
    if state.get('phase') not in ('idle','cancelled','completed','fault'):
        return str(state.get('reason') or '自動制御の状態が開始可能ではありません。')
    if not recording_active:return 'センサー記録が動作していません。記録を開始してから再試行してください。'
    return None


def finite_pose(data):
    values = [data.get(k) for k in ('x', 'y', 'yaw')]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError('位置と向きには有限の数値を入力してください')
    if max(abs(values[0]), abs(values[1])) > 10000:
        raise ValueError('位置が許容範囲外です')
    return dict(zip(('x', 'y', 'yaw'), values))


def validate_grid(grid):
    w, h = grid['width'], grid['height']
    if type(w) is not int or type(h) is not int or not (1 <= w <= 2000 and 1 <= h <= 2000 and w*h <= 1000000):
        raise ValueError('地図の大きさが不正です')
    r = grid['resolution']
    if not isinstance(r, (int, float)) or not math.isfinite(r) or not .01 <= r <= 5:
        raise ValueError('地図の解像度が不正です')
    if grid['frame'] != 'map' or len(grid['data']) != w*h:
        raise ValueError('地図座標系またはセル数が不正です')
    finite_pose(grid['origin'])
    if any(type(v) is not int or not -1 <= v <= 100 for v in grid['data']):
        raise ValueError('地図セルが不正です')
    return grid


class ProjectionMap:
    """Bounded 2D projection in an existing map frame; NOT a SLAM estimator.

    Obstacles persist during a session; no ray can clear a hit cell. Ground and
    ceiling filtering happens before update. Unknown cells remain unknown.
    """
    def __init__(self, x=0., y=0., size=20., resolution=.1):
        n = round(size/resolution)
        self.grid = dict(width=n, height=n, resolution=resolution, frame='map',
                         origin=dict(x=x-size/2, y=y-size/2, yaw=0.), data=[-1]*(n*n))
        self.frames = 0

    def cell(self, x, y):
        g = self.grid
        return (math.floor((x-g['origin']['x'])/g['resolution']),
                math.floor((y-g['origin']['y'])/g['resolution']))

    def update(self, origin, points):
        g = self.grid; n = g['width']; ox, oy = self.cell(*origin)
        if not (0 <= ox < n and 0 <= oy < n):
            raise ValueError('計測位置が地図の範囲外です。新しい地図を開始してください')
        for px, py, *_ in points:
            if not math.isfinite(px+py):
                continue
            tx, ty = self.cell(px, py)
            dx, dy = tx-ox, ty-oy
            steps = max(abs(dx), abs(dy), 1)
            if steps > 2000:
                continue
            for j in range(steps):
                x = round(ox+dx*j/steps); y = round(oy+dy*j/steps)
                if not (0 <= x < n and 0 <= y < n):
                    break
                i = y*n+x
                if g['data'][i] != 100:
                    g['data'][i] = 0
            if 0 <= tx < n and 0 <= ty < n:
                g['data'][ty*n+tx] = 100
        self.frames += 1


class MapStore:
    def __init__(self, root):
        self.root = Path(root).expanduser(); self.root.mkdir(parents=True, exist_ok=True)

    def list(self):
        result = []
        for p in self.root.glob('*/metadata.json'):
            if p.parent.name.startswith('.'):
                continue
            try:
                result.append(json.loads(p.read_text()))
            except (OSError, ValueError):
                continue
        return sorted(result, key=lambda m: m['created'], reverse=True)

    def load(self, key):
        if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{32}', key):
            raise ValueError('地図IDが不正です')
        p = self.root/key
        return json.loads((p/'metadata.json').read_text()), validate_grid(json.loads((p/'grid.json').read_text()))

    def save(self, name, grid, mode, frames, *, details=None, finalize=None):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError('地図名は1〜80文字で入力してください')
        validate_grid(grid)
        if not any(v >= 0 for v in grid['data']):
            raise ValueError('観測された地図セルがありません')
        key = uuid.uuid4().hex; p = self.root/('.'+key); p.mkdir()
        metadata = dict(id=key, name=name.strip(), created=time.time(), mode=mode,
                        frames=frames, resolution=grid['resolution'], frame='map',
                        method='pointcloud_projection', loop_closure=False)
        # A directory rename commits all files together. Names never become paths.
        (p/'grid.json').write_text(json.dumps(grid, allow_nan=False))
        (p/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        w, h = grid['width'], grid['height']
        pixels = bytes(205 if grid['data'][y*w+x] < 0 else 0 if grid['data'][y*w+x] >= 65 else 254
                       for y in range(h-1, -1, -1) for x in range(w))
        (p/'map.pgm').write_bytes(f'P5\n{w} {h}\n255\n'.encode()+pixels)
        o = grid['origin']
        (p/'map.yaml').write_text(f'image: map.pgm\nmode: trinary\nresolution: {grid["resolution"]}\n'
                                f'origin: [{o["x"]}, {o["y"]}, {o["yaw"]}]\n'
                                'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
        if details:
            metadata.update(details)
        if finalize:
            finalize(p)
        (p/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        os.replace(p, self.root/key)
        return metadata


def serve(backend, web_root, host='127.0.0.1', port=8765):
    web_root = Path(web_root)
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, data, content_type='application/json; charset=utf-8'):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if not isinstance(data, bytes) else data
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/session':
                self.reply(200, dict(token=token)); return
            if path == '/api/state':
                self.reply(200, backend.snapshot()); return
            if path == '/api/viewer':
                self.reply(200, backend.viewer_status()); return
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                self.reply(404, dict(error='Not found')); return
            file, mime = files[path]
            self.reply(200, (web_root/file).read_bytes(), mime)

        def do_POST(self):
            if self.headers.get('X-Gouda-Session') != token:
                self.reply(403, dict(error='操作セッションが無効です。画面を再読込してください')); return
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                self.reply(403, dict(error='Origin mismatch')); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    raise ValueError('操作データのサイズが不正です')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('操作データが不正です')
                action = urlsplit(self.path).path.removeprefix('/api/')
                if not self.path.startswith('/api/'):
                    self.reply(404, dict(error='Not found')); return
                self.reply(200, backend.command(action, data))
            except (ValueError, KeyError, FileNotFoundError) as exc:
                self.reply(400, dict(error=str(exc)))
            except (RuntimeError, TimeoutError) as exc:
                self.reply(409, dict(error=str(exc)))

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    return server

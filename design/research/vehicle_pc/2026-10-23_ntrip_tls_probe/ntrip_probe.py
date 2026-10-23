# DIAGNOSTIC ONLY (bin 145): classify how the NTRIP caster in <data_root>/config/gnss_rtk.yaml answers.
# Never prints the caster, port, mountpoint, user, password or position: only categories, status codes and byte counts.
# Usage: python3 -I ntrip_probe.py <gnss_rtk.yaml> [<lat_deg> <lon_deg> read from a file path instead of argv]
import base64
import socket
import sys
import time

import yaml


def say(*a):
    print(*a, flush=True)


def classify(data: bytes) -> str:
    head = data[:64]
    if head.startswith(b'ICY 200 OK'):
        return 'ICY 200 OK (NTRIP v1 accepted)'
    if head.startswith(b'SOURCETABLE 200 OK'):
        return 'SOURCETABLE (mountpoint not served / not found)'
    if head.startswith(b'HTTP/'):
        line = head.split(b'\r\n')[0].decode('ascii', 'replace')
        parts = line.split(' ')
        return f'HTTP response, version {parts[0]}, status {parts[1] if len(parts) > 1 else "?"}'
    if not data:
        return 'no bytes'
    return f'unrecognised first bytes (printable {sum(32 <= b < 127 for b in head)}/{len(head)})'


def gga(lat, lon):
    t = time.gmtime()
    def dm(v, w):
        a = abs(v); d = int(a); m = (a - d) * 60
        return f'{d:0{w}d}{m:07.4f}'
    body = (f"GPGGA,{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00,{dm(lat, 2)},{'N' if lat >= 0 else 'S'},"
            f"{dm(lon, 3)},{'E' if lon >= 0 else 'W'},1,12,1.0,30.0,M,40.0,M,,")
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return f'${body}*{cs:02X}\r\n'.encode()


def attempt(cfg, version, send_gga_after, pos, wait_s=8.0):
    host, port = str(cfg['caster']), int(cfg['port'])
    auth = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
    req = f"GET /{cfg['mountpoint']} HTTP/1.{1 if version == 2 else 0}\r\n"
    if version == 2:
        req += f"Host: {host}\r\nNtrip-Version: Ntrip/2.0\r\n"
    req += f"User-Agent: NTRIP RTKLIB/2.4.3\r\nAuthorization: Basic {auth}\r\n\r\n"
    label = f'v{version}' + (' + GGA right after the request' if send_gga_after else '')
    try:
        s = socket.create_connection((host, port), timeout=10)
    except socket.gaierror:
        say(f'[{label}] DNS resolution failed'); return
    except OSError as e:
        say(f'[{label}] TCP connect failed: {type(e).__name__} errno {getattr(e, "errno", None)}'); return
    say(f'[{label}] TCP connected')
    s.settimeout(0.5)
    s.sendall(req.encode())
    if send_gga_after and pos:
        s.sendall(gga(*pos))
    data, t0, first_at, gga_sent = b'', time.time(), None, send_gga_after
    while time.time() - t0 < wait_s:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            chunk = None
        except OSError as e:
            say(f'[{label}] recv error {type(e).__name__}'); break
        if chunk == b'':
            say(f'[{label}] closed by caster after {time.time() - t0:.1f} s'); break
        if chunk:
            if first_at is None:
                first_at = time.time() - t0
            data += chunk
            if not gga_sent and pos and (data.startswith(b'ICY 200 OK') or data.startswith(b'HTTP/1.1 200')):
                s.sendall(gga(*pos)); gga_sent = True
    s.close()
    say(f'[{label}] first answer after {first_at if first_at is None else round(first_at, 2)} s: {classify(data)}; '
        f'total {len(data)} bytes in {wait_s:.0f} s; GGA sent: {gga_sent}')
    if data[:1] and data.find(b'\r\n\r\n') > 0 and data.startswith(b'HTTP/'):
        hdr = data[:data.find(b'\r\n\r\n')].decode('ascii', 'replace').split('\r\n')[1:]
        say(f'[{label}] response header names: {[h.split(":")[0] for h in hdr]}')
    body = data.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in data else (data[12:] if data.startswith(b'ICY 200 OK') else b'')
    say(f'[{label}] body bytes {len(body)}, RTCM3 preambles (0xD3) {body.count(bytes([0xD3]))}')


def main():
    cfg = yaml.safe_load(open(sys.argv[1]))['ntrip']
    missing = [k for k in ('caster', 'port', 'mountpoint', 'user', 'password') if not cfg.get(k)]
    say('keys present:', sorted(cfg.keys()), 'missing:', missing)
    pos = None
    if len(sys.argv) > 2:
        vals = open(sys.argv[2]).read().split()
        if len(vals) == 2:
            pos = (float(vals[0]), float(vals[1]))
    say('position for GGA available:', pos is not None)
    attempt(cfg, 1, False, pos)          # exactly what str2str does, but GGA as soon as the answer is OK
    attempt(cfg, 1, True, pos)           # GGA right after the request (some casters answer only after GGA)
    attempt(cfg, 2, False, pos)
    attempt(cfg, 2, True, pos)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:   # never print the message (could contain values)
        say('probe error:', type(e).__name__)

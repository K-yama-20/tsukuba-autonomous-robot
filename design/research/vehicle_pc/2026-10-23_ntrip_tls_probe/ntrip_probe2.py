# DIAGNOSTIC ONLY (bin 145): why does the caster reset the plain-TCP NTRIP request? Prints categories only, never values.
import base64, socket, ssl, sys, time
import yaml

def say(*a): print(*a, flush=True)

def classify(data):
    if data.startswith(b'ICY 200 OK'): return 'ICY 200 OK (v1 accepted)'
    if data.startswith(b'SOURCETABLE 200 OK'): return 'SOURCETABLE'
    if data.startswith(b'HTTP/'):
        p = data.split(b'\r\n')[0].decode('ascii', 'replace').split(' ')
        return f'HTTP {p[0]} status {p[1] if len(p) > 1 else "?"}'
    return 'no bytes' if not data else f'other ({len(data)} bytes)'

def read_for(s, secs):
    s.settimeout(0.5); data, t0, end = b'', time.time(), None
    while time.time() - t0 < secs:
        try:
            c = s.recv(4096)
        except socket.timeout:
            continue
        except OSError as e:
            end = f'{type(e).__name__} after {time.time() - t0:.2f} s'; break
        if c == b'':
            end = f'closed after {time.time() - t0:.2f} s'; break
        data += c
    return data, end or 'still open'

cfg = yaml.safe_load(open(sys.argv[1]))['ntrip']
host, port = str(cfg['caster']), int(cfg['port'])
auth = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
v1 = f"GET /{cfg['mountpoint']} HTTP/1.0\r\nUser-Agent: NTRIP RTKLIB/2.4.3\r\nAuthorization: Basic {auth}\r\n\r\n".encode()
v2 = f"GET /{cfg['mountpoint']} HTTP/1.1\r\nHost: {host}\r\nNtrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP probe\r\nAuthorization: Basic {auth}\r\n\r\n".encode()
st = b"GET / HTTP/1.0\r\nUser-Agent: NTRIP RTKLIB/2.4.3\r\n\r\n"
try:
    addrs = sorted({a[4][0] for a in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    say('DNS: resolved to', len(addrs), 'address(es); IPv6 among them:', any(':' in a for a in addrs))
except Exception as e:
    say('DNS failed', type(e).__name__); sys.exit()
# 1. connect and send nothing
s = socket.create_connection((host, port), timeout=10); d, e = read_for(s, 4); s.close()
say('[plain, no request] ', classify(d), '|', e)
# 2. plain source-table request without credentials
s = socket.create_connection((host, port), timeout=10); s.sendall(st); d, e = read_for(s, 6); s.close()
say('[plain, source table request] ', classify(d), '|', e)
# 3. plain v1 again, timing of the reset
s = socket.create_connection((host, port), timeout=10); s.sendall(v1); d, e = read_for(s, 6); s.close()
say('[plain, v1 mountpoint request] ', classify(d), '|', e)
# 4. TLS on the same port
for name, req in (('source table', st), ('v1', v1), ('v2', v2)):
    try:
        raw = socket.create_connection((host, port), timeout=10)
        ctx = ssl.create_default_context()
        t = ctx.wrap_socket(raw, server_hostname=host)
        say(f'[TLS same port, {name}] handshake OK, protocol {t.version()}')
        t.sendall(req); d, e = read_for(t, 6); t.close()
        say(f'[TLS same port, {name}] ', classify(d), '|', e, '| bytes', len(d))
    except ssl.SSLError as ex:
        say(f'[TLS same port, {name}] TLS error {type(ex).__name__} {getattr(ex, "reason", "")}')
    except OSError as ex:
        say(f'[TLS same port, {name}] socket error {type(ex).__name__}')

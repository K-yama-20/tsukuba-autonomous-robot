# DIAGNOSTIC ONLY (bin 145): over TLS, does RTCM flow after a GGA? Prints counts only (no caster data, no position).
import base64, re, socket, ssl, sys, time
import yaml
cfg = yaml.safe_load(open(sys.argv[1]))['ntrip']
nums = [float(x) for x in re.findall(r'-?\d+\.\d+', open(sys.argv[2]).read())]
if len(nums) < 2:
    print('no position'); sys.exit()
lat, lon = nums[0], nums[1]
def dm(v, w):
    a = abs(v); d = int(a); return f'{d:0{w}d}{(a - d) * 60:07.4f}'
def gga():
    t = time.gmtime()
    b = (f"GPGGA,{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00,{dm(lat, 2)},{'N' if lat >= 0 else 'S'},{dm(lon, 3)},"
         f"{'E' if lon >= 0 else 'W'},1,12,1.0,30.0,M,40.0,M,,")
    c = 0
    for ch in b: c ^= ord(ch)
    return f'${b}*{c:02X}\r\n'.encode()
host, port = str(cfg['caster']), int(cfg['port'])
auth = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
req = f"GET /{cfg['mountpoint']} HTTP/1.0\r\nUser-Agent: NTRIP RTKLIB/2.4.3\r\nAuthorization: Basic {auth}\r\n\r\n".encode()
t = ssl.create_default_context().wrap_socket(socket.create_connection((host, port), timeout=10), server_hostname=host)
t.sendall(req); t.settimeout(0.5)
data, t0, last_gga, first = b'', time.time(), 0, None
while time.time() - t0 < 20:
    if data.startswith(b'ICY 200 OK') and time.time() - last_gga > 1:
        t.sendall(gga()); last_gga = time.time()
    try:
        c = t.recv(8192)
    except socket.timeout:
        continue
    if c == b'':
        print('closed by caster'); break
    if len(data) > 14 and first is None: first = time.time() - t0
    data += c
body = data[data.find(b'\r\n\r\n') + 4:] if b'\r\n\r\n' in data else b''
n, i, types = 0, 0, {}
while i + 6 <= len(body):   # count RTCM3 frames (0xD3, 10-bit length) and message numbers
    if body[i] == 0xD3:
        ln = ((body[i + 1] & 0x03) << 8) | body[i + 2]
        if i + 6 + ln <= len(body):
            mt = (body[i + 3] << 4) | (body[i + 4] >> 4); types[mt] = types.get(mt, 0) + 1; n += 1; i += 6 + ln; continue
    i += 1
print(f'answer: {data[:10]!r}; body {len(body)} bytes in 20 s; RTCM3 frames {n}; message types {dict(sorted(types.items()))}')

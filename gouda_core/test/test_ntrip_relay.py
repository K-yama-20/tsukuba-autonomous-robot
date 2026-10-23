"""NTRIP relay (DEC-139 option B1, DEC-151 step 3, DEC-156, DEC-361) without ROS. All NTRIP values are made up.

Checked: str2str connects only to stunnel4 on the loopback port (never to the caster: no plaintext path), the connection data
goes to the runner on stdin (never in an argv) and the recorded command holds none of it; without stunnel4 nothing is
started; stunnel4's configuration checks the certificate and holds no credentials; stunnel4's log is reduced to TLS event
categories; str2str's status lines are reduced to states / bytes / bps; only changes are reported; fake stunnel4 + str2str
run end to end through the runner leak nothing into the reports; the supervisor never passes the started command to a record."""
import ast
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import ntrip_relay as nr  # noqa: E402

FAKE = {'caster': 'caster.example.invalid', 'port': 47613, 'mountpoint': 'FAKEMOUNT', 'user': 'fakeuser', 'password': 'fakepass'}
DEVICE = 'serial:/dev/serial/by-id/usb-Fake_Receiver_TEST-if02'
SUPERVISOR = Path(__file__).resolve().parents[1] / 'gouda_core' / 'sensor_supervisor_node.py'


def secrets_in(text):
    return [str(v) for v in FAKE.values() if str(v) in text]


MSG = 'caster.example.invalid:47613/FAKEMOUNT'


class CommandTests(unittest.TestCase):
    def test_launch_and_public_commands(self):
        launch, public = nr.relay_commands('/usr/bin/str2str', FAKE, DEVICE, 115200, 40123)
        self.assertEqual(launch, ['/usr/bin/str2str', '-in', 'ntrip://fakeuser:fakepass@127.0.0.1:40123/FAKEMOUNT',
                                  '-out', 'serial://serial/by-id/usb-Fake_Receiver_TEST-if02:115200', '-b', '1'])
        self.assertNotIn('caster.example.invalid', ' '.join(launch), 'str2str never reaches the caster itself (no plaintext path)')
        self.assertNotIn('47613', ' '.join(launch))
        self.assertEqual(secrets_in(' '.join(public)), [])
        self.assertIn('ntrip://<redacted>', public)
        self.assertEqual(public[3:], launch[3:], 'only the ntrip URL differs')

    def test_serial_path(self):
        self.assertEqual(nr.serial_path(DEVICE), 'serial/by-id/usb-Fake_Receiver_TEST-if02')
        for bad in ('', None, 'serial:/dev/ttyACM1', '/dev/serial/by-id/x', 'tcp://192.0.2.1:1'):
            self.assertIsNone(nr.serial_path(bad), bad)

    def test_stunnel_config_checks_the_certificate_and_holds_no_credentials(self):
        conf = nr.stunnel_config(FAKE, 40123)
        lines = conf.splitlines()
        for want in ('client = yes', 'accept = 127.0.0.1:40123', 'connect = caster.example.invalid:47613', 'sni = caster.example.invalid',
                     'verifyChain = yes', f'CAfile = {nr.CA_FILE}', 'checkHost = caster.example.invalid', 'foreground = yes'):
            self.assertIn(want, lines)
        for secret in ('fakeuser', 'fakepass', 'FAKEMOUNT'):
            self.assertNotIn(secret, conf)


class BuildRelayTests(unittest.TestCase):
    def test_reasons_and_commands(self):
        ok = nr.build_relay('/usr/bin/str2str', FAKE, DEVICE, 115200, True, '/usr/bin/stunnel4')
        self.assertIsNone(ok['reason']); self.assertEqual(ok['serial_path'], '/dev/serial/by-id/usb-Fake_Receiver_TEST-if02')
        self.assertEqual(secrets_in(' '.join(ok['launch'])), [], 'the started argv holds no connection data (it goes on stdin)')
        self.assertEqual(ok['launch'][1:], ['-m', 'gouda_core.ntrip_relay_runner'])
        self.assertEqual(json.loads(ok['launch_input'])['ntrip'], FAKE)
        self.assertEqual(secrets_in(' '.join(ok['public'])), [])
        self.assertIn('ntrip://<redacted>', ok['public']); self.assertIn('/usr/bin/stunnel4', ok['public'])
        cases = {'driver': ('/usr/bin/str2str', FAKE, DEVICE, 115200, False, '/usr/bin/stunnel4'),
                 'ntrip': ('/usr/bin/str2str', None, DEVICE, 115200, True, '/usr/bin/stunnel4'),
                 'device': ('/usr/bin/str2str', FAKE, 'serial:/dev/ttyACM1', 115200, True, '/usr/bin/stunnel4'),
                 'exe': (None, FAKE, DEVICE, 115200, True, '/usr/bin/stunnel4'),
                 'stunnel': ('/usr/bin/str2str', FAKE, DEVICE, 115200, True, None),
                 'baud': ('/usr/bin/str2str', FAKE, DEVICE, None, True, '/usr/bin/stunnel4')}
        for name, args in cases.items():
            r = nr.build_relay(*args)
            self.assertIsNone(r['launch'], name); self.assertIsNone(r['launch_input'], name); self.assertIsNone(r['public'], name)
            self.assertTrue(r['reason'], name)
            self.assertEqual(secrets_in(json.dumps(r)), [], name)
        self.assertIn('plaintext', nr.build_relay(*cases['stunnel'])['reason'])
        self.assertEqual(nr.build_relay(*cases['stunnel'])['serial_path'], '/dev/serial/by-id/usb-Fake_Receiver_TEST-if02',
                         'a relay that is not started still watches its device (no fall-through to the LiDAR branch of _observe)')
        self.assertIsNone(nr.build_relay(*cases['device'])['serial_path'])


class TlsEventTests(unittest.TestCase):
    def test_categories_never_carry_the_line(self):
        cases = {
            '2026.10.23 20:38:30 LOG5[0]: Service [ntrip] connected remote server from 192.0.2.7:43874': 'connected',
            '2026.10.23 20:38:30 LOG5[0]: s_connect: connected 192.0.2.9:47613': None,
            '2026.10.23 20:38:30 LOG3[0]: s_connect: connect 192.0.2.9:47613: Connection refused (111)': 'connect_failed',
            '2026.10.23 20:38:30 LOG4[0]: Rejected by CERT at depth=0: CN=caster.example.invalid': 'certificate_rejected',
            '2026.10.23 20:38:30 LOG3[0]: SSL_connect: ssl/statem/statem_clnt.c: certificate verify failed': 'certificate_rejected',
            '2026.10.23 20:38:30 LOG5[0]: Connection closed: 120 byte(s) sent to TLS, 4000 byte(s) sent to socket': 'closed',
            '2026.10.23 20:38:30 LOG6[ui]: Service [ntrip] (FD=9) bound to 127.0.0.1:40123': None,
            '2026.10.23 20:38:30 LOG5[ui]: Configuration successful': None,
        }
        for line, want in cases.items():
            self.assertEqual(nr.tls_event(line), want, line)
        self.assertTrue(nr.stunnel_bound('2026.10.23 20:38:30 LOG6[ui]: Service [ntrip] (FD=9) bound to 127.0.0.1:40123'))
        self.assertFalse(nr.stunnel_bound('2026.10.23 20:38:30 LOG7[ui]: Binding service [ntrip]'))

    def test_parse_tls_and_reader_report_changes_only(self):
        self.assertEqual(nr.parse_tls('[TLS] connected'), 'connected')
        self.assertIsNone(nr.parse_tls('[TLS] caster.example.invalid'), 'only known categories pass')
        self.assertEqual(nr.parse_tls('[TLS] stunnel_exited'), nr.STUNNEL_EXITED)
        lines = ['[TLS] connected', f'2026/10/20 12:00:00 [WC] 0 B 0 bps {MSG}', '[TLS] connected', '[TLS] closed', '[TLS] connected']
        tls, states, tr = [], [], nr.StatusTracker()
        nr.read_status(iter(lines), tr, states.append, tls.append)
        self.assertEqual(tls, ['connected', 'closed', 'connected'])
        self.assertEqual(len(states), 1); self.assertEqual(tr.unparsed, 0)

    def test_free_loopback_port(self):
        p = nr.free_loopback_port()
        self.assertTrue(0 < p < 65536)


class StatusTests(unittest.TestCase):
    LINE = '2026/10/20 12:00:05 [CC---]       4096 B    6553 bps caster.example.invalid:47613/FAKEMOUNT'

    def test_parse_drops_the_message(self):
        st = nr.parse_status(self.LINE)
        self.assertEqual(st, {'input': 'connected', 'outputs': ['connected', 'closed', 'closed', 'closed'], 'bytes': 4096, 'bps': 6553})
        self.assertEqual(secrets_in(json.dumps(st)), [])
        for not_status in ('stream server start', '', 'caster.example.invalid:47613/FAKEMOUNT', '[XX] 1 B 1 bps'):
            self.assertIsNone(nr.parse_status(not_status), not_status)

    def test_tracker_reports_state_changes_only(self):
        t = [0.0]
        tr = nr.StatusTracker(clock=lambda: t[0])
        self.assertIsNotNone(tr.feed('2026/10/20 12:00:00 [WC]   0 B   0 bps x'))
        self.assertEqual(tr.bytes_changed_at, 0.0, 'the first status counts as the start')
        t[0] = 5.0
        self.assertIsNone(tr.feed('2026/10/20 12:00:05 [WC]   0 B   0 bps x'), 'same states: no report')
        self.assertIsNotNone(tr.feed('2026/10/20 12:00:10 [CC] 100 B 160 bps x'))
        self.assertEqual(tr.bytes_changed_at, 5.0)
        t[0] = 9.0
        self.assertIsNone(tr.feed('2026/10/20 12:00:15 [CC] 900 B 1280 bps x'))
        self.assertEqual(tr.bytes_changed_at, 9.0)
        self.assertIsNone(tr.feed('garbage with caster.example.invalid'))
        self.assertEqual(tr.unparsed, 1)


class ReaderTests(unittest.TestCase):
    def test_reader_keeps_draining_after_a_callback_error(self):
        lines = [f'2026/10/20 12:00:{i:02d} [{"WC"[i % 2]}C] {i} B 0 bps {MSG}' for i in range(10)]
        seen = []

        def boom(st):
            seen.append(st)
            raise RuntimeError('publish failed')
        it = iter(lines)
        tr = nr.StatusTracker()
        nr.read_status(it, tr, boom)
        self.assertEqual(next(it, None), None, 'every line was read')
        self.assertEqual(tr.callback_errors, len(seen)); self.assertGreater(len(seen), 1)


FAKE_STUNNEL = textwrap.dedent('''\
    #!{python}
    # fake stunnel4 -fd 0: reads the configuration on stdin, listens on its accept port, logs like stunnel 5.72 (with the
    # caster's name, which must never reach a report), relays nothing; ends on SIGTERM
    import json, re, signal, socket, sys
    conf = sys.stdin.read()
    json.dump({{'argv': sys.argv[1:], 'conf': conf}}, open({out!r}, 'w'))
    port = int(re.search(r'accept = 127\\.0\\.0\\.1:(\\d+)', conf).group(1))
    host = re.search(r'connect = (\\S+)', conf).group(1)
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(('127.0.0.1', port)); srv.listen()
    log = lambda m: (print('2026.10.23 20:38:30 ' + m, flush=True))
    log('LOG5[ui]: Configuration successful')
    log(f'LOG6[ui]: Service [ntrip] (FD=9) bound to 127.0.0.1:{{port}}')
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    conn, _ = srv.accept()
    log(f'LOG5[0]: s_connect: connected {{host}}')
    log('LOG5[0]: Service [ntrip] connected remote server from 127.0.0.1:43874')
    conn.recv(4096)
    signal.pause()
    ''')

FAKE_STR2STR = textwrap.dedent('''\
    #!{python}
    # fake str2str: records its argv, connects to the -in URL's host:port (must be stunnel's loopback port), prints status lines
    import json, re, socket, sys
    json.dump(sys.argv[1:], open({out!r}, 'w'))
    host, port = re.search(r'@([^:/]+):(\\d+)/', sys.argv[2]).groups()
    s = socket.create_connection((host, int(port))); s.sendall(b'GET /FAKEMOUNT HTTP/1.0\\r\\n\\r\\n')
    msg = 'caster.example.invalid:47613/FAKEMOUNT'
    for line in ('stream server start',
                 f'2026/10/20 12:00:00 [WC]          0 B       0 bps {{msg}}',
                 f'2026/10/20 12:00:05 [CC]        512 B     819 bps {{msg}}',
                 f'2026/10/20 12:00:10 [CC]       1024 B     819 bps {{msg}}',
                 'connect error (111) fakeuser fakepass',
                 f'2026/10/20 12:00:15 [EC]       1024 B       0 bps {{msg}}'):
        print(line, file=sys.stderr)
    ''')


def write_fakes(d):
    """(stunnel path, str2str path, stunnel record file, str2str record file) in d."""
    paths = []
    for name, template in (('stunnel4', FAKE_STUNNEL), ('str2str', FAKE_STR2STR)):
        rec, exe = os.path.join(d, name + '.json'), os.path.join(d, name)
        with open(exe, 'w') as f:
            f.write(template.format(python=sys.executable, out=rec))
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR)
        paths.append((exe, rec))
    return paths[0][0], paths[1][0], paths[0][1], paths[1][1]


class FakeRunnerTests(unittest.TestCase):
    def test_end_to_end_through_stunnel_reports_hold_no_secret(self):
        with tempfile.TemporaryDirectory() as d:
            stunnel, str2str, stunnel_rec, str2str_rec = write_fakes(d)
            r = nr.build_relay(str2str, FAKE, DEVICE, 115200, True, stunnel)
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get('PYTHONPATH', ''))
            proc = subprocess.Popen(r['launch'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    text=True, errors='replace', env=env)
            proc.stdin.write(r['launch_input']); proc.stdin.close()
            reports, tls, tracker = [], [], nr.StatusTracker()
            nr.read_status(proc.stderr, tracker, reports.append, tls.append)
            proc.stderr.close()
            self.assertEqual(proc.wait(timeout=30), 0, "the runner ends with str2str's code and stops stunnel")
            with open(str2str_rec) as f:
                args = json.load(f)
            self.assertRegex(args[1], r'^ntrip://fakeuser:fakepass@127\.0\.0\.1:\d+/FAKEMOUNT$', 'str2str goes to stunnel only')
            with open(stunnel_rec) as f:
                st = json.load(f)
            self.assertEqual(st['argv'], ['-fd', '0'], 'the caster is not in stunnel\'s argv')
            self.assertIn('connect = caster.example.invalid:47613', st['conf'])
            self.assertIn('verifyChain = yes', st['conf'])
            self.assertEqual([x['input'] for x in reports], ['waiting', 'connected', 'error'])
            self.assertEqual(tls, ['connected'])
            self.assertEqual(tracker.unparsed, 2)
            self.assertEqual(secrets_in(json.dumps(reports) + json.dumps(tls) + json.dumps(r['public']) + ' '.join(r['launch'])), [])

    def test_stunnel_that_never_listens_is_reported_and_str2str_not_started(self):
        with tempfile.TemporaryDirectory() as d:
            _stunnel, str2str, _a, str2str_rec = write_fakes(d)
            bad = os.path.join(d, 'stunnel_bad')
            with open(bad, 'w') as f:
                f.write(f'#!{sys.executable}\nimport sys\nsys.stdin.read()\nprint("LOG3[ui]: bad option caster.example.invalid")\nsys.exit(1)\n')
            os.chmod(bad, os.stat(bad).st_mode | stat.S_IXUSR)
            r = nr.build_relay(str2str, FAKE, DEVICE, 115200, True, bad)
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]) + os.pathsep + os.environ.get('PYTHONPATH', ''))
            proc = subprocess.run(r['launch'], input=r['launch_input'], capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(os.path.exists(str2str_rec), 'str2str is never started without the TLS tunnel')
            self.assertIn('[TLS] stunnel_exited', proc.stderr)
            self.assertEqual(secrets_in(proc.stderr), [])


class SupervisorSourceTests(unittest.TestCase):
    def test_started_command_never_recorded(self):
        """Static check: no _decision(...) call and no logger call in the supervisor mentions `launch` or `launch_input` (the secret)."""
        tree = ast.parse(SUPERVISOR.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('_decision', 'info', 'warn', 'warning', 'error'):
                names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                self.assertNotIn('launch', names, ast.unparse(node)[:120])
                self.assertNotIn('ntrip', names, ast.unparse(node)[:120])
                self.assertNotIn('launch_input', names, ast.unparse(node)[:120])


if __name__ == '__main__':
    unittest.main()

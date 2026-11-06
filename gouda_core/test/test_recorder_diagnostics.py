"""Unit tests without ROS: gouda_recorder (ND-04) writes the MID-360's /diagnostics status to the log (DEC-479 / DEC-494).

Checked: only the status named mid360 is taken out of a DiagnosticArray (other names and near misses are not written); the payload
shape (stamp from the header, integer level from rclpy's byte field, message, values as key -> string); every status is written
(no thinning); nothing is written while the log is stopped (RecorderCore as before); the subscription is /diagnostics with the
rclcpp default QoS agreed with the driver patch. recorder_node.py is loaded with stand-ins for the ROS modules, and its real
callback is called. The values are made up for the test (no address, no serial number, no log data).
"""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import mid360_config as m3  # noqa: E402
from gouda_core.recorder_core import TRIGGER_HUMAN, diagnostic_payloads  # noqa: E402

NODE_FILE = Path(__file__).resolve().parents[1] / 'gouda_core' / 'recorder_node.py'
# the keys of the driver patch (DEC-494); values are strings, arrays are JSON array strings
MID360_KEYS = ('cur_work_state', 'core_temp', 'powerup_cnt', 'last_sync_time', 'time_offset', 'time_sync_type', 'status_code',
               'lidar_diag_status', 'lidar_flash_status', 'FW_TYPE', 'hms_code', 'version_app', 'version_loader', 'version_hardware')


# ---- stand-ins of the message types (the same shape as diagnostic_msgs in rclpy: level is a 1-byte bytes) ----
class KeyValue:
    def __init__(self, key='', value=''): self.key, self.value = key, value


class DiagnosticStatus:
    OK, WARN, ERROR, STALE = b'\x00', b'\x01', b'\x02', b'\x03'

    def __init__(self, name='', level=b'\x00', message='', hardware_id='', values=None):
        self.name, self.level, self.message, self.hardware_id, self.values = name, level, message, hardware_id, list(values or [])


class DiagnosticArray:
    def __init__(self, status=None, sec=0, nanosec=0):
        self.header = types.SimpleNamespace(stamp=types.SimpleNamespace(sec=sec, nanosec=nanosec), frame_id='')
        self.status = list(status or [])


def mid360_values(**over):
    v = {'cur_work_state': '1', 'core_temp': '4321', 'powerup_cnt': '7', 'last_sync_time': '0', 'time_offset': '0',
         'time_sync_type': '0', 'status_code': '[0,0,0,0]', 'lidar_diag_status': '0', 'lidar_flash_status': '0', 'FW_TYPE': '1',
         'hms_code': '[0,0,0,0,0,0,0,0]', 'version_app': '[1,2,3,4]', 'version_loader': '[5,6,7,8]', 'version_hardware': '[9,8,7,6]'}
    v.update(over)
    return [KeyValue(k, v[k]) for k in MID360_KEYS]


def mid360(level=DiagnosticStatus.OK, **over):
    return DiagnosticStatus(name=m3.DIAGNOSTIC_NAME, level=level, message='info push', hardware_id='', values=mid360_values(**over))


def others():
    """Statuses other nodes put on /diagnostics (the NDT's scan status, the EKF, near misses of the name)."""
    return [DiagnosticStatus('ndt_scan_matcher: scan_matching_status', DiagnosticStatus.OK, 'OK', '', [KeyValue('is_activated', 'True')]),
            DiagnosticStatus('ekf_localizer: pose_no_update_count', DiagnosticStatus.WARN, 'warn', '', [KeyValue('pose_no_update_count', '3')]),
            DiagnosticStatus('MID360', DiagnosticStatus.ERROR, 'info push', '', mid360_values()),
            DiagnosticStatus('mid360 ', DiagnosticStatus.ERROR, 'info push', '', mid360_values()),
            DiagnosticStatus('livox_ros_driver2: mid360', DiagnosticStatus.ERROR, 'info push', '', mid360_values())]


# ---- recorder_node.py with stand-ins for the ROS modules ----
class FakeTime:
    def __init__(self, t): self.t = t
    def seconds_nanoseconds(self): return int(self.t), int(round((self.t - int(self.t)) * 1e9))
    def to_msg(self): s, n = self.seconds_nanoseconds(); return types.SimpleNamespace(sec=s, nanosec=n)


class FakeNode:
    """The part of rclpy.node.Node that RecorderNode uses; subscriptions and published messages are kept for the test."""
    record_root = ''
    now = 1000.25

    def __init__(self, name):
        self.node_name = name; self.subscriptions = []; self.published = []

    def declare_parameter(self, name, value): pass
    def get_parameter(self, name):
        root = type(self).record_root
        return types.SimpleNamespace(get_parameter_value=lambda: types.SimpleNamespace(string_value=root))
    def create_publisher(self, typ, topic, qos): return types.SimpleNamespace(publish=self.published.append)
    def create_service(self, typ, name, cb): return None
    def create_subscription(self, typ, topic, cb, qos): self.subscriptions.append((typ, topic, cb, qos))
    def get_logger(self): return types.SimpleNamespace(info=lambda m: None, warning=lambda m: None)
    def get_clock(self): return types.SimpleNamespace(now=lambda: FakeTime(type(self).now))
    def destroy_node(self): pass


class QoSProfile:
    def __init__(self, **kw): self.kw = kw


def load_node():
    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); return m
    policy = lambda **names: types.SimpleNamespace(**names)
    stub = object
    mods = {'rclpy': mod('rclpy', init=stub, spin=stub, try_shutdown=stub), 'rclpy.node': mod('rclpy.node', Node=FakeNode),
            'rclpy.qos': mod('rclpy.qos', QoSProfile=QoSProfile, ReliabilityPolicy=policy(RELIABLE='reliable', BEST_EFFORT='best_effort'),
                             DurabilityPolicy=policy(TRANSIENT_LOCAL='transient_local', VOLATILE='volatile'),
                             HistoryPolicy=policy(KEEP_LAST='keep_last', KEEP_ALL='keep_all')),
            'std_srvs': mod('std_srvs'), 'std_srvs.srv': mod('std_srvs.srv', Trigger=stub),
            'diagnostic_msgs': mod('diagnostic_msgs'),
            'diagnostic_msgs.msg': mod('diagnostic_msgs.msg', DiagnosticArray=DiagnosticArray, DiagnosticStatus=DiagnosticStatus, KeyValue=KeyValue),
            'gouda_interfaces': mod('gouda_interfaces'), 'gouda_interfaces.msg': mod('gouda_interfaces.msg', SoftwareMode=stub, DecisionEvent=stub)}
    with mock.patch.dict(sys.modules, mods):
        spec = importlib.util.spec_from_file_location('gouda_recorder_node_under_test', NODE_FILE)
        node = importlib.util.module_from_spec(spec); spec.loader.exec_module(node)
    return node


class PayloadTests(unittest.TestCase):
    def test_the_name_is_the_one_agreed_with_the_driver_patch(self):
        self.assertEqual(m3.DIAGNOSTIC_NAME, 'mid360')

    def test_only_mid360_statuses_are_taken_in_order(self):
        arr = DiagnosticArray(others()[:2] + [mid360(DiagnosticStatus.WARN)] + others()[2:] + [mid360(DiagnosticStatus.STALE)])
        got = diagnostic_payloads(arr, m3.DIAGNOSTIC_NAME)
        self.assertEqual([(p['name'], p['level']) for p in got], [('mid360', 1), ('mid360', 3)])
        self.assertEqual(diagnostic_payloads(DiagnosticArray(others()), m3.DIAGNOSTIC_NAME), [])
        self.assertEqual(diagnostic_payloads(DiagnosticArray([]), m3.DIAGNOSTIC_NAME), [])

    def test_payload_shape(self):
        arr = DiagnosticArray([mid360(core_temp='4567', hms_code='[1,0,0,0,0,0,0,0]')], sec=1700000000, nanosec=500000000)
        (p,) = diagnostic_payloads(arr, m3.DIAGNOSTIC_NAME)
        self.assertEqual(set(p), {'stamp', 'name', 'level', 'message', 'values'})   # no hardware_id
        self.assertAlmostEqual(p['stamp'], 1700000000.5, places=6)
        self.assertEqual((p['name'], p['message']), ('mid360', 'info push'))
        self.assertIs(type(p['level']), int); self.assertEqual(p['level'], 0)
        self.assertEqual(list(p['values']), list(MID360_KEYS))
        self.assertTrue(all(isinstance(v, str) for v in p['values'].values()))
        self.assertEqual(p['values']['core_temp'], '4567')                       # 0.01 degC integer, kept as the string received
        self.assertEqual(json.loads(p['values']['hms_code']), [1, 0, 0, 0, 0, 0, 0, 0])
        json.dumps(p)   # written to events.jsonl as JSON

    def test_every_level_is_an_integer(self):
        for raw, want in ((b'\x00', 0), (b'\x01', 1), (b'\x02', 2), (b'\x03', 3), (bytearray(b'\x02'), 2), (2, 2)):
            (p,) = diagnostic_payloads(DiagnosticArray([mid360(raw)]), m3.DIAGNOSTIC_NAME)
            self.assertIs(type(p['level']), int, raw); self.assertEqual(p['level'], want, raw)

    def test_a_status_without_values_is_kept_as_received(self):
        st = DiagnosticStatus(m3.DIAGNOSTIC_NAME, DiagnosticStatus.STALE, 'info push', '', [])
        (p,) = diagnostic_payloads(DiagnosticArray([st]), m3.DIAGNOSTIC_NAME)
        self.assertEqual((p['level'], p['values']), (3, {}))   # nothing is filled in (RQ-I015)


class NodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        FakeNode.record_root = self.tmp.name; FakeNode.now = 1000.25
        self.mod = load_node()
        self.node = self.mod.RecorderNode()
        subs = [s for s in self.node.subscriptions if s[1] == '/diagnostics']
        self.assertEqual(len(subs), 1)
        self.sub = subs[0]
        self.on_diagnostics = self.sub[2]

    def tearDown(self): self.tmp.cleanup()

    def events(self):
        s = self.node.core.session
        f = s.directory / 'log' / 'events.jsonl' if s else None
        if f is None or not f.exists():
            return []
        return [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]

    def diag_events(self):
        return [e for e in self.events() if e['kind'] == 'input' and e.get('topic') == '/diagnostics']

    def test_subscription_contract(self):
        typ, topic, _cb, qos = self.sub
        self.assertIs(typ, DiagnosticArray)
        self.assertEqual(topic, '/diagnostics')   # absolute name
        self.assertEqual(qos.kw, {'reliability': 'reliable', 'durability': 'volatile', 'history': 'keep_last', 'depth': 10})

    def test_every_mid360_status_is_written_and_nothing_else(self):
        ok, msg = self.node.core.start_log(TRIGGER_HUMAN); self.assertTrue(ok, msg)
        for i in range(5):   # the same status again and again: every one is written (no thinning)
            FakeNode.now = 1000.25 + i
            self.on_diagnostics(DiagnosticArray(others() + [mid360()], sec=990 + i))
        self.on_diagnostics(DiagnosticArray(others()))
        self.on_diagnostics(DiagnosticArray([mid360(DiagnosticStatus.ERROR), mid360(DiagnosticStatus.WARN)], sec=999))
        got = self.diag_events()
        self.assertEqual(len(got), 7)
        self.assertTrue(all(e['kind'] == 'input' and e['data']['name'] == 'mid360' for e in got))
        for i, e in enumerate(got[:5]):
            self.assertAlmostEqual(e['t'], 1000.25 + i, places=6)   # receive time on the node's clock
        self.assertEqual([e['data']['stamp'] for e in got[:5]], [990 + i for i in range(5)])   # the header time
        self.assertEqual([e['data']['level'] for e in got], [0, 0, 0, 0, 0, 2, 1])
        self.assertEqual(got[-1]['data']['values'], {k.key: k.value for k in mid360_values()})
        names = {e['data'].get('name') for e in self.events() if 'data' in e and isinstance(e['data'], dict)}
        self.assertEqual(names, {'mid360'})   # no other status reached the log

    def test_nothing_is_written_while_the_log_is_stopped(self):
        self.on_diagnostics(DiagnosticArray([mid360()]))           # before any start: no session, no file
        self.assertIsNone(self.node.core.session)
        self.node.core.start_log(TRIGGER_HUMAN)
        self.on_diagnostics(DiagnosticArray([mid360(core_temp='4000')]))
        self.node.core.stop_log(TRIGGER_HUMAN)
        before = self.events()
        FakeNode.now = 2000.5
        self.on_diagnostics(DiagnosticArray([mid360(core_temp='4100')]))
        self.on_diagnostics(DiagnosticArray([mid360(core_temp='4200')]))
        self.assertEqual(self.events(), before)                     # nothing was appended while stopped
        self.assertEqual([e['data']['values']['core_temp'] for e in self.diag_events()], ['4000'])
        # RecorderCore as before: at the next start the last status received is written once as a snapshot with its own receive time
        FakeNode.now = 2100.0
        self.node.core.start_log(TRIGGER_HUMAN)
        snap = [e for e in self.events()[len(before):] if e['kind'] == 'snapshot' and e['topic'] == '/diagnostics']
        self.assertEqual(len(snap), 1)
        self.assertAlmostEqual(snap[0]['t'], 2000.5, places=6)
        self.assertEqual(snap[0]['data']['values']['core_temp'], '4200')

    def test_a_write_failure_is_shown_in_record_status(self):
        self.node.core.start_log(TRIGGER_HUMAN)
        published = len(self.node.published)
        with mock.patch('builtins.open', side_effect=OSError('disk full')):
            self.on_diagnostics(DiagnosticArray([mid360()]))
        self.assertEqual(len(self.node.published), published + 1)   # record/status sent again (the failure count changed)
        self.assertEqual(self.node.core.status()['failures'], 1)


if __name__ == '__main__':
    unittest.main()

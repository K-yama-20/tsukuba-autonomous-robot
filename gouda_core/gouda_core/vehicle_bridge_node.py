"""vehicle_bridge node (ND-12) — stage 5-5 (vehicle output), lifecycle node around BridgeCore and a serial transport to the ESP32.

Protocol v4: design/docs/esp32_protocol_v4.md (IFD-17 out, IFD-43 in). Subscribes vehicle/joystick_command (IFD-16).
Publishes /esp32/status (IFD-38, diagnostic_msgs/DiagnosticArray, reliable, volatile, depth 10; display/diagnosis only,
DEC-006) on every STATUS, and log/decision (IFD-28) for session events, config registration results and output changes.

Session: on configure the port is opened, HELLO is sent, the HELLO_REPLY gives the boot_token, and the firmware
configuration from design/generated/params/firmware_config.yaml (plus firmware_config.trial.yaml when trial:=true; stub
tests only) is registered with SET_CONFIG. A rejected or missing ACK is recorded and never stops anything. A reboot of the
ESP32 (uptime going backwards / new boot token) repeats the session start.
USB re-plug (DEC-176): a lost link is reported and the same by-id name is reopened on the next device event; the session then
restarts with HELLO. The lifecycle state does not change and autonomy is not paused by a lost link (人の決定).
Link counts (DEC-177): vehicle/link_status (diagnostic_msgs/DiagnosticArray, reliable, transient_local, depth 1) carries the link
state and the disconnect / reconnect counts of the current 事前地図作成 or 自律走行 session (from mode/state, IFD-01; pause and
resume continue the count), published on every change; each disconnect / reconnect / session end is also a DecisionEvent.
While ACTIVE a COMMAND (flags bit0 = pc_enable_request) is sent every send_period_s (PRM-14): the last joystick_command if it
is younger than joystick_timeout_s (PRM-09), else neutral. While inactive no COMMAND is sent (the firmware's PC source expires
and goes neutral); STATUS keeps being received and published. Manual priority and the ESP32-side neutralisation are the
firmware's job (RQ-I023, RQ-I068) and are not replaced here.

Settings: serial_port (operational value, launch argument; a pty path in stub tests), params_dir and trial (where the firmware
config is read from), joystick_timeout_s / send_period_s from the generated parameter file. No number is written here.
"""
from __future__ import annotations

import json
import os
import threading
import time

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Joy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from gouda_interfaces.msg import DecisionEvent, SoftwareMode

from gouda_core import esp32_protocol as proto
from gouda_core.vehicle_core import BridgeCore, BridgeSettings, LinkCounter, LINK_UP, LINK_DOWN, LINK_NOT_OPEN

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
COMMAND_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)
STATUS_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)   # IFD-38
SERIAL_BAUD = 460800   # link setting of protocol v4 (docs/esp32_protocol_v4.md); not a vehicle value


def optional_double(node, name):
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None


def load_firmware_config(params_dir: str, trial: bool) -> dict:
    """Wire config from the generated firmware_config.yaml (approved / recorded values) and, only when trial, the trial file."""
    import yaml
    merged = {}
    for name in ['firmware_config.yaml'] + (['firmware_config.trial.yaml'] if trial else []):
        path = os.path.join(params_dir, name)
        if os.path.isfile(path):
            doc = yaml.safe_load(open(path, encoding='utf-8')) or {}
            if isinstance(doc, dict): merged.update({k: v for k, v in doc.items() if v is not None})
    return proto.config_from_params(merged)


class SerialTransport:
    """pyserial wrapper with a reader thread that survives a USB re-plug (DEC-176). Replaceable by a stub in tests.

    Connected: the reader thread reads; a read error (the USB link went away) closes the port and reports
    on_link(False, reason) once. Disconnected: writes are dropped without a report per frame (the link-down decision is
    the report), and the thread waits for a device event (`udevadm monitor`, tty add/remove; event driven, no polling
    period) and then tries to open the same by-id name again; success reports on_link(True, ''). The ESP32's own
    behaviour does not depend on this link: the gamepad keeps driving through the firmware while the USB link is down.
    """

    WATCH = ['udevadm', 'monitor', '--udev', '--subsystem-match=tty']

    def __init__(self, port: str, on_bytes, on_error, on_link=None, watch_cmd=WATCH):
        import serial
        self._serial = serial
        self.port = port; self.on_bytes = on_bytes; self.on_error = on_error; self.on_link = on_link or (lambda up, why: None)
        self._stop = threading.Event(); self._wake = threading.Event(); self._io = threading.Lock()
        self.ser = None; self._watch_proc = None
        self._open()   # the first open raises: configure fails exactly as before when the device is absent
        if watch_cmd:
            threading.Thread(target=self._watch, args=(watch_cmd,), name='vehicle_bridge_watch', daemon=True).start()
        self.thread = threading.Thread(target=self._run, name='vehicle_bridge_serial', daemon=True); self.thread.start()

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def _open(self):
        ser = self._serial.Serial(self.port, SERIAL_BAUD, timeout=0.05, exclusive=True)   # writes do not use pyserial (see write)
        ser.reset_input_buffer()
        with self._io: self.ser = ser

    def _drop(self, reason: str):
        with self._io:
            ser, self.ser = self.ser, None
        if ser is None: return
        try: ser.close()
        except Exception: pass
        self.on_link(False, reason)

    def wake(self):
        """A device event (or a test) asks the disconnected reader to try the by-id name again."""
        self._wake.set()

    def _watch(self, cmd):
        import subprocess
        try:
            self._watch_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError as e:
            self.on_error(f'device watch could not be started ({cmd[0]}: {e}); a re-plugged ESP32 is not reopened'); return
        for _ in self._watch_proc.stdout:
            if self._stop.is_set(): break
            self._wake.set()

    def _run(self):
        while not self._stop.is_set():
            ser = self.ser
            if ser is None:
                self._wake.wait(); self._wake.clear()
                if self._stop.is_set(): break
                if not os.path.exists(self.port): continue
                try:
                    self._open()
                except Exception as e:   # e.g. the node exists before udev finished; the next device event tries again
                    self.on_error(f'serial reopen failed: {e}'); continue
                self.on_link(True, '')
                continue
            try:
                data = ser.read(256)
            except Exception as e:
                self._drop(f'serial read failed: {e}'); continue
            if data: self.on_bytes(data)

    def write(self, data: bytes):
        """Non-blocking (DEC-174): the executor never waits for the port. pyserial opens the port O_NONBLOCK; what the OS
        buffer does not take now is dropped, and the next period sends a fresh frame (a cut frame fails the firmware CRC).
        pyserial's own write is not used: with write_timeout=0 it retries EAGAIN in a busy loop (pyserial 3.5).
        While the link is down the frame is dropped silently (the link-down decision already reports it)."""
        with self._io:
            ser = self.ser
            if ser is None: return
            n, err = 0, None
            try:
                n = os.write(ser.fileno(), data)
            except BlockingIOError:
                n = 0
            except Exception as e:
                err = e
        if err is not None:
            self._drop(f'serial write failed: {err}'); return
        if n < len(data):   # one fixed reason so that the monitor aggregates repeats into one line (×count)
            self.on_error('serial write incomplete: the OS buffer was full; the frame was dropped (the next period sends a fresh one)')

    def close(self):
        self._stop.set(); self._wake.set()
        if self._watch_proc:   # SIGKILL cannot be ignored, so the wait returns
            try: self._watch_proc.kill(); self._watch_proc.wait(); self._watch_proc.stdout.close()
            except Exception: pass
        self.thread.join(timeout=1)
        with self._io:
            ser, self.ser = self.ser, None
        if ser:
            try: ser.close()
            except Exception: pass


class VehicleBridgeNode(LifecycleNode):
    def __init__(self):
        super().__init__('vehicle_bridge')
        self.declare_parameter('serial_port', '')     # PRM-61 (ESP32 by-id name) from the generated file; empty: refuse to configure
        self.declare_parameter('params_dir', '')      # where firmware_config.yaml is read from
        self.declare_parameter('trial', False)        # also read firmware_config.trial.yaml (stub tests only)
        for key in ('joystick_timeout_s', 'send_period_s'):
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self._lock = threading.RLock()
        self.core = None; self.transport = None; self.parser = proto.Parser()
        self.timer = None; self.joy_sub = None
        self.status_pub = self.create_publisher(DiagnosticArray, '/esp32/status', STATUS_QOS)
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        # DEC-177: link state and per-session counts; mode/state decides the session (works in every lifecycle state)
        self.link = LinkCounter()
        self.link_pub = self.create_publisher(DiagnosticArray, 'vehicle/link_status', LATCHED)
        self.create_subscription(SoftwareMode, 'mode/state', self._on_mode, LATCHED)
        self._publish_link()
        self.session_id = int(time.time()) & 0xFFFFFFFF
        self.firmware_config = {}
        self.last_sent_reason = None
        self.pending_ack = None

    # ---- lifecycle ----
    def on_configure(self, state) -> TransitionCallbackReturn:
        port = self.get_parameter('serial_port').get_parameter_value().string_value
        params_dir = self.get_parameter('params_dir').get_parameter_value().string_value
        trial = self.get_parameter('trial').get_parameter_value().bool_value
        values = {k: optional_double(self, k) for k in ('joystick_timeout_s', 'send_period_s')}
        missing = [k for k, v in values.items() if v is None]
        if not port or missing:
            self._decision('configure_refused', f'serial_port={port!r}; unresolved settings {missing} (pass design/generated/params/vehicle_bridge.yaml and the trial file for stub tests)', values)
            return TransitionCallbackReturn.FAILURE
        try:
            self.core = BridgeCore(BridgeSettings(values['joystick_timeout_s'], values['send_period_s']))
            self.firmware_config = load_firmware_config(params_dir, trial) if params_dir else {}
            self.transport = SerialTransport(port, self._on_bytes, lambda m: self._decision('serial_error', m, {}), self._on_link)
        except Exception as e:
            self._decision('configure_refused', f'cannot open serial port {port}: {e}', values); self.core = None
            return TransitionCallbackReturn.FAILURE
        self.joy_sub = self.create_subscription(Joy, 'vehicle/joystick_command', self._on_joy, COMMAND_QOS)
        self._decision('settings', 'configured', dict(values, serial_port=port, firmware_config=self.firmware_config, trial=trial))
        self._set_link(LINK_UP)
        self._start_session()
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.timer = self.create_timer(self.core.s.send_period_s, self._send_command)
        self._decision('activated', 'COMMAND transmission started (period PRM-14, pc_enable_request set)', {})
        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        self.last_sent_reason = None
        self._decision('deactivated', 'COMMAND transmission stopped; the firmware PC source expires (PRM-13) and goes neutral', {})
        return super().on_deactivate(state)

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        if self.joy_sub: self.destroy_subscription(self.joy_sub); self.joy_sub = None
        if self.transport: self.transport.close(); self.transport = None
        self.core = None
        self._set_link(LINK_NOT_OPEN)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        if self.transport: self.transport.close(); self.transport = None
        return TransitionCallbackReturn.SUCCESS

    # ---- session ----
    def _ms(self) -> int:
        return int(time.monotonic() * 1000) & 0xFFFFFFFF

    def _start_session(self):
        with self._lock:
            self.transport.write(proto.encode_hello(self.core.next_seq(), self._ms(), self.session_id))
            self._decision('hello_sent', 'HELLO sent; waiting for HELLO_REPLY (boot_token)', {'session_id': self.session_id})

    def _register_config(self):
        if not self.firmware_config:
            self._decision('config_not_registered', 'no firmware configuration values available (firmware_config.yaml has no decided values; trial file not loaded)', {}); return
        self.transport.write(proto.encode_set_config(self.core.next_seq(), self._ms(), self.core.boot_token, self.firmware_config))
        self.pending_ack = proto.SET_CONFIG
        self._decision('config_sent', 'SET_CONFIG sent (apply_timing=runtime_set)', {'config': self.firmware_config})

    def _on_link(self, up: bool, reason: str):
        """USB link down / back (DEC-176). Nothing else changes: the lifecycle state stays, autonomy is not paused (人の
        決定), and while the link is down the firmware's PC source expires (PRM-13) and goes neutral while the gamepad keeps
        working. Back: HELLO again; the HELLO_REPLY decides whether the configuration is registered (new boot_token or
        config not valid), and COMMAND resumes with the reply's boot_token."""
        with self._lock:
            if not self.core: return
            now = time.time()
            if not up:
                self.link.on_link(LINK_DOWN, now); counts = self._counts(now)
                # fixed reason (DEC-177): the monitor aggregates repeats into one line, and its ×count is the number of losses
                self._decision('serial_disconnected', 'ESP32 USB link lost: no COMMAND reaches the ESP32, which neutralises the PC source after PRM-13, so the vehicle stops; the mode is unchanged (autonomy continues, DEC-176); the gamepad still works; waiting for the by-id device to come back', {'cause': reason, 'vehicle': 'stopped by the firmware PC-source expiry (PRM-13)', 'mode': 'unchanged', **counts})
                self._publish_link()
                return
            self.link.on_link(LINK_UP, now); counts = self._counts(now)
            self.parser = proto.Parser()
            self._decision('serial_reconnected', 'ESP32 USB link back (same by-id name); restarting the session with HELLO', counts)
            self._publish_link()
            self._start_session()

    # ---- link counts (DEC-177) ----
    def _counts(self, now: float) -> dict:
        st = self.link.status(now)
        return {k: st[k] for k in ('session', 'disconnects', 'reconnects', 'down_total_s')}

    def _set_link(self, state: str):
        if self.link.on_link(state, time.time()):
            self._publish_link()

    def _on_mode(self, msg: SoftwareMode):
        with self._lock:
            now = time.time()
            change = self.link.on_mode(int(msg.mode), now)
            if change is None:
                return
            kind, data = change
            if kind == 'session_started':
                self._decision('link_count_started', f'USB link counting started for the {data} session (DEC-177)', self._counts(now))
            else:
                self._decision('link_count_ended', f"USB link counts of the {data['kind']} session: {data['disconnects']} disconnects", data)
            self._publish_link()

    def _publish_link(self):
        st = self.link.status(time.time())
        arr = DiagnosticArray(); arr.header.stamp = self.get_clock().now().to_msg()
        d = DiagnosticStatus(); d.name = 'esp32_usb_link'; d.hardware_id = ''
        d.level = DiagnosticStatus.WARN if st['link'] == LINK_DOWN else DiagnosticStatus.OK
        d.message = f"link {st['link']}" + (f", {st['session']} session: {st['disconnects']} disconnects" if st['session'] else ', no session')
        d.values = [KeyValue(key=k, value='' if v is None else (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v))) for k, v in st.items()]
        arr.status = [d]; self.link_pub.publish(arr)

    # ---- serial input ----
    def _on_bytes(self, data: bytes):
        with self._lock:
            if not self.core: return
            for f in self.parser.feed(data):
                try:
                    self._handle(f)
                except Exception as e:
                    self._decision('frame_decode_failed', f'kind=0x{f.kind:02x}: {e}', {})

    def _handle(self, f: proto.Frame):
        if f.kind == proto.HELLO_REPLY:
            r = proto.decode_hello_reply(f.payload)
            changed = self.core.on_hello_reply(r)
            self._decision('hello_reply', f'boot_token=0x{r["boot_token"]:08x} config_valid={r["config_valid"]} generation={r["config_generation"]} protocol={r["protocol_version"]}', r)
            if changed or not r['config_valid']:
                self._register_config()
        elif f.kind == proto.STATUS:
            s = proto.decode_status(f.payload)
            if self.core.on_status(s):
                self._decision('esp32_rebooted', 'uptime went backwards: restarting the session (HELLO, SET_CONFIG)', {'uptime_ms': s['uptime_ms']})
                self._start_session()
            self._publish_status(s)
        elif f.kind == proto.EVENT:
            e = proto.decode_event(f.payload)
            self._decision('esp32_event', e['name'], e)
            if e['code'] == 0:   # boot
                self._start_session()
        elif f.kind == proto.ACK:
            a = proto.decode_ack(f.payload)
            self._decision('esp32_ack', f'request 0x{a["request_type"]:02x}: {a["result_name"]}', a)
        elif f.kind == proto.CONFIG:
            self._decision('esp32_config', 'CONFIG received', proto.decode_config(f.payload))

    def _publish_status(self, s: dict):
        arr = DiagnosticArray(); arr.header.stamp = self.get_clock().now().to_msg()
        st = DiagnosticStatus(); st.name = 'esp32'; st.hardware_id = f'boot_token=0x{self.core.boot_token:08x}' if self.core.boot_token is not None else ''
        st.level = DiagnosticStatus.OK if s.get('config_valid') else DiagnosticStatus.WARN
        st.message = f"source={s['source']} reason={s['reason']}"
        st.values = [KeyValue(key=k, value=v) for k, v in BridgeCore.status_key_values(s)]
        arr.status = [st]
        self.status_pub.publish(arr)

    # ---- inputs / output ----
    def _on_joy(self, msg: Joy):
        with self._lock:
            if self.core and len(msg.axes) >= 2:
                self.core.on_joystick(msg.axes[0], msg.axes[1], time.monotonic())

    def _send_command(self):
        with self._lock:
            if not self.core or not self.transport: return
            d = self.core.command(time.monotonic(), True)
            if not d.send: return
            if self.core.boot_token is None:
                if self.last_sent_reason != 'no_token':
                    self.last_sent_reason = 'no_token'; self._decision('command_not_sent', 'no boot_token yet (HELLO_REPLY not received); COMMAND withheld', {})
                    self._start_session()
                return
            self.transport.write(proto.encode_command(self.core.next_seq(), self._ms(), self.core.boot_token, d.x_q10000, d.y_q10000, d.flags))
            if d.reason != self.last_sent_reason:
                self.last_sent_reason = d.reason
                self._decision('command_output', d.reason, {'x_q10000': d.x_q10000, 'y_q10000': d.y_q10000, 'flags': d.flags})

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'vehicle_bridge'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = ''; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)


def main(args=None):
    rclpy.init(args=args)
    node = VehicleBridgeNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()

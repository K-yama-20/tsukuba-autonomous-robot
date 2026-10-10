"""vehicle_bridge node (ND-12) — stage 5-5 (vehicle output), lifecycle node around BridgeCore and a serial transport to the ESP32.

Protocol v4: design/docs/esp32_protocol_v4.md (IFD-17 out, IFD-43 in). Subscribes vehicle/joystick_command (IFD-16).
Publishes /esp32/status (IFD-38, diagnostic_msgs/DiagnosticArray, reliable, volatile, depth 10; display/diagnosis only,
DEC-006) on every STATUS, and log/decision (IFD-28) for session events, config registration results and output changes.

Session: on configure the port is opened, HELLO is sent, the HELLO_REPLY gives the boot_token, and the firmware
configuration from design/generated/params/firmware_config.yaml (plus firmware_config.trial.yaml when trial:=true; stub
tests only) is registered with SET_CONFIG. A rejected or missing ACK is recorded and never stops anything. A reboot of the
ESP32 (uptime going backwards / new boot token) repeats the session start.
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
from gouda_interfaces.msg import DecisionEvent

from gouda_core import esp32_protocol as proto
from gouda_core.vehicle_core import BridgeCore, BridgeSettings

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
    """pyserial wrapper with a reader thread. Replaceable by a stub in tests."""

    def __init__(self, port: str, on_bytes, on_error):
        import serial
        self.ser = serial.Serial(port, SERIAL_BAUD, timeout=0.05, write_timeout=0.2, exclusive=True)
        self.ser.reset_input_buffer()
        self.on_bytes = on_bytes; self.on_error = on_error
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name='vehicle_bridge_serial', daemon=True); self.thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                data = self.ser.read(256)
            except Exception as e:
                self.on_error(f'serial read failed: {e}'); time.sleep(0.5); continue
            if data: self.on_bytes(data)

    def write(self, data: bytes):
        try:
            self.ser.write(data)
        except Exception as e:
            self.on_error(f'serial write failed: {e}')

    def close(self):
        self._stop.set(); self.thread.join(timeout=1)
        try: self.ser.close()
        except Exception: pass


class VehicleBridgeNode(LifecycleNode):
    def __init__(self):
        super().__init__('vehicle_bridge')
        self.declare_parameter('serial_port', '')     # operational value (launch argument)
        self.declare_parameter('params_dir', '')      # where firmware_config.yaml is read from
        self.declare_parameter('trial', False)        # also read firmware_config.trial.yaml (stub tests only)
        for key in ('joystick_timeout_s', 'send_period_s'):
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self._lock = threading.RLock()
        self.core = None; self.transport = None; self.parser = proto.Parser()
        self.timer = None; self.joy_sub = None
        self.status_pub = self.create_publisher(DiagnosticArray, '/esp32/status', STATUS_QOS)
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
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
            self.transport = SerialTransport(port, self._on_bytes, lambda m: self._decision('serial_error', m, {}))
        except Exception as e:
            self._decision('configure_refused', f'cannot open serial port {port}: {e}', values); self.core = None
            return TransitionCallbackReturn.FAILURE
        self.joy_sub = self.create_subscription(Joy, 'vehicle/joystick_command', self._on_joy, COMMAND_QOS)
        self._decision('settings', 'configured', dict(values, serial_port=port, firmware_config=self.firmware_config, trial=trial))
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

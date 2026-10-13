"""gouda_sensor_supervisor (ND-18): starts the sensor drivers ND-14 (hesai_ros_driver, XT-32) and ND-15 (adi_imu_driver,
ADIS16607-2) as child processes and re-creates a driver ONLY when its device is re-connected (DEC-088).
Design: docs/sensor_supervision.md, device_watch.py (identity and the restart rule).

- Devices are found by name: the IMU by its /dev/serial/by-id name (PRM-54), the LiDAR link by the interface that holds the PC
  address PRM-51. Kernel numbers (ttyACMn, ifindex) only serve to notice a new enumeration.
- Evaluation is event driven: `udevadm monitor` (tty / net add-remove) and `ip monitor link address` wake it up; there is no
  polling period. It also runs once at start.
- Same identity -> no restart, even when a driver exits (restarting the IMU driver without a re-plug freezes the IMU). A
  previous session's identity is kept in <run_dir>/sensor_devices.json; reopening the same IMU enumeration is recorded as a
  warning because that is the case where the IMU has stopped answering.
- Every decision is a DecisionEvent (IFD-28, node gouda_sensor_supervisor) and appears in the monitor history.
Settings: params_dir / trial (driver settings, as before), run_dir, driver_stop_wait_s (PRM-59; while unresolved a stopping
driver is waited for without an upper limit). No number is written here (RQ-I076).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from gouda_interfaces.msg import DecisionEvent

from gouda_core import sensor_config as sc
from gouda_core import device_watch as dw

DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
PRM = {'device_ip_address': 'PRM-50', 'host_ip_address': 'PRM-51', 'udp_port': 'PRM-52', 'ptc_port': 'PRM-53', 'use_timestamp_type': 'PRM-55',
       'device': 'PRM-54', 'rate': 'PRM-56'}


def optional_double(node, name):
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None


def executable(package: str, name: str):
    from ament_index_python.packages import get_package_prefix, PackageNotFoundError
    try:
        path = os.path.join(get_package_prefix(package), 'lib', package, name)
    except PackageNotFoundError:
        return None
    return path if os.access(path, os.X_OK) else None


class Driver:
    """One driver child process and the device it belongs to."""

    def __init__(self, key, label, device, command, not_started_reason=None):
        self.key, self.label, self.device, self.command = key, label, device, command
        self.not_started_reason = not_started_reason
        self.proc = None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None


class SensorSupervisorNode(Node):
    def __init__(self):
        super().__init__('gouda_sensor_supervisor')
        self.declare_parameter('params_dir', '')
        self.declare_parameter('run_dir', '')
        self.declare_parameter('trial', False)
        self.declare_parameter('driver_stop_wait_s', Parameter.Type.DOUBLE)   # PRM-59
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        params_dir = self.get_parameter('params_dir').get_parameter_value().string_value
        self.run_dir = os.path.expanduser(self.get_parameter('run_dir').get_parameter_value().string_value or '.')
        trial = self.get_parameter('trial').get_parameter_value().bool_value
        self.stop_wait_s = optional_double(self, 'driver_stop_wait_s')
        os.makedirs(self.run_dir, exist_ok=True)
        self.state_path = os.path.join(self.run_dir, 'sensor_devices.json')
        self.previous = self._load_previous()
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stopping = False
        self.drivers = self._build_drivers(params_dir, trial)
        self._decision('settings', 'sensor supervisor configured', {
            'drivers': {k: {'device': d.device.name, 'command': d.command, 'not_started_reason': d.not_started_reason} for k, d in self.drivers.items()},
            'driver_stop_wait_s': self.stop_wait_s if self.stop_wait_s is not None else 'none (PRM-59 unresolved: no upper limit)',
            'trial': trial, 'previous_identities': self.previous})
        self._watchers = []
        for cmd in (['udevadm', 'monitor', '--udev', '--subsystem-match=tty', '--subsystem-match=net'], ['ip', '-o', 'monitor', 'link', 'address']):
            threading.Thread(target=self._watch, args=(cmd,), name='watch_' + cmd[0], daemon=True).start()
        threading.Thread(target=self._loop, name='evaluate', daemon=True).start()
        self._wake.set()   # first evaluation at start

    # ---- configuration ----
    def _build_drivers(self, params_dir, trial):
        drivers = {}
        # ND-14 XT-32: config file generated from the upstream template (sensor_config), device = interface holding PRM-51
        hp = sc.read_node_params(params_dir, 'hesai_ros_driver', trial) if params_dir else {}
        exe = executable('hesai_ros_driver', 'hesai_ros_driver_node')
        template = None
        try:
            from ament_index_python.packages import get_package_share_directory
            template = sc.find_template(get_package_share_directory('hesai_ros_driver'))
        except Exception:
            pass
        reason, cmd = None, None
        cfg_path = os.path.join(self.run_dir, 'hesai_ros_driver.config.yaml')
        if exe is None or template is None:
            reason = 'hesai_ros_driver is not installed'
        else:
            missing = sc.write_hesai_config(template, hp, cfg_path)
            if missing:
                reason = f'unresolved {[f"{k} ({PRM[k]})" for k in missing]} in hesai_ros_driver.yaml'
            else:
                cmd = [exe, '--ros-args', '-r', '__node:=hesai_ros_driver', '-p', f'config_path:={cfg_path}']
        host_ip = hp.get('host_ip_address')
        drivers['lidar'] = Driver('lidar', 'XT-32 (ND-14)', dw.WatchedDevice(f'interface holding {host_ip} (PRM-51)'), cmd, reason)
        drivers['lidar'].host_ip = host_ip
        # ND-15 IMU: ROS parameters; device = by-id name (PRM-54)
        ip_, missing = sc.imu_parameters(sc.read_node_params(params_dir, 'adi_imu_driver', trial) if params_dir else {})
        exe = executable('adi_imu_tr_driver_ros2', 'adis_rcv_bin_node')
        reason, cmd = None, None
        if exe is None:
            reason = 'adi_imu_tr_driver_ros2 is not installed'
        elif missing:
            reason = f'unresolved {[f"{k} ({PRM[k]})" for k in missing]} in adi_imu_driver.yaml'
        else:
            cmd = [exe, '--ros-args', '-r', '__node:=adi_imu_driver', '-r', f'{sc.IMU_DRIVER_TOPIC}:={sc.IMU_TOPIC}']
            for k, v in ip_.items():
                cmd += ['-p', f'{k}:={str(v).lower() if isinstance(v, bool) else v}']
        drivers['imu'] = Driver('imu', 'IMU (ND-15)', dw.WatchedDevice(ip_.get('device') or 'by-id name (PRM-54) unresolved'), cmd, reason)
        drivers['imu'].by_id = ip_.get('device')
        for d in drivers.values():
            if d.not_started_reason:
                self._decision('driver_not_started', f'{d.label} is not started: {d.not_started_reason}', {'driver': d.key})
        return drivers

    # ---- device identities ----
    def _observe(self, d):
        if d.key == 'imu':
            return dw.tty_identity(d.by_id) if d.by_id else None
        try:
            out = subprocess.run(['ip', '-j', '-4', 'addr'], capture_output=True, text=True).stdout
        except OSError:
            return None
        return dw.net_identity(d.host_ip, out) if d.host_ip else None

    def _watch(self, cmd):
        """Wake the evaluation on every device / address event (event driven; no polling period)."""
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError as e:
            self._decision('watch_failed', f'{cmd[0]} could not be started: {e}; device changes are only seen at start', {})
            return
        self._watchers.append(p)
        for _ in p.stdout:
            if self._stopping: break
            self._wake.set()

    def _loop(self):
        while not self._stopping:
            self._wake.wait()
            self._wake.clear()
            if self._stopping: break
            with self._lock:
                for d in self.drivers.values():
                    self._evaluate(d)

    def _evaluate(self, d):
        observed = self._observe(d)
        action = d.device.decide(observed)
        if d.device.presence_changed(observed):
            self._decision('device_present' if observed else 'device_absent', f'{d.label}: {d.device.name} -> {observed or "absent (the driver is started when it appears)"}', {'driver': d.key, 'identity': observed})
        if d.command is None:   # settings incomplete or driver not installed: presence is recorded, nothing is started
            d.device.seen = observed; d.device.evaluated = True
            return
        if action == dw.ACTION_START:
            if d.key == 'imu' and self.previous.get('imu') == observed:   # opened before (this or an earlier session) without a re-plug
                self._decision('device_reopened_without_reconnect', f'{d.label}: same USB enumeration {observed} as the previous session; '
                               'the IMU may not answer (known problem after a driver restart). Re-plug the IMU USB if no IMU data arrives', {'driver': d.key, 'identity': observed})
            self._start(d, observed, 'driver_started', 'device present')
        elif action == dw.ACTION_RESTART:
            self._decision('device_reconnected', f'{d.label}: new enumeration {d.device.identity} -> {observed}', {'driver': d.key, 'old': d.device.identity, 'new': observed})
            self._stop(d)
            self._start(d, observed, 'driver_restarted', 'device re-connected')
        elif action == dw.ACTION_STOP:
            self._stop(d)
            self._decision('driver_stopped', f'{d.label}: device absent; the driver is started again when the device re-appears', {'driver': d.key})
        d.device.apply(observed, action)
        self._save()

    # ---- processes ----
    def _start(self, d, identity, event, why):
        try:
            d.proc = subprocess.Popen(d.command)   # same process group: gouda.sh stop signals it too
        except OSError as e:
            self._decision('driver_start_failed', f'{d.label}: {e}', {'driver': d.key}); d.proc = None; return
        self._decision(event, f'{d.label}: started (pid {d.proc.pid}) for {identity} ({why})', {'driver': d.key, 'identity': identity, 'pid': d.proc.pid})
        threading.Thread(target=self._wait_exit, args=(d, d.proc), daemon=True).start()

    def _wait_exit(self, d, proc):
        code = proc.wait()
        if self._stopping or d.proc is not proc: return
        self._decision('driver_exited', f'{d.label}: exited with code {code}; it is NOT restarted for the same device '
                       '(re-created only when the device is re-connected)', {'driver': d.key, 'exit_code': code, 'identity': d.device.identity})

    def _stop(self, d):
        proc, d.proc = d.proc, None
        if proc is None or proc.poll() is not None: return
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            try: proc.send_signal(sig)
            except ProcessLookupError: return
            try:
                proc.wait(timeout=self.stop_wait_s)   # None: no upper limit while PRM-59 is unresolved
                return
            except subprocess.TimeoutExpired:
                self._decision('driver_stop_escalated', f'{d.label}: still running {self.stop_wait_s} s after {sig.name}', {'driver': d.key})

    def _load_previous(self):
        try:
            with open(os.path.join(self.run_dir, 'sensor_devices.json'), encoding='utf-8') as f:
                return json.load(f).get('identities', {})
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.previous = dw.merge_opened(self.previous, {k: d.device.identity for k, d in self.drivers.items()})
        data = {'identities': self.previous, 'saved_at': time.time()}
        tmp = self.state_path + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f: json.dump(data, f)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_sensor_supervisor'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = ''; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)
        self.get_logger().info(f'{event}: {reason}')

    def shutdown(self):
        self._stopping = True; self._wake.set()
        for p in self._watchers:
            try: p.terminate()
            except Exception: pass
        for d in self.drivers.values():
            self._stop(d)


def main(args=None):
    rclpy.init(args=args)
    node = SensorSupervisorNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.shutdown(); node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()

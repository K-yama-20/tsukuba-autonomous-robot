"""Opt-in USB v3 bridge. The legacy simulation PTY bridge stays independent."""
from __future__ import annotations

import json
import math
import re
import time

import rclpy
import serial
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool

from .protocol_v3 import Parser, STATUS, encode_arm, encode_command, encode_disarm


def validate_hardware_port(port):
    if not isinstance(port, str) or not (
        re.fullmatch(r'/dev/serial/by-id/[A-Za-z0-9_.:+-]+', port)
        or re.fullmatch(r'/dev/tty(?:ACM|USB)\d+', port)
    ):
        raise ValueError('Select an explicit /dev/serial/by-id, /dev/ttyACM<n>, or /dev/ttyUSB<n> device')
    return port


def open_hardware_serial(port, serial_factory=serial.Serial):
    """Open USB without requesting DTR or RTS assertion; drivers may still pulse on open."""
    port = validate_hardware_port(port)
    connection = serial_factory()
    connection.baudrate = 115200
    connection.timeout = 0
    connection.write_timeout = 0.02
    connection.exclusive = True
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    return connection


class HardwareSerialBridge(Node):
    def __init__(self):
        super().__init__('gouda_hardware_serial_bridge')
        self.declare_parameter('hardware_enabled', False)
        self.declare_parameter('port', '')
        if self.get_parameter('hardware_enabled').value is not True:
            raise RuntimeError('Hardware serial is disabled; set hardware_enabled=true explicitly')
        port = validate_hardware_port(self.get_parameter('port').value)
        self.serial = open_hardware_serial(port)
        self.parser = Parser()
        self.status_frame = None
        self.status_values = None
        self.last_status_wall = 0.0
        self.last_drive_wall = 0.0
        self.drive = None
        self.sender_seq = 0
        self.arm_requested = False
        self.token = None
        self.status_pub = self.create_publisher(String, '/esp32/status', 10)
        self.manual_pub = self.create_publisher(String, '/gouda/control/manual_input', 10)
        self.trace_pub = self.create_publisher(String, '/gouda/control_trace', 10)
        self.drive_sub = self.create_subscription(String, '/gouda/control/drive', self.on_drive, 10)
        self.arm_srv = self.create_service(SetBool, '/gouda/arm', self.on_arm)
        self.timer = self.create_timer(.02, self.tick)

    def on_drive(self, msg):
        try:
            value = json.loads(msg.data)
            axes = (value.get('forward_norm'), value.get('yaw_left_norm'))
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in axes):
                return
            if any(abs(v) > 1 for v in axes):
                return
            stamp = value.get('issued_at')
            if not isinstance(stamp, dict) or type(stamp.get('sec')) is not int or type(stamp.get('nanosec')) is not int:
                return
            now = self.get_clock().now().nanoseconds
            issued = stamp['sec']*1_000_000_000 + stamp['nanosec']
            age = (now-issued)/1e9
            if not -.05 <= age <= .15:
                return
            if not isinstance(value.get('request_id'), str) or len(value['request_id']) > 80:
                return
            self.drive = {
                'forward_norm': float(axes[0]),
                'yaw_left_norm': float(axes[1]),
                'request_id': value['request_id'],
                'enable_requested': value.get('enable_requested') is True,
                'issued_at': stamp,
            }
            self.last_drive_wall = time.monotonic()
        except (ValueError, TypeError, json.JSONDecodeError):
            return

    def _fresh_status(self):
        return bool(self.status_values and self.last_status_wall and
                    time.monotonic()-self.last_status_wall < .25 and
                    self.status_values['connected'] and self.status_values['fresh'])

    def _next_seq(self):
        self.sender_seq = (self.sender_seq + 1) & 0xFFFFFFFF
        return self.sender_seq

    @staticmethod
    def _sender_ms():
        return (time.monotonic_ns() // 1_000_000) & 0xFFFFFFFF

    def _write(self, data):
        try:
            count = self.serial.write(data)
            if count != len(data):
                self.arm_requested = False
                return False
            return True
        except (serial.SerialException, OSError):
            self.arm_requested = False
            return False

    def _send_command(self, forward=0.0, yaw_left=0.0):
        if self.token is None:
            return False
        return self._write(encode_command(self.token, self._next_seq(), self._sender_ms(),
                                          forward, yaw_left))

    def on_arm(self, req, res):
        if not req.data:
            self.arm_requested = False
            if self.token is not None:
                self._write(encode_disarm(self.token, self._next_seq(), self._sender_ms()))
            res.success = True
            res.message = 'DISARM sent; device manual input remains firmware-prioritized'
            return res
        if self.drive is None or time.monotonic()-self.last_drive_wall > .15:
            res.success=False;res.message='Fresh PC drive heartbeat required before ARM';return res
        if not self._fresh_status():
            res.success = False
            res.message = 'Fresh connected device status is required before explicit ARM'
            return res
        if (not self.status_values['centered'] or self.status_values['owner']==1
                or self.status_values['manual_right_norm'] != 0 or self.status_values['manual_forward_norm'] != 0):
            res.success = False
            res.message = 'Center the physical controller before ARM'
            return res
        if self.status_values['auto_enabled']:
            res.success=False;res.message='Device already armed; cancel first';return res
        # Firmware requires a fresh neutral PC candidate immediately before ARM.
        if not self._send_command(0.0, 0.0):
            res.success = False
            res.message = 'Could not send neutral command'
            return res
        if not self._write(encode_arm(self.token, self._next_seq(), self._sender_ms())):
            res.success = False
            res.message = 'Could not send ARM'
            return res
        self.arm_requested = True
        self.arm_started = time.monotonic()
        res.success = True
        res.message = 'ARM sent; autonomy must wait for device auto_enabled status'
        return res

    def _publish_status(self, frame):
        values = frame.status()
        if values is None:
            return
        now = self.get_clock().now().to_msg()
        stamp = {'sec': int(now.sec), 'nanosec': int(now.nanosec)}
        self.status_pub.publish(String(data=json.dumps({
            **values,
            'boot_token': frame.boot_token,
            'device_monotonic_ms': frame.sender_monotonic_ms,
            'device_seq': frame.sender_seq,
            'ros_received_stamp': stamp,
            'host_monotonic_ns': time.monotonic_ns(),
            'requested_millivolts_are_not_measured': True,
        }, separators=(',', ':'))))
        self.manual_pub.publish(String(data=json.dumps({
            'ros_received_stamp': stamp, 'host_monotonic_ns': time.monotonic_ns(),
            'boot_token': frame.boot_token, 'device_seq': frame.sender_seq,
            'owner': values['owner'], 'raw_x_counts': values['raw_x_counts'], 'raw_y_counts': values['raw_y_counts'],
            'manual_right_norm': values['manual_right_norm'],
            'manual_forward_norm': values['manual_forward_norm'],
        }, separators=(',', ':'))))
        drive = self.drive or {}
        self.trace_pub.publish(String(data=json.dumps({
            'ros_received_stamp': stamp,
            'host_monotonic_ns': time.monotonic_ns(),
            'boot_token': frame.boot_token,
            'device_monotonic_ms': frame.sender_monotonic_ms,
            'device_seq': frame.sender_seq,
            'device_owner': values['owner'],
            'manual_input': {'raw_x_counts': values['raw_x_counts'], 'raw_y_counts': values['raw_y_counts'],
                             'right_norm': values['manual_right_norm'],
                             'forward_norm': values['manual_forward_norm']},
            'pc_request': {'request_id': drive.get('request_id'),
                           'forward_norm': drive.get('forward_norm', 0.0),
                           'yaw_left_norm': drive.get('yaw_left_norm', 0.0),
                           'right_norm': -drive.get('yaw_left_norm', 0.0)},
            'applied_normalized': {'right_norm': values['applied_right_norm'],
                                   'forward_norm': values['applied_forward_norm']},
            'dac_codes': {'x': values['dac_x_code'], 'y': values['dac_y_code']},
            'requested_millivolts': {'x': values['requested_mv_x'], 'y': values['requested_mv_y'],
                                     'is_measurement': False},
            'link_ages_ms': {'bluetooth': values['bt_age_ms'], 'pc': values['pc_age_ms']},
        }, separators=(',', ':'))))

    def tick(self):
        try:
            frames = self.parser.feed(self.serial.read(256))
        except (serial.SerialException, OSError) as exc:
            self.arm_requested = False
            self.get_logger().error(f'USB serial read failed: {exc}')
            return
        for frame in frames:
            if frame.kind != STATUS:
                continue
            try:
                decoded_status = frame.status()
            except ValueError:
                continue
            if decoded_status is None:
                continue
            if self.token != frame.boot_token:
                # A device reboot never triggers automatic ARM recovery.
                self.token = frame.boot_token
                self.arm_requested = False
            if self.status_frame and self.status_frame.boot_token == frame.boot_token:
                delta=(frame.sender_seq-self.status_frame.sender_seq)&0xFFFFFFFF
                if not 0 < delta < 0x80000000:continue
            self.status_frame = frame
            self.status_values = decoded_status
            self.last_status_wall = time.monotonic()
            self._publish_status(frame)
            if not self.status_values['connected'] or not self.status_values['fresh']:
                self.arm_requested = False
        drive_fresh = self.drive is not None and time.monotonic()-self.last_drive_wall <= .15
        if not self._fresh_status() or not drive_fresh:
            if self.arm_requested:
                self.arm_requested=False
                if self.token is not None:self._write(encode_disarm(self.token,self._next_seq(),self._sender_ms()))
            return
        if not self.arm_requested:return
        if not self.status_values['auto_enabled']:
            if time.monotonic()-self.arm_started < .2:self._send_command()
            else:self.arm_requested=False
            return
        if self.drive['enable_requested']:
            self._send_command(self.drive['forward_norm'], self.drive['yaw_left_norm'])
        else:
            self._send_command(0.0, 0.0)

    def close(self):
        if self.token is not None:
            self._write(encode_disarm(self.token, self._next_seq(), self._sender_ms()))
        self.arm_requested = False
        self.serial.close()


def main():
    rclpy.init()
    node = HardwareSerialBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

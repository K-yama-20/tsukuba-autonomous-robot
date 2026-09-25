import json
import os
import time
import serial
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from std_msgs.msg import UInt8, Bool, String
from std_srvs.srv import SetBool
from .protocol import Frame, Parser, COMMAND, ARM, DISARM, STATUS


class Bridge(Node):
    def __init__(self):
        super().__init__('serial_bridge_node')
        self.declare_parameter('port', '')
        self.declare_parameter('profile', 'simulation')
        port = os.path.realpath(self.get_parameter('port').value)
        profile = self.get_parameter('profile').value
        if profile != 'simulation' or not port.startswith('/dev/pts/'):
            raise ValueError('This development bridge permits simulation PTYs only; hardware calibration review is pending')
        self.serial = serial.Serial(port, 115200, timeout=0, write_timeout=0.02, exclusive=True)
        self.serial.reset_input_buffer()
        self.parser = Parser()
        self.status = None
        self.last_status = -1e9
        self.command, self.last_command = 0, -1e9
        self.permit, self.last_permit = False, -1e9
        self.requested = False
        self.seq = 0
        self.output = self.create_publisher(String, '/esp32/status', 1)
        self.create_subscription(UInt8, '/cmd_motion', self.on_command, 1)
        self.create_subscription(Bool, '/gouda/motion_permit', self.on_permit, 1)
        self.create_service(SetBool, '/gouda/arm', self.arm)
        self.create_timer(.05, self.tick, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_command(self, msg):
        self.command = msg.data if msg.data <= 4 else 0
        self.last_command = time.monotonic()
        if msg.data > 4:
            self.requested = False
        if self.command == 0 and self.status and self.status.flags:
            self.send(COMMAND, 0, 1)  # STOP does not wait for the periodic heartbeat

    def on_permit(self, msg):
        self.permit, self.last_permit = msg.data, time.monotonic()
        if not msg.data:
            self.requested = False

    def fresh(self):
        now = time.monotonic()
        return self.permit and now-self.last_permit < .2 and now-self.last_command < .2 and now-self.last_status < .2

    def arm(self, req, res):
        if not req.data:
            self.requested = False
            if self.status:
                self.send(DISARM)
            res.success = True
        elif self.status and self.fresh() and self.command == 0:
            self.requested = True
            self.send(ARM, 0, 1)
            res.success = True
        else:
            res.success = False
        res.message = 'requested; verify enabled status' if res.success else 'fresh STOP, sensor permit, and status required'
        return res

    def send(self, kind, motion=0, flags=0):
        if self.status is None:
            return
        self.seq = (self.seq + 1) & 0xffffffff
        try:
            self.serial.write(Frame(kind, self.status.token, self.seq, motion, flags).encode())
        except (serial.SerialException, serial.SerialTimeoutException, OSError):
            self.requested = False

    def tick(self):
        try:
            for frame in self.parser.feed(self.serial.read(4096)):
                if frame.kind != STATUS or frame.motion > 4 or frame.flags > 1:
                    continue
                if self.status and frame.token != self.status.token:
                    self.requested = False
                    self.command, self.last_command = 0, -1e9
                if self.status is None or frame.token != self.status.token:
                    self.seq = frame.seq
                self.status, self.last_status = frame, time.monotonic()
                self.output.publish(String(data=json.dumps(vars(frame))))
        except (serial.SerialException, OSError):
            self.requested = False
        if not self.fresh():
            self.requested = False
        if self.status and self.status.flags:
            self.send(COMMAND, self.command, 1) if self.requested else self.send(DISARM)

    def close(self):
        self.send(DISARM)
        self.serial.close()


def main():
    rclpy.init()
    node = Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close(); node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

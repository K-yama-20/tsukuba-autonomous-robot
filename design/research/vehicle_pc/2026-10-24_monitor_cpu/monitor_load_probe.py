"""Read-only probe (第161便): subscribe like gouda_monitor and measure this process's own CPU. Publishes nothing."""
import sys, time, os, resource
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Imu, NavSatFix
from diagnostic_msgs.msg import DiagnosticArray
from hesai_ros_driver.msg import LossPacket
from gouda_interfaces.msg import SoftwareMode, DecisionEvent

mode, executor_kind, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
rclpy.init()
n = Node('_probe_monitor_load')
counts = {}
def cb(k):
    def f(_m): counts[k] = counts.get(k, 0) + 1
    return f
sensor_qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=5)
latched = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
n.create_subscription(Imu, 'sensors/imu/data', cb('imu'), sensor_qos, raw=True)
if mode == 'all':
    n.create_subscription(LossPacket, 'sensors/xt32/packet_loss', cb('loss'), QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10))
    n.create_subscription(NavSatFix, 'sensors/gnss/navsatfix', cb('gnss'), sensor_qos, raw=True)
    n.create_subscription(SoftwareMode, 'mode/state', cb('mode'), latched)
    n.create_subscription(DiagnosticArray, '/esp32/status', cb('esp32'), 10)
    n.create_subscription(DecisionEvent, 'log/decision', cb('decision'), QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50))
    n.create_timer(2.0, lambda: n.get_node_names_and_namespaces())
ex = rclpy.executors.MultiThreadedExecutor(num_threads=4) if executor_kind == 'multi' else rclpy.executors.SingleThreadedExecutor()
ex.add_node(n)
end = time.monotonic() + 5
while time.monotonic() < end: ex.spin_once(timeout_sec=0.1)   # discovery
counts.clear(); r0 = resource.getrusage(resource.RUSAGE_SELF); t0 = time.monotonic()
end = t0 + secs
while time.monotonic() < end: ex.spin_once(timeout_sec=0.1)
r1 = resource.getrusage(resource.RUSAGE_SELF); dt = time.monotonic() - t0
cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
print(f'{mode:4s} {executor_kind:6s} wall {dt:.1f}s cpu {cpu:.2f}s = {100*cpu/dt:.0f}% msgs/s', {k: round(v/dt, 1) for k, v in counts.items()})
ex.shutdown(); n.destroy_node(); rclpy.try_shutdown()

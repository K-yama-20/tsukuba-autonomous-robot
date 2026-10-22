# TEST ONLY (bin 117): per-second counts and last values of localization / velocity topics during one autonomy start.
import json, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rosidl_runtime_py.utilities import get_message
KEYS = ("cmd_vel", "localization/odometry", "points_downsampled", "ndt_pose_with_covariance", "ekf_pose_with_covariance", "/diagnostics", "mode/state", "localization/status", "motion_hold", "/plan")
class R(Node):
    def __init__(s, out, dur):
        super().__init__("claude_rates_tmp"); s.out = open(out, "w"); s.cnt = {}; s.last = {}; s.subs = {}; s.t0 = time.time(); s.dur = dur
        s.create_timer(1.0, s.tick); s.create_timer(2.0, s.discover)
    def discover(s):
        for name, types in s.get_topic_names_and_types():
            if name in s.subs or not any(k in name for k in KEYS) or "transition_event" in name: continue
            try: cls = get_message(types[0])
            except Exception: continue
            for rel in (ReliabilityPolicy.BEST_EFFORT,):
                q = QoSProfile(depth=10, reliability=rel, durability=DurabilityPolicy.VOLATILE)
                s.subs[name] = s.create_subscription(cls, name, lambda m, n=name: s.on(n, m), q)
    def on(s, n, m):
        s.cnt[n] = s.cnt.get(n, 0) + 1
        if "cmd_vel" in n:
            tw = getattr(m, "twist", m); s.last[n] = (round(tw.linear.x, 3), round(tw.angular.z, 3))
        elif n.endswith("localization/status"): s.last[n] = (m.state, m.reason, m.detail[:80])
        elif n.endswith("mode/state"): s.last[n] = (m.mode, m.stop_reason, m.remaining_waypoints)
        elif n.endswith("motion_hold"): s.last[n] = getattr(m, "data", str(m)[:40])
    def tick(s):
        s.out.write(json.dumps({"t": round(time.time(), 1), "counts": s.cnt, "last": s.last}, ensure_ascii=False) + "\n"); s.out.flush()
        s.cnt = {}
        if time.time() - s.t0 > s.dur: raise SystemExit
rclpy.init(); n = R(sys.argv[1], float(sys.argv[2]))
try: rclpy.spin(n)
except SystemExit: pass

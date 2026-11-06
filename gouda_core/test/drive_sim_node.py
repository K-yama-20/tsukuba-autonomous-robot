"""TEST ONLY (第179便): the vehicle and the world of the driving simulator, standing in for the sensors, GLIM and ND-07's TF.

Subscribes cmd_vel (IFD-15), publishes map -> odom -> base_link, localization/odometry (IFD-25) and sensors/xt32/points (IFD-21, in
base_link) from drive_sim_core, and rewrites <report> about once a second. The real pointcloud_to_laserscan, costmaps and Nav2 read it.
usage: python3 drive_sim_node.py <scenario> <report.json> [--seed N] [--delay S] [--tau-v S] [--tau-w S] [--noise M] [--mid360-height M]
With --mid360-height it also publishes sensors/mid360/points (in base_link) for the MID-360 plan; nothing reads it yet.
第245便 (#90): about once a second it also writes obstacles.csv (where each obstacle is) and costmap_marks.csv (the lethal cells of the
local costmap and of its obstacle layers, and how many of them are not near any existing obstacle: drive_sim_blind.stale_marks).
"""
import argparse
import json
import math
import os
import time

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped, TwistStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import PointCloud2, PointField
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

import drive_sim_blind as db
import drive_sim_core as ds

PLANT_HZ, CLOUD_HZ, SCORE_HZ = 50.0, 10.0, 20.0   # the XT-32 is 10 Hz (PRM-60 600 rpm)
GRID_TOPICS = ('local_costmap/costmap', 'local_costmap/obstacle_layer', 'local_costmap/mid360_layer')   # the layers' own grids (Nav2 publishes each)
FIELDS = [PointField(name=n, offset=i * 4, datatype=PointField.FLOAT32, count=1) for i, n in enumerate('xyz')]


class DriveSim(Node):
    def __init__(self, a):
        super().__init__('drive_sim')
        self.sc = ds.scenario(a.scenario, a.seed)
        self.report_path = a.report
        self.trace = open(os.path.join(os.path.dirname(a.report) or '.', 'trace.csv'), 'w', encoding='utf-8')
        self.trace.write('t,x,y,yaw,v,w,cmd_v,cmd_w\n')
        rx, ry = self.sc.route[0], self.sc.route[1]
        self.plant = ds.Plant(x=rx[0], y=rx[1], yaw=math.atan2(ry[1] - rx[1], ry[0] - rx[0]), delay_s=a.delay, tau_v_s=a.tau_v, tau_w_s=a.tau_w)
        self.scorer = ds.Scorer(self.sc)
        self.rays = ds.beams()
        self.noise, self.rng = a.noise, np.random.default_rng(a.seed)
        self.ghost = a.ghost
        self.cmd_v, self.cmd_w, self.commands = 0.0, 0.0, 0
        self.t0 = time.monotonic()
        self.last = self.t0
        self.tf = TransformBroadcaster(self)
        self.odom_pub = self.create_publisher(Odometry, 'localization/odometry', 10)
        self.cloud_pub = self.create_publisher(PointCloud2, 'sensors/xt32/points', qos_profile_sensor_data)
        self.mid = ds.MidMount(height_m=a.mid360_height, pitch_down_deg=a.mid360_pitch) if a.mid360_height else None
        if self.mid:   # MID-360 plan stage 1: published in base_link like the XT-32's cloud; nothing reads it until stage 2
            self.mid_pub = self.create_publisher(PointCloud2, 'sensors/mid360/points', qos_profile_sensor_data)
            st = TransformStamped(); st.header.stamp = self.get_clock().now().to_msg(); st.header.frame_id = 'base_link'
            st.child_frame_id = 'mid360_link'   # the clearing origin of the MID-360 layer (stage 2); its rotation is not used there
            st.transform.translation.x, st.transform.translation.y, st.transform.translation.z = self.mid.origin()
            h = math.radians(self.mid.pitch_down_deg) / 2
            st.transform.rotation.y, st.transform.rotation.w = math.sin(h), math.cos(h)
            self.static_tf = StaticTransformBroadcaster(self); self.static_tf.sendTransform(st)
        self.create_subscription(TwistStamped, 'cmd_vel', self._on_cmd, 10)
        out = os.path.dirname(a.report) or '.'
        self.obstacle_log = open(os.path.join(out, 'obstacles.csv'), 'w', encoding='utf-8'); self.obstacle_log.write('t,name,x,y,exists\n')
        self.marks_log = open(os.path.join(out, 'costmap_marks.csv'), 'w', encoding='utf-8'); self.marks_log.write('t,topic,lethal,stale,stale_near\n')
        self.grids, self.marks = {}, {}
        grid_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)   # as Costmap2DPublisher
        for topic in GRID_TOPICS:
            self.create_subscription(OccupancyGrid, topic, lambda m, k=topic: self.grids.__setitem__(k, m), grid_qos)
        self.create_timer(1 / PLANT_HZ, self._step)
        self.create_timer(1 / CLOUD_HZ, self._cloud)
        self.create_timer(1 / SCORE_HZ, self._score)
        self.create_timer(1.0, self._write)

    def _on_cmd(self, m):
        self.cmd_v, self.cmd_w = m.twist.linear.x, m.twist.angular.z
        self.commands += 1

    def _now(self):
        return time.monotonic() - self.t0

    def _step(self):
        now = time.monotonic()
        dt, self.last = now - self.last, now
        t, p = now - self.t0, self.plant
        p.step(t, dt, self.cmd_v, self.cmd_w)
        for o in self.sc.obstacles:
            o.update(t, p.x, p.y)
        stamp = self.get_clock().now().to_msg()
        identity = TransformStamped(); identity.header.stamp = stamp; identity.header.frame_id = 'map'; identity.child_frame_id = 'odom'
        identity.transform.rotation.w = 1.0
        base = TransformStamped(); base.header.stamp = stamp; base.header.frame_id = 'odom'; base.child_frame_id = 'base_link'
        base.transform.translation.x, base.transform.translation.y = p.x, p.y
        base.transform.rotation.z, base.transform.rotation.w = math.sin(p.yaw / 2), math.cos(p.yaw / 2)
        self.tf.sendTransform([identity, base])
        o = Odometry(); o.header.stamp = stamp; o.header.frame_id = 'odom'; o.child_frame_id = 'base_link'
        o.pose.pose.position.x, o.pose.pose.position.y = p.x, p.y
        o.pose.pose.orientation = base.transform.rotation
        o.twist.twist.linear.x, o.twist.twist.angular.z = p.v, p.w
        self.odom_pub.publish(o)

    def _cloud(self):
        p, t = self.plant, self._now()
        pts = ds.cloud((p.x, p.y, p.yaw), self.sc.obstacles, t, self.rays, noise_m=self.noise, rng=self.rng)
        if self.ghost > 0:   # false points around the sensor each scan (as 第200便): 0.5-8 m out, 0-1.2 m above base_link
            r_ = np.sqrt(self.rng.uniform(0.25, 64.0, self.ghost)); a_ = self.rng.uniform(-np.pi, np.pi, self.ghost)
            pts = np.vstack((pts, np.column_stack((r_ * np.cos(a_), r_ * np.sin(a_), self.rng.uniform(0.0, 1.2, self.ghost))).astype(np.float32)))
        self.cloud_pub.publish(self._msg(pts))
        if self.mid:
            self.mid_pub.publish(self._msg(ds.mid360_cloud((p.x, p.y, p.yaw), self.sc.obstacles, t, self.mid, self.rng, noise_m=self.noise)))

    def _msg(self, pts):
        m = PointCloud2(); m.header.stamp = self.get_clock().now().to_msg(); m.header.frame_id = 'base_link'
        m.height, m.width = 1, len(pts); m.fields = FIELDS; m.is_bigendian = False; m.point_step = 12
        m.row_step = 12 * len(pts); m.is_dense = True; m.data = pts.tobytes()
        return m

    def _score(self):
        self.scorer.add(self._now(), self.plant, self.cmd_v, self.cmd_w, self.sc.obstacles)
        p = self.plant
        self.trace.write(f'{self._now():.2f},{p.x:.3f},{p.y:.3f},{p.yaw:.3f},{p.v:.3f},{p.w:.3f},{self.cmd_v:.3f},{self.cmd_w:.3f}\n')

    def _marks(self):
        """The obstacles' places and the costmap's marks left behind, at this moment (the local costmap's frame odom is the world here)."""
        t, p = self._now(), self.plant
        for o in self.sc.obstacles:
            cx, cy = o.center(t)
            self.obstacle_log.write(f'{t:.2f},{o.name},{cx:.3f},{cy:.3f},{int(o.exists(t))}\n')
        for topic, m in self.grids.items():
            i = m.info
            c = db.stale_marks(m.data, i.width, i.height, i.resolution, i.origin.position.x, i.origin.position.y, self.sc.obstacles, t, (p.x, p.y))
            self.marks_log.write(f"{t:.2f},{topic},{c['lethal']},{c['stale']},{c['stale_near']}\n")
            s = self.marks.setdefault(topic, {'max_stale': 0, 'max_stale_near': 0})
            s.update(max_stale=max(s['max_stale'], c['stale']), max_stale_near=max(s['max_stale_near'], c['stale_near']), last_stale=c['stale'])
        self.obstacle_log.flush(); self.marks_log.flush()

    def _write(self):
        self._marks()
        r = dict(self.scorer.report(), commands=self.commands, pose=[round(self.plant.x, 2), round(self.plant.y, 2), round(self.plant.yaw, 2)],
                 plant={'delay_s': self.plant.delay_s, 'tau_v_s': self.plant.tau_v_s, 'tau_w_s': self.plant.tau_w_s}, elapsed_s=round(self._now(), 1), marks=self.marks)
        self.trace.flush()
        tmp = self.report_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False)
        os.replace(tmp, self.report_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario'); ap.add_argument('report')
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--delay', type=float, default=ds.Plant.delay_s)
    ap.add_argument('--tau-v', type=float, default=ds.Plant.tau_v_s); ap.add_argument('--tau-w', type=float, default=ds.Plant.tau_w_s)
    ap.add_argument('--noise', type=float, default=0.02)
    ap.add_argument('--ghost', type=int, default=0, help='false points added to each XT-32 scan (0: none)')
    ap.add_argument('--mid360-height', type=float, default=0.0, help='MID-360 above the ground [m]; 0: no MID-360 (stage 1 of the plan)')
    ap.add_argument('--mid360-pitch', type=float, default=50.0, help='MID-360 pitched down [deg] (DEC-424)')
    a = ap.parse_args()
    rclpy.init()
    n = DriveSim(a)
    try:
        rclpy.spin(n)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        n._write(); n.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__':
    main()

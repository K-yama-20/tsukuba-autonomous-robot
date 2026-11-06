"""TEST ONLY (第179便): the vehicle and the world of the driving simulator, standing in for the sensors, GLIM and ND-07's TF.

Subscribes cmd_vel (IFD-15), publishes map -> odom -> base_link, localization/odometry (IFD-25) and sensors/xt32/points (IFD-21, in
base_link) from drive_sim_core, and rewrites <report> about once a second. The real pointcloud_to_laserscan, costmaps and Nav2 read it.
usage: python3 drive_sim_node.py <scenario> <report.json> [--seed N] [--delay S] [--tau-v S] [--tau-w S] [--tau-w-stop S] [--start-delay S] [--min-turn-w W] [--no-dead-band] [--comp F_MIN,F_T,R_MIN,R_T,T_MIN,T_T] [--noise M] [--speed S]
--speed S: the simulated world runs S times as fast and publishes /clock (run the stack with GOUDA_TEST_NAV2 {"use_sim_time": true}, drive_sim.sh SIM_SPEED).
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
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2, PointField
from tf2_ros import TransformBroadcaster

import drive_sim_core as ds
from collections import deque
from gouda_core.motion_core import MotionCore, MotionSettings, Feedback, Feedforward, FeedforwardAxis
# DEC-445 feedforward (FILE-MIN-SPEED-20261107) and PRM-08/39/40/42/78 as in the generated file; test copy only
FF_MAXV, FF_MAXW, FF_MAXR = 1.25, 0.97, 0.472
FF_TABLE = Feedforward(FeedforwardAxis(0.185, 0.21, 0.09, FF_MAXV), FeedforwardAxis(0.215, 0.24, 0.075, FF_MAXR),
                       FeedforwardAxis(0.184, 0.195, 0.075, FF_MAXW, 0.28, 0.19))

PLANT_HZ, CLOUD_HZ, SCORE_HZ = 50.0, 10.0, 20.0   # the XT-32 is 10 Hz (PRM-60 600 rpm)
FIELDS = [PointField(name=n, offset=i * 4, datatype=PointField.FLOAT32, count=1) for i, n in enumerate('xyz')]


class DriveSim(Node):
    def __init__(self, a):
        super().__init__('drive_sim')
        self.sc = ds.scenario(a.scenario, a.seed)
        self.report_path = a.report
        self.trace = open(os.path.join(os.path.dirname(a.report) or '.', 'trace.csv'), 'w', encoding='utf-8')
        self.trace.write('t,x,y,yaw,v,w,cmd_v,cmd_w\n')
        rx, ry = self.sc.route[0], self.sc.route[1]
        self.plant = ds.Plant(x=rx[0], y=rx[1], yaw=math.atan2(ry[1] - rx[1], ry[0] - rx[0]), delay_s=a.delay, tau_v_s=a.tau_v, tau_w_s=a.tau_w,
                              tau_w_stop_s=a.tau_w_stop, start_delay_s=a.start_delay, min_turn_w=a.min_turn_w, dead_band=not a.no_dead_band,
                              comp=tuple(zip(a.comp[::2], a.comp[1::2])) if a.comp else None, floor=tuple(a.floor) if a.floor else None,
                              dead_scale=a.dead_scale, v_gain=a.v_gain, w_gain=a.w_gain, min_fwd_v=a.min_fwd_v, moving_turn_dead=a.moving_turn_dead, m1107=a.m1107)
        self.scorer = ds.Scorer(self.sc)
        self._ffpi_args = a.ffpi
        self.ffpi = None
        if a.ffpi:
            self.ffpi = MotionCore(MotionSettings(0.7, FF_MAXV, FF_MAXW, 0.5, FF_MAXR), FF_TABLE)
            assert not self.ffpi.set_feedback(Feedback(True, *a.ffpi))
        self.odom_delay = a.odom_delay; self.odq = deque(); self.next_odom = 0.0; self.next_ctrl = 0.0
        self.stick = (0.0, 0.0); self.ffo = None; self.cmd_t = None
        self.fftrace = open(os.path.join(os.path.dirname(a.report) or '.', 'ffpi.csv'), 'w', encoding='utf-8') if a.ffpi else None
        if self.fftrace: self.fftrace.write('t,cmd_v,cmd_w,v,w,meas_v,meas_w,mode,f_ff,f_p,f_i,f_out,t_ff,t_p,t_i,t_out\n')
        self.rays = ds.beams()
        self.noise, self.rng = a.noise, np.random.default_rng(a.seed)
        self.cmd_v, self.cmd_w, self.commands = 0.0, 0.0, 0
        self.t0 = time.monotonic()
        self.last = self.t0
        self.speed, self.steps = a.speed, 0
        self.clock_base = int(time.time())
        self.clock_pub = self.create_publisher(Clock, '/clock', 10) if a.speed else None
        self.tf = TransformBroadcaster(self)
        self.odom_pub = self.create_publisher(Odometry, 'localization/odometry', 10)
        self.cloud_pub = self.create_publisher(PointCloud2, 'sensors/xt32/points', qos_profile_sensor_data)
        self.create_subscription(TwistStamped, 'cmd_vel', self._on_cmd, 10)
        s = a.speed or 1.0
        self.create_timer(1 / PLANT_HZ / s, self._step)
        self.create_timer(1 / CLOUD_HZ / s, self._cloud)
        self.create_timer(1 / SCORE_HZ / s, self._score)
        self.create_timer(1.0, self._write)   # in wall time: the report is for the waiting script

    def _on_cmd(self, m):
        self.cmd_v, self.cmd_w = m.twist.linear.x, m.twist.angular.z
        self.commands += 1
        if self.ffpi: self.ffpi.on_cmd_vel(self.cmd_v, self.cmd_w, self._now())

    def _now(self):
        return self.steps / PLANT_HZ if self.speed else time.monotonic() - self.t0

    def _stamp(self):
        if not self.speed: return self.get_clock().now().to_msg()
        return Time(nanoseconds=int((self.clock_base + self._now()) * 1e9)).to_msg()

    def _step(self):
        if self.speed:   # a fixed step of simulated time, whatever the timer really did
            self.steps += 1
            t, dt, p = self._now(), 1 / PLANT_HZ, self.plant
            c = Clock(); c.clock = self._stamp(); self.clock_pub.publish(c)
        else:
            now = time.monotonic()
            dt, self.last = now - self.last, now
            t, p = now - self.t0, self.plant
        if self.ffpi:
            c = self.ffpi
            self.odq.append((t, p.v, p.w))
            while self.odq and self.odq[0][0] < t - self.odom_delay - 1: self.odq.popleft()
            if t >= self.next_odom:
                old = [x for x in self.odq if x[0] <= t - self.odom_delay]
                if old: c.on_odometry(old[-1][1], old[-1][2], t)
                self.next_odom = t + 0.1
            if t >= self.next_ctrl:
                c.on_motion_hold(False, 'sim', 3, t)
                o = c.output(t); self.stick = (o.forward, o.turn); self.ffo = o
                self.next_ctrl = t + 0.05
                ft, tt = o.forward_terms, o.turn_terms
                g = lambda x, k: '' if x is None else f'{getattr(x, k):.4f}'
                self.fftrace.write(f'{t:.2f},{self.cmd_v:.3f},{self.cmd_w:.3f},{p.v:.3f},{p.w:.3f},{g(ft, "measured")},{g(tt, "measured")},{o.feedback_mode},'
                                   f'{g(ft, "ff")},{g(ft, "p")},{g(ft, "i")},{o.forward:.4f},{g(tt, "ff")},{g(tt, "p")},{g(tt, "i")},{o.turn:.4f}\n')
            f, s = self.stick
            p.step(t, dt, f * (FF_MAXV if f >= 0 else FF_MAXR), s * FF_MAXW)
        else:
            p.step(t, dt, self.cmd_v, self.cmd_w)
        for o in self.sc.obstacles:
            o.update(t, p.x, p.y)
        stamp = self._stamp()
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
        m = PointCloud2(); m.header.stamp = self._stamp(); m.header.frame_id = 'base_link'
        m.height, m.width = 1, len(pts); m.fields = FIELDS; m.is_bigendian = False; m.point_step = 12
        m.row_step = 12 * len(pts); m.is_dense = True; m.data = pts.tobytes()
        self.cloud_pub.publish(m)

    def _score(self):
        self.scorer.add(self._now(), self.plant, self.cmd_v, self.cmd_w, self.sc.obstacles)
        p = self.plant
        self.trace.write(f'{self._now():.2f},{p.x:.3f},{p.y:.3f},{p.yaw:.3f},{p.v:.3f},{p.w:.3f},{self.cmd_v:.3f},{self.cmd_w:.3f}\n')

    def _write(self):
        r = dict(self.scorer.report(), commands=self.commands, pose=[round(self.plant.x, 2), round(self.plant.y, 2), round(self.plant.yaw, 2)],
                 plant={'delay_s': self.plant.delay_s, 'tau_v_s': self.plant.tau_v_s, 'tau_w_s': self.plant.tau_w_s, 'tau_w_stop_s': self.plant.tau_w_stop_s,
                        'start_delay_s': self.plant.start_delay_s, 'min_turn_w': self.plant.min_turn_w, 'dead_band': self.plant.dead_band, 'floor': self.plant.floor, 'dead_scale': self.plant.dead_scale, 'v_gain': self.plant.v_gain, 'w_gain': self.plant.w_gain, 'min_fwd_v': self.plant.min_fwd_v, 'moving_turn_dead': self.plant.moving_turn_dead, 'm1107': self.plant.m1107, 'ffpi': self._ffpi_args, 'odom_delay': self.odom_delay, 'comp': self.plant.comp}, elapsed_s=round(self._now(), 1))
        self.trace.flush()
        if self.fftrace: self.fftrace.flush()
        tmp = self.report_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False)
        os.replace(tmp, self.report_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario'); ap.add_argument('report')
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--delay', type=float, default=ds.Plant.delay_s)
    ap.add_argument('--tau-v', type=float, default=ds.Plant.tau_v_s); ap.add_argument('--tau-w', type=float, default=ds.Plant.tau_w_s)
    ap.add_argument('--tau-w-stop', type=float, default=ds.Plant.tau_w_stop_s); ap.add_argument('--start-delay', type=float, default=ds.Plant.start_delay_s)
    ap.add_argument('--min-turn-w', type=float, default=ds.Plant.min_turn_w); ap.add_argument('--no-dead-band', action='store_true')
    ap.add_argument('--comp', type=lambda s: [float(x) for x in s.split(',')], default=None)
    ap.add_argument('--floor', type=lambda s: [float(x) for x in s.split(',')], default=None)
    ap.add_argument('--dead-scale', type=float, default=ds.Plant.dead_scale); ap.add_argument('--v-gain', type=float, default=ds.Plant.v_gain)
    ap.add_argument('--w-gain', type=float, default=ds.Plant.w_gain); ap.add_argument('--min-fwd-v', type=float, default=ds.Plant.min_fwd_v)
    ap.add_argument('--m1107', action='store_true')
    ap.add_argument('--ffpi', type=lambda s: [float(x) for x in s.split(',')], default=None)
    ap.add_argument('--odom-delay', type=float, default=0.0)
    ap.add_argument('--moving-turn-dead', type=float, default=ds.Plant.moving_turn_dead)
    ap.add_argument('--noise', type=float, default=0.02)
    ap.add_argument('--speed', type=float, default=0.0)
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

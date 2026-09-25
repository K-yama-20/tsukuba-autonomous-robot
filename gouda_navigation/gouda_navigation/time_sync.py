"""Gate GLIM inputs on explicit clock provenance; never infer hardware lock from stamps."""
import json
import math
import os
from collections import deque
from pathlib import Path
import time


def check_runtime_clock(settings, use_sim_time, host_path=None):
    policy = settings['clock_policy']
    if use_sim_time:
        if policy != 'simulation' or os.environ.get('ROS_DOMAIN_ID') != '101':
            raise ValueError('Simulation clock requires clock_policy=simulation and ROS_DOMAIN_ID=101')
        return
    if policy != 'host_mapped':
        raise ValueError('Real USB IMU supports host_mapped only; external common clock is unverified')
    root = Path(os.environ.get('GOUDA_WORKSPACE', Path.home()/'gouda_ws'))/'bags/gouda'
    host = json.loads(Path(host_path or root/'host.json').read_text())
    import yaml
    config = yaml.safe_load(Path(host['hesai_config']).expanduser().read_text())
    driver = config['lidar'][0]['driver']
    if driver.get('source_type') != 1 or type(driver.get('use_timestamp_type')) is not int or driver['use_timestamp_type'] != 0:
        raise ValueError('GLIM requires LiDAR sensor timestamps (use_timestamp_type: 0); receive-time fallback is disabled')


def stamp(msg):
    return msg.sec + msg.nanosec * 1e-9


class ClockGate:
    """Clock/sequence checks independent of ROS. Freshness uses monotonic receipt time."""
    def __init__(self, policy, imu_offset=0., lidar_offset=0.):
        self.policy = policy
        self.offsets = {'imu': imu_offset, 'lidar': lidar_offset}
        self.last = {}
        self.received = {}
        self.errors = {}
        self.statuses = deque(maxlen=1000)
        self.accepted = {'imu': 0, 'lidar': 0}
        self.rejected = {'imu': 0, 'lidar': 0}
        self.previous_clocks = None
        self.reset_required = False

    def observe_clock(self, ros_now, steady_now):
        if self.previous_clocks and self.policy != 'simulation':
            ros_prev, steady_prev = self.previous_clocks
            if abs((ros_now-ros_prev)-(steady_now-steady_prev)) > .1:
                self.reset_required = True
        self.previous_clocks = ros_now, steady_now

    def add_status(self, status, now):
        # A status is evidence for one exact sample, not permission for all later samples.
        self.statuses.append((status, now))

    def fail(self, kind, reason):
        self.errors[kind] = reason
        self.rejected[kind] += 1
        return False

    def accept(self, kind, sensor_stamp, ros_now, steady_now):
        self.observe_clock(ros_now, steady_now)
        if self.reset_required:
            return self.fail(kind, 'PC clock jumped; restart mapping after clock stabilizes')
        adjusted = sensor_stamp + self.offsets[kind]
        if not math.isfinite(adjusted) or adjusted <= 0 or not -.05 <= ros_now-adjusted <= 2.:
            return self.fail(kind, 'Measurement time is outside the common ROS clock window')
        if adjusted <= self.last.get(kind, -math.inf):
            return self.fail(kind, 'Measurement time duplicated or moved backwards')
        if self.policy != 'simulation' and kind == 'imu':
            found = [s for s, t in self.statuses if 0 <= steady_now-t <= .5
                     and isinstance(s.get('measurement_stamp'), (int,float))
                     and abs(s['measurement_stamp']-sensor_stamp) <= 1e-6]
            if not found:
                return self.fail(kind, 'Matching IMU clock evidence is missing')
            evidence = found[-1]
            residual = evidence.get('residual_ms')
            if (evidence.get('state') != 'host_mapped' or not isinstance(residual,(int,float))
                    or not math.isfinite(residual) or not 0 <= residual <= 2.):
                return self.fail(kind, 'IMU clock model is unlocked or residual exceeds 2 ms')
        if kind == 'lidar' and (steady_now-self.received.get('imu', -math.inf) > .5
                or abs(adjusted-self.last.get('imu', -math.inf)) > .5):
            return self.fail(kind, 'No recent IMU in the same clock interval')
        self.last[kind] = adjusted
        self.received[kind] = steady_now
        self.errors.pop(kind, None)
        self.accepted[kind] += 1
        return True

    def snapshot(self, now):
        errors = dict(self.errors)
        for kind in ('imu','lidar'):
            if now-self.received.get(kind, -math.inf) > .5:
                errors[kind] = 'No valid recent measurement'
        return dict(status='blocked' if errors else ('simulation' if self.policy=='simulation' else 'host_mapped'),
                    clock_policy=self.policy, hardware_synchronized=False,
                    hardware_lock='not_observed', errors=list(errors.values()),
                    accepted=dict(self.accepted), rejected=dict(self.rejected),
                    last_measurement=dict(self.last), restart_required=self.reset_required)


def point_time_error(msg, settings):
    """Check all times, preserving message bytes and the original header unchanged."""
    import numpy as np
    from sensor_msgs_py.point_cloud2 import read_points
    field = settings['point_time_field']
    aliases = [f.name for f in msg.fields if f.name in ('t','time','time_stamp','timestamp')]
    f = next((f for f in msg.fields if f.name == field), None)
    expected = {'uint32':6, 'float32':7, 'float64':8}[settings['point_time_datatype']]
    if not aliases or aliases[-1] != field or f is None or f.datatype != expected or f.count != 1:
        return 'Point time field/type differs from configured GLIM input'
    try:
        values = np.asarray(read_points(msg, field_names=[field], skip_nans=False)[field], dtype=np.float64)
        if values.size == 0 or not np.isfinite(values).all():
            return 'Point times are empty or nonfinite'
        if settings['point_time_unit'] == 'nanoseconds': values = values*1e-9
        lo, hi = float(values.min()), float(values.max())
        if hi-lo > .5: return 'Point time span exceeds 0.5 s'
        if settings['point_time_mode'] == 'relative':
            if lo < 0 or hi > .5: return 'Relative point times outside scan interval'
        elif max(abs(lo-stamp(msg.header.stamp)), abs(hi-stamp(msg.header.stamp))) > .5:
            return 'Absolute point times and cloud header use different clocks'
    except (ValueError, TypeError, KeyError, AssertionError) as exc:
        return 'Invalid point time payload: '+str(exc)
    return ''


def main():
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Imu, PointCloud2
    from std_msgs.msg import String
    from .mapping import load_mapping_settings, validate_mapping_settings

    class TimeSyncNode(Node):
        def __init__(self):
            super().__init__('gouda_time_sync')
            path = self.declare_parameter('settings_file','').value
            self.settings = load_mapping_settings(path)
            errors = validate_mapping_settings(self.settings, require_ready=True)
            if errors: raise ValueError('; '.join(errors))
            check_runtime_clock(self.settings, self.get_parameter('use_sim_time').value)
            self.gate = ClockGate(self.settings['clock_policy'], self.settings['imu_clock_offset_sec'], self.settings['lidar_clock_offset_sec'])
            self.pending = deque(maxlen=200)
            self.imu_pub = self.create_publisher(Imu,'/gouda/synced/imu',qos_profile_sensor_data)
            self.cloud_pub = self.create_publisher(PointCloud2,'/gouda/synced/points',qos_profile_sensor_data)
            self.state_pub = self.create_publisher(String,'/gouda/time_sync/state',10)
            self.create_subscription(String,'/imu/clock_status',self.clock_status,1000)
            self.create_subscription(Imu,self.settings['imu_topic'],self.imu,qos_profile_sensor_data)
            self.create_subscription(PointCloud2,self.settings['lidar_topic'],self.cloud,qos_profile_sensor_data)
            self.create_timer(.02,self.flush)
            self.create_timer(.2,self.report)

        def clock_status(self, msg):
            try:
                value=json.loads(msg.data)
                if isinstance(value,dict): self.gate.add_status(value,time.monotonic())
            except (ValueError, TypeError): pass
            self.flush()

        def imu(self, msg):
            self.pending.append((msg,time.monotonic()))
            self.flush()

        def flush(self):
            now=time.monotonic()
            # Independent ROS topics can arrive in either order; wait for paired evidence.
            while self.pending:
                msg, received=self.pending[0]
                matching = any(isinstance(s.get('measurement_stamp'),(int,float)) and
                               abs(s['measurement_stamp']-stamp(msg.header.stamp))<=1e-6
                               for s,t in self.gate.statuses)
                if self.gate.policy!='simulation' and not matching and now-received<.1: break
                self.pending.popleft()
                if msg.header.frame_id != self.settings['imu_frame']:
                    self.gate.fail('imu','IMU frame differs from configured frame');continue
                if self.gate.accept('imu',stamp(msg.header.stamp),self.get_clock().now().nanoseconds/1e9,now):
                    self.imu_pub.publish(msg)

        def cloud(self, msg):
            error=point_time_error(msg,self.settings)
            if msg.header.frame_id!=self.settings['lidar_frame']:error='LiDAR frame differs from configured frame'
            if error:self.gate.fail('lidar',error);return
            if self.gate.accept('lidar',stamp(msg.header.stamp),self.get_clock().now().nanoseconds/1e9,time.monotonic()):
                self.cloud_pub.publish(msg)

        def report(self):
            value=self.gate.snapshot(time.monotonic())
            value['clock_evidence']=self.settings['clock_evidence']
            value['note']='Software clock fit; USB delay and MCU timestamp-to-sample delay are not independently measured'
            self.state_pub.publish(String(data=json.dumps(value,allow_nan=False)))

    rclpy.init()
    node=None
    try:
        node=TimeSyncNode();rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):pass
    finally:
        if node:node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


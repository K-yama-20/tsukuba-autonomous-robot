"""Pure configuration, transform, feedback, and swept-footprint helpers for the autonomy MVP."""
from __future__ import annotations

import json
import math
import os
import re
import numpy as np
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_SETTINGS = {
    'schema_version': SCHEMA_VERSION,
    'hardware_enabled': False,
    'serial_port': None,
    'body_to_lidar': None,
    'imu_gyro_bias_body_rad_s': [0.0, 0.0, 0.0],
    'gyro_bias_note': 'provisional_zero_not_calibrated',
    'footprint': {
        'length_m': 1.105, 'width_m': 0.600, 'height_m': 0.950,
        'origin': 'geometric_center_ground', 'source': 'drawing_based',
    },
    'obstacle_min_height_m': 0.04,
    'max_sensor_age_sec': 0.25,
    'max_sensor_skew_sec': 0.05,
    'controller': {
        'linear_ff_norm_per_mps': 0.25,
        'linear_kp_norm_per_mps': 0.25,
        'linear_ki_norm_per_mps_s': 0.0,
        'yaw_ff_norm_per_rps': 0.25,
        'yaw_kp_norm_per_rps': 0.25,
        'yaw_ki_norm_per_rps_s': 0.0,
        'integral_limit_norm': 0.25,
        'position_tolerance_m': 0.05,
        'heading_tolerance_rad': 0.08,
    },
}


def autonomy_config_path(path=None):
    if path is not None:
        return Path(path).expanduser()
    workspace = Path(os.environ.get('GOUDA_WORKSPACE', Path.home() / 'gouda_ws')).expanduser()
    return workspace / 'bags' / 'gouda' / 'autonomy.json'


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _transform_valid(value):
    if not isinstance(value, dict):
        return False
    t, q = value.get('translation_m'), value.get('quaternion_xyzw')
    if not isinstance(t, list) or len(t) != 3 or not all(_finite(v) for v in t):
        return False
    if not isinstance(q, list) or len(q) != 4 or not all(_finite(v) for v in q):
        return False
    norm = math.sqrt(sum(v*v for v in q))
    return 0.999 <= norm <= 1.001


def validate_autonomy_settings(settings, require_ready=False):
    errors = []
    if not isinstance(settings, dict):
        return ['Autonomy settings must be a JSON object']
    cfg = {**DEFAULT_SETTINGS, **settings}
    if cfg.get('schema_version', SCHEMA_VERSION) != SCHEMA_VERSION:
        errors.append('Unsupported autonomy settings version')
    if type(cfg.get('hardware_enabled')) is not bool:
        errors.append('hardware_enabled must be true or false')
    port = cfg.get('serial_port')
    if port is not None and (not isinstance(port, str) or not (
            re.fullmatch(r'/dev/serial/by-id/[A-Za-z0-9_.:+-]+', port) or
            re.fullmatch(r'/dev/tty(?:ACM|USB)\d+', port))):
        errors.append('serial_port must be an explicit /dev/serial/by-id, /dev/ttyACM<n>, or /dev/ttyUSB<n> path')
    if cfg.get('hardware_enabled') and port is None:
        errors.append('Hardware is enabled but serial_port is not set')
    transform = cfg.get('body_to_lidar')
    if transform is not None and not _transform_valid(transform):
        errors.append('body_to_lidar requires translation_m and a normalized quaternion_xyzw')
    if require_ready and transform is None:
        errors.append('Body-to-LiDAR transform is UNKNOWN; measure and configure it')
    bias = cfg.get('imu_gyro_bias_body_rad_s')
    if not isinstance(bias, list) or len(bias) != 3 or not all(_finite(v) for v in bias):
        errors.append('imu_gyro_bias_body_rad_s must contain three finite values')
    fp = cfg.get('footprint')
    if not isinstance(fp, dict) or not all(_finite(fp.get(k)) and fp[k] > 0 for k in ('length_m', 'width_m', 'height_m')):
        errors.append('footprint length_m, width_m, and height_m must be positive finite values')
    elif fp.get('origin') != 'geometric_center_ground':
        errors.append('footprint origin must be geometric_center_ground')
    for key in ('obstacle_min_height_m', 'max_sensor_age_sec', 'max_sensor_skew_sec'):
        if not _finite(cfg.get(key)) or cfg[key] < 0:
            errors.append(f'{key} must be a nonnegative finite number')
    gains = cfg.get('controller')
    gain_names = ('linear_ff_norm_per_mps', 'linear_kp_norm_per_mps',
                  'linear_ki_norm_per_mps_s', 'yaw_ff_norm_per_rps',
                  'yaw_kp_norm_per_rps', 'yaw_ki_norm_per_rps_s',
                  'integral_limit_norm', 'position_tolerance_m', 'heading_tolerance_rad')
    if not isinstance(gains, dict):
        errors.append('controller must be an object')
    else:
        for name in gain_names:
            if not _finite(gains.get(name)) or gains[name] < 0:
                errors.append(f'controller.{name} must be a nonnegative finite number')
    if require_ready and cfg.get('hardware_enabled') is not True:
        errors.append('Hardware control is disabled; opt in explicitly in autonomy settings')
    return errors


def validate_autonomy_settings_or_raise(settings, require_ready=False):
    errors = validate_autonomy_settings(settings, require_ready)
    if errors:
        raise ValueError('; '.join(errors))
    result = {**DEFAULT_SETTINGS, **settings}
    result['footprint'] = {**DEFAULT_SETTINGS['footprint'], **settings.get('footprint', {})}
    result['controller'] = {**DEFAULT_SETTINGS['controller'], **settings.get('controller', {})}
    return result


def load_autonomy_settings(path=None):
    target = autonomy_config_path(path)
    if not target.exists():
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        raw = json.loads(target.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Cannot read autonomy settings: {exc}') from exc
    return validate_autonomy_settings_or_raise(raw)


def save_autonomy_settings(settings, path=None):
    value = validate_autonomy_settings_or_raise(settings)
    target = autonomy_config_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.chmod(temporary, 0o600)
    temporary.replace(target)
    return target


def normalize_quaternion(q):
    if not isinstance(q, (list, tuple)) or len(q) != 4 or not all(_finite(v) for v in q):
        raise ValueError('quaternion must contain four finite xyzw values')
    norm = math.sqrt(sum(v*v for v in q))
    if norm < 1e-9:
        raise ValueError('quaternion cannot have zero norm')
    return tuple(v / norm for v in q)


def quaternion_multiply(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz)


def quaternion_inverse(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def rotate(q, v):
    qv = (v[0], v[1], v[2], 0.0)
    r = quaternion_multiply(quaternion_multiply(q, qv), quaternion_inverse(q))
    return (r[0], r[1], r[2])


def compose_transforms(t_ab, q_ab, t_bc, q_bc):
    """Compose T_A_B * T_B_C using origins expressed in their parent frames."""
    rotated = rotate(q_ab, t_bc)
    return (tuple(t_ab[i] + rotated[i] for i in range(3)),
            normalize_quaternion(quaternion_multiply(q_ab, q_bc)))


def body_pose_from_lidar(position_ol, orientation_ol, t_bl, q_bl):
    """Convert GLIM T_O_L to body pose T_O_B; T_B_L maps LiDAR coordinates to body."""
    q_ob = normalize_quaternion(quaternion_multiply(orientation_ol, quaternion_inverse(q_bl)))
    offset_o = rotate(q_ob, t_bl)
    p_ob = tuple(position_ol[i] - offset_o[i] for i in range(3))
    return p_ob, q_ob


def estimate_body_twist(velocity_oi, angular_velocity_i, q_ob, t_bi, q_bi, bias_b=(0.0, 0.0, 0.0)):
    """Convert IMU-origin world velocity and IMU gyro to body-origin body-frame twist."""
    rotated_gyro_b = rotate(q_bi, angular_velocity_i)
    omega_b = tuple(rotated_gyro_b[i] - bias_b[i] for i in range(3))
    v_b_at_i = rotate(quaternion_inverse(q_ob), velocity_oi)
    lever = (omega_b[1]*t_bi[2] - omega_b[2]*t_bi[1],
             omega_b[2]*t_bi[0] - omega_b[0]*t_bi[2],
             omega_b[0]*t_bi[1] - omega_b[1]*t_bi[0])
    return tuple(v_b_at_i[i] - lever[i] for i in range(3)), omega_b


def obstacle_in_swept_envelope(points_lidar, t_bl, q_bl, footprint, obstacle_min_height_m,
                               motion_kind, forward_distance=0.0):
    """Conservative circumscribed-circle sweep includes combined translation/yaw.

    No automatic chair self-mask: an unclassified return blocks autonomous motion."""
    length, width, height = (footprint[k] for k in ('length_m', 'width_m', 'height_m'))
    radius = math.hypot(length/2, width/2)
    if motion_kind not in ('turn', 'forward', 'reverse'):
        raise ValueError('motion_kind must be turn, forward, or reverse')
    points = np.asarray(points_lidar, dtype=float).reshape(-1, 3)
    if not len(points):
        return False
    rotation = np.asarray([rotate(q_bl, axis) for axis in ((1,0,0),(0,1,0),(0,0,1))]).T
    body = points @ rotation.T + np.asarray(t_bl)
    body = body[(body[:,2] >= obstacle_min_height_m) & (body[:,2] <= height)]
    if not len(body):
        return False
    x, y = body[:,0], body[:,1]
    distance = max(0.0, forward_distance)
    nearest_x = np.clip(x, 0., distance) if motion_kind == 'forward' else (np.clip(x, -distance, 0.) if motion_kind == 'reverse' else 0.)
    return bool(np.any((x-nearest_x)**2 + y*y <= radius*radius))


class AxisPI:
    def __init__(self, feedforward, kp, ki, integral_limit):
        self.feedforward, self.kp, self.ki = feedforward, kp, ki
        self.integral_limit = integral_limit
        self.integral = 0.0

    def reset(self):
        self.integral = 0.0

    def update(self, reference, measured, dt):
        error = reference - measured
        self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral + error*max(0.0, dt)))
        return max(-1.0, min(1.0, self.feedforward*reference + self.kp*error + self.ki*self.integral))

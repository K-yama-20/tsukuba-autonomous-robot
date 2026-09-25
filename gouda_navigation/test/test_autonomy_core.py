import json
import math

import pytest

from gouda_navigation.autonomy_core import (
    DEFAULT_SETTINGS, AxisPI, body_pose_from_lidar, compose_transforms,
    estimate_body_twist, load_autonomy_settings, normalize_quaternion,
    obstacle_in_swept_envelope, save_autonomy_settings, validate_autonomy_settings,
)


def test_autonomy_config_defaults_fail_closed_and_round_trip(tmp_path):
    path = tmp_path/'bags/gouda/autonomy.json'
    defaults = load_autonomy_settings(path)
    assert defaults['hardware_enabled'] is False
    assert defaults['serial_port'] is None
    assert defaults['body_to_lidar'] is None
    assert validate_autonomy_settings(defaults, require_ready=True)
    defaults['hardware_enabled'] = True
    defaults['serial_port'] = '/dev/serial/by-id/usb-test'
    defaults['body_to_lidar'] = {'translation_m': [0.4, 0.0, 0.7],
                                 'quaternion_xyzw': [0.0, 0.0, 0.0, 1.0]}
    save_autonomy_settings(defaults, path)
    loaded = load_autonomy_settings(path)
    assert loaded['body_to_lidar'] == defaults['body_to_lidar']
    assert json.loads(path.read_text())['hardware_enabled'] is True


@pytest.mark.parametrize('port', ['/dev/ttyACM0', '/dev/ttyUSB12', '/dev/serial/by-id/usb-x'])
def test_explicit_supported_serial_paths(port):
    cfg = {**DEFAULT_SETTINGS, 'hardware_enabled': True, 'serial_port': port}
    assert validate_autonomy_settings(cfg) == []


@pytest.mark.parametrize('port', ['', 'ttyUSB0', '/tmp/ttyUSB0', '/dev/ttyACMabc', '/dev/serial/by-id/../bad'])
def test_rejects_ambiguous_or_injectable_serial_paths(port):
    cfg = {**DEFAULT_SETTINGS, 'hardware_enabled': True, 'serial_port': port}
    assert any('serial_port' in error for error in validate_autonomy_settings(cfg))


def test_transform_composition_uses_nonidentity_rotations_and_lidar_offset():
    sqrt2 = math.sqrt(0.5)
    q_bl = [0.0, 0.0, sqrt2, sqrt2]  # LiDAR forward points body left.
    t_bl, q_bl_out = compose_transforms((1.0, 0.0, 0.5), q_bl,
                                        (0.0, 0.2, 0.0), [0.0, 0.0, 0.0, 1.0])
    assert t_bl == pytest.approx((0.8, 0.0, 0.5))
    assert q_bl_out == pytest.approx(q_bl)
    p_ob, q_ob = body_pose_from_lidar((3.0, 4.0, 0.0), [0, 0, 0, 1],
                                       (1.0, 0.0, 0.0), q_bl)
    assert p_ob == pytest.approx((3.0, 5.0, 0.0))
    assert q_ob == pytest.approx((0.0, 0.0, -sqrt2, sqrt2))


def test_body_twist_rotates_gyro_once_and_removes_imu_lever_arm_velocity():
    sqrt2 = math.sqrt(0.5)
    q_bi = (0.0, 0.0, sqrt2, sqrt2)  # IMU X maps to body Y.
    velocity_b, omega_b = estimate_body_twist(
        velocity_oi=(0.9, 0.0, 0.0),
        angular_velocity_i=(1.0, 0.0, 0.0),
        q_ob=(0.0, 0.0, 0.0, 1.0),
        t_bi=(0.0, 0.0, 1.0),
        q_bi=q_bi,
        bias_b=(0.0, 0.1, 0.0),
    )
    assert omega_b == pytest.approx((0.0, 0.9, 0.0))
    assert velocity_b == pytest.approx((0.0, 0.0, 0.0))


def test_turn_sweep_uses_3d_height_and_body_bounded_radius():
    footprint = {'length_m': 2.0, 'width_m': 1.0, 'height_m': 0.95}
    identity = [0.0, 0.0, 0.0, 1.0]
    t_bl = (0.0, 0.0, 0.0)
    assert obstacle_in_swept_envelope([(0.0, 0.0, 0.2)], t_bl, identity,
                                      footprint, 0.04, 'turn')
    assert not obstacle_in_swept_envelope([(0.0, 0.0, 0.02)], t_bl, identity,
                                          footprint, 0.04, 'turn')
    assert not obstacle_in_swept_envelope([(2.0, 0.0, 0.3)], t_bl, identity,
                                          footprint, 0.04, 'turn')
    assert obstacle_in_swept_envelope([(1.1, 0.0, 0.3)], t_bl, identity,
                                      footprint, 0.04, 'turn')


def test_feedback_is_provisional_bounded_and_resettable():
    pi = AxisPI(.2, .5, .1, .25)
    out = pi.update(.4, .1, .1)
    assert 0 < out < 1
    assert pi.integral > 0
    pi.reset()
    assert pi.integral == 0
    assert pi.update(-100, 0, 1) == -1

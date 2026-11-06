"""MID-360 (ND-20 livox_ros_driver2, ND-21 mid360_scan) as a costmap layer of its own beside the XT-32's (REV-242, DEC-454). No ROS dependency.

The MID-360 path (driver, band scan, the costmap layers) is used only when ALL of these hold; otherwise nothing of it is started
and the reason is logged (the XT-32 path stays exactly as before):
- PRM-142 (mid360_enabled, or the value saved in the monitor's /config 「Nav2」 tab) is true;
- the vehicle PC's own file <data_root>/config/mid360.json (IFD-61, written by the human, never in the repository: the public
  repository holds no addresses) gives the PC's and the MID-360's address;
- the monitor's /config (IFD-26, <data_root>/config/sensor_config.json, 「センサ取付・座標方向」) gives the whole mounting of
  mid360_link in base_link: the seven mid360_* fields (REV-266, DEC-485). Unlike the XT-32's fields they are never replaced by the
  neutral element (DEC-457 / DEC-425: not measured yet, so no value is assumed here);
- livox_ros_driver2 is installed (setup.sh builds it in <workspace>_livox; gouda.sh loads it) with its MID360_config.json template.
The driver's config is the UPSTREAM template (share/livox_ros_driver2/config/MID360_config.json, commit 2144554) with only the
addresses replaced and the extrinsic kept at zero (the TF has one owner, ND-13). Every other template value (ports, data type,
pattern mode) stays.
mid360.json (since REV-266 only the addresses are read):
  {"host_ip": "<PC address on the MID-360's network>", "lidar_ip": "<MID-360 address>"}
/config (the monitor saves them; the same meaning as the XT-32's fields, sensor_extrinsics: R = R_rpy * A, REP-103):
  mid360_mount_x_m, mid360_mount_y_m, mid360_mount_z_m, mid360_mount_roll_rad, mid360_mount_pitch_rad, mid360_mount_yaw_rad,
  mid360_axis_mapping ("+x forward, +y left, +z up" style)
Migration from REV-242 (mid360.json held the mounting too): mounting keys left in mid360.json are not read; the launch log and
the static TF record say so, and whether they give the same transform as /config (read_local / mount_from_file read that format).
"""
from __future__ import annotations

import ipaddress
import json
import math
import os
from typing import Optional

from gouda_core import sensor_extrinsics as se

# Interface names (not settings)
FRAME = 'mid360_link'                          # IFD-20 (ND-13)
POINTS_TOPIC = '/sensors/mid360/points'        # IFD-59
SCAN_TOPIC = '/sensors/mid360/scan'            # IFD-60
SCAN_NODE = 'mid360_scan'                      # ND-21 (pointcloud_to_laserscan, the same package as xt32_scan)
LAYER = 'mid360_layer'                         # the MID-360's own ObstacleLayer in both costmaps (plan B1, simulator S2)
DRIVER_PACKAGE, DRIVER_EXECUTABLE, DRIVER_NODE = 'livox_ros_driver2', 'livox_ros_driver2_node', 'livox_ros_driver2'   # ND-20
DRIVER_TOPIC = 'livox/lidar'                   # the driver's own topic with multi_topic 0 (upstream src/lddc.cpp), remapped to IFD-59
XFER_POINTCLOUD2 = 0                           # upstream launch: "0-Pointcloud2(PointXYZRTL)" (a format constant, not a vehicle value)
# name of the MID-360's DiagnosticStatus in /diagnostics (DEC-479 / DEC-494): the patched driver that setup.sh builds publishes the
# device's state push under this name (hardware_id '', message 'info push'), and gouda_recorder (ND-04) writes every such status
# to the log. Fixed by the driver patch, so it is not derived from SENSOR (the prefix of the /config keys)
DIAGNOSTIC_NAME = 'mid360'
LOCAL_FILE = 'mid360.json'                     # IFD-61, in <data_root>/config
CONFIG_FILE = 'sensor_config.json'             # IFD-26, the monitor's /config in <data_root>/config (the mounting, REV-266)
ADDRESS_KEYS = ('host_ip', 'lidar_ip')
SENSOR = 'mid360'
MOUNT_KEYS = tuple(f'{SENSOR}_mount_{k}' for k in ('x_m', 'y_m', 'z_m', 'roll_rad', 'pitch_rad', 'yaw_rad')) + (f'{SENSOR}_axis_mapping',)
TEMPLATE_NAME = 'MID360_config.json'
HOST_IP_KEYS = ('cmd_data_ip', 'push_msg_ip', 'point_data_ip', 'imu_data_ip')   # host_net_info of the template (log_data_ip stays '')


def read_local(config_dir: Optional[str]) -> dict:
    """{'path', 'values', 'problems'}: the vehicle PC's mid360.json read in the REV-242 format (addresses and mounting). problems is
    empty only when every key is present and valid. Since REV-266 the path uses read_addresses; this reads the old format only to
    tell the human about mounting keys left in the file (legacy_mount_note)."""
    path = os.path.join(config_dir, LOCAL_FILE) if config_dir else None
    if not path or not os.path.isfile(path):
        return {'path': path, 'values': {}, 'problems': [f'{path or LOCAL_FILE} does not exist (the vehicle PC has no MID-360 settings)']}
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError('not an object')
    except (OSError, ValueError) as e:
        return {'path': path, 'values': {}, 'problems': [f'{path} could not be read ({type(e).__name__})']}
    problems = []
    for k in ADDRESS_KEYS:
        v = doc.get(k)
        try:
            if not isinstance(v, str) or ipaddress.ip_address(v).version != 4:
                raise ValueError
        except ValueError:
            problems.append(f'{k} is missing or not an IPv4 address')
    for k in MOUNT_KEYS[:-1]:
        v = doc.get(k)
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)):
            problems.append(f'{k} is missing or not a number')
    axes = doc.get(MOUNT_KEYS[-1])
    if not isinstance(axes, str):
        problems.append(f'{MOUNT_KEYS[-1]} is missing')
    else:
        why = se.validate_axis_mapping(axes)
        if why is None and se.determinant(se.parse_axis_mapping(axes)) < 0:
            why = 'left-handed (not a rotation)'
        if why:
            problems.append(f'{MOUNT_KEYS[-1]}: {why}')
    return {'path': path, 'values': {k: doc.get(k) for k in ADDRESS_KEYS + MOUNT_KEYS}, 'problems': problems}


def mount_transform(values: dict) -> Optional[dict]:
    """base_link -> mid360_link from complete mounting values, or None when any value is missing or invalid (never the neutral
    element: unlike the XT-32's /config fields, a MID-360 with an assumed pose would mark the ground or miss obstacles)."""
    r, t, defaulted, problems = se.sensor_pose(values, SENSOR)
    if defaulted or problems:
        return None
    return {'parent': se.BASE_LINK, 'child': FRAME, 'translation': t, 'rotation': se.quaternion(r)}


def mount_from_file(config_dir: Optional[str]) -> tuple:
    """(transform or None, reason): the transform only when the mounting part of mid360.json (REV-242 format) is complete. Since
    REV-266 it is used only to compare mounting keys left in the file with /config (legacy_mount_note); ND-13 uses /config."""
    local = read_local(config_dir)
    mount_problems = [p for p in local['problems'] if not p.startswith(ADDRESS_KEYS)]
    if mount_problems:
        return None, '; '.join(mount_problems)
    return mount_transform(local['values']), ''


def mount_from_config(values: dict) -> tuple:
    """(transform or None, reason) of base_link -> mid360_link from the /config values (IFD-26, REV-266). The transform only when
    all seven mid360_* fields are set and valid; otherwise None and the fields that are not (never the neutral element, DEC-457)."""
    _r, _t, defaulted, problems = se.sensor_pose(values, SENSOR)
    if defaulted or problems:
        bad_axes = {MOUNT_KEYS[-1]} if problems else set()   # sensor_pose lists a bad axis mapping both in defaulted and in problems
        unset = [k for k in defaulted if k not in bad_axes]
        bad = [p.replace('; base_link axes used instead', '') for p in problems]   # nothing is used instead for the MID-360
        parts = ([f"not set in /config (UNKNOWN or not a finite number): {', '.join(unset)}"] if unset else []) + bad
        return None, '; '.join(parts)
    return mount_transform(values), ''


def read_config_mount(config_dir: Optional[str]) -> tuple:
    """(transform or None, reason) from <config_dir>/sensor_config.json, read as the monitor and ND-13 read it (SensorConfig)."""
    if not config_dir:
        return None, 'no config directory is given (the /config of the monitor cannot be read)'
    from gouda_core.monitor_core import SensorConfig   # here, not at the top: monitor_core -> nav2_config -> this module
    path = os.path.join(config_dir, CONFIG_FILE)
    mount, why = mount_from_config(dict(SensorConfig(path).values))
    if mount is None and not os.path.isfile(path):
        why = f'{path} does not exist; {why}'
    return mount, why


def read_addresses(config_dir: Optional[str]) -> dict:
    """{'path', 'values' (host_ip, lidar_ip), 'problems', 'legacy_mount_keys'}: the vehicle PC's mid360.json (IFD-61) since REV-266.
    problems is empty when the file has both addresses. Mounting keys still in the file (REV-242 format) are only listed."""
    local = read_local(config_dir)
    return {'path': local['path'], 'values': {k: local['values'].get(k) for k in ADDRESS_KEYS},
            'problems': [p for p in local['problems'] if not p.startswith(MOUNT_KEYS)],
            'legacy_mount_keys': [k for k in MOUNT_KEYS if local['values'].get(k) is not None]}


def _same_transform(a: dict, b: dict, tol: float = 1e-9) -> bool:
    close = lambda x, y: all(abs(float(p) - float(q)) <= tol for p, q in zip(x, y))
    return close(a['translation'], b['translation']) and (close(a['rotation'], b['rotation'])
                                                          or close(a['rotation'], [-float(c) for c in b['rotation']]))


def legacy_mount_note(config_dir: Optional[str], mount: Optional[dict]) -> str:
    """'' or a note for the human when mid360.json still holds mounting keys (REV-242 format). They are not read since REV-266
    (DEC-485): /config is the one place of the mounting. The note says whether they agree with /config. Nothing is copied."""
    keys = read_addresses(config_dir)['legacy_mount_keys']
    if not keys:
        return ''
    note = f"{LOCAL_FILE} still has the mounting key(s) {', '.join(keys)}: not read since REV-266 (the mounting is in /config)"
    if mount is None:
        return note + '; enter the mounting in the monitor /config (センサ取付・座標方向)'
    old, _ = mount_from_file(config_dir)
    if old is None:
        return note
    return note + ('; they give the same transform as /config' if _same_transform(old, mount)
                   else '; they give a DIFFERENT transform from /config, which is the one used')


def static_tf(values: dict, config_dir: Optional[str]) -> tuple:
    """ND-13: (base_link -> mid360_link or None, the note for the static_tf_published record) from the /config values."""
    mount, why = mount_from_config(values)
    note = 'mid360_link published from /config' if mount is not None else f'mid360_link not published: {why}'
    legacy = legacy_mount_note(config_dir, mount)
    return mount, note + (f' ({legacy})' if legacy else '')


def launch_inputs(config_dir: Optional[str]) -> tuple:
    """(reason, addresses, note) for gouda_nav2.launch.py at gouda.sh start: reason is '' when mid360.json has both addresses and
    /config the whole mounting; addresses is read_addresses(); note is legacy_mount_note() ('' when there is nothing to say)."""
    addresses = read_addresses(config_dir)
    mount, why = read_config_mount(config_dir)
    problems = addresses['problems'] + ([] if mount is not None else [f'the MID-360 mounting is not complete ({why})'])
    return '; '.join(problems), addresses, legacy_mount_note(config_dir, mount)


def driver_config(template: dict, host_ip: str, lidar_ip: str) -> dict:
    """The upstream MID360_config.json with the addresses replaced; the extrinsic stays zero (TF owner ND-13). Raises ValueError
    when the template does not have the expected shape (a changed upstream version)."""
    cfg = json.loads(json.dumps(template))   # deep copy
    try:
        host = cfg['MID360']['host_net_info']; lidars = cfg['lidar_configs']
    except (KeyError, TypeError):
        raise ValueError('the upstream MID360_config.json does not have MID360.host_net_info / lidar_configs')
    if not isinstance(lidars, list) or len(lidars) != 1 or any(k not in host for k in HOST_IP_KEYS):
        raise ValueError('the upstream MID360_config.json does not have one lidar_configs entry and the host_net_info addresses')
    for k in HOST_IP_KEYS:
        host[k] = host_ip
    lidars[0]['ip'] = lidar_ip
    ext = lidars[0].get('extrinsic_parameter', {})
    if any(v != 0 for v in ext.values()):
        raise ValueError('the upstream MID360_config.json has a non-zero extrinsic_parameter')
    return cfg


def write_driver_config(template_path: str, local: dict, out_path: str) -> None:
    with open(template_path, encoding='utf-8') as f:
        template = json.load(f)
    cfg = driver_config(template, local['values']['host_ip'], local['values']['lidar_ip'])
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def driver_parameters(config_path: str) -> dict:
    """ROS parameters of livox_ros_driver2_node: PointCloud2 in mid360_link from the written config; the others stay the driver's."""
    return {'xfer_format': XFER_POINTCLOUD2, 'frame_id': FRAME, 'user_config_path': config_path}


def find_template(share_dir: Optional[str]) -> Optional[str]:
    if not share_dir:
        return None
    path = os.path.join(share_dir, 'config', TEMPLATE_NAME)
    return path if os.path.isfile(path) else None

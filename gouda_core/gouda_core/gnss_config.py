"""GNSS driver settings for ND-19 (septentrio_gnss_driver, mosaic-go G5 P6, dual antenna). No ROS dependency.

Design: design/model.yaml ND-19, IFD-47..49, PRM-65 (REV-061, DEC-123).
- The driver reads one ROS parameter file. It is built from the UPSTREAM template (installed
  share/septentrio_gnss_driver/config/gnss.yaml) with only the Gouda keys replaced: the connection (`device`, PRM-65), the
  frames (main antenna gnss_link, aux antenna gnss_aux1_link, vehicle base_link; positions come from TF published by ND-13
  from /config), receiver_type gnss with multi_antenna, PC time, and no TF from the driver (one TF owner, RQ-I004).
  Every other template value is kept as it is (no silent changes).
- Network RTK: the corrections settings (caster, account) are private and are not in the public repository. When the human
  has put <data_root>/config/gnss_rtk.yaml (a mapping with `rtk_settings`), its rtk_settings replace the template's;
  otherwise the template's (empty) rtk_settings stay and the receiver runs without corrections (DEC-125).
- The connection is either "tcp://<ip>:<port>" (the receiver's USB ethernet) or "serial:/dev/serial/by-id/<name>". Any other serial path
  (e.g. /dev/ttyACM0, whose number swaps with the IMU's on re-plugging) is refused and the driver is not started (DEC-141).
- configure_rx (PRM-74) must be decided (DEC-140); while it is not, the driver is not started (DEC-141).
  The supervisor watches the device by that name (serial: the by-id name; tcp: the network interface whose IPv4 prefix
  contains the receiver address).
A missing value is reported, never filled in (RQ-I076, CLAUDE.md 1.5).
"""
from __future__ import annotations

import copy
import ipaddress
import json
import os
from typing import Optional

import yaml

from gouda_core.device_watch import BY_ID_DIR, by_id_problem

# Interface names from the design (IFD-20, IFD-47..49). These are names, not settings.
NAMESPACE = '/sensors/gnss'
MAIN_FRAME = 'gnss_link'
AUX1_FRAME = 'gnss_aux1_link'
VEHICLE_FRAME = 'base_link'
NAVSATFIX_TOPIC = NAMESPACE + '/navsatfix'
PVTGEODETIC_TOPIC = NAMESPACE + '/pvtgeodetic'
ATTEULER_TOPIC = NAMESPACE + '/atteuler'
ATTCOVEULER_TOPIC = NAMESPACE + '/attcoveuler'   # IFD-50 (heading covariance; REV-063)
KEYS = ('device', 'configure_rx')     # PRM-65, PRM-74 (configure_rx undecided (DEC-140) -> the driver is not started: DEC-141)
RTK_FILE = 'gnss_rtk.yaml'            # under <data_root>/config, put there by the human (never in the repository)


def parse_device(device: Optional[str]) -> Optional[dict]:
    """{'kind': 'tcp', 'host': ip, 'port': n} or {'kind': 'serial', 'path': p}; None when the text is not one of the two."""
    if not device:
        return None
    if device.startswith('tcp://'):
        host, _, port = device[len('tcp://'):].rpartition(':')
        try:
            ipaddress.IPv4Address(host)
            return {'kind': 'tcp', 'host': host, 'port': int(port)}
        except ValueError:
            return None
    if device.startswith('serial:'):
        path = device[len('serial:'):]
        return {'kind': 'serial', 'path': path} if by_id_problem(path) is None else None   # by-id names only (DEC-141)
    return None


def read_rtk(config_dir: Optional[str]) -> tuple:
    """(rtk_settings or None, note). The file is private to the vehicle PC; its content is not recorded, only whether it was used."""
    if not config_dir:
        return None, 'no config directory'
    path = os.path.join(config_dir, RTK_FILE)
    if not os.path.isfile(path):
        return None, f'{path} not found: no RTK corrections'
    try:
        with open(path, encoding='utf-8') as f:
            doc = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        return None, f'{path} could not be read ({type(e).__name__}): no RTK corrections'
    rtk = doc.get('rtk_settings') if isinstance(doc, dict) else None
    if not isinstance(rtk, dict):
        return None, f'{path} has no rtk_settings mapping: no RTK corrections'
    return rtk, f'rtk_settings from {path}'


def driver_parameters(template: dict, params: dict, rtk: Optional[dict] = None) -> tuple:
    """Return (parameter dict, missing keys, problems). The template is the upstream gnss.yaml parsed; it is not modified."""
    missing = [k for k in KEYS if params.get(k) is None]
    problems = []
    if params.get('device') is not None and parse_device(params['device']) is None:
        problems.append(f"device {params['device']!r} is neither tcp://<ip>:<port> nor serial:{BY_ID_DIR}<name> (ttyACM numbers are not accepted: DEC-141)")
    p = copy.deepcopy(template)
    if params.get('device') is not None:
        p['device'] = params['device']
    if params.get('configure_rx') is not None:
        p['configure_rx'] = bool(params['configure_rx'])   # PRM-74 (DEC-140)
    p.update({'frame_id': MAIN_FRAME, 'aux1_frame_id': AUX1_FRAME, 'vehicle_frame_id': VEHICLE_FRAME, 'poi_frame_id': VEHICLE_FRAME,
              'get_spatial_config_from_tf': True, 'receiver_type': 'gnss', 'multi_antenna': True, 'use_gnss_time': False})
    pub = dict(p.get('publish') or {})
    pub.update({'tf': False, 'navsatfix': True, 'pvtgeodetic': True, 'atteuler': True, 'attcoveuler': True})   # one TF owner (ND-13); IFD-47..50
    p['publish'] = pub
    if rtk is not None:
        p['rtk_settings'] = copy.deepcopy(rtk)
    return p, missing, problems


def write_parameter_file(template_path: str, params: dict, out_path: str, config_dir: Optional[str]) -> dict:
    """Write the driver's ROS parameter file. Returns {'missing': [...], 'problems': [...], 'rtk': note}; the file is written
    only when nothing is missing and there is no problem."""
    with open(template_path, encoding='utf-8') as f:
        template = yaml.safe_load(f) or {}
    rtk, note = read_rtk(config_dir)
    p, missing, problems = driver_parameters(template, params, rtk)
    result = {'missing': missing, 'problems': problems, 'rtk': note}
    if missing or problems:
        return result
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('# GENERATED by gouda_core.gnss_config from the upstream septentrio_gnss_driver config/gnss.yaml and design/generated/params/septentrio_gnss_driver.yaml\n')
        yaml.safe_dump({'/**': {'ros__parameters': p}}, f, sort_keys=False, allow_unicode=True)
    os.chmod(out_path, 0o600)   # may hold the private RTK account
    return result


def find_template(share_dir: Optional[str]) -> Optional[str]:
    if not share_dir: return None
    path = os.path.join(share_dir, 'config', 'gnss.yaml')
    return path if os.path.isfile(path) else None


def peer_interface(ip: str, ip_addr_json: str) -> Optional[str]:
    """'enx… #7' for the interface whose IPv4 prefix contains ip (from `ip -j -4 addr`), or None (receiver not connected)."""
    try:
        links = json.loads(ip_addr_json or '[]')
        target = ipaddress.IPv4Address(ip)
    except ValueError:
        return None
    for link in links:
        for a in link.get('addr_info', []):
            try:
                net = ipaddress.IPv4Network(f"{a.get('local')}/{a.get('prefixlen')}", strict=False)
            except ValueError:
                continue
            if target in net and link.get('ifname') != 'lo':
                return f"{link.get('ifname')} #{link.get('ifindex')}"
    return None

"""GNSS driver settings for ND-19 (septentrio_gnss_driver, mosaic-go G5 P6, dual antenna). No ROS dependency.

Design: design/model.yaml ND-19, IFD-47..49, PRM-65, PRM-74..76 (REV-061, DEC-123, DEC-154).
- The driver reads one ROS parameter file. It is built from the UPSTREAM template (installed
  share/septentrio_gnss_driver/config/gnss.yaml) with only the Gouda keys replaced: the connection (`device`, PRM-65), the
  frames (main antenna gnss_link, aux antenna gnss_aux1_link, vehicle base_link; positions come from TF published by ND-13
  from /config), receiver_type gnss with multi_antenna, PC time, and no TF from the driver (one TF owner, RQ-I004).
  Every other template value is kept as it is (no silent changes).
- Network RTK (DEC-139 option B1, DEC-154): the NTRIP connection data (caster, port, mountpoint, user, password) is secret
  (DEC-139: never in the repository, logs, rosbag or records). It is only in <data_root>/config/gnss_rtk.yaml under `ntrip:`,
  written by the human with owner-only permissions, and only the NTRIP relay reads it (DEC-151 step 3). The driver never gets
  it: when the ntrip section is valid, the only change to the template's rtk_settings is serial_1.port = PRM-75 (the receiver
  port that takes the RTCM corrections and outputs GGA); rtk_standard, send_gga, baud_rate and keep_open stay as in the
  template. Without a valid file the template's (empty) rtk_settings stay and the receiver runs without corrections; the
  driver is started either way. Notes about the file name its keys only, never its values.
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
NTRIP_KEYS = ('caster', 'port', 'mountpoint', 'user', 'password')   # the ntrip section of RTK_FILE (DEC-154)


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


def _ntrip_problems(ntrip) -> list:
    """Key names that are missing or malformed (never the values)."""
    if not isinstance(ntrip, dict):
        return ['ntrip is not a mapping']
    out = [f'{k} missing' for k in NTRIP_KEYS if k not in ntrip]
    port = ntrip.get('port')
    if 'port' in ntrip and (isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536):
        out.append('port is not an integer port number')
    for k in ('caster', 'mountpoint', 'user', 'password'):
        v = ntrip.get(k)
        if k in ntrip and not isinstance(v, str):
            out.append(f'{k} is not a string (YAML read it as {type(v).__name__}: write the value in quotes)')
        elif k in ntrip and (not v or any(c.isspace() for c in v)):
            out.append(f'{k} is empty or contains spaces')
    if isinstance(ntrip.get('mountpoint'), str) and '/' in ntrip['mountpoint']:
        out.append('mountpoint contains /')
    # RTKLIB's ntrip://user:password@caster:port/mountpoint (decodetcppath; DEC-156): the last '#' ends the path, the first ':'
    # splits user and password, a ':' after the mountpoint starts another field, and the caster ends at ':' or '/'
    for k, bad in (('caster', ':/@#'), ('mountpoint', ':#'), ('user', ':#'), ('password', '#')):
        v = ntrip.get(k)
        if isinstance(v, str) and any(c in v for c in bad):
            out.append(f'{k} contains one of {list(bad)}')
    return out


def read_ntrip(config_dir: Optional[str]) -> tuple:
    """(ntrip mapping or None, note). The mapping is SECRET: give it only to the NTRIP relay, never log or record it.
    The note names the file and key names only (DEC-139, DEC-154)."""
    if not config_dir:
        return None, 'no config directory: no RTK corrections'
    path = os.path.join(config_dir, RTK_FILE)
    if not os.path.isfile(path):
        return None, f'{path} not found: no RTK corrections'
    try:
        if os.stat(path).st_mode & 0o077:
            return None, f'{path} can be read or written by others (chmod 600 it): not used, no RTK corrections'
        with open(path, encoding='utf-8') as f:
            doc = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        return None, f'{path} could not be read ({type(e).__name__}): no RTK corrections'
    if not isinstance(doc, dict):
        return None, f'{path} is not a mapping: no RTK corrections'
    if 'rtk_settings' in doc:
        return None, f'{path} has rtk_settings (old format, not passed to the driver: DEC-154): not used, no RTK corrections'
    problems = _ntrip_problems(doc.get('ntrip'))
    if problems:
        return None, f'{path}: {"; ".join(problems)}: not used, no RTK corrections'
    ignored = sorted(str(k) for k in doc if k != 'ntrip')
    note = f'ntrip from {path}' + (f' (ignored keys: {ignored})' if ignored else '')
    return {k: doc['ntrip'][k] for k in NTRIP_KEYS}, note


def driver_parameters(template: dict, params: dict, corrections: bool = False) -> tuple:
    """Return (parameter dict, missing keys, problems). The template is the upstream gnss.yaml parsed; it is not modified.
    corrections: a valid ntrip section exists; then rtk_settings.serial_1.port is set to PRM-75 (if decided) and nothing else
    in rtk_settings changes. No NTRIP value ever reaches the driver."""
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
    if corrections and params.get('rtk_input_port'):
        rtk = copy.deepcopy(p.get('rtk_settings') or {})
        serial_1 = dict(rtk.get('serial_1') or {})
        serial_1['port'] = str(params['rtk_input_port'])   # PRM-75 (DEC-154); the other serial_1 values stay as in the template
        rtk['serial_1'] = serial_1
        p['rtk_settings'] = rtk
    return p, missing, problems


def prepare_driver(template_path: str, params: dict, out_path: str, config_dir: Optional[str]) -> tuple:
    """Write the driver's ROS parameter file and decide the corrections, reading the template and the private file once.
    Returns (result, ntrip): result = {'missing', 'problems', 'rtk' (note), 'corrections', 'baud'} holds no secret and may be
    recorded; ntrip is the SECRET mapping for the NTRIP relay (None when there are no corrections) and must never be recorded.
    The file is written only when nothing is missing and there is no problem."""
    with open(template_path, encoding='utf-8') as f:
        template = yaml.safe_load(f) or {}
    ntrip, note = read_ntrip(config_dir)
    if ntrip is not None and not params.get('rtk_input_port'):
        ntrip, note = None, note + '; rtk_input_port (PRM-75) unresolved: no RTK corrections'
    corrections = ntrip is not None
    p, missing, problems = driver_parameters(template, params, corrections)
    baud = ((template.get('rtk_settings') or {}).get('serial_1') or {}).get('baud_rate')   # also the relay's serial:// rate
    result = {'missing': missing, 'problems': problems, 'rtk': note, 'corrections': corrections, 'baud': baud}
    if missing or problems:
        return result, ntrip
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('# GENERATED by gouda_core.gnss_config from the upstream septentrio_gnss_driver config/gnss.yaml and design/generated/params/septentrio_gnss_driver.yaml\n')
        yaml.safe_dump({'/**': {'ros__parameters': p}}, f, sort_keys=False, allow_unicode=True)
    os.chmod(out_path, 0o600)   # owner only (it holds no secret since DEC-154, kept as before)
    return result, ntrip


def write_parameter_file(template_path: str, params: dict, out_path: str, config_dir: Optional[str]) -> dict:
    """prepare_driver without the secret: only the recordable result."""
    return prepare_driver(template_path, params, out_path, config_dir)[0]


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

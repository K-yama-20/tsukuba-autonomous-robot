#!/usr/bin/env python3
"""Read-only clock inspection and explicit host-side profile/PTP preparation."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import yaml


def inspect_host(workspace):
    root = workspace/'bags/gouda'
    result={'imu_sync_wiring':'none (user reported)', 'hardware_synchronized':False,
            'required_device_settings':{'clock_source':'PTP','profile':'1588v2','transport':'UDP/IP','domain':0}}
    try:
        host=json.loads((root/'host.json').read_text())
        config=yaml.safe_load(Path(host['hesai_config']).expanduser().read_text())
        result['lidar_timestamp_type']=config['lidar'][0]['driver'].get('use_timestamp_type')
        result['sensor_timestamp_selected']=result['lidar_timestamp_type']==0
        iface=host.get('lidar_interface','')
        result['interface']=iface
        if re.fullmatch(r'[A-Za-z0-9_.:-]{1,15}',iface) and shutil.which('ethtool'):
            p=subprocess.run(['ethtool','-T',iface],capture_output=True,text=True,timeout=5)
            result['interface_timestamp_capabilities']=p.stdout+p.stderr
    except (OSError, ValueError, KeyError, TypeError) as exc:result['configuration_error']=str(exc)
    result['ptp4l_available']=bool(shutil.which('ptp4l'))
    result['lidar_lock']='UNKNOWN: check XT32 web Home/PTP status; no inferred lock from clock proximity'
    return result


def prepare(workspace, evidence):
    """Only change host timestamp selection; back up both files, never sensor settings."""
    root=workspace/'bags/gouda'
    host_path=root/'host.json'
    host=json.loads(host_path.read_text())
    original=Path(host['hesai_config']).expanduser()
    config=yaml.safe_load(original.read_text())
    if config['lidar'][0]['driver']['source_type']!=1:raise ValueError('hardware profile required')
    mapping_path=root/'mapping.json'
    mapping=json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    if not evidence.strip():raise ValueError('Record device clock source, status and no-sync-wire configuration')
    # Create unique durable evidence/backup directory; never overwrite previous profiles.
    backup=Path(tempfile.mkdtemp(prefix='time-sync-',dir=root))
    shutil.copy2(host_path,backup/'host.before.json')
    shutil.copy2(original,backup/'hesai.before.yaml')
    if mapping_path.exists():shutil.copy2(mapping_path,backup/'mapping.before.json')
    config['lidar'][0]['driver']['use_timestamp_type']=0
    target=backup/'hesai.sensor-time.yaml'
    target.write_text(yaml.safe_dump(config,sort_keys=False))
    host['hesai_config']=str(target.resolve())
    mapping.update(clock_policy='host_mapped',clock_evidence=evidence)
    # Unknown physical offsets/extrinsics are deliberately retained, not set to zero.
    for path,value in ((mapping_path,mapping),(host_path,host)):
        tmp=path.with_suffix('.sync.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(path)
    return {'backup':str(backup),'status':'host profile prepared; device PTP lock remains unverified'}


def ptp_command(interface):
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,15}',interface):raise ValueError('Invalid interface')
    if not (Path('/sys/class/net')/interface).exists():raise ValueError('Interface does not exist')
    # Software timestamping uses CLOCK_REALTIME; do not discipline the PC from LiDAR.
    config=Path(__file__).resolve().parent.parent/'gouda_sensors/config/ptp_host.cfg'
    return ['ptp4l','-S','-4','-m','-i',interface,'-f',str(config)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,default=Path(os.environ.get('GOUDA_WORKSPACE',Path.home()/'gouda_ws')))
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('inspect')
    q=sub.add_parser('prepare');q.add_argument('--evidence',required=True)
    q=sub.add_parser('ptp');q.add_argument('--interface',required=True)
    a=p.parse_args()
    if a.action=='inspect':print(json.dumps(inspect_host(a.workspace),ensure_ascii=False,indent=2))
    elif a.action=='prepare':print(json.dumps(prepare(a.workspace,a.evidence),ensure_ascii=False,indent=2))
    else:
        command=ptp_command(a.interface)
        if os.geteuid()!=0:raise SystemExit('Run this explicit ptp command with sudo; no clock service is started automatically')
        os.execvp(command[0],command)

if __name__=='__main__':main()


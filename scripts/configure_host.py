"""Per-host setup. Sensor calibration is read from the device, never substituted."""
import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time


def config_root(workspace):
    return Path(workspace).expanduser().resolve()/'bags'/'gouda'


def legacy_config_root():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'gouda'


def process_is_alive(item):
    try:
        pid=int(item['pid'])
        stat=Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        current=boot+':'+stat[19] if stat[0] != 'Z' else None
        return current is not None and current == item.get('start')
    except (KeyError, ValueError, OSError, IndexError, TypeError):
        return False

def running_gouda(workspace=None):
    proc = Path('/proc')
    if not proc.is_dir():
        return False
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except (OSError, PermissionError):
            continue
        if 'gouda_gui.runtime' in cmd or 'gouda_gui/runtime.py' in cmd:
            return True
    # The legacy CLI exits after launching process groups. Validate both PID and
    # start identity from its registry to avoid PID reuse false positives.
    registries=[Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'gouda/runtime/processes.json']
    workspace=workspace or os.environ.get('GOUDA_WORKSPACE')
    if workspace:
        registries.append(Path(workspace).expanduser().resolve()/'bags/gouda/runtime/processes.json')
    for registry in dict.fromkeys(registries):
        if not registry.is_file():
            continue
        try:
            state=json.loads(registry.read_text())
            if any(process_is_alive(item) for item in state.get('processes', {}).values()):
                return True
        except (OSError, ValueError, AttributeError):
            return True
    return False


def migrate_maps(workspace):
    """Copy legacy maps once; leave the source untouched and reject collisions."""
    legacy = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'gouda'
    if not legacy.is_dir():
        return
    target_root = Path(workspace).expanduser().resolve()
    marker=target_root/'.gouda-map-migration-complete'
    if marker.exists():
        return
    maps = [name for name in ('maps', 'maps_sensor_slam') if (legacy/name).exists() or (legacy/name).is_symlink()]
    if not maps:
        return
    if running_gouda():
        raise ValueError('Goudaプロセスが稼働中のため地図を移行できません。先にbash scripts/gouda.sh stopを実行してください。')
    # Preflight every file before writing anything. Identical existing files are
    # safe on reruns; differing content and link targets are never overwritten.
    copies, conflicts = [], []
    for name in maps:
        source = legacy/name
        target = target_root/name
        for item in [source, *source.rglob('*')]:
            relative = item.relative_to(source)
            destination = target/relative
            if item.is_dir() and not item.is_symlink():
                if destination.exists() or destination.is_symlink():
                    if not destination.is_dir() or destination.is_symlink():
                        conflicts.append(str(destination))
                else:
                    copies.append((item, destination))
            else:
                if destination.exists() or destination.is_symlink():
                    same = (item.is_symlink() and destination.is_symlink()
                            and item.readlink() == destination.readlink())
                    same = same or (item.is_file() and destination.is_file()
                                    and not destination.is_symlink()
                                    and item.stat().st_size == destination.stat().st_size
                                    and __import__('filecmp').cmp(item, destination, shallow=False))
                    if not same:
                        conflicts.append(str(destination))
                else:
                    copies.append((item, destination))
    if conflicts:
        raise ValueError('既存マップと移行先が競合します: '+', '.join(conflicts)+'。移行元・移行先を両方保持して手動で整理してください。')
    target_root.mkdir(parents=True, exist_ok=True)
    for source, destination in copies:
        if source.is_dir() and not source.is_symlink():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            destination.symlink_to(source.readlink(), target_is_directory=source.is_dir())
        else:
            shutil.copy2(source, destination)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('legacy maps copied; workspace maps are now authoritative\n')
    marker.chmod(0o600)


def write_migration_marker(path, contents):
    path.write_text(contents+'\n')
    path.chmod(0o600)


def migrate_legacy_sensor_config(cfg, workspace, root):
    """Copy a validated XDG Hesai profile and referenced files into workspace state."""
    marker=root/'.sensor-migration-complete'
    if marker.exists():
        return
    source=Path(cfg.get('hesai_config','')).expanduser()
    workspace=Path(workspace).expanduser().resolve()
    if source.is_file() and source.resolve() == (root/'hesai.yaml').resolve():
        from gouda_sensors.hesai_config import checked_config
        checked_config(source,'hardware')
        write_migration_marker(marker,'legacy sensor profile copied; workspace settings are now authoritative')
        return
    if not source.is_file() or workspace in source.resolve().parents:
        return
    from gouda_sensors.hesai_config import checked_config
    import yaml
    checked_config(source,'hardware')
    data=yaml.safe_load(source.read_text())
    copies={}
    destinations={}
    for key in ('lidar_udp_type','pcap_type','rosbag_type'):
        block=data['lidar'][0]['driver'].get(key,{})
        for field in ('correction_file_path','firetimes_path'):
            value=block.get(field)
            if not value:
                continue
            original=Path(value).expanduser()
            if not original.is_file():
                raise ValueError(f'参照ファイルが見つかりません: {original}')
            if field == 'correction_file_path':
                validate_correction(original.read_bytes())
            if workspace in original.resolve().parents:
                continue
            destination=root/original.name
            prior=destinations.get(destination)
            if prior is not None and not __import__('filecmp').cmp(original,prior,shallow=False):
                raise ValueError(f'同名の設定ファイルが異なる内容です: {original} / {prior}')
            destinations[destination]=original
            if destination.exists():
                if not destination.is_file() or not __import__('filecmp').cmp(original,destination,shallow=False):
                    raise ValueError(f'移行先に異なる設定ファイルがあります: {destination}')
            else:
                copies[original]=destination
            block[field]=str(destination)
    target=root/'hesai.yaml'
    rendered=yaml.safe_dump(data,sort_keys=False)
    if target.exists() and target.read_text()!=rendered:
        raise ValueError(f'移行先に異なるLiDAR設定があります: {target}')
    for original,destination in copies.items():
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,destination)
    if not target.exists():
        target.write_text(rendered)
        target.chmod(0o600)
    checked_config(target,'hardware')
    cfg['hesai_config']=str(target)
    save(root/'host.json',cfg)
    write_migration_marker(marker,'legacy sensor profile copied; workspace settings are now authoritative')


def checked_hardware(workspace, preferred=None):
    """Reuse a validated checked_hardware.yaml without guessing between bag folders."""
    bags = Path(workspace).expanduser().resolve()/'bags'
    if preferred:
        chosen = Path(preferred).expanduser()
        if chosen.is_file() and chosen.name == 'checked_hardware.yaml' and bags in chosen.resolve().parents:
            from gouda_sensors.hesai_config import checked_config
            checked_config(chosen, 'hardware')
            return chosen.resolve()
    candidates = sorted(bags.glob('*/checked_hardware.yaml'))
    if len(candidates) > 1:
        raise ValueError('checked_hardware.yamlが複数あります。host.jsonで使用先を明示してください。')
    if not candidates:
        return None
    candidate = candidates[0]
    from gouda_sensors.hesai_config import checked_config
    checked_config(candidate, 'hardware')
    return candidate


def correction_from_config(path):
    import yaml
    data = yaml.safe_load(Path(path).read_text())
    return Path(data['lidar'][0]['driver']['lidar_udp_type']['correction_file_path'])


def load_or_migrate_config(workspace, root):
    path = root/'host.json'
    old = legacy_config_root()/'host.json'
    marker = root/'.legacy-migration-complete'
    if path.exists() and old.exists() and not marker.exists():
        current, legacy = json.loads(path.read_text()), json.loads(old.read_text())
        if current != legacy:
            raise ValueError(f'設定が新旧両方にあり内容が異なります: {path} / {old}')
        if Path(current.get('workspace', '')).expanduser().resolve() != Path(workspace).expanduser().resolve():
            raise ValueError('別workspaceを指すhost.jsonがあります。設定を上書きしません。')
        marker.write_text('legacy and workspace settings matched; workspace settings are now authoritative\n')
        marker.chmod(0o600)
    source = path if path.exists() else old if old.exists() and not marker.exists() else None
    if source:
        cfg = json.loads(source.read_text())
        if Path(cfg.get('workspace', '')).expanduser().resolve() != Path(workspace).expanduser().resolve():
            raise ValueError('別workspaceを指すhost.jsonがあります。設定を上書きしません。')
        if not path.exists():
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(cfg, indent=2)+'\n')
            temp.chmod(0o600)
            temp.replace(path)
        if source == old and not marker.exists():
            marker.write_text('legacy host settings copied; old file retained\n')
            marker.chmod(0o600)
        return cfg
    cfg = dict(workspace=str(Path(workspace).expanduser().resolve()), imu_device='', lidar_interface='',
               hesai_config=str(root/'hesai.yaml'))
    existing = checked_hardware(workspace)
    if existing:
        cfg['hesai_config'] = str(existing)
    return cfg



def archive_build_outputs(workspace, source):
    """Move stale generated colcon state aside before a source/mode change."""
    workspace=Path(workspace).expanduser().resolve()
    source=Path(source).expanduser().resolve()
    state_path=workspace/'.gouda-build-state.json'
    current={'source':str(source),'install_mode':'symlink'}
    try:
        previous=json.loads(state_path.read_text())
    except (OSError,ValueError):
        previous=None
    outputs=[workspace/name for name in ('build','install','log') if (workspace/name).exists() or (workspace/name).is_symlink()]
    if not outputs or previous == current:
        return None
    if running_gouda(workspace):
        raise ValueError('Gouda is still running; stop it before moving build/install/log.')
    archive=workspace/'bags/gouda/archive'/str(time.time_ns())
    archive.mkdir(parents=True,exist_ok=False)
    for path in outputs:
        path.rename(archive/path.name)
    return archive


def record_build_state(workspace, source):
    workspace=Path(workspace).expanduser().resolve()
    state_path=workspace/'.gouda-build-state.json'
    temp=state_path.with_suffix('.tmp')
    temp.write_text(json.dumps({'source':str(Path(source).expanduser().resolve()),
                                'install_mode':'symlink'},indent=2)+'\n')
    temp.replace(state_path)

def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2)+'\n')
    tmp.replace(path)


def recv_exact(sock, count):
    result = b''
    while len(result) < count:
        chunk = sock.recv(count-len(result))
        if not chunk:
            raise ValueError('PTC response ended early')
        result += chunk
    return result


def validate_correction(data):
    # XT32 CSV: Laser id,Elevation,Azimuth. Reject other devices/partial data.
    rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig').strip('\x00\r\n'))))
    if len(rows) < 33 or [v.strip().lower() for v in rows[0][:3]] != ['laser id','elevation','azimuth']:
        raise ValueError('Expected XT32 correction CSV header and 32 channels')
    ids = []
    for row in rows[1:33]:
        ids.append(int(row[0]))
        if not all(math.isfinite(float(v)) and abs(float(v)) <= 180 for v in row[1:3]) or len(row) < 3:
            raise ValueError('Invalid correction angle')
    if ids != list(range(1, 33)):
        raise ValueError('Expected XT32 channels 1..32')
    return data


def fetch_correction(host, port=9347):
    # Pinned Hesai SDK PTC 1.0 header, read-only GetLidarCalibration command 0x05.
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(struct.pack('!2sBBI', b'Gt', 5, 0, 0))
        magic, command, status, size = struct.unpack('!2sBBI', recv_exact(sock, 8))
        if magic != b'Gt' or command != 5 or status != 0 or not 0 < size <= 1024*1024:
            raise ValueError('Unexpected PTC calibration response')
        return validate_correction(recv_exact(sock, size))


def choose(label, values):
    print(label)
    for i, item in enumerate(values, 1):
        print(f'  {i}: {item}')
    answer = input('番号（Enterで後から設定）: ').strip()
    if not answer:
        return None
    if not answer.isdigit() or not 1 <= int(answer) <= len(values):
        raise ValueError('一覧の番号を入力してください')
    return values[int(answer)-1]


def network(iface, root):
    routes = json.loads(subprocess.check_output(['ip','-j','route','show','default'], text=True))
    if any(r.get('dev') == iface for r in routes):
        raise ValueError('インターネットの既定経路を持つLANです。LiDAR専用LANを選択してください。')
    addresses = json.loads(subprocess.check_output(['ip','-j','address'], text=True))
    if any(a['ifname'] != iface and any(v.get('local') == '192.168.1.100' for v in a['addr_info']) for a in addresses):
        raise ValueError('192.168.1.100が別のLANにあります。重複IPを解消してから実行してください。')
    name = 'gouda-lidar-'+iface
    connections = subprocess.check_output(['nmcli','-t','-f','NAME','con','show'],text=True).splitlines()
    if name in connections:
        # Never rewrite an existing profile with the same name.
        address = subprocess.check_output(['nmcli','-g','ipv4.addresses','con','show',name],text=True).strip()
        device = subprocess.check_output(['nmcli','-g','connection.interface-name','con','show',name],text=True).strip()
        if address != '192.168.1.100/24' or device != iface:
            raise ValueError('既存の同名LAN設定が異なります。自動変更しません。')
    else:
        backup = root/'network-backups'/str(time.time_ns())
        backup.mkdir(parents=True, mode=0o700)
        for cmd, filename in [(['nmcli','-f','all','device','show',iface],'device.txt'),
                              (['nmcli','connection','show'],'connections.txt')]:
            (backup/filename).write_bytes(subprocess.check_output(cmd))
        subprocess.run(['sudo','nmcli','con','add','type','ethernet','ifname',iface,'con-name',name,
                        'ipv4.method','manual','ipv4.addresses','192.168.1.100/24',
                        'ipv4.never-default','yes','ipv6.method','disabled'],check=True)
    subprocess.run(['sudo','nmcli','con','up',name,'ifname',iface],check=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--defaults',action='store_true')
    parser.add_argument('--prepare-build',action='store_true')
    parser.add_argument('--record-build',action='store_true')
    parser.add_argument('--source')
    args=parser.parse_args()
    if args.prepare_build or args.record_build:
        if not args.source:
            parser.error('--source is required for build-state actions')
        if args.prepare_build:
            archive_build_outputs(args.workspace,args.source)
        if args.record_build:
            record_build_state(args.workspace,args.source)
        return
    workspace=Path(args.workspace).expanduser().resolve()
    os.environ['GOUDA_WORKSPACE']=str(workspace)
    root=config_root(workspace); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    path=root/'host.json'
    cfg=load_or_migrate_config(workspace, root)
    if Path(cfg['workspace']).expanduser().resolve() != workspace:
        raise SystemExit('別のworkspace設定が存在します。設定を上書きしません。')
    migrate_maps(workspace)
    migrate_legacy_sensor_config(cfg, workspace, root)
    if Path(cfg['workspace']).expanduser().resolve() != workspace:
        raise SystemExit('別のworkspace設定が存在します。設定を上書きしません。')
    current_config=Path(cfg.get('hesai_config', '')).expanduser()
    from gouda_sensors.hesai_config import checked_config
    current_valid=False
    if current_config.is_file():
        try:
            checked_config(current_config, 'hardware')
            current_valid=True
        except (KeyError, TypeError, ValueError, OSError):
            pass
    if current_valid:
        # Keep legacy absolute calibration references intact when still valid.
        pass
    else:
        hardware=checked_hardware(workspace, current_config)
        if hardware:
            cfg['hesai_config']=str(hardware)
        elif current_config.exists():
            raise ValueError(f'既存のLiDAR設定を検証できません: {current_config}')
    save(path,cfg)
    if args.defaults:
        return
    if not os.isatty(0):
        raise SystemExit('機器設定には対話端末が必要です。CIでは --no-configure を指定してください。')
    print('機器が未接続ならEnterで省略できます。あとから bash scripts/gouda.sh configure で設定できます。')
    nics=[p.name for p in Path('/sys/class/net').iterdir() if p.name!='lo' and not (p/'wireless').exists()]
    nic=choose('LiDAR専用LAN（既定経路のLANは変更しません）',sorted(nics))
    if nic:
        network(nic, root)
        cfg['lidar_interface']=nic
        save(path,cfg)
    imu=choose('IMUのUSB接続', sorted(str(p) for p in Path('/dev/serial/by-id').glob('*')))
    if imu:
        cfg['imu_device']=imu
        save(path,cfg)
        if not os.access(imu, os.R_OK|os.W_OK):
            subprocess.run(['sudo','usermod','-aG','dialout',__import__('getpass').getuser()],check=True)
            print('USB権限を追加しました。ログアウト・ログイン後にobserveを起動してください。')
    target=Path(cfg['hesai_config'])
    if nic and not target.exists():
        try:
            data=fetch_correction('192.168.1.201')
        except (OSError,ValueError) as exc:
            print(f'LiDAR補正データを取得できません: {exc}')
            source=input('機器から取得済みの補正CSVのパス（Enterで後から設定）: ').strip()
            if not source:
                print('GUIの受信待ち画面は利用可能です。実機設定は configure で再実行してください。')
                return
            data=validate_correction(Path(source).expanduser().read_bytes())
        calibration=root/'xt32_correction.csv'
        if not calibration.exists():
            calibration.write_bytes(data)
        from gouda_sensors.profiles import make_profile
        from gouda_sensors.hesai_config import checked_config
        import yaml
        profile=make_profile(Path(args.workspace)/'src/HesaiLidar_ROS_2.0/config/config.yaml',
            'hardware',calibration,device='192.168.1.201',host='192.168.1.100',udp=2368,ptc=9347)
        temp=target.with_suffix('.tmp'); temp.write_text(yaml.safe_dump(profile))
        checked_config(temp,'hardware'); temp.replace(target)
    print('設定保存:', path)


if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))

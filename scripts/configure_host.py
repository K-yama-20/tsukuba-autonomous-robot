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


def config_root():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'gouda'


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
    args=parser.parse_args()
    root=config_root(); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path=root/'host.json'
    cfg=json.loads(path.read_text()) if path.exists() else dict(
        workspace=str(Path(args.workspace).resolve()), imu_device='', lidar_interface='',
        hesai_config=str(root/'hesai.yaml'))
    if Path(cfg['workspace']).resolve() != Path(args.workspace).resolve():
        raise SystemExit('別のworkspace設定が存在します。XDG_CONFIG_HOMEで分離してください。')
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

"""Own only processes launched here; reconnecting a browser never touches sensors."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from .paths import config_dir, data_dir


def identity(pid):
    try:
        # comm can contain spaces/parentheses; starttime is field 22.
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return boot+':'+fields[19] if fields[0] != 'Z' else None
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(item):
    return item.get('start') is not None and identity(item['pid']) == item['start']


def occupied(port):
    with socket.socket() as sock:
        sock.settimeout(.2)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def terminate(item):
    if not alive(item):
        return
    os.killpg(item['pid'], signal.SIGTERM)
    for _ in range(100):
        if not alive(item):
            return
        time.sleep(.1)
    if alive(item):
        os.killpg(item['pid'], signal.SIGKILL)


def write_state(path, value):
    temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(value,indent=2)); temp.replace(path)


def status():
    result={}
    for name, url in [('gui','http://127.0.0.1:8766/api/state'),('viewer','http://127.0.0.1:8766/api/viewer')]:
        try:
            with urlopen(url,timeout=3) as r:
                data=json.load(r)
            result[name]={'connected':True, **({k:data[k] for k in ('available','fresh','ages') if k in data} if name=='viewer' else {})}
        except Exception as exc:
            result[name]={'connected':False,'error':str(exc)}
    return result


def validate_hardware(cfg):
    from gouda_sensors.hesai_config import checked_config
    checked_config(cfg['hesai_config'],'hardware')
    if not cfg.get('imu_device') or not os.access(cfg['imu_device'],os.R_OK|os.W_OK):
        raise ValueError('IMUが未設定・未接続、またはUSB権限がありません。gouda.sh configure を確認してください。')
    iface=cfg.get('lidar_interface')
    if not iface or not Path('/sys/class/net',iface).exists():
        raise ValueError('LiDAR専用LANが未設定・未接続です。gouda.sh configure を実行してください。')
    addresses=json.loads(subprocess.check_output(['ip','-j','address'],text=True))
    hosts=[a['ifname'] for a in addresses if any(v.get('local')=='192.168.1.100' for v in a['addr_info'])]
    if hosts != [iface]:
        raise ValueError('LiDAR側IP 192.168.1.100 が選択したLANだけに設定されている必要があります。')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['view','observe','doctor','stop'])
    args=parser.parse_args()
    root=data_dir()/'runtime'; root.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=(root/'lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    path=root/'processes.json'
    state=json.loads(path.read_text()) if path.exists() else {'mode':None,'processes':{}}
    if args.command=='stop':
        for item in reversed(list(state['processes'].values())):
            terminate(item)
        write_state(path,{'mode':None,'processes':{}})
        print('管理対象のプロセスを停止しました。'); return
    cfgfile=config_dir()/'host.json'
    cfg=json.loads(cfgfile.read_text()) if cfgfile.exists() else {}
    if args.command=='doctor':
        import shutil
        result={'config':str(cfgfile),'commands':{n:shutil.which(n) for n in ['ros2','Xvfb','x11vnc','wmctrl','openbox']},
                'mode':state['mode'],'processes':{k:alive(v) for k,v in state['processes'].items()},
                'ports':{p:occupied(p) for p in (8765,8766,6080,5907)},**status()}
        try: validate_hardware(cfg); result['hardware']='configured'
        except Exception as exc: result['hardware']=str(exc)
        print(json.dumps(result,indent=2,ensure_ascii=False)); return
    if not cfg:
        raise ValueError('初回セットアップを実行してください。')
    if state['mode'] not in (None,'observation') and any(alive(v) for v in state['processes'].values()):
        raise ValueError('以前の起動が稼働中です。先に gouda.sh stop を実行してください。')
    if args.command=='observe': validate_hardware(cfg)
    env=dict(os.environ,ROS_DOMAIN_ID='99',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    env.pop('ROS_LOCALHOST_ONLY',None)
    launches=[]
    if args.command=='observe':
        launches.append(('sensors',['ros2','launch','gouda_gui','sensors_only.launch.py',
                             'hesai_config:='+cfg['hesai_config'],'imu_device:='+cfg['imu_device']],[]))
    launches.extend([
        ('processing',['ros2','launch','gouda_gui','observation.launch.py','sensors:=false'],[8765]),
        ('viewer',['ros2','run','gouda_gui','native_view'],[6080,5907])])
    launches.append(('gateway',[sys.executable,'-m','gouda_gui.gateway'],[8766]))
    # Check all resources before starting sensors. Never adopt an unrelated process.
    for name,cmd,ports in launches:
        if not alive(state['processes'].get(name,{})):
            for port in ports:
                if occupied(port): raise ValueError(f'Port {port} is already used by another process.')
            if name=='viewer' and Path('/tmp/.X97-lock').exists():
                raise ValueError('Display :97 is occupied by another process.')
    state['mode']='observation'
    new=[]
    try:
        for name,cmd,ports in launches:
            if alive(state['processes'].get(name,{})): continue
            with (root/(name+'.log')).open('a') as log:
                process=subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            item={'pid':process.pid,'start':identity(process.pid)}
            state['processes'][name]=item; new.append(name); write_state(path,state)
            time.sleep(.5)
            if process.poll() is not None: raise ValueError(f'{name} failed; see {root/name}.log')
        for _ in range(100):
            if not all(alive(v) for v in state['processes'].values()):
                raise ValueError(f'A process exited. Logs: {root}')
            try:
                with urlopen('http://127.0.0.1:8766/api/state',timeout=1) as response:
                    if response.status==200: break
            except Exception: time.sleep(.2)
        else: raise ValueError(f'GUI readiness timeout. Logs: {root}')
    except Exception:
        for name in reversed(new):
            terminate(state['processes'].pop(name))
        write_state(path,state); raise
    print('GUI: http://127.0.0.1:8766')
    print('実機走行出力は起動していません。終了: bash scripts/gouda.sh stop')


if __name__=='__main__':
    try: main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc: raise SystemExit(str(exc))

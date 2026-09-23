"""Own only processes launched here; reconnecting a browser never touches sensors."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from .paths import config_dir, runtime_dir, logs_dir


def identity(pid):
    try:
        # comm can contain spaces/parentheses; starttime is field 22.
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return boot+':'+fields[19] if fields[0] != 'Z' else None
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(item):
    return bool(item) and item.get('start') is not None and identity(item['pid']) == item['start']


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


def display_status(item):
    if not item or not alive(item):
        result={'available':False,'state':'stopped','error':'RViz2 process is not running'}
        log=logs_dir()/'viewer.log'
        if log.exists(): result['failure']=log.read_text(errors='replace')[-1200:].strip()
        return result
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return {'available':True,'state':'running','pid':item['pid'],'display':item.get('display'),'window_visible':None,'error':'This shell has no desktop connection, so window visibility cannot be checked.'}
    result={'available':True,'state':'running','pid':item['pid'],'display':os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')}
    try:
        out=subprocess.check_output(['xwininfo','-root','-tree'],stderr=subprocess.DEVNULL,text=True,timeout=2)
        result['window_visible']='rviz' in out.lower()
    except (FileNotFoundError,subprocess.SubprocessError):
        result['window_visible']=None
    return result


def status():
    result={}
    for name, url in [('gui','http://127.0.0.1:8766/api/state')]:
        try:
            with urlopen(url,timeout=3) as r: json.load(r)
            result[name]={'connected':True}
        except Exception as exc: result[name]={'connected':False,'error':str(exc)}
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


def rviz_command(cfg):
    from ament_index_python.packages import get_package_share_directory
    config=Path(get_package_share_directory('kiss_icp'))/'rviz/kiss_icp.rviz'
    return [shutil.which('rviz2') or '/opt/ros/jazzy/lib/rviz2/rviz2','-d',str(config),'--ros-args',
            '-r','/initialpose:=/gouda/viewer/initialpose_unused',
            '-r','/goal_pose:=/gouda/viewer/goal_unused']


def start_viewer(state,path,logs,cfg):
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Ubuntuデスクトップの表示環境がありません。デスクトップから gouda.sh observe を実行してください。')
    item=state['processes'].get('viewer',{})
    if alive(item): return
    logpath=logs/'viewer.log'
    env=dict(os.environ,ROS_DOMAIN_ID='99',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    env.pop('ROS_LOCALHOST_ONLY',None)
    if env.get('DISPLAY'): env['QT_QPA_PLATFORM']='xcb'
    with logpath.open('a') as log:
        p=subprocess.Popen(rviz_command(cfg),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                           start_new_session=True)
    item={'pid':p.pid,'start':identity(p.pid),'display':env.get('WAYLAND_DISPLAY') or env.get('DISPLAY')};state['processes']['viewer']=item;write_state(path,state)
    for _ in range(100):
        if not alive(item):
            tail=logpath.read_text(errors='replace')[-1500:]
            raise ValueError(f'RViz2終了。原因: {tail or "ログがありません"}')
        try:
            windows=subprocess.check_output(['xwininfo','-root','-tree'],stderr=subprocess.DEVNULL,text=True,timeout=1)
            if any('rviz' in line.lower() for line in windows.splitlines()): return
        except (FileNotFoundError,subprocess.SubprocessError):
            # Wayland compositors do not expose a portable window-list API; verify
            # the actual RViz process and report window visibility as unknown.
            if os.environ.get('WAYLAND_DISPLAY') and _process_is_rviz(item['pid']): return
        time.sleep(.2)
    terminate(item);state['processes'].pop('viewer',None);write_state(path,state)
    tail=logpath.read_text(errors='replace')[-1500:]
    raise ValueError(f'RViz2ウィンドウを確認できません。原因: {tail or "xwininfoでウィンドウが見つかりません"}')


def _process_is_rviz(pid):
    try: return 'rviz2' in Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace')
    except OSError: return False


def restart_viewer(state,path,logs,cfg):
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Ubuntuデスクトップの表示環境がありません。デスクトップから gouda.sh viewer を実行してください。')
    old=state['processes'].get('viewer',{})
    active_display=os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')
    if alive(old) and old.get('display') and old['display']!=active_display:
        raise ValueError('管理中のRViz2は別のデスクトップで動作中です。そのデスクトップで gouda.sh viewer を実行してください。')
    if alive(old): terminate(old)
    state['processes'].pop('viewer',None);write_state(path,state)
    start_viewer(state,path,logs,cfg)
    print('UbuntuデスクトップのRViz2ウィンドウを再起動しました。センサーは再起動していません。')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['view','observe','viewer','doctor','stop'])
    args=parser.parse_args()
    root=runtime_dir(); root.mkdir(parents=True,exist_ok=True,mode=0o700)
    logs=logs_dir(); logs.mkdir(parents=True,exist_ok=True,mode=0o700)
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
        result={'config':str(cfgfile),'commands':{n:shutil.which(n) for n in ['ros2','rviz2','xwininfo']},
                'mode':state['mode'],'processes':{k:alive(v) for k,v in state['processes'].items()},
                'ports':{p:occupied(p) for p in (8765,8766)},'viewer':display_status(state['processes'].get('viewer')),'display':{'DISPLAY':os.environ.get('DISPLAY'),'WAYLAND_DISPLAY':os.environ.get('WAYLAND_DISPLAY')},**status()}
        try: validate_hardware(cfg); result['hardware']='configured'
        except Exception as exc: result['hardware']=str(exc)
        print(json.dumps(result,indent=2,ensure_ascii=False)); return
    if not cfg:
        raise ValueError('初回セットアップを実行してください。')
    # Retire only the legacy browser-transfer viewer; leave sensors and other nodes alone.
    old=state['processes'].get('viewer')
    if alive(old):
        try:
            cmdline=Path(f"/proc/{old['pid']}/cmdline").read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except OSError: cmdline=''
        if 'native_view' in cmdline:
            terminate(old); state['processes'].pop('viewer',None); write_state(path,state)
    if args.command=='viewer':
        restart_viewer(state,path,logs,cfg)
        return
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
        ('processing',['ros2','launch','gouda_gui','observation.launch.py','sensors:=false'],[8765])])
    launches.append(('gateway',[sys.executable,'-m','gouda_gui.gateway'],[8766]))
    # Check all resources before starting sensors. Never adopt an unrelated process.
    for name,cmd,ports in launches:
        if not alive(state['processes'].get(name,{})):
            for port in ports:
                if occupied(port): raise ValueError(f'Port {port} is already used by another process.')

    state['mode']='observation'
    new=[]
    try:
        for name,cmd,ports in launches:
            if alive(state['processes'].get(name,{})): continue
            with (logs/(name+'.log')).open('a') as log:
                process=subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            item={'pid':process.pid,'start':identity(process.pid)}
            state['processes'][name]=item; new.append(name); write_state(path,state)
            time.sleep(.5)
            if process.poll() is not None: raise ValueError(f'{name} failed; see {logs/name}.log')
        for _ in range(100):
            if not all(alive(state['processes'].get(n,{})) for n in ('processing','gateway')):
                raise ValueError(f'A GUI process exited. Logs: {logs}')
            try:
                with urlopen('http://127.0.0.1:8766/api/state',timeout=1) as response:
                    if response.status==200: break
            except Exception: time.sleep(.2)
        else: raise ValueError(f'GUI readiness timeout. Logs: {logs}')
    except Exception:
        for name in reversed(new):
            if name=='sensors': continue
            item=state['processes'].pop(name,None)
            if item: terminate(item)
        write_state(path,state); raise
    try:
        start_viewer(state,path,logs,cfg)
    except Exception:
        # A viewer/display failure must not stop healthy sensors or the API.
        print(f'RViz2を起動できませんでした。ログ: {logs / "viewer.log"}',file=sys.stderr)
        raise
    print('GUI: http://127.0.0.1:8766')
    print('RViz2はUbuntuデスクトップの別ウィンドウです。再起動: bash scripts/gouda.sh viewer')
    print('実機走行出力は起動していません。終了: bash scripts/gouda.sh stop')


if __name__=='__main__':
    try: main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc: raise SystemExit(str(exc))

"""Own only processes launched here; reconnecting a browser never touches sensors."""
import argparse
import fcntl
import json
import math
import os
import re
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


def terminate(item, graceful_signal=signal.SIGTERM, timeout=10.0, initial_group=True):
    if not alive(item):
        return
    (os.killpg if initial_group else os.kill)(item['pid'], graceful_signal)
    deadline = time.monotonic() + timeout
    while alive(item) and time.monotonic() < deadline:
        time.sleep(.1)
    if alive(item):
        os.killpg(item['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 10.0
        while alive(item) and time.monotonic() < deadline:
            time.sleep(.1)
    if alive(item):
        os.killpg(item['pid'], signal.SIGKILL)


def write_state(path, value):
    temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(value,indent=2)); temp.replace(path)


def display_identity(env=None):
    env=os.environ if env is None else env
    if env.get('DISPLAY'):
        return 'x11:'+env['DISPLAY']
    if env.get('WAYLAND_DISPLAY'):
        return 'wayland:'+env['WAYLAND_DISPLAY']
    return None


def rviz_window_for_pid(pid):
    try:
        tree=subprocess.check_output(['xwininfo','-root','-tree'],stderr=subprocess.DEVNULL,text=True,timeout=2)
    except (FileNotFoundError,subprocess.SubprocessError):
        return None
    for line in tree.splitlines():
        match=re.match(r'^\s*(0x[0-9a-fA-F]+)\s+"([^"]*)"',line)
        if not match or not match.group(2).lower().endswith(' - rviz'): continue
        window_id,title=match.groups()
        try:
            info=subprocess.check_output(['xwininfo','-id',window_id],stderr=subprocess.DEVNULL,text=True,timeout=1)
            props=subprocess.check_output(['xprop','-id',window_id,'_NET_WM_PID','WM_CLASS'],
                stderr=subprocess.DEVNULL,text=True,timeout=1)
        except (FileNotFoundError,subprocess.SubprocessError):
            continue
        dimensions=re.search(r'Width:\s+(\d+)\s+Height:\s+(\d+)',info)
        pid_prop=re.search(r'_NET_WM_PID(?:\([^)]*\))?\s*=\s*(\d+)\s*$',props,re.MULTILINE)
        wm_class=re.search(r'WM_CLASS[^=]*=\s*(.*)',props)
        if (pid_prop and int(pid_prop.group(1))==pid and
                wm_class and 'rviz2' in wm_class.group(1).lower() and
                'Map State: IsViewable' in info and dimensions and
                int(dimensions.group(1))>=300 and int(dimensions.group(2))>=200):
            return True
    return False


def display_status(item):
    if not item or not alive(item):
        result={'available':False,'state':'stopped','error':'RViz2 process is not running'}
        log=logs_dir()/'viewer.log'
        if log.exists(): result['failure']=log.read_text(errors='replace')[-1200:].strip()
        return result
    target=item.get('display')
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return {'available':True,'state':'running','pid':item['pid'],'display':target,'window_visible':None,'error':'This shell has no desktop connection, so window visibility cannot be checked.'}
    if target and display_identity()!=target:
        return {'available':True,'state':'running','pid':item['pid'],'display':target,'window_visible':None,'error':'This shell is connected to a different desktop display.'}
    result={'available':True,'state':'running','pid':item['pid'],'display':target}
    result['window_visible']=rviz_window_for_pid(item['pid']) if target and target.startswith('x11:') else None
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
    try:
        from gouda_navigation.mapping import load_mapping_settings
        selected = load_mapping_settings().get('backend', 'kiss_icp')
    except Exception:
        selected = 'kiss_icp'
    config = (Path(get_package_share_directory('gouda_navigation'))/'config/glim.rviz'
              if selected == 'glim_imu' else Path(get_package_share_directory('kiss_icp'))/'rviz/kiss_icp.rviz')
    return [shutil.which('rviz2') or '/opt/ros/jazzy/lib/rviz2/rviz2','-d',str(config),'--ros-args',
            '-r','/initialpose:=/gouda/viewer/initialpose_unused',
            '-r','/goal_pose:=/gouda/viewer/goal_unused']


def start_viewer(state,path,logs,cfg):
    if os.environ.get('GOUDA_HEADLESS') == '1':
        return
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
    item={'pid':p.pid,'start':identity(p.pid),'display':display_identity(env),'window_visible':None};state['processes']['viewer']=item;write_state(path,state)
    started=time.monotonic()
    for _ in range(100):
        if not alive(item):
            tail=logpath.read_text(errors='replace')[-1500:]
            raise ValueError(f'RViz2終了。原因: {tail or "ログがありません"}')
        if env.get('DISPLAY'):
            visible=rviz_window_for_pid(item['pid'])
            if visible:
                item['window_visible']=True;write_state(path,state);return
        elif env.get('WAYLAND_DISPLAY') and time.monotonic()-started>=3:
            # Wayland has no portable window-list API; require a stable direct RViz
            # child before reporting launch success and mark visibility unknown.
            if _process_is_rviz(item['pid']):
                item['window_visible']=None;write_state(path,state);return
        time.sleep(.2)
    terminate(item);state['processes'].pop('viewer',None);write_state(path,state)
    tail=logpath.read_text(errors='replace')[-1500:]
    raise ValueError(f'RViz2ウィンドウを確認できません。原因: {tail or "表示ウィンドウのPIDを確認できません"}')


def _process_is_rviz(pid):
    try: return 'rviz2' in Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace')
    except OSError: return False


def restart_viewer(state,path,logs,cfg):
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Ubuntuデスクトップの表示環境がありません。デスクトップから gouda.sh viewer を実行してください。')
    old=state['processes'].get('viewer',{})
    active_display=display_identity()
    if alive(old) and old.get('display') and old['display']!=active_display:
        raise ValueError('管理中のRViz2は別のデスクトップで動作中です。そのデスクトップで gouda.sh viewer を実行してください。')
    if alive(old): terminate(old)
    state['processes'].pop('viewer',None);write_state(path,state)
    start_viewer(state,path,logs,cfg)
    print('UbuntuデスクトップのRViz2ウィンドウを再起動しました。センサーは再起動していません。')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['view','observe','autonomy','viewer','doctor','stop'])
    args=parser.parse_args()
    root=runtime_dir(); root.mkdir(parents=True,exist_ok=True,mode=0o700)
    logs=logs_dir(); logs.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=(root/'lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    path=root/'processes.json'
    state=json.loads(path.read_text()) if path.exists() else {'mode':None,'processes':{}}
    if args.command=='stop':
        for name, item in reversed(list(state['processes'].items())):
            if name == 'processing':
                # MissionControl closes GLIM on SIGINT; allow the native graph dump to finish.
                terminate(item, graceful_signal=signal.SIGINT, timeout=180.0, initial_group=False)
            else:
                terminate(item)
        write_state(path,{'mode':None,'processes':{}})
        print('管理対象のプロセスを停止しました。'); return
    cfgfile=config_dir()/'host.json'
    cfg=json.loads(cfgfile.read_text()) if cfgfile.exists() else {}
    if args.command=='doctor':
        import shutil
        result={'config':str(cfgfile),'commands':{n:shutil.which(n) for n in ['ros2','rviz2','xwininfo']},
                'mode':state['mode'],'processes':{k:alive(v) for k,v in state['processes'].items()},
                'ports':{p:occupied(p) for p in (8765,8766,8443)},'viewer':display_status(state['processes'].get('viewer')),'display':{'DISPLAY':os.environ.get('DISPLAY'),'WAYLAND_DISPLAY':os.environ.get('WAYLAND_DISPLAY')},**status()}
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
    desired_mode='autonomy' if args.command=='autonomy' else 'observation'
    if state['mode'] not in (None,desired_mode) and any(alive(v) for v in state['processes'].values()):
        raise ValueError('以前の起動が稼働中です。先に gouda.sh stop を実行してください。')
    if args.command in ('observe','autonomy'): validate_hardware(cfg)

    env=dict(os.environ,ROS_DOMAIN_ID='99',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    env.pop('ROS_LOCALHOST_ONLY',None)
    launches=[]
    if args.command in ('observe','autonomy'):
        launches.append(('sensors',['ros2','launch','gouda_gui','sensors_only.launch.py',
                             'hesai_config:='+cfg['hesai_config'],'imu_device:='+cfg['imu_device']],[]))
    from gouda_navigation.mapping import load_mapping_settings
    mapping_backend = load_mapping_settings().get('backend', 'kiss_icp')
    if args.command=='autonomy' and mapping_backend!='glim_imu':
        raise ValueError('GUIの地図設定でGLIM + IMUを選択して保存してください。')
    launches.extend([
        ('processing',(['ros2','launch','gouda_gui','autonomy_mvp.launch.py'] if args.command=='autonomy' else ['ros2','launch','gouda_gui','observation.launch.py','sensors:=false',
                       'backend:='+mapping_backend]),[8765])])
    launches.append(('gateway',[sys.executable,'-m','gouda_gui.gateway'],[8766]))
    # Check all resources before starting sensors. Never adopt an unrelated process.
    for name,cmd,ports in launches:
        if not alive(state['processes'].get(name,{})):
            for port in ports:
                if occupied(port): raise ValueError(f'Port {port} is already used by another process.')

    state['mode']=desired_mode
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
    print('自動MVPを起動しました。走行開始はGUIで明示操作してください。' if args.command=='autonomy' else '実機走行出力は起動していません。終了: bash scripts/gouda.sh stop')


# The phone gateway imports these functions directly. Actions are an allowlist of
# existing Gouda profiles; no client-supplied command, path, or ROS goal is run.
LIFECYCLE_ACTIONS = {'start_observe', 'start_autonomy', 'stop', 'restart', 'apply_config'}
ACTIVE_RECORDING_PHASES = {'awaiting_sensor_data', 'recording', 'no_sensor_data', 'finalizing'}
ACTIVE_AUTONOMY_PHASES = {'arming', 'running', 'paused_manual', 'blocked'}
TERMINAL_AUTONOMY_PHASES = {'idle', 'cancelled', 'completed', 'fault'}
RECORDING_PHASES = {'idle', 'awaiting_sensor_data', 'recording', 'no_sensor_data', 'finalizing', 'completed', 'failed'}


def _read_process_state():
    path = runtime_dir()/'processes.json'
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('processes'), dict):
            raise ValueError('Malformed Gouda process state')
        return value
    except FileNotFoundError:
        return {'mode': None, 'processes': {}}


def runtime_status():
    """Return read-only process and backend status for the authenticated phone gateway."""
    state = _read_process_state()
    processes = {name: {'running': alive(item), 'pid': item.get('pid') if alive(item) else None}
                 for name, item in state['processes'].items()}
    result = {'mode': state.get('mode'), 'processes': processes,
              'lifecycle_busy': (runtime_dir()/'lifecycle.lock').exists() and _lock_is_held(runtime_dir()/'lifecycle.lock'),
              'backend': {'connected': False}}
    if any(v['running'] for k, v in processes.items() if k in ('processing', 'gateway')):
        try:
            with urlopen('http://127.0.0.1:8765/api/state', timeout=2) as response:
                snapshot = json.load(response)
                recording = snapshot.get('recording') if isinstance(snapshot, dict) else None
                autonomy = snapshot.get('autonomy') if isinstance(snapshot, dict) else None
                controller = autonomy.get('state') if isinstance(autonomy, dict) else None
                ages = snapshot.get('ages') if isinstance(snapshot, dict) else None
                result['backend'] = {
                    'connected': response.status == 200,
                    'recording_phase': recording.get('phase') if isinstance(recording, dict) else None,
                    'mapping': snapshot.get('mapping') if isinstance(snapshot.get('mapping'), bool) else None,
                    'autonomy': {
                        'profile_enabled': autonomy.get('profile_enabled') if isinstance(autonomy, dict) else None,
                        'state_fresh': autonomy.get('state_fresh') if isinstance(autonomy, dict) else None,
                        'phase': controller.get('phase') if isinstance(controller, dict) else None,
                        'device_fresh': controller.get('device_fresh') if isinstance(controller, dict) else None,
                    },
                    'esp_auto_enabled': (snapshot.get('esp') or {}).get('auto_enabled') if isinstance(snapshot.get('esp'), dict) else None,
                    'esp_age_sec': ages.get('esp32') if isinstance(ages, dict) else None,
                }
        except Exception as exc:
            result['backend'] = {'connected': False, 'error': str(exc)[:300]}
    return result


def _lock_is_held(path):
    try:
        with path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock, fcntl.LOCK_UN)
            return False
    except OSError:
        return True


def _ensure_disruption_safe(state=None):
    """Reject shutdown/restart whenever data capture or motion may be underway."""
    state = _read_process_state() if state is None else state
    processing = alive(state.get('processes', {}).get('processing', {}))
    if not processing:
        return
    try:
        with urlopen('http://127.0.0.1:8765/api/state', timeout=2) as response:
            if response.status != 200:
                raise RuntimeError('Backend state is unavailable; refusing to stop or restart a live runtime')
            backend = json.load(response)
    except Exception as exc:
        raise RuntimeError('Backend state is unavailable; refusing to stop or restart a live runtime') from exc
    recording = backend.get('recording')
    if not isinstance(recording, dict) or recording.get('phase') not in RECORDING_PHASES:
        raise RuntimeError('Recording state is missing or malformed; refusing to stop or restart a live runtime')
    if recording.get('phase') in ACTIVE_RECORDING_PHASES:
        raise RuntimeError('Recording is active or finalizing. Finish recording and verify its saved result before stopping or restarting.')
    if type(backend.get('mapping')) is not bool:
        raise RuntimeError('Mapping state is missing or malformed; refusing to stop or restart a live runtime')
    if backend['mapping']:
        raise RuntimeError('Mapping is active. Stop mapping and preserve its result before stopping or restarting.')
    if state.get('mode') == 'autonomy':
        autonomy = backend.get('autonomy')
        controller = autonomy.get('state') if isinstance(autonomy, dict) else None
        esp = backend.get('esp')
        ages = backend.get('ages')
        esp_age = ages.get('esp32') if isinstance(ages, dict) else None
        if (not isinstance(autonomy, dict) or autonomy.get('profile_enabled') is not True or
                autonomy.get('state_fresh') is not True or not isinstance(controller, dict) or
                controller.get('phase') not in TERMINAL_AUTONOMY_PHASES or
                controller.get('device_fresh') is not True or not isinstance(esp, dict) or
                esp.get('auto_enabled') is not False or not isinstance(esp_age, (int, float)) or not math.isfinite(esp_age) or
                esp_age < 0 or esp_age > .6):
            raise RuntimeError('Autonomy state or fresh ESP32 disarmed readback is missing, stale, or active; refusing to stop or restart')


def _profile(value):
    if value not in ('observation', 'autonomy'):
        raise ValueError('profile must be observation or autonomy')
    return value


def _run_profile(command):
    env = dict(os.environ, GOUDA_HEADLESS='1')
    result = subprocess.run([sys.executable, '-m', 'gouda_gui.runtime', command],
                            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=240)
    if result.returncode:
        raise RuntimeError((result.stdout or 'Gouda lifecycle command failed')[-1500:].strip())
    return result.stdout.strip()


def runtime_action(payload):
    """Run one fixed lifecycle operation. Caller must enforce remote auth and origin."""
    if not isinstance(payload, dict):
        raise ValueError('Lifecycle action must be a JSON object')
    action = payload.get('action')
    if action not in LIFECYCLE_ACTIONS:
        raise ValueError('Unsupported lifecycle action')
    # Reject extra command-like fields to keep the adapter's input surface narrow.
    permitted = {'action', 'profile'}
    if set(payload) - permitted:
        raise ValueError('Unsupported lifecycle fields')
    if 'profile' in payload and action != 'restart':
        raise ValueError('profile is accepted only for restart')
    lock_path = runtime_dir()/'lifecycle.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another lifecycle action is in progress') from exc
        state = _read_process_state()
        if action in ('start_observe', 'start_autonomy'):
            command = 'observe' if action == 'start_observe' else 'autonomy'
            output = _run_profile(command)
        elif action == 'stop':
            _ensure_disruption_safe(state)
            output = _run_profile('stop')
        elif action == 'restart':
            profile = _profile(payload.get('profile'))
            _ensure_disruption_safe(state)
            _run_profile('stop')
            output = _run_profile('observe' if profile == 'observation' else 'autonomy')
        else:  # apply_config restarts the currently selected fixed profile
            profile = state.get('mode')
            if profile not in ('observation', 'autonomy'):
                raise RuntimeError('There is no running profile to apply configuration to')
            _ensure_disruption_safe(state)
            _run_profile('stop')
            output = _run_profile('observe' if profile == 'observation' else 'autonomy')
    return {'ok': True, 'action': action, 'message': output, 'status': runtime_status()}


if __name__=='__main__':
    try: main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc: raise SystemExit(str(exc))

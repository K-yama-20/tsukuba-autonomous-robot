import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading

import pytest
from gouda_gui import runtime
from gouda_gui.gateway import allowed_path

spec=importlib.util.spec_from_file_location('configure_host',Path(__file__).parents[1]/'scripts/configure_host.py')
configure=importlib.util.module_from_spec(spec);spec.loader.exec_module(configure)


def test_stop_never_kills_reused_pid():
    process=subprocess.Popen(['sleep','10'],start_new_session=True)
    try:
        runtime.terminate({'pid':process.pid,'start':'incorrect-start-time'})
        assert process.poll() is None
        runtime.terminate({'pid':process.pid,'start':runtime.identity(process.pid)})
        process.wait(timeout=3)
    finally:
        if process.poll() is None: process.terminate();process.wait()


def test_hardware_requires_exclusive_ip(monkeypatch,tmp_path):
    from gouda_sensors import hesai_config
    monkeypatch.setattr(hesai_config,'checked_config',lambda *args:None)
    monkeypatch.setattr(os,'access',lambda *args:True)
    monkeypatch.setattr(Path,'exists',lambda *args:True)
    monkeypatch.setattr(subprocess,'check_output',lambda *args,**kwargs:json.dumps([
        {'ifname':dev,'addr_info':[{'local':'192.168.1.100'}]} for dev in ('eth1','eth2')]))
    with pytest.raises(ValueError,match='選択したLANだけ'):
        runtime.validate_hardware({'hesai_config':'test','imu_device':'test','lidar_interface':'eth1'})


def test_ptc_partial_reads_and_read_only_command():
    data=('Laser id,Elevation,Azimuth\n'+''.join(f'{i},0,0\n' for i in range(1,33))).encode()
    server=socket.socket();server.bind(('127.0.0.1',0));server.listen()
    requests=[]
    def serve():
        with server:
            conn,_=server.accept()
            with conn:
                requests.append(configure.recv_exact(conn,8))
                for b in struct.pack('!2sBBI',b'Gt',5,0,len(data))+data:
                    conn.sendall(bytes([b]))
    thread=threading.Thread(target=serve);thread.start()
    try: assert configure.fetch_correction('127.0.0.1',server.getsockname()[1])==data
    finally: thread.join(timeout=3)
    assert requests==[b'Gt\x05\x00\x00\x00\x00\x00']


@pytest.mark.parametrize('data',[b'example',b'Laser id,Elevation,Azimuth\n1,0,0',
    ('Laser id,Elevation,Azimuth\n'+''.join(f'{i},nan,0\n' for i in range(1,33))).encode()])
def test_calibration_rejects_truncated_or_invalid(data):
    with pytest.raises(ValueError):configure.validate_correction(data)


def test_gateway_only_known_routes():
    assert not allowed_path('/native/ws')
    assert allowed_path('/api/viewer')
    assert not allowed_path('/native/vendor/core/rfb.js')
    assert not allowed_path('/runtime/id_ed25519')
    assert not allowed_path('/api/unknown')


def test_viewer_launch_uses_display_and_ros_domain(monkeypatch,tmp_path):
    from ament_index_python import packages
    config=tmp_path/'kiss_icp'/'rviz';config.mkdir(parents=True)
    (config/'kiss_icp.rviz').write_text('upstream')
    monkeypatch.setattr(packages,'get_package_share_directory',lambda _:str(config.parent))
    monkeypatch.setenv('DISPLAY',':99');monkeypatch.setenv('WAYLAND_DISPLAY','wayland-0')
    for key in ('LIBGL_ALWAYS_SOFTWARE','LP_NUM_THREADS','MESA_GLTHREAD'):monkeypatch.delenv(key,raising=False)
    commands=[];environments=[];children=[]
    real_popen=subprocess.Popen
    def fake_popen(command,**kwargs):
        commands.append(command);environments.append(kwargs['env'])
        child=real_popen(['sleep','10'],start_new_session=True);children.append(child);return child
    monkeypatch.setattr(runtime.subprocess,'Popen',fake_popen)
    def fake_check_output(command,**kwargs):
        q=chr(34)
        if command[:2]==['xwininfo','-root']:
            return f'0x1 {q}Qt Selection Owner{q}\n0x2 {q}RViz splash{q}\n0x3 {q}kiss_icp.rviz - RViz{q}'
        if command[:2]==['xwininfo','-id']:
            return 'Map State: IsViewable\nWidth: 1920\nHeight: 1043'
        if command[0]=='xprop':
            return f'_NET_WM_PID(CARDINAL) = {children[0].pid}\nWM_CLASS(STRING) = {q}rviz2{q}, {q}rviz2{q}'
        raise AssertionError(command)
    monkeypatch.setattr(runtime.subprocess,'check_output',fake_check_output)
    state={'processes':{}}
    try:
        runtime.start_viewer(state,tmp_path/'state.json',tmp_path,{})
        env=environments[0]
        assert env['ROS_DOMAIN_ID']=='99'
        assert env['ROS_AUTOMATIC_DISCOVERY_RANGE']=='LOCALHOST'
        assert env['QT_QPA_PLATFORM']=='xcb'
        assert all(key not in env for key in ('LIBGL_ALWAYS_SOFTWARE','LP_NUM_THREADS','MESA_GLTHREAD'))
        assert state['processes']['viewer']['display']=='x11::99'
        assert state['processes']['viewer']['window_visible'] is True
        assert commands[0][0].endswith('/rviz2')
        assert commands[0][1:3]==['-d',str(config/'kiss_icp.rviz')]
        assert state['processes']['viewer']['pid']==children[0].pid
    finally:
        for child in children:
            if child.poll() is None:child.terminate();child.wait()


def test_display_failure_leaves_base_processes_running(monkeypatch,tmp_path):
    monkeypatch.delenv('DISPLAY',raising=False);monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    children=[];processes={}
    for name in ('sensors','processing','gateway'):
        child=subprocess.Popen(['sleep','10'],start_new_session=True);children.append(child)
        processes[name]={'pid':child.pid,'start':runtime.identity(child.pid)}
    state={'processes':processes}
    try:
        with pytest.raises(ValueError,match='表示環境'):
            runtime.start_viewer(state,tmp_path/'state.json',tmp_path,{})
        assert all(runtime.alive(item) for item in processes.values())
        assert state['processes']==processes
    finally:
        for child in children:
            if child.poll() is None:child.terminate();child.wait()


def test_viewer_restart_without_display_preserves_running_viewer(monkeypatch,tmp_path):
    monkeypatch.delenv('DISPLAY',raising=False);monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    process=subprocess.Popen(['sleep','10'],start_new_session=True)
    item={'pid':process.pid,'start':runtime.identity(process.pid),'display':':0'}
    state={'processes':{'viewer':item}}
    try:
        with pytest.raises(ValueError,match='表示環境'):
            runtime.restart_viewer(state,tmp_path/'state.json',tmp_path,{})
        assert process.poll() is None
        assert state['processes']['viewer']==item
    finally:
        process.terminate();process.wait()


def test_process_identity_includes_boot():
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert runtime.identity(os.getpid()).startswith(boot+':')
    assert not runtime.alive(None)


def test_window_detection_ignores_splash_and_other_process(monkeypatch):
    q=chr(34)
    props_pid=[9001]
    def fake_check_output(command,**kwargs):
        if command[:2]==['xwininfo','-root']:
            return f'0x1 {q}Qt Selection Owner{q}\n0x2 {q}RViz splash{q}\n0x3 {q}kiss_icp.rviz - RViz{q}'
        if command[:2]==['xwininfo','-id']:
            return 'Map State: IsViewable\nWidth: 1920\nHeight: 1043'
        if command[0]=='xprop':
            return f'_NET_WM_PID(CARDINAL) = {props_pid[0]}\nWM_CLASS(STRING) = {q}rviz2{q}, {q}rviz2{q}'
        raise AssertionError(command)
    monkeypatch.setattr(runtime.subprocess,'check_output',fake_check_output)
    assert runtime.rviz_window_for_pid(42) is False
    props_pid[0]=42
    assert runtime.rviz_window_for_pid(42) is True


def test_display_identity_prefers_xwayland_when_display_exists():
    assert runtime.display_identity({'DISPLAY':':99','WAYLAND_DISPLAY':'wayland-0'})=='x11::99'
    assert runtime.display_identity({'WAYLAND_DISPLAY':'wayland-0'})=='wayland:wayland-0'


def test_pure_wayland_readiness_waits_and_reports_unknown_window(monkeypatch,tmp_path):
    from ament_index_python import packages
    config=tmp_path/'kiss_icp'/'rviz';config.mkdir(parents=True)
    (config/'kiss_icp.rviz').write_text('upstream')
    monkeypatch.setattr(packages,'get_package_share_directory',lambda _:str(config.parent))
    monkeypatch.delenv('DISPLAY',raising=False);monkeypatch.setenv('WAYLAND_DISPLAY','wayland-0')
    children=[];real_popen=subprocess.Popen
    def fake_popen(command,**kwargs):
        child=real_popen(['sleep','10'],start_new_session=True);children.append(child);return child
    monkeypatch.setattr(runtime.subprocess,'Popen',fake_popen)
    monkeypatch.setattr(runtime,'_process_is_rviz',lambda pid:True)
    ticks=[0.]
    monkeypatch.setattr(runtime.time,'monotonic',lambda:ticks[0])
    monkeypatch.setattr(runtime.time,'sleep',lambda seconds:ticks.__setitem__(0,ticks[0]+seconds))
    state={'processes':{}}
    try:
        runtime.start_viewer(state,tmp_path/'state.json',tmp_path,{})
        assert ticks[0]>=3.
        assert state['processes']['viewer']['window_visible'] is None
        assert state['processes']['viewer']['display']=='wayland:wayland-0'
    finally:
        for child in children:
            if child.poll() is None:child.terminate();child.wait()

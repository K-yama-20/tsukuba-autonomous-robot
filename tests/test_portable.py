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


def test_state_locations_respect_xdg(monkeypatch,tmp_path):
    from gouda_gui.paths import config_dir,data_dir
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    assert config_dir()==tmp_path/'config/gouda'
    assert data_dir()==tmp_path/'data/gouda'


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
    assert allowed_path('/native/ws')
    assert allowed_path('/api/viewer')
    assert not allowed_path('/runtime/id_ed25519')
    assert not allowed_path('/api/unknown')


def test_process_identity_includes_boot():
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert runtime.identity(os.getpid()).startswith(boot+':')

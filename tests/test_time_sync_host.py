import importlib.util
import json
from pathlib import Path
import pytest
import yaml

spec=importlib.util.spec_from_file_location('time_sync_host',Path(__file__).parents[1]/'scripts/time_sync_host.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)

def test_prepare_backs_up_and_preserves_unknown_calibration(tmp_path):
    root=tmp_path/'bags/gouda';root.mkdir(parents=True)
    old=root/'old.yaml';old.write_text(yaml.safe_dump({'lidar':[{'driver':{'source_type':1,'use_timestamp_type':1}}]}))
    (root/'host.json').write_text(json.dumps(dict(hesai_config=str(old),imu_device='/dev/example')))
    (root/'mapping.json').write_text(json.dumps(dict(extrinsic_lidar_imu=None,imu_clock_offset_sec=None,lidar_clock_offset_sec=None)))
    result=host.prepare(tmp_path,'No sync wire; test-only evidence')
    backup=Path(result['backup']);assert (backup/'host.before.json').is_file()
    assert yaml.safe_load(old.read_text())['lidar'][0]['driver']['use_timestamp_type']==1
    cfg=json.loads((root/'host.json').read_text())
    assert cfg['imu_device']=='/dev/example'
    assert yaml.safe_load(Path(cfg['hesai_config']).read_text())['lidar'][0]['driver']['use_timestamp_type']==0
    mapping=json.loads((root/'mapping.json').read_text())
    assert mapping['clock_policy']=='host_mapped'
    assert mapping['imu_clock_offset_sec'] is None and mapping['extrinsic_lidar_imu'] is None
    again=host.prepare(tmp_path,'second recorded inspection')
    assert again['backup']!=result['backup']

def test_inspection_never_claims_hardware_lock(tmp_path):
    result=host.inspect_host(tmp_path)
    assert result['hardware_synchronized'] is False
    assert result['lidar_lock'].startswith('UNKNOWN')
    assert 'configuration_error' in result

def test_ptp_rejects_invalid_or_missing_interface():
    for value in ('bad/interface','eth0; reboot','notexist999'):
        with pytest.raises(ValueError):host.ptp_command(value)

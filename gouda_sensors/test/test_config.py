from copy import deepcopy
import yaml
import pytest
from gouda_sensors.hesai_config import checked_config


def test_profile_requires_known_network_and_correction(tmp_path):
    correction=tmp_path/'correction.csv';correction.write_text('device calibration')
    d={'source_type':1,'transform_flag':False,'use_timestamp_type':1,
       'lidar_udp_type':{'device_ip_address':'192.168.1.201','host_ip_address':'192.168.1.100',
       'udp_port':2368,'ptc_port':9347,'correction_file_path':str(correction),'firetimes_path':''}}
    r={'ros_frame_id':'hesai_lidar','ros_send_point_cloud_topic':'/lidar_points','send_point_cloud_ros':True}
    path=tmp_path/'config.yaml'
    config={'lidar':[{'driver':d,'ros':r}]};path.write_text(yaml.safe_dump(config))
    assert checked_config(path,'hardware')
    with pytest.raises(ValueError):checked_config(path,'pcap')
    for key,value in [('device_ip_address',None),('udp_port',None),('correction_file_path','Your correction file path')]:
        changed=deepcopy(config);changed['lidar'][0]['driver']['lidar_udp_type'][key]=value
        path.write_text(yaml.safe_dump(changed))
        with pytest.raises((ValueError,TypeError)):checked_config(path,'hardware')

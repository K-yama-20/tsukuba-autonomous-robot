"""Validate the selected source without silently accepting upstream sample values."""
from ipaddress import ip_address
from pathlib import Path
import yaml


def checked_config(path, mode):
    if mode not in ('hardware', 'pcap', 'packet_replay'):
        raise ValueError('mode must be hardware, pcap, or packet_replay')
    data = yaml.safe_load(Path(path).read_text())
    items = data.get('lidar', [])
    if len(items) != 1:
        raise ValueError('exactly one LiDAR must be configured')
    driver, ros = items[0]['driver'], items[0]['ros']
    expected = {'hardware': 1, 'pcap': 2, 'packet_replay': 3}[mode]
    if driver.get('source_type') != expected:
        raise ValueError('source_type does not match selected mode')
    if driver.get('transform_flag') is not False:
        raise ValueError('TF owns extrinsics; driver transform_flag must be false')
    if driver.get('use_timestamp_type') not in (0, 1):
        raise ValueError('timestamp source must be explicitly selected')
    if ros.get('ros_frame_id') != 'hesai_lidar' or ros.get('ros_send_point_cloud_topic') != '/lidar_points':
        raise ValueError('unexpected cloud frame/topic')
    if ros.get('send_point_cloud_ros') is not True:
        raise ValueError('point cloud publishing must be enabled')
    block = driver[{'hardware': 'lidar_udp_type', 'pcap': 'pcap_type', 'packet_replay': 'rosbag_type'}[mode]]
    if mode == 'hardware':
        for key in ('device_ip_address', 'host_ip_address'):
            ip_address(block[key])
        for key in ('udp_port', 'ptc_port'):
            if type(block[key]) is not int or not 1 <= block[key] <= 65535:
                raise ValueError('invalid ' + key)
        if driver.get('standby_mode', -1) != -1 or block.get('standby_mode', -1) != -1 or block.get('speed', -1) != -1:
            raise ValueError('sensor reconfiguration is outside bringup')
    for key in ('correction_file_path', 'firetimes_path'):
        value = block.get(key)
        if value == '' and key == 'firetimes_path':
            continue  # explicit unused; applicability still needs device validation
        if not value or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError('missing verified file: ' + key)
    if mode == 'pcap' and not Path(block['pcap_path']).is_file():
        raise ValueError('PCAP not found')
    return data

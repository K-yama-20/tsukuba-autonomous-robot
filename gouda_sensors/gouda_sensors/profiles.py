"""Create an explicit profile from the pinned upstream schema and local evidence."""
from pathlib import Path
from copy import deepcopy
import yaml


def make_profile(upstream, mode, correction, *, device=None, host=None, udp=None, ptc=None, pcap=None, timestamp_source="receive"):
    if timestamp_source not in ("receive", "sensor"):raise ValueError("unknown timestamp source")
    config=deepcopy(yaml.safe_load(Path(upstream).read_text()))
    if mode not in ('hardware','pcap','packet_replay'):raise ValueError('unknown mode')
    d=config['lidar'][0]['driver'];r=config['lidar'][0]['ros']
    d.update(source_type={'hardware':1,'pcap':2,'packet_replay':3}[mode],use_gpu=False,
             use_timestamp_type=0 if timestamp_source == "sensor" else 1,transform_flag=False,thread_num=2,channel_fov_filter_path='')
    # PC receive time is a declared fallback; it is NOT calibrated synchronization.
    # Firetime is intentionally unavailable. Keep this in the measurement limitations.
    for key in ('lidar_udp_type','pcap_type','rosbag_type'):
        d[key].update(correction_file_path=str(Path(correction).resolve()),firetimes_path='')
    d['lidar_udp_type'].update(device_ip_address=device,host_ip_address=host,udp_port=udp,
        ptc_port=ptc,multicast_ip_address='',standby_mode=-1,speed=-1,
        recv_point_cloud_timeout=3,ptc_connect_timeout=3)
    d['pcap_type']['pcap_path']=pcap or ''
    r.update(ros_frame_id='hesai_lidar',ros_send_point_cloud_topic='/lidar_points',
             ros_send_packet_topic='/lidar_packets',ros_recv_packet_topic='/lidar_packets',
             ros_send_correction_topic='/lidar_corrections',send_packet_ros=mode=='hardware',
             send_point_cloud_ros=True,send_imu_ros=False)
    return config


def main():
    import argparse
    from .hesai_config import checked_config
    parser=argparse.ArgumentParser(description='Prepare host-side config only; never changes a sensor')
    parser.add_argument('--upstream',required=True)
    parser.add_argument('--correction',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--mode',choices=['hardware','pcap','packet_replay'],required=True)
    parser.add_argument('--device-ip');parser.add_argument('--host-ip')
    parser.add_argument('--udp',type=int);parser.add_argument('--ptc',type=int)
    parser.add_argument('--pcap')
    parser.add_argument('--timestamp-source', choices=['receive','sensor'], default='receive')
    args=parser.parse_args()
    target=Path(args.output)
    if target.exists():parser.error('output exists; choose a new path')
    config=make_profile(args.upstream,args.mode,args.correction,device=args.device_ip,host=args.host_ip,
                        udp=args.udp,ptc=args.ptc,pcap=args.pcap,timestamp_source=args.timestamp_source)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w',suffix='.yaml') as test:
        yaml.safe_dump(config,test);test.flush();checked_config(test.name,args.mode)
    target.write_text(yaml.safe_dump(config))
    print(str(target.resolve()))
    print('Timestamp source: '+args.timestamp_source+'; external clock lock, firetime and mounting remain unverified.')

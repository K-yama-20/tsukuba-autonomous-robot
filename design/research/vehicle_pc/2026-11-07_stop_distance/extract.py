"""停止距離の解析（DEC-346 (1)・DEC-377 (1)・DEC-378 (1)）の前段: rosbag (mcap) から CSV を抜き出す。
ROS 2 Jazzy のある計算機で実行する（rosbag2_py が要る）。生データと CSV はリポジトリに入れない。

usage: python3 extract.py <bag_dir> <out_dir>
  -> <out_dir>/hold.csv      control/motion_hold（IFD-40）: t, stamp, hold, mode, reason
     <out_dir>/odom.csv      localization/odometry（IFD-25）: t, stamp, x, y, yaw
     <out_dir>/decision.csv  log/decision（IFD-28、gouda_mode_manager の rule_stop_hold だけ）: t, stamp, event, details
     <out_dir>/esp32.csv     /esp32/status（IFD-38）: t, stamp, source, manual_y_q10000, applied_y_q10000
t は rosbag が受け取った時刻、stamp はメッセージの header.stamp（どちらも秒）。bag にない topic の CSV は見出しだけになる。
"""
import csv
import math
import sys
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

WANTED = {'control/motion_hold': 'hold', 'localization/odometry': 'odom', 'log/decision': 'decision', 'esp32/status': 'esp32'}
ESP32_KEYS = ['source', 'manual_y_q10000', 'applied_y_q10000']
HEADERS = {'hold': ['t', 'stamp', 'hold', 'mode', 'reason'], 'odom': ['t', 'stamp', 'x', 'y', 'yaw'],
           'decision': ['t', 'stamp', 'event', 'details'], 'esp32': ['t', 'stamp'] + ESP32_KEYS}


def stamp_s(header):
    return header.stamp.sec + header.stamp.nanosec * 1e-9


def rows_of(kind, m):
    """The CSV rows (without t) of one message."""
    if kind == 'hold':
        return [[f'{stamp_s(m.header):.6f}', int(m.hold), int(m.mode), m.reason]]
    if kind == 'odom':
        p, q = m.pose.pose.position, m.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        return [[f'{stamp_s(m.header):.6f}', p.x, p.y, yaw]]
    if kind == 'decision':
        if m.node != 'gouda_mode_manager' or m.event != 'rule_stop_hold':
            return []
        return [[f'{stamp_s(m.header):.6f}', m.event, m.details]]
    out = []
    for st in m.status:
        v = {kv.key: kv.value for kv in st.values}
        if 'applied_y_q10000' in v:
            out.append([f'{stamp_s(m.header):.6f}'] + [v.get(k, '') for k in ESP32_KEYS])
    return out


def main():
    bag, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    kinds = {name: kind for name in types for want, kind in WANTED.items() if name.strip('/') == want}
    files = {kind: open(out / f'{kind}.csv', 'w', newline='', encoding='utf-8') for kind in HEADERS}
    writers = {kind: csv.writer(f) for kind, f in files.items()}
    for kind, w in writers.items():
        w.writerow(HEADERS[kind])
    counts = {kind: 0 for kind in HEADERS}
    if kinds:
        reader.set_filter(rosbag2_py.StorageFilter(topics=list(kinds)))
        while reader.has_next():
            topic, data, ts = reader.read_next()
            kind = kinds[topic]
            for row in rows_of(kind, deserialize_message(data, get_message(types[topic]))):
                writers[kind].writerow([f'{ts * 1e-9:.6f}'] + row)
                counts[kind] += 1
    for f in files.values():
        f.close()
    print('rows:', counts)
    missing = sorted(set(WANTED) - {n.strip('/') for n in kinds})
    if missing:
        print('topics not in the bag:', missing)


if __name__ == '__main__':
    main()

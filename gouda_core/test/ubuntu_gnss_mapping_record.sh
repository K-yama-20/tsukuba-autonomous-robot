#!/bin/bash
# DEC-126 VM test (REV-063): GNSS recorded during 事前地図作成 and registered next to the source map.
# Test only: the septentrio_gnss_driver message types are read from an extracted copy of the ROS apt package (UPSTREAM_EXTRACT;
# not installed on the VM: no sudo). GNSS messages are published by this script (no receiver); GLIM runs without sensor data.
#   G1 mapping start -> GNSS messages (navsatfix, pvtgeodetic, atteuler, attcoveuler) -> mapping end -> gnss.jsonl next to source/
#   G2 mapping with no GNSS message -> record has no GNSS line; mapping is not stopped
set -o pipefail
WS=~/gouda_fix_ws; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/gnssrec
X=${UPSTREAM_EXTRACT:-$HOME/upstream_pkgs/x}
export ROS_DOMAIN_ID=77
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
export AMENT_PREFIX_PATH=$X/opt/ros/jazzy:$AMENT_PREFIX_PATH PYTHONPATH=$X/opt/ros/jazzy/lib/python3.12/site-packages:$PYTHONPATH LD_LIBRARY_PATH=$X/opt/ros/jazzy/lib:$LD_LIBRARY_PATH
rm -rf $ROOT; mkdir -p $ROOT
bash $REPO/gouda_core/test/stack.sh start $ROOT || exit 1
trap 'bash $REPO/gouda_core/test/stack.sh stop $ROOT' EXIT
URL=$(cat $ROOT/run/monitor.url)
svc() { ros2 service call "/$1" std_srvs/srv/Trigger "{}" 2>&1 | grep -oE "success=(True|False), message='[^']*'" ; }
ev() { curl -s "$URL/api/state" | python3 -c "
import json,sys; s=json.load(sys.stdin)
for e in reversed(s['events']):
    if e['event'] in ('gnss_record_started','gnss_record_stopped','source_map_registered','source_map_not_registered'): print('  ', e['transition_id'], e['event'], '|', e['reason'][:220], '| x%d' % e['count'])"; }
echo "=== G0 /config saved (antenna and LiDAR mounting; the snapshot of the run is registered with the source map: REV-067)"
curl -s -X POST -H 'Content-Type: application/json' -d '{"gnss_main_mount_x_m": "-0.2", "gnss_main_mount_z_m": "0.85", "lidar_mount_z_m": "0.9"}' "$URL/api/config" | head -c 120; echo
echo "=== G1 mapping with GNSS messages"
svc mode/start_mapping; sleep 3
python3 - <<'PY'
import time, rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import NavSatFix
from septentrio_gnss_driver.msg import PVTGeodetic, AttEuler, AttCovEuler
rclpy.init(); n = rclpy.create_node('gnss_fake')
q = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
pubs = [(n.create_publisher(NavSatFix, 'sensors/gnss/navsatfix', q), NavSatFix), (n.create_publisher(PVTGeodetic, 'sensors/gnss/pvtgeodetic', q), PVTGeodetic),
        (n.create_publisher(AttEuler, 'sensors/gnss/atteuler', q), AttEuler), (n.create_publisher(AttCovEuler, 'sensors/gnss/attcoveuler', q), AttCovEuler)]
time.sleep(3)   # discovery
for i in range(20):
    for p, T in pubs:
        m = T(); m.header.stamp = n.get_clock().now().to_msg()
        if T is NavSatFix: m.latitude, m.longitude = 36.08 + i * 1e-6, 140.11
        if T is PVTGeodetic: m.mode = 4; m.nr_sv = 20; m.h_accuracy = 2
        if T is AttEuler: m.mode = 2; m.heading = 90.0
        p.publish(m)
    time.sleep(0.1)
time.sleep(1); print('published 20 x 4 messages')
PY
svc mode/end_mapping; sleep 12
ev
O=$(ls -d $ROOT/maps/*/ 2>/dev/null | head -1)
echo "source map dir: $O"; ls $O 2>/dev/null
python3 -c "import json,hashlib; m=json.load(open('$O/source_manifest.json')); print('manifest sensor_config:', m.get('sensor_config')); print('file sha256 matches:', hashlib.sha256(open('$O/sensor_config.json','rb').read()).hexdigest()==m['sensor_config']['sha256'])"
python3 -c "import json,sys; m=json.load(open('$O/source_manifest.json')); print('manifest gnss:', m.get('gnss')); print('source content_hash:', m['content_hash'][:16])" 2>&1
[ -f $O/gnss.jsonl ] && { echo "gnss.jsonl lines: $(wc -l < $O/gnss.jsonl), sha256: $(sha256sum $O/gnss.jsonl | cut -c1-64)"; head -c 400 $O/gnss.jsonl; echo; grep -c pvtgeodetic $O/gnss.jsonl; }
echo "=== G2 mapping without GNSS messages"
svc mode/start_mapping; sleep 4; svc mode/end_mapping; sleep 12
ev | tail -3

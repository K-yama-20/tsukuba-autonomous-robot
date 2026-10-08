"""Read-only upstream evidence capture; never runs downloaded source.

The commit is pinned by research/upstream_jazzy/evidence.json once captured, so
re-runs add files at the same upstream revision instead of silently moving it.
This records the upstream jazzy branch, not the version installed on the vehicle PC.
"""
import hashlib,json,urllib.request
from pathlib import Path
D=Path(__file__).resolve().parents[1]
OUT=D/'research/upstream_jazzy'
PATHS=['nav2_msgs/action/NavigateThroughPoses.action','nav2_msgs/action/NavigateToPose.action','nav2_msgs/msg/SpeedLimit.msg','nav2_controller/src/controller_server.cpp','nav2_util/include/nav2_util/twist_publisher.hpp','nav2_route/package.xml','nav2_route/src/plugins/route_operations/adjust_speed_limit.cpp','nav2_costmap_2d/plugins/costmap_filters/speed_filter.cpp','nav2_bt_navigator/package.xml',
       # Added for REV-002: pass judgement, default BT, filter info type, cancel behaviour
       'nav2_behavior_tree/plugins/action/remove_passed_goals_action.cpp','nav2_bt_navigator/behavior_trees/navigate_through_poses_w_replanning_and_recovery.xml','nav2_msgs/msg/CostmapFilterInfo.msg','nav2_costmap_2d/include/nav2_costmap_2d/costmap_filters/speed_filter.hpp','nav2_msgs/package.xml','nav2_bt_navigator/src/navigators/navigate_through_poses.cpp',
       # Added for REV-003: QoS of map, costmap and plan publishers
       'nav2_map_server/src/map_server/map_server.cpp','nav2_costmap_2d/src/costmap_2d_publisher.cpp','nav2_planner/src/planner_server.cpp',
       # Added for REV-006: filter placement, re-initialisation, lifecycle bond, default params
       'nav2_costmap_2d/src/costmap_2d_ros.cpp','nav2_costmap_2d/plugins/costmap_filters/costmap_filter.cpp','nav2_costmap_2d/include/nav2_costmap_2d/costmap_filters/costmap_filter.hpp','nav2_lifecycle_manager/src/lifecycle_manager.cpp','nav2_lifecycle_manager/include/nav2_lifecycle_manager/lifecycle_manager.hpp','nav2_bringup/params/nav2_params.yaml','nav2_mppi_controller/src/controller.cpp','nav2_dwb_controller/dwb_core/src/dwb_local_planner.cpp','nav2_regulated_pure_pursuit_controller/src/regulated_pure_pursuit_controller.cpp','nav2_controller/include/nav2_controller/controller_server.hpp','nav2_bringup/launch/navigation_launch.py','nav2_bringup/launch/bringup_launch.py']
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Gouda-design-evidence'})
    with urllib.request.urlopen(req,timeout=30) as f: return f.read()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    ev=OUT/'evidence.json'
    if ev.exists(): commit=json.loads(ev.read_text())['commit']
    else: commit=json.loads(get('https://api.github.com/repos/ros-navigation/navigation2/commits/jazzy'))['sha']
    records=[]
    for p in PATHS:
        url=f'https://raw.githubusercontent.com/ros-navigation/navigation2/{commit}/{p}'
        target=OUT/p
        if not target.exists():
            b=get(url); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b)
        records.append(dict(path=str(target.relative_to(D)),url=url,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    url='https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0103.rst'
    target=OUT/'rep-0103.rst'
    if not target.exists(): target.write_bytes(get(url))
    records.append(dict(path=str(target.relative_to(D)),url=url,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    ev.write_text(json.dumps(dict(repository='ros-navigation/navigation2',branch='jazzy',commit=commit,vehicle_installation_verified=False,records=records),indent=2)+'\n')
    print('Captured upstream commit',commit,'; not the installed vehicle version;',len(records),'files')
if __name__=='__main__': main()

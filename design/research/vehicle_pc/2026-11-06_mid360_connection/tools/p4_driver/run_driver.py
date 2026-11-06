#!/usr/bin/env python3
"""P4: start livox_ros_driver2 ONLY (no Gouda), with the parameters the product gives it (gouda_core.mid360_config.driver_parameters,
REV-242: xfer_format 0 = PointCloud2, frame_id mid360_link, user_config_path) and the product's node name, through
`ros2 run ... --ros-args` (the upstream launch msg_MID360_launch.py has no launch arguments: it fixes xfer_format 1 and the template
in share/, so it cannot be used without editing). The topics are the driver's own (livox/lidar, livox/imu; not remapped).

    python3 run_driver.py --config <outside the repository>/MID360_config.json [--dry-run]

--dry-run prints the command and starts nothing. Otherwise the command is printed and this process becomes it (exec); stop with Ctrl-C.
Load the driver first: source <workspace>_livox/install/setup.bash
"""
from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_common  # noqa: E402


def build_command(config_path: str, m3=None) -> list:
    m3 = m3 or p4_common.import_mid360_config()
    params = m3.driver_parameters(os.path.abspath(os.path.expanduser(config_path)))
    return (['ros2', 'run', m3.DRIVER_PACKAGE, m3.DRIVER_EXECUTABLE, '--ros-args', '-r', f'__node:={m3.DRIVER_NODE}']
            + p4_common.ros_param_args(params))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--config', required=True, help='the driver config written by make_config.py')
    ap.add_argument('--dry-run', action='store_true', help='print the command only')
    args = ap.parse_args(argv)
    m3 = p4_common.import_mid360_config()
    cmd = build_command(args.config, m3)
    print('command: ' + shlex.join(cmd))
    print(f'topics: {p4_common.absolute_topic(m3.DRIVER_TOPIC)} (sensor_msgs/msg/PointCloud2, frame_id {m3.FRAME}), '
          f'{p4_common.absolute_topic(p4_common.IMU_TOPIC)} (sensor_msgs/msg/Imu, frame_id {p4_common.IMU_FRAME}: fixed in the driver)')
    sys.stdout.flush()
    if args.dry_run:
        return 0
    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError:
        print('ERROR: ros2 not found: source /opt/ros/jazzy/setup.bash and <workspace>_livox/install/setup.bash first', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

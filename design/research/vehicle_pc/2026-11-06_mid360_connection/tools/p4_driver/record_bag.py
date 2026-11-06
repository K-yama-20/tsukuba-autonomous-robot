#!/usr/bin/env python3
"""P4 T04-6: record the MID-360 point cloud and IMU (the driver's own topics) to a rosbag outside the repository for --duration seconds
(default 60, the plan's T04-6), then send the recorder ONE SIGINT (as Ctrl-C does) and wait, without a time limit, until it has
closed the bag.

    python3 record_bag.py --out <outside the repository>/<new folder> [--duration 60] [--dry-run]

The folder must not exist yet (ros2 bag record refuses an existing one). Storage: the rosbag2 default (mcap on Jazzy), as the
product's recorder (gouda_core/recorder_node.py). Keyboard controls are off, so the recorder never reads the terminal.
The topics are given positionally, which every Jazzy rosbag2 accepts ('--topics' exists only from 0.26.4; newer versions print a
deprecation warning for the positional form). Ctrl-C before the end stops the recording early (the recorder gets that SIGINT itself).
--dry-run prints the command and records nothing.
"""
from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_common  # noqa: E402

DEFAULT_DURATION_S = 60   # plan T04-6 「rosbag を 60 s 記録」 (a test condition of the plan, changeable with --duration)


def build_command(out_dir: str, m3=None) -> list:
    m3 = m3 or p4_common.import_mid360_config()
    topics = [p4_common.absolute_topic(m3.DRIVER_TOPIC), p4_common.absolute_topic(p4_common.IMU_TOPIC)]
    return ['ros2', 'bag', 'record', '--disable-keyboard-controls', '-o', os.path.abspath(os.path.expanduser(out_dir))] + topics


def record(cmd: list, duration_s: float) -> int:
    """Run cmd; after duration_s send one SIGINT; wait for the end. The return code is the recorder's."""
    proc = subprocess.Popen(cmd)   # same process group: a Ctrl-C in the terminal reaches the recorder directly
    try:
        try:
            return proc.wait(timeout=duration_s)   # it ended by itself (an error, or Ctrl-C)
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGINT)
        return proc.wait()
    except KeyboardInterrupt:   # the recorder got the same Ctrl-C; do not signal it again, only wait until the bag is closed
        while True:
            try:
                return proc.wait()
            except KeyboardInterrupt:
                continue


def _positive_int(text: str) -> int:
    v = int(text)
    if v <= 0:
        raise argparse.ArgumentTypeError('must be a positive number of seconds')
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True, help='the bag folder to create (outside the repository; must not exist)')
    ap.add_argument('--duration', type=_positive_int, default=DEFAULT_DURATION_S, help='seconds (default %(default)s)')
    ap.add_argument('--dry-run', action='store_true', help='print the command only')
    args = ap.parse_args(argv)
    cmd = build_command(args.out)
    print('command: ' + shlex.join(cmd))
    print(f'stop: one SIGINT after {args.duration} s, then wait until the recorder has closed the bag')
    print('after it ends: ros2 bag info ' + shlex.quote(cmd[cmd.index('-o') + 1]))
    sys.stdout.flush()
    if args.dry_run:
        return 0
    try:
        return record(cmd, args.duration)
    except FileNotFoundError:
        print('ERROR: ros2 not found: source /opt/ros/jazzy/setup.bash first', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

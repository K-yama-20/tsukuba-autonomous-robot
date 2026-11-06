"""Shared parts of the P4 tools (MID-360 test plan P4, design/proposals/mid360_connection_test_plan_2026-11-06.md; DEC-474 / DEC-475,
flow E). No ROS dependency, so the tools can be tested on a PC without ROS.

The product's gouda_core.mid360_config (REV-242) is imported from THIS checkout of the repository (never copied), so the driver
config of P4 is made exactly as the product makes it at the same commit."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]          # <repo>/design/research/vehicle_pc/<date>/tools/p4_driver/p4_common.py
GOUDA_CORE_DIR = REPO / 'gouda_core'                # the ament package folder; the Python package is gouda_core/gouda_core
IMU_TOPIC = 'livox/imu'                             # the driver's own IMU topic with multi_topic 0 (upstream src/lddc.cpp:684, 2144554)
IMU_FRAME = 'livox_frame'                           # fixed in the driver for the IMU, whatever frame_id is (upstream src/lddc.cpp:481)


def import_mid360_config():
    """gouda_core.mid360_config of this checkout (inserted before an installed gouda_core, so both always come from one commit)."""
    if not (GOUDA_CORE_DIR / 'gouda_core' / 'mid360_config.py').is_file():
        raise SystemExit(f'gouda_core/gouda_core/mid360_config.py not found under {REPO}: keep this folder inside the repository')
    if sys.path[:1] != [str(GOUDA_CORE_DIR)]:
        sys.path.insert(0, str(GOUDA_CORE_DIR))
    from gouda_core import mid360_config
    return mid360_config


def repo_commit() -> str:
    """The checkout's commit (for the record), with '+changes' when gouda_core/gouda_core differs from it; 'unknown' without git."""
    try:
        head = subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--', 'gouda_core/gouda_core'],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'
    return head + ('+changes' if dirty else '')


def absolute_topic(name: str) -> str:
    """The driver node runs in the root namespace, so its relative topic 'livox/lidar' is '/livox/lidar'."""
    return name if name.startswith('/') else '/' + name


_PLAIN = re.compile(r'[A-Za-z_/][A-Za-z0-9_./-]*')
_YAML_WORDS = {'true', 'false', 'yes', 'no', 'on', 'off', 'y', 'n', 'null', '~'}


def yaml_scalar(value) -> str:
    """A value for `--ros-args -p name:=value`. rcl reads the value as YAML, so the type must be visible in the text: int as is, float
    with a point (10.0, never 10: the driver declares publish_freq as double), and a string plain only when YAML would keep it a string;
    otherwise double-quoted (a JSON string is a YAML double-quoted scalar), e.g. a path with ' #' or ': ' in it."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        if _PLAIN.fullmatch(value) and value.lower() not in _YAML_WORDS:
            return value
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f'unsupported parameter type {type(value).__name__}')


def ros_param_args(params: dict) -> list:
    out = []
    for name, value in params.items():
        out += ['-p', f'{name}:={yaml_scalar(value)}']
    return out

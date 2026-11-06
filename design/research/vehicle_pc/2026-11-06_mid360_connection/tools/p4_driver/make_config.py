#!/usr/bin/env python3
"""P4: write the livox_ros_driver2 config (MID360_config.json) from the vehicle PC's mid360.json (IFD-61) and the driver's installed
template, the way the product does it (gouda_core.mid360_config.read_local / find_template / write_driver_config, REV-242):
only the addresses are replaced, the extrinsic stays zero, every other template value stays as upstream.

    python3 make_config.py --mid360-json <data_root>/config/mid360.json --out <outside the repository>/MID360_config.json
                           [--template <share>/livox_ros_driver2/config/MID360_config.json]

Without --template the template is found from the loaded ROS environment (source <workspace>_livox/install/setup.bash).
P4 needs only host_ip and lidar_ip of mid360.json; missing mounting values are reported but do not stop P4 (the product's MID-360
path does need them). The written file holds the addresses: it is never printed here and must stay outside the repository.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_common  # noqa: E402


def changed_paths(a, b, path: str = '') -> list:
    """The JSON paths whose values differ between a and b (names only, never the values)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            sub = f'{path}.{k}' if path else k
            out += changed_paths(a.get(k), b.get(k), sub) if (k in a and k in b) else [sub]
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += changed_paths(x, y, f'{path}[{i}]')
        return out
    return [] if (a == b and type(a) is type(b)) else [path]


def find_installed_template(m3) -> tuple:
    """(template path or None, reason) from the loaded ROS environment, as gouda_nav2.launch.py does."""
    try:
        from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
    except ImportError:
        return None, 'ROS is not loaded (no ament_index_python): give --template, or source <workspace>_livox/install/setup.bash'
    try:
        share = get_package_share_directory(m3.DRIVER_PACKAGE)
    except PackageNotFoundError:
        return None, f'{m3.DRIVER_PACKAGE} is not found: source <workspace>_livox/install/setup.bash (setup.sh builds it there)'
    tpl = m3.find_template(share)
    return (tpl, '') if tpl else (None, f'{share}/config/{m3.TEMPLATE_NAME} does not exist')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--mid360-json', required=True, help='the vehicle PC\'s mid360.json (IFD-61), e.g. <data_root>/config/mid360.json')
    ap.add_argument('--out', required=True, help='the driver config to write (outside the repository)')
    ap.add_argument('--template', help='the upstream MID360_config.json (default: from the loaded ROS environment)')
    args = ap.parse_args(argv)
    m3 = p4_common.import_mid360_config()

    local_path = Path(args.mid360_json).expanduser()
    if local_path.name != m3.LOCAL_FILE:
        print(f'ERROR: gouda_core.mid360_config.read_local reads <folder>/{m3.LOCAL_FILE}; give a file named {m3.LOCAL_FILE}', file=sys.stderr)
        return 2
    local = m3.read_local(str(local_path.parent))
    mount_notes = [p for p in local['problems'] if p.startswith(m3.MOUNT_KEYS)]
    blocking = [p for p in local['problems'] if not p.startswith(m3.MOUNT_KEYS)]
    if blocking:
        print('ERROR: mid360.json cannot be used for P4: ' + '; '.join(blocking), file=sys.stderr)
        return 2

    if args.template:
        tpl = str(Path(args.template).expanduser())
    else:
        tpl, why = find_installed_template(m3)
        if tpl is None:
            print(f'ERROR: {why}', file=sys.stderr)
            return 2
    out = str(Path(args.out).expanduser().resolve())
    try:
        m3.write_driver_config(tpl, local, out)
    except (OSError, ValueError) as e:
        print(f'ERROR: the driver config could not be written ({e})', file=sys.stderr)
        return 2

    with open(tpl, encoding='utf-8') as f:
        template = json.load(f)
    with open(out, encoding='utf-8') as f:
        written = json.load(f)
    ext = written['lidar_configs'][0].get('extrinsic_parameter', {})
    print(f'written: {out}')
    print(f'template: {tpl}')
    print(f'made by: gouda_core.mid360_config.write_driver_config of this checkout ({p4_common.repo_commit()})')
    print('changed from the template: ' + ', '.join(changed_paths(template, written)))
    print('extrinsic_parameter: ' + ', '.join(f'{k} {v}' for k, v in ext.items()))
    if mount_notes:
        print('note: the mounting in mid360.json is not complete (not used by P4; the product starts its MID-360 path only when it is): '
              + '; '.join(mount_notes))
    print('the written file holds the PC\'s and the MID-360\'s addresses: keep it outside the repository and the ledger')
    return 0


if __name__ == '__main__':
    sys.exit(main())

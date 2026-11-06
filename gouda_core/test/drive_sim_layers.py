"""TEST ONLY (MID-360 plan, stage 2): costmap layer variants for the MID-360 in the driving simulator. Product code is unchanged.

Variants (design/proposals/mid360_simulation_plan_2026-11-06.md):
  S0  the XT-32 only (no change)
  S1  the MID-360 in the XT-32's ObstacleLayer (B0): the XT-32's empty beams also clear the MID-360's marks
  S2  the MID-360 in its own ObstacleLayer (B1, #35): only the MID-360's own rays clear its marks
MID-360 sources: marking from its base_link-band LaserScan (mid360_scan, the same band as the XT-32's), clearing from its raw
points with the sensor at mid360_link, so a cell is cleared only where a MID-360 ray really passed (to the ground or further).
apply() is called by a test hook that exists only in a simulator copy of nav2_config.py (patch_copy); the repository's
nav2_config.py has no hook.
usage: python3 drive_sim_layers.py --patch-copy <path to a COPY of gouda_core/nav2_config.py>
"""
from __future__ import annotations

import copy
import os
import sys

MID_SCAN_TOPIC = '/sensors/mid360/scan'
MID_POINTS_TOPIC = '/sensors/mid360/points'
MID_FRAME = 'mid360_link'
LAYER = 'mid360_layer'
VARIANTS = ('S0', 'S1', 'S2')
ENV = 'GOUDA_TEST_LAYERS'


def sources(xt_scan: dict) -> dict:
    """The two MID-360 sources, with the XT-32 source's ranges."""
    inf = float('inf')
    mark = {'topic': MID_SCAN_TOPIC, 'data_type': 'LaserScan', 'marking': True, 'clearing': False, 'inf_is_valid': False,
            'min_obstacle_height': -inf, 'max_obstacle_height': inf,
            'obstacle_max_range': xt_scan['obstacle_max_range'], 'obstacle_min_range': xt_scan.get('obstacle_min_range', 0.0)}
    clear = {'topic': MID_POINTS_TOPIC, 'data_type': 'PointCloud2', 'marking': False, 'clearing': True, 'sensor_frame': MID_FRAME,
             'min_obstacle_height': -inf, 'max_obstacle_height': inf,
             'raytrace_max_range': xt_scan['raytrace_max_range'], 'raytrace_min_range': xt_scan.get('raytrace_min_range', 0.0)}
    return {'mid_mark': mark, 'mid_clear': clear}


def apply(params: dict, variant: str) -> None:
    if variant not in VARIANTS:
        raise ValueError(f'unknown layer variant {variant!r}')
    if variant == 'S0':
        return
    for name in ('local_costmap', 'global_costmap'):
        c = params[name][name]['ros__parameters']
        xt = c['obstacle_layer']
        src = sources(xt['scan'])
        if variant == 'S1':
            xt['observation_sources'] = xt['observation_sources'] + ' mid_mark mid_clear'
            xt.update(copy.deepcopy(src))
        else:
            layer = {'plugin': 'nav2_costmap_2d::ObstacleLayer', 'enabled': True, 'observation_sources': 'mid_mark mid_clear',
                     'min_obstacle_height': xt['min_obstacle_height'], 'max_obstacle_height': xt['max_obstacle_height']}
            if 'combination_method' in xt:
                layer['combination_method'] = xt['combination_method']
            layer.update(copy.deepcopy(src))
            c[LAYER] = layer
            plugins = list(c['plugins'])
            plugins.insert(plugins.index('obstacle_layer') + 1, LAYER)
            c['plugins'] = plugins


HOOK = ("    if os.environ.get('GOUDA_TEST_LAYERS'):   # SIMULATOR COPY ONLY (drive_sim_layers.patch_copy)\n"
        "        import importlib.util as _u\n"
        "        _s = _u.spec_from_file_location('drive_sim_layers', os.environ['GOUDA_TEST_LAYERS_PY']); _m = _u.module_from_spec(_s)\n"
        "        _s.loader.exec_module(_m); _m.apply(params, os.environ['GOUDA_TEST_LAYERS'])\n")
ANCHOR = "    apply_tunables(params, t, template['controller_server']['ros__parameters']['FollowPath'])\n"


def patch_copy(path: str) -> bool:
    """Insert the hook after apply_tunables in a COPY of nav2_config.py. Refuses a file inside a git checkout (the repository)."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, '.git')):
            raise SystemExit('refusing to patch a file inside a git checkout; patch a simulator copy')
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    s = open(path, encoding='utf-8').read()
    if HOOK in s:
        return False
    if s.count(ANCHOR) != 1:
        raise SystemExit('nav2_config.py does not have the expected apply_tunables line')
    open(path, 'w', encoding='utf-8').write(s.replace(ANCHOR, ANCHOR + HOOK))
    return True


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--patch-copy':
        print('patched' if patch_copy(sys.argv[2]) else 'already patched')
    else:
        print(__doc__)

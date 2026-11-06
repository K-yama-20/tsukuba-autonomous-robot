"""TEST ONLY (第245便, DEC-493, issue #90): scenes and a measure for the marks that stay in the costmap after a small robot left
the sensors' view. Product code is unchanged. No ROS.

Scenes (P1 of the plan is the existing L10 / L11). Sizes, speeds and positions are PROVISIONAL (the other robots' real size and
speed are not known; the human is asked in #90), and the simulated robots do not avoid the vehicle:
  blind_pass_h30 / _h50   P2  an oncoming small robot passes 0.8 m to the left just before the route turns left
  blind_overtake          P3  a small robot comes from behind on the left, passes and drifts into the lane
  blind_cross             P4  a small robot crosses the route from left to right ahead of the vehicle
  blind_wait              P5  the route is blocked for 20 s; meanwhile three small robots pass on both sides
  blind_stop_h30 / _h50   P6  as P2, but the robot stops inside the corner the route turns into
  blind_clear             P7  a low object stands beside the route where a block ahead makes Nav2 run its recoveries
stale_marks() counts the lethal cells of a costmap grid that are not near any existing obstacle (the truth is known here).
"""
from __future__ import annotations

import math

import numpy as np

import drive_sim_core as ds

ROBOT_RADIUS_M = 0.25            # provisional
HEIGHTS = {'h30': 0.3, 'h50': 0.5}   # provisional; 0.3 m and 0.5 m as the low objects L11 / L10
STALE_MARGIN_M = 0.5             # a lethal cell further than this from every existing obstacle is a mark left behind
NEAR_M = 2.0                     # ... and within this distance of the vehicle it can get in the way of a turn or a reverse
LETHAL = 100                     # nav_msgs/OccupancyGrid value of a lethal cell (99: inscribed, -1: unknown)
SCENARIOS = ('blind_pass_h30', 'blind_pass_h50', 'blind_overtake', 'blind_cross', 'blind_wait', 'blind_stop_h30', 'blind_stop_h50',
             'blind_clear')


def _corner_route(length: float = 15.0, side: float = 10.0, step: float = 5.0) -> list:
    """Along +x, then a left turn along +y at x = length."""
    return [(i * step, 0.0) for i in range(int(length / step) + 1)] + [(length, j * step) for j in range(1, int(side / step) + 1)]


def _robot(x: float, y: float, height: float = 0.3, **kw) -> ds.Obstacle:
    return ds.Obstacle(x, y, height=height, radius=ROBOT_RADIUS_M, **kw)


def _block(x: float, dwell_s: float) -> ds.Obstacle:
    """A wall across the route, too wide to go around inside the local costmap; it appears in front of the vehicle and leaves."""
    return ds.Obstacle(x, 0.0, height=1.7, half_x=0.3, half_y=6.0, trigger_m=3.0, dwell_s=dwell_s, name='block')


def scenario(name: str) -> ds.Scenario:
    kind, _, h = name.rpartition('_')
    if kind in ('blind_pass', 'blind_stop') and h in HEIGHTS:
        stop = dict(stop_after_s=5.0) if kind == 'blind_stop' else {}   # blind_stop: it stops at (14.0, 0.9), inside the corner
        start = (16.5, 0.9) if kind == 'blind_stop' else (15.5, 0.8)
        trigger = 5.0 if kind == 'blind_stop' else 4.0
        return ds.Scenario(name, _corner_route(), [_robot(*start, height=HEIGHTS[h], vx=-0.5, trigger_m=trigger, name='robot', **stop)])
    if name == 'blind_overtake':     # from behind the start at 1.0 m/s; passes only while the vehicle is slower than that
        return ds.Scenario(name, ds._route(), [_robot(-3.0, 0.9, vx=1.0, vy=-0.06, dwell_s=40.0, name='robot')])
    if name == 'blind_cross':
        return ds.Scenario(name, ds._route(), [_robot(12.0, 3.0, vy=-0.5, trigger_m=5.0, dwell_s=20.0, name='robot')])
    if name == 'blind_wait':         # the robots start from the block's side as the vehicle comes near, one after the other
        robots = [_robot(9.5, y, vx=-0.5, trigger_m=tr, dwell_s=25.0, name=f'robot{i}') for i, (y, tr) in enumerate(((0.9, 4.0), (-0.9, 3.5), (1.3, 3.0)))]
        return ds.Scenario(name, [(i * 5.0, 0.0) for i in range(5)], [_block(10.0, 20.0)] + robots)
    if name == 'blind_clear':        # the low object's surface is 0.5 m from the centre line: inside the footprint's turning circle
        return ds.Scenario(name, [(i * 5.0, 0.0) for i in range(5)], [_robot(9.0, 0.75, name='low'), _block(10.5, 40.0)], timeout_s=180.0)
    raise ValueError(f'unknown scenario {name}')


def stale_marks(data, width: int, height: int, resolution: float, origin_x: float, origin_y: float, obstacles: list, t: float,
                pose: tuple, margin_m: float = STALE_MARGIN_M, near_m: float = NEAR_M) -> dict:
    """{'lethal', 'stale', 'stale_near'} of one OccupancyGrid (row-major, in the frame the obstacles and the pose are in).
    stale: lethal cells further than margin_m from every obstacle that exists at t. stale_near: those within near_m of the vehicle."""
    grid = np.asarray(data, dtype=np.int16).reshape(height, width)
    rows, cols = np.nonzero(grid >= LETHAL)
    if len(rows) == 0:
        return {'lethal': 0, 'stale': 0, 'stale_near': 0}
    xs, ys = origin_x + (cols + 0.5) * resolution, origin_y + (rows + 0.5) * resolution
    dist = np.full(len(xs), math.inf)
    for o in obstacles:
        if o.exists(t):
            dist = np.minimum(dist, o.distance(t, xs, ys))
    stale = dist > margin_m
    near = stale & (np.hypot(xs - pose[0], ys - pose[1]) <= near_m)
    return {'lethal': int(len(xs)), 'stale': int(stale.sum()), 'stale_near': int(near.sum())}

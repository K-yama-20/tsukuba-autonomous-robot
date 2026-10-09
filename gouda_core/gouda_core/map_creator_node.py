"""gouda_map_creator node (ND-05): map/convert action (IFD-37) over the map database (IFD-29). Stage 5-3.

Converts a registered source map (GLIM dump, 原図) into a Nav2 2D map and publishes it as converted/<revision> with a
manifest (origin id, content hashes, converter version, settings: RQ-I009). A failed conversion keeps the source and
discards the incomplete output. Re-conversion can be requested any time (from gouda_monitor, stage 5-4+).

Settings (PRM-33..36) are ROS parameters read from design/generated/params/gouda_map_creator.yaml (or the .trial.yaml
software trial values in stub tests). They are unresolved until measured on the vehicle (Q-06); the node refuses to
convert when a setting is missing rather than using a default. No numeric value is hard-coded (RQ-I076).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node
from rclpy.parameter import Parameter
from gouda_interfaces.action import ConvertMap

from gouda_core import map_convert
from gouda_core.map_database import MapDatabase

def optional_double(node, name):
    """Value of a declared-but-possibly-unset DOUBLE parameter, or None (rclpy raises on an uninitialised parameter)."""
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None

SETTING_PARAMS = ['map_resolution_m', 'ground_band_max_m', 'obstacle_band_min_m', 'obstacle_band_max_m', 'occupied_min_points']


class MapCreatorNode(Node):
    def __init__(self):
        super().__init__('gouda_map_creator')
        self.declare_parameter('data_root', '')   # PRM-25
        root = self.get_parameter('data_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('data_root is not set (PRM-25)')
        for key in SETTING_PARAMS:
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self.db = MapDatabase(Path(os.path.expanduser(root)) / 'maps')
        self._lock = threading.Lock()
        self.server = ActionServer(self, ConvertMap, 'map/convert', execute_callback=self._execute, goal_callback=self._goal, cancel_callback=self._cancel)
        self.get_logger().info(f'gouda_map_creator ready; maps={self.db.root}; settings={self._settings(require=False)}')

    def _settings(self, require=True) -> dict:
        s = {}
        for key in SETTING_PARAMS:
            s[key] = optional_double(self, key)
        if require and any(v is None for v in s.values()):
            missing = [k for k, v in s.items() if v is None]
            raise ValueError(f'conversion settings unresolved: {missing} (PRM-33..36; pass the generated parameter file, or the trial file for stub tests)')
        return s

    def _goal(self, goal):
        return GoalResponse.ACCEPT if goal.origin_id else GoalResponse.REJECT

    def _cancel(self, handle):
        return CancelResponse.ACCEPT

    def _execute(self, handle):
        goal = handle.request; result = ConvertMap.Result(); result.origin_id = goal.origin_id
        fb = ConvertMap.Feedback()
        def feedback(stage, progress):
            fb.stage, fb.progress = stage, float(progress); handle.publish_feedback(fb)
        with self._lock:   # one conversion at a time; the source is never modified
            try:
                settings = json.loads(goal.settings_json) if goal.settings_json else self._settings()
                src_manifest = self.db.source_manifest(goal.origin_id)
                if src_manifest is None:
                    raise ValueError(f'origin {goal.origin_id} is not registered')
                feedback('reading', 0.1)
                tmp = self.db.begin_conversion(goal.origin_id)
                try:
                    feedback('converting', 0.4)
                    stats = map_convert.convert(self.db.source_dir(goal.origin_id), tmp, settings)
                    feedback('publishing', 0.9)
                    ok, msg, manifest = self.db.finish_conversion(goal.origin_id, tmp, {'version': map_convert.CONVERTER_VERSION}, settings, stats)
                except Exception as e:
                    msg = self.db.abort_conversion(tmp, str(e)); ok, manifest = False, None
                result.ok, result.message = ok, msg
                if manifest:
                    result.revision = int(manifest['revision']); result.content_hash = manifest['content_hash']
                    result.source_content_hash = manifest['source_content_hash'] or ''
                    result.map_yaml_path = str(self.db.root / goal.origin_id / 'converted' / f"{manifest['revision']:03d}" / 'map.yaml')
            except Exception as e:
                result.ok, result.message = False, f'conversion not started: {e}'
        (self.get_logger().info if result.ok else self.get_logger().warning)(result.message)
        handle.succeed() if result.ok else handle.abort()
        return result


def main(args=None):
    rclpy.init(args=args)
    node = MapCreatorNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try: executor.spin()
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()

"""GLIM runner (ND-06 is external software; this module starts/stops it for 事前地図作成, stage 5-3).

GLIM 1.2.2 (ros-jazzy-glim-ros, DEC-062) is run as a child process of gouda_mode_manager (TR-03 "GLIM を起動・有効化",
TR-04 "GLIM に保存を要求"). It reads a runtime configuration directory (config_path) that this module derives from the
package's installed templates (/opt/ros/jazzy/share/glim/config) with the CPU modules selected and the Gouda topics and
frames filled in. On SIGINT GLIM writes its map to dump_path (graph.txt, values.bin, traj_*.txt, config/, and one
%06d/ directory per submap when data was received) — observed on the VM on 2026-10-09 (FILE-VEHICLE-PC-STAGE53).

No ROS dependency here; the node supplies paths, topic/frame names and the stop-wait parameter.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REQUIRED_DUMP_FILES = ('graph.txt', 'values.bin')   # written by GLIM 1.2.2 on shutdown even without data
SUBMAP_DIR = re.compile(r'^\d{6}$')


@dataclass
class GlimSettings:
    points_topic: str          # IFD-21 (sensors/xt32/points)
    imu_topic: str             # IFD-22 (sensors/imu/data)
    lidar_frame_id: str        # xt32_link (IFD-20)
    imu_frame_id: str          # imu_link (IFD-20)
    base_frame_id: str         # base_link (REP-103, PRM-07); GLIM publishes map->odom->base_frame (IFD-19 in MODE-MAP)
    odom_frame_id: str = 'odom'
    map_frame_id: str = 'map'
    template_dir: Path = Path('/opt/ros/jazzy/share/glim/config')
    executable: str = '/opt/ros/jazzy/lib/glim_ros/glim_rosnode'
    extension_modules: tuple = ()   # no viewers: the monitor owns the display areas (design rules §6)


def _strip_comments(text: str) -> str:
    """GLIM's config files are JSON with // and /* */ comments; remove them for parsing."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'(?m)^\s*//.*$', '', text)
    text = re.sub(r'(?m)(?<=[,{\[\s])//.*$', '', text)
    return text


def build_runtime_config(settings: GlimSettings, out_dir: Path) -> dict:
    """Copy the template config into out_dir with CPU modules, Gouda topics/frames and no viewer modules.

    Returns the effective config_ros values (for the record). Raises FileNotFoundError when the template is missing.
    """
    tpl = Path(settings.template_dir)
    if not (tpl / 'config.json').is_file():
        raise FileNotFoundError(f'GLIM config template not found: {tpl} (is ros-jazzy-glim installed?)')
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    for f in tpl.iterdir():
        if f.is_file(): (out_dir / f.name).write_bytes(f.read_bytes())
    top = json.loads(_strip_comments((out_dir / 'config.json').read_text()))
    g = top['global']
    g['config_odometry'] = 'config_odometry_cpu.json'; g['config_sub_mapping'] = 'config_sub_mapping_cpu.json'; g['config_global_mapping'] = 'config_global_mapping_cpu.json'
    (out_dir / 'config.json').write_text(json.dumps(top, indent=2) + '\n')
    ros = json.loads(_strip_comments((out_dir / 'config_ros.json').read_text()))
    r = ros['glim_ros']
    r.update({'points_topic': settings.points_topic, 'imu_topic': settings.imu_topic, 'lidar_frame_id': settings.lidar_frame_id,
              'imu_frame_id': settings.imu_frame_id, 'base_frame_id': settings.base_frame_id, 'odom_frame_id': settings.odom_frame_id,
              'map_frame_id': settings.map_frame_id, 'extension_modules': list(settings.extension_modules)})
    (out_dir / 'config_ros.json').write_text(json.dumps(ros, indent=2) + '\n')
    return r


@dataclass
class GlimRun:
    config_dir: Path
    dump_dir: Path
    pid: int
    started_at: float
    stopped_at: Optional[float] = None
    exit_code: Optional[int] = None
    dump_ok: Optional[bool] = None
    submaps: int = 0
    note: str = ''


class GlimRunner:
    """Start GLIM as a child process group; stop it with SIGINT and wait for the dump (the only way GLIM 1.2.2 saves)."""

    def __init__(self, settings: GlimSettings, clock: Callable[[], float] = time.time, popen=subprocess.Popen):
        self.settings = settings; self.clock = clock; self._popen = popen
        self.proc: Optional[subprocess.Popen] = None
        self.run: Optional[GlimRun] = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, work_dir: Path, dump_dir: Path, log_file: Path) -> GlimRun:
        if self.running:
            raise RuntimeError('GLIM is already running')
        cfg = Path(work_dir) / 'glim_config'
        build_runtime_config(self.settings, cfg)
        Path(dump_dir).parent.mkdir(parents=True, exist_ok=True)
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.settings.executable, '--ros-args', '-p', f'config_path:={cfg}', '-p', f'dump_path:={dump_dir}']
        self._log = open(log_file, 'ab')
        self.proc = self._popen(cmd, stdout=self._log, stderr=subprocess.STDOUT, start_new_session=True)
        self.run = GlimRun(config_dir=cfg, dump_dir=Path(dump_dir), pid=self.proc.pid, started_at=self.clock())
        return self.run

    def stop(self, wait_s: float) -> GlimRun:
        """SIGINT the process group and wait up to wait_s for exit and the dump files. Never raises for a failed save:
        the outcome is in GlimRun.dump_ok / note (RQ-I009: the source map is only published when complete)."""
        r = self.run
        if r is None:
            raise RuntimeError('GLIM was not started')
        if self.proc is not None and self.proc.poll() is None:
            try: os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
            except ProcessLookupError: pass
            deadline = self.clock() + wait_s
            while self.proc.poll() is None and self.clock() < deadline:
                time.sleep(0.2)
            if self.proc.poll() is None:
                try: os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                except ProcessLookupError: pass
                r.note = f'GLIM did not exit within {wait_s} s after SIGINT; SIGTERM sent (dump may be incomplete)'
        r.stopped_at = self.clock(); r.exit_code = self.proc.poll() if self.proc else None
        if getattr(self, '_log', None): self._log.close(); self._log = None
        r.dump_ok, r.submaps, detail = inspect_dump(r.dump_dir)
        r.note = (r.note + ' ' + detail).strip()
        return r


def inspect_dump(dump_dir: Path) -> tuple[bool, int, str]:
    """True when the dump has GLIM's required files; counts submap directories (0 when no sensor data arrived)."""
    d = Path(dump_dir)
    if not d.is_dir():
        return False, 0, f'dump directory {d} does not exist'
    missing = [f for f in REQUIRED_DUMP_FILES if not (d / f).is_file()]
    submaps = sum(1 for x in d.iterdir() if x.is_dir() and SUBMAP_DIR.match(x.name))
    if missing:
        return False, submaps, f'dump incomplete: missing {missing}'
    return True, submaps, f'dump complete ({submaps} submap(s))' + ('' if submaps else '; no submap: no sensor data was received')

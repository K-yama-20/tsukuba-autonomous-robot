"""Own one SLAM process; expose mapping/localization, never vehicle control."""
from pathlib import Path
import signal
import subprocess
import threading
import time
import yaml
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from lifecycle_msgs.srv import ChangeState
from slam_toolbox.srv import SerializePoseGraph, Pause


class SlamSession:
    def __init__(self, node, directory, replay=False):
        self.node = node; self.directory = Path(directory) / '.slam-runtime'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.replay = replay; self.process = None; self.log = None; self.phase = 'idle'
        self.change = node.create_client(ChangeState, '/slam_toolbox/change_state')
        self.serialize = node.create_client(SerializePoseGraph, '/slam_toolbox/serialize_map')
        self.pause = node.create_client(Pause, '/slam_toolbox/pause_new_measurements')

    def request(self, client, request, timeout=4.):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError('SLAMサービスの起動を確認できません')
        f = client.call_async(request); done = threading.Event()
        f.add_done_callback(lambda _: done.set())
        if not done.wait(timeout):
            raise TimeoutError('SLAMの応答待ちです。再操作前に状態を確認してください')
        return f.result()

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try: self.process.wait(timeout=2)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
        self.process = None
        if self.log: self.log.close(); self.log = None
        self.phase = 'idle'

    def start(self, graph=None):
        self.close()
        config = yaml.safe_load((Path(get_package_share_directory('slam_toolbox')) /
                                 'config/mapper_params_online_async.yaml').read_text())
        p = config['slam_toolbox']['ros__parameters']
        p.update(base_frame='hesai_lidar', odom_frame='odom_lidar', map_frame='map',
                 scan_topic='/scan', mode='localization' if graph else 'mapping',
                 use_sim_time=self.replay, use_lifecycle_manager=False,
                 use_map_saver=False, map_update_interval=1., resolution=.1,
                 minimum_time_interval=.2, minimum_travel_distance=.1,
                 minimum_travel_heading=.1, enable_interactive_mode=False,
                 transform_timeout=.5, scan_queue_size=10)
        if graph:
            p.update(map_file_name=str(graph), map_start_pose=[0., 0., 0.], map_start_at_dock=False)
        path = self.directory / 'params.yaml'; path.write_text(yaml.safe_dump(config))
        exe = 'localization_slam_toolbox_node' if graph else 'async_slam_toolbox_node'
        self.log = (self.directory / ('localization.log' if graph else 'mapping.log')).open('a')
        self.process = subprocess.Popen([str(Path(get_package_prefix('slam_toolbox')) / 'lib/slam_toolbox' / exe),
              '--ros-args', '--params-file', str(path)], stdout=self.log, stderr=subprocess.STDOUT)
        try:
            for transition in (1, 3):
                req = ChangeState.Request(); req.transition.id = transition
                if not self.request(self.change, req).success:
                    raise RuntimeError('SLAMの状態切替に失敗しました')
            self.phase = 'localization' if graph else 'mapping'
        except Exception:
            self.close(); raise

    def stop_mapping(self):
        if self.phase != 'mapping': raise RuntimeError('地図作成中ではありません')
        response = self.request(self.pause, Pause.Request())
        if not response.status: raise RuntimeError('SLAMの計測停止に失敗しました')
        self.phase = 'paused'

    def save(self, directory):
        if self.phase != 'paused': raise RuntimeError('計測を終了してから保存してください')
        req = SerializePoseGraph.Request(); req.filename = str(directory / 'slam')
        if self.request(self.serialize, req).result != 0:
            raise RuntimeError('SLAMグラフを保存できませんでした')
        for suffix in ('.posegraph', '.data'):
            p = directory / ('slam' + suffix)
            if not p.is_file() or p.stat().st_size == 0:
                raise RuntimeError('保存されたSLAMグラフを確認できません')

    def status(self):
        if self.process and self.process.poll() is not None: return 'failed'
        return self.phase

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gouda_gui import runtime


class Response:
    status = 200
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *_): pass


def response(value):
    result = Response(value)
    result.read = lambda: json.dumps(value).encode()
    return result


class RuntimeLifecycleTest(unittest.TestCase):
    def test_active_recording_blocks_stop_and_restart(self):
        state = {'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        backend = {'recording': {'phase': 'finalizing'}, 'mapping': False, 'autonomy': {}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
            with self.assertRaisesRegex(RuntimeError, 'Recording is active or finalizing'):
                runtime._ensure_disruption_safe(state)

    def test_paused_manual_goal_blocks_restart(self):
        state = {'mode': 'autonomy', 'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        backend = {'recording': {'phase': 'idle'}, 'mapping': False,
                   'autonomy': {'profile_enabled': True, 'state_fresh': True,
                                'state': {'phase': 'paused_manual', 'goal': [1, 0, 0], 'device_fresh': True}},
                   'esp': {'auto_enabled': True}, 'ages': {'esp32': .2}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
            with self.assertRaisesRegex(RuntimeError, 'Autonomy state or fresh ESP32'):
                runtime._ensure_disruption_safe(state)

    def test_missing_backend_state_fails_closed_for_live_processing(self):
        state = {'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', side_effect=OSError('offline')):
            with self.assertRaisesRegex(RuntimeError, 'Backend state is unavailable'):
                runtime._ensure_disruption_safe(state)

    def test_stale_autonomy_state_blocks_disruption(self):
        state = {'mode': 'autonomy', 'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        backend = {'recording': {'phase': 'idle'}, 'mapping': False,
                   'autonomy': {'profile_enabled': True, 'state': {'phase': 'cancelled'}, 'state_fresh': False}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
            with self.assertRaisesRegex(RuntimeError, 'Autonomy state or fresh ESP32'):
                runtime._ensure_disruption_safe(state)

    def test_malformed_backend_snapshot_fails_closed(self):
        state = {'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response({})):
            with self.assertRaisesRegex(RuntimeError, 'Recording state is missing or malformed'):
                runtime._ensure_disruption_safe(state)

    def test_observation_can_restart_after_mapping_was_stopped_and_saved(self):
        state = {'mode': 'observation', 'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        backend = {'recording': {'phase': 'idle'}, 'mapping': False, 'slam_phase': 'paused',
                   'autonomy': {'profile_enabled': False, 'state': None}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
            runtime._ensure_disruption_safe(state)

    def test_idle_profile_can_be_disrupted(self):
        state = {'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        backend = {'recording': {'phase': 'completed'}, 'mapping': False, 'slam_phase': 'paused',
                   'autonomy': {'profile_enabled': True, 'state_fresh': True,
                                'state': {'phase': 'completed', 'goal': [1, 0, 0], 'device_fresh': True}},
                   'esp': {'auto_enabled': False}, 'ages': {'esp32': .2}}
        with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
            runtime._ensure_disruption_safe(state)

    def test_blocked_phone_stop_never_runs_a_profile_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {'mode': 'observation', 'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
            backend = {'recording': {'phase': 'finalizing'}, 'mapping': False}
            with patch.object(runtime, 'runtime_dir', return_value=root), \
                 patch.object(runtime, '_read_process_state', return_value=state), \
                 patch.object(runtime, 'alive', return_value=True), \
                 patch.object(runtime, 'urlopen', return_value=response(backend)), \
                 patch.object(runtime, '_run_profile') as run_profile:
                with self.assertRaisesRegex(RuntimeError, 'Recording is active or finalizing'):
                    runtime.runtime_action({'action': 'stop'})
                run_profile.assert_not_called()

    def test_completed_or_cancelled_retained_goal_with_disarmed_fresh_esp_is_safe(self):
        state = {'mode': 'autonomy', 'processes': {'processing': {'pid': 1, 'start': 'owned'}}}
        for phase in ('cancelled', 'completed'):
            backend = {'recording': {'phase': 'idle'}, 'mapping': False,
                       'autonomy': {'profile_enabled': True, 'state_fresh': True,
                                    'state': {'phase': phase, 'goal': [1, 0, 0], 'device_fresh': True}},
                       'esp': {'auto_enabled': False}, 'ages': {'esp32': .2}}
            with patch.object(runtime, 'alive', return_value=True), patch.object(runtime, 'urlopen', return_value=response(backend)):
                runtime._ensure_disruption_safe(state)

    def test_lifecycle_lock_contention_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runtime, 'runtime_dir', return_value=root), patch.object(runtime, '_read_process_state', return_value={'mode': None, 'processes': {}}):
                lock_path = root/'lifecycle.lock'
                with lock_path.open('a') as held:
                    import fcntl
                    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with self.assertRaisesRegex(RuntimeError, 'Another lifecycle action'):
                        runtime.runtime_action({'action': 'stop'})

    def test_headless_viewer_start_skips_display_and_process_launch(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(runtime.os.environ, {'GOUDA_HEADLESS': '1'}):
            with patch.object(runtime, 'rviz_command', side_effect=AssertionError('must not launch')):
                runtime.start_viewer({'processes': {}}, Path(directory)/'state.json', Path(directory), {})

    def test_lifecycle_rejects_unknown_action_and_command_fields(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported lifecycle action'):
            runtime.runtime_action({'action': 'shell'})
        with self.assertRaisesRegex(ValueError, 'Unsupported lifecycle fields'):
            runtime.runtime_action({'action': 'start_observe', 'command': 'whoami'})
        with self.assertRaisesRegex(ValueError, 'profile is accepted only for restart'):
            runtime.runtime_action({'action': 'start_autonomy', 'profile': 'autonomy'})


if __name__ == '__main__':
    unittest.main()

"""The tests of the /dev tab. To add one: a module here with build_trials(params) and analyze(run, params), a YAML file with the same
name in gouda_core/vehicle_tests/ (conditions and runner settings), and one line in TESTS. See vehicle_test_core."""
from gouda_core.vehicle_tests import motion_start

TESTS = {'motion_start': motion_start}

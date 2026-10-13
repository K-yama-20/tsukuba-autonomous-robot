"""Regression test: rclpy raises "Logger severity cannot be changed between calls" when one logging call site (same file and
line) is used with different severities. That killed gouda_mode_manager and aborted a gouda_map_creator conversion on the VM
(2026-10-13, design/research/vehicle_pc/2026-10-13_gouda_mode_manager_crash_launch_log.txt). No line of the node code may
contain two logger calls of different severity."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'gouda_core'
CALL = re.compile(r'get_logger\(\)\.(debug|info|warning|warn|error|fatal)\b')


class LoggingCallSiteTests(unittest.TestCase):
    def test_one_severity_per_line(self):
        bad = []
        for f in sorted(SRC.glob('*.py')):
            for n, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
                if len(set(CALL.findall(line))) > 1:
                    bad.append(f'{f.name}:{n}: {line.strip()}')
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()

"""LinkCounter (ND-12, DEC-177): ESP32 USB disconnects are counted only in a 事前地図作成 or 自律走行 session; pause and resume
continue the count; the session ends when the mode returns to 手動走行."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.vehicle_core import LinkCounter, LINK_UP, LINK_DOWN, LINK_NOT_OPEN, MODE_MANUAL, MODE_MAPPING, MODE_AUTONOMY, MODE_PAUSE  # noqa: E402


class LinkCounterTests(unittest.TestCase):
    def setUp(self):
        self.c = LinkCounter(); self.c.on_mode(MODE_MANUAL, 0); self.c.on_link(LINK_UP, 0)

    def test_nothing_counted_outside_a_session(self):
        self.c.on_link(LINK_DOWN, 1); self.c.on_link(LINK_UP, 2)
        st = self.c.status(3)
        self.assertEqual(st['link'], LINK_UP); self.assertEqual(st['session'], ''); self.assertIsNone(st['disconnects'])

    def test_autonomy_session_counts_through_pause_and_resume(self):
        self.assertEqual(self.c.on_mode(MODE_AUTONOMY, 10), ('session_started', 'autonomy'))
        self.c.on_link(LINK_DOWN, 11); self.c.on_link(LINK_UP, 13)
        self.assertIsNone(self.c.on_mode(MODE_PAUSE, 20)); self.assertIsNone(self.c.on_mode(MODE_AUTONOMY, 25))   # pause / resume: same session
        self.c.on_link(LINK_DOWN, 30)
        st = self.c.status(31)
        self.assertEqual((st['disconnects'], st['reconnects']), (2, 1)); self.assertEqual(st['link'], LINK_DOWN)
        self.assertEqual(st['down_since'], 30); self.assertAlmostEqual(st['down_total_s'], 3.0)
        kind, summary = self.c.on_mode(MODE_MANUAL, 34)
        self.assertEqual(kind, 'session_ended'); self.assertEqual(summary['disconnects'], 2); self.assertAlmostEqual(summary['down_total_s'], 6.0)
        self.assertEqual(self.c.status(35)['last_session']['kind'], 'autonomy')

    def test_new_session_starts_from_zero(self):
        self.c.on_mode(MODE_MAPPING, 0); self.c.on_link(LINK_DOWN, 1); self.c.on_link(LINK_UP, 2); self.c.on_mode(MODE_MANUAL, 3)
        self.assertEqual(self.c.on_mode(MODE_MAPPING, 4), ('session_started', 'mapping'))
        st = self.c.status(5); self.assertEqual((st['disconnects'], st['reconnects'], st['down_total_s']), (0, 0, 0.0))
        self.assertEqual(st['last_session']['disconnects'], 1)

    def test_link_already_down_when_the_session_starts(self):
        self.c.on_link(LINK_DOWN, 1); self.c.on_mode(MODE_AUTONOMY, 5); self.c.on_link(LINK_UP, 8)
        st = self.c.status(9)
        self.assertEqual((st['disconnects'], st['reconnects']), (0, 0))   # the outage began before the session
        self.assertAlmostEqual(st['down_total_s'], 3.0)                   # but its time inside the session is counted

    def test_pause_at_boot_starts_an_autonomy_session(self):
        c = LinkCounter(); self.assertEqual(c.on_mode(MODE_PAUSE, 0), ('session_started', 'autonomy'))

    def test_closing_the_port_is_not_a_disconnect(self):
        self.c.on_mode(MODE_AUTONOMY, 0); self.c.on_link(LINK_NOT_OPEN, 1)
        self.assertEqual(self.c.status(2)['disconnects'], 0)


if __name__ == '__main__': unittest.main()

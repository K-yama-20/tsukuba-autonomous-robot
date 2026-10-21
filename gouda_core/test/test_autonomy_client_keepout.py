"""The keepout check (a) of the autonomy start with the real ROS message types (REV-137, DEC-224; TS-47). Runs where nav2_msgs is
installed (the VM); skipped elsewhere. Found on the VM, 2026-10-21: the filter info's mask topic field is filter_mask_topic (an
AttributeError on mask_topic killed the mode manager at the first keepout filter info)."""
import hashlib
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import numpy as np
    from nav2_msgs.msg import CostmapFilterInfo
    from nav_msgs.msg import OccupancyGrid
    from gouda_core.autonomy_client import AutonomyClient
    from gouda_core import nav2_config as nc
except ImportError:   # no ROS / Nav2 here (the Mac)
    CostmapFilterInfo = None


@unittest.skipIf(CostmapFilterInfo is None, 'nav2_msgs not installed')
class KeepoutCheckTests(unittest.TestCase):
    def client(self, values, size):
        seen = []
        class Stand(types.SimpleNamespace):   # the client's own property and state, without a ROS node
            keepout_confirmed = AutonomyClient.keepout_confirmed
        c = Stand(keepout_expected=(hashlib.sha256(np.asarray(values, dtype=np.int8).tobytes()).hexdigest(), size),
                                  keepout_mask_state=None, keepout_info_received=False, on_keepout=lambda ok, d: seen.append((ok, d)))
        c._keepout_changed = lambda details: AutonomyClient._keepout_changed(c, details)
        return c, seen

    @staticmethod
    def confirmed(c):
        return c.keepout_confirmed

    def mask(self, values, w, h):
        m = OccupancyGrid(); m.info.width, m.info.height = w, h; m.data = list(values); return m

    def info(self, type_=0, topic=None, base=0.0, mult=1.0):
        i = CostmapFilterInfo(); i.type = type_; i.filter_mask_topic = topic or nc.KEEPOUT_MASK_TOPIC; i.base = base; i.multiplier = mult; return i

    def test_confirmed_only_with_matching_mask_and_keepout_info(self):
        vals = [100, -1, 0, -1]
        c, seen = self.client(vals, (2, 2))
        AutonomyClient._on_keepout_info(c, self.info()); self.assertFalse(self.confirmed(c))   # mask not yet
        AutonomyClient._on_keepout_mask(c, self.mask(vals, 2, 2)); self.assertTrue(self.confirmed(c))
        self.assertTrue(seen[-1][0])

    def test_mismatch_or_wrong_info_is_not_confirmed(self):
        vals = [100, -1, 0, -1]
        c, _ = self.client(vals, (2, 2))
        AutonomyClient._on_keepout_mask(c, self.mask([100, -1, -1, -1], 2, 2)); AutonomyClient._on_keepout_info(c, self.info())
        self.assertFalse(self.confirmed(c)); self.assertIn('mismatch', c.keepout_mask_state)
        c, _ = self.client(vals, (2, 2))
        AutonomyClient._on_keepout_mask(c, self.mask(vals, 2, 2))
        for bad in (self.info(type_=2), self.info(topic='/speed_filter_mask'), self.info(mult=0.05)):
            AutonomyClient._on_keepout_info(c, bad); self.assertFalse(self.confirmed(c))


if __name__ == '__main__':
    unittest.main()

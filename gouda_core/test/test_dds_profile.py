"""Unit tests of dds_profile (ND-01, PRM-100; REV-144, DEC-279) without ROS.

Checked: the profile carries the buffer size of the generated settings for both UDP buffers, keeps the shared-memory transport
with its default segment (no segment_size: DEC-138 is a separate question), replaces the builtin transports by exactly these
two; a missing or invalid value writes nothing and gives the reason (nothing is filled in); trial files are never read."""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import dds_profile as dp  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PARAMS = str(REPO / 'design' / 'generated' / 'params')
NS = {'p': 'http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles'}


def write_params(d, text, name='gouda_dds.yaml'):
    with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
        f.write(text)


class DdsProfileTests(unittest.TestCase):
    def test_profile_from_the_generated_settings(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'run', 'fastdds_profile.xml')
            self.assertEqual(dp.write(PARAMS, out), '')
            root = ET.parse(out).getroot()
        value = dp.read_node_params(PARAMS, dp.NODE, trial=False)[dp.KEY]
        descs = {t.find('p:transport_id', NS).text: t for t in root.iterfind('p:transport_descriptors/p:transport_descriptor', NS)}
        udp = descs['gouda_udp']
        self.assertEqual(udp.find('p:type', NS).text, 'UDPv4')
        self.assertEqual(int(udp.find('p:receiveBufferSize', NS).text), value)
        self.assertEqual(int(udp.find('p:sendBufferSize', NS).text), value)
        shm = descs['gouda_shm']
        self.assertEqual(shm.find('p:type', NS).text, 'SHM')
        self.assertIsNone(shm.find('p:segment_size', NS))
        part = root.find('p:participant', NS)
        self.assertEqual(part.get('is_default_profile'), 'true')
        self.assertEqual([t.text for t in part.iterfind('p:rtps/p:userTransports/p:transport_id', NS)], ['gouda_shm', 'gouda_udp'])
        self.assertEqual(part.find('p:rtps/p:useBuiltinTransports', NS).text, 'false')

    def test_missing_or_invalid_value_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'fastdds_profile.xml')
            self.assertIn('PRM-100', dp.write(d, out))                       # no gouda_dds.yaml
            write_params(d, 'gouda_dds:\n  ros__parameters: {}\n')
            write_params(d, 'gouda_dds:\n  ros__parameters:\n    udp_buffer_bytes: 4194304\n', 'gouda_dds.trial.yaml')
            self.assertIn('PRM-100', dp.write(d, out))                       # the trial file is never read
            write_params(d, 'gouda_dds:\n  ros__parameters:\n    udp_buffer_bytes: 0\n')
            self.assertIn('positive integer', dp.write(d, out))
            write_params(d, 'gouda_dds:\n  ros__parameters:\n    udp_buffer_bytes: 1.5\n')
            self.assertIn('positive integer', dp.write(d, out))
            self.assertFalse(os.path.exists(out))
            self.assertEqual(dp.main([d, out]), 1)
            self.assertEqual(dp.main([d]), 2)


if __name__ == '__main__':
    unittest.main()

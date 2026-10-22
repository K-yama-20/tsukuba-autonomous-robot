"""Unit tests of a3_points (ND-07 trial A3 point pre-processing; REV-148, DEC-283 plan a, TS-41) without ROS.

Checked: x, y, z are read from the XT-32 layout (point_step 26, ring UINT16, timestamp FLOAT64 at the unaligned offset 18) and
from any layout; non-FLOAT32 or missing x, y, z are refused; the crop keeps the box +-far and drops the box +-near with
inclusive limits (as pcl CropBox); non-finite points are dropped; each leaf cube (floor(p / leaf), as pcl VoxelGrid) becomes the
centroid of its points; cubes with fewer than min_points points are dropped (PRM-102, DEC-284); the result is FLOAT32; invalid
settings are refused."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as F

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import a3_points as ap  # noqa: E402

XT32_FIELDS = [F(name='x', offset=0, datatype=7, count=1), F(name='y', offset=4, datatype=7, count=1), F(name='z', offset=8, datatype=7, count=1),
               F(name='intensity', offset=12, datatype=7, count=1), F(name='ring', offset=16, datatype=4, count=1),
               F(name='timestamp', offset=18, datatype=8, count=1)]


def xt32_buffer(xyz):
    dt = np.dtype({'names': ['x', 'y', 'z', 'intensity', 'ring', 'timestamp'], 'formats': ['<f4', '<f4', '<f4', '<f4', '<u2', '<f8'],
                   'offsets': [0, 4, 8, 12, 16, 18], 'itemsize': 26})
    rec = np.zeros(len(xyz), dtype=dt)
    rec['x'], rec['y'], rec['z'] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    rec['intensity'] = 7.0; rec['ring'] = 31; rec['timestamp'] = 1792603554.123456
    return rec.tobytes()


class A3PointsTests(unittest.TestCase):
    def test_reads_xyz_from_the_xt32_layout(self):
        xyz = np.array([[1.5, -2.25, 0.5], [10.0, 20.0, -3.0], [-0.125, 0.0, 7.75]])
        offs = ap.xyz_offsets(XT32_FIELDS)
        self.assertEqual(offs, {'x': 0, 'y': 4, 'z': 8})
        got = ap.xyz_view(xt32_buffer(xyz), 26, len(xyz), offs, False)
        np.testing.assert_array_equal(got, xyz)
        np.testing.assert_array_equal(ap.xyz_view(bytearray(xt32_buffer(xyz)), 26, len(xyz), offs, False), xyz)   # array-like data

    def test_refuses_unreadable_clouds(self):
        with self.assertRaises(ValueError): ap.xyz_offsets(XT32_FIELDS[1:])                                   # no x
        with self.assertRaises(ValueError): ap.xyz_offsets([F(name='x', offset=0, datatype=8, count=1)] + XT32_FIELDS[1:])  # FLOAT64 x
        with self.assertRaises(ValueError): ap.xyz_view(b'', 26, 0, {'x': 0, 'y': 4, 'z': 8}, True)          # big-endian

    def test_crop_is_inclusive_like_pcl_cropbox(self):
        near, far, leaf = 1.0, 5.0, 0.001
        p = np.array([[5.0, 0.0, 0.0],    # on the far limit: kept
                      [5.01, 0.0, 0.0],   # outside far: dropped
                      [1.0, 1.0, 1.0],    # on the near box corner: inside near -> dropped
                      [1.01, 0.0, 0.0],   # just outside near on x: kept
                      [0.5, 0.5, 4.0],    # inside near on x, y but not z: kept
                      [np.nan, 2.0, 2.0], [np.inf, 2.0, 2.0]])   # non-finite: dropped
        got = {tuple(np.round(r.astype(float), 4)) for r in ap.filter_points(p, near, far, leaf, 1)}
        self.assertEqual(got, {(5.0, 0.0, 0.0), (1.01, 0.0, 0.0), (0.5, 0.5, 4.0)})

    def test_voxel_centroids_by_floor_index(self):
        p = np.array([[2.1, 2.1, 2.1], [2.3, 2.4, 2.2], [2.6, 2.1, 2.1],    # cubes (4,4,4), (4,4,4), (5,4,4) of leaf 0.5
                      [-2.1, 2.2, 2.0], [-2.4, 2.4, 2.4]])                  # floor of negatives: (-5,4,4) both
        got = ap.filter_points(p, 1.0, 10.0, 0.5, 1)
        self.assertEqual(got.dtype, np.float32); self.assertEqual(got.shape, (3, 3))
        want = {(2.2, 2.25, 2.15), (2.6, 2.1, 2.1), (-2.25, 2.3, 2.2)}
        self.assertEqual({tuple(np.round(r.astype(float), 4)) for r in got}, want)
        # PRM-102 = 2 (DEC-284, as pcl_ros VoxelGrid's min_points_per_voxel): the cube with one point (2.6, 2.1, 2.1) is dropped
        got2 = ap.filter_points(p, 1.0, 10.0, 0.5, 2)
        self.assertEqual({tuple(np.round(r.astype(float), 4)) for r in got2}, want - {(2.6, 2.1, 2.1)})

    def test_empty_and_invalid_settings(self):
        self.assertEqual(ap.filter_points(np.zeros((0, 3)), 1.0, 10.0, 0.5, 2).shape, (0, 3))
        self.assertEqual(ap.filter_points(np.array([[0.1, 0.1, 0.1]]), 1.0, 10.0, 0.5, 1).shape, (0, 3))   # all inside near
        for near, far, leaf, mp in ((1.0, 1.0, 0.5, 2), (-1.0, 10.0, 0.5, 2), (1.0, 10.0, 0.0, 2), (1.0, 10.0, 0.5, 0)):
            with self.assertRaises(ValueError): ap.filter_points(np.zeros((1, 3)), near, far, leaf, mp)

    def test_size_of_an_xt32_cloud(self):
        rng = np.random.default_rng(1)
        xyz = rng.uniform(-60.0, 60.0, size=(64000, 3)); xyz[:, 2] /= 10.0
        p = ap.xyz_view(xt32_buffer(xyz), 26, len(xyz), ap.xyz_offsets(XT32_FIELDS), False)
        got = ap.filter_points(p, 1.0, 100.0, 0.5, 2)
        self.assertLess(len(got), len(p)); self.assertGreater(len(got), 0)
        idx = np.unique(np.floor(got / 0.5).astype(np.int64), axis=0)
        self.assertEqual(len(idx), len(got))   # one centroid per cube


if __name__ == '__main__':
    unittest.main()

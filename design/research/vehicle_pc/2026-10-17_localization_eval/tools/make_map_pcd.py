"""Localization-evaluation map from a GLIM dump: all submap points in the GLIM map frame (loop-closure corrected T_world_origin),
voxel-downsampled, written as a binary PCD (x y z float32). Analysis tooling, not product code.
usage: python3 make_map_pcd.py <dump_dir> <out.pcd> [voxel_m=0.2]"""
import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc

dump, out = sys.argv[1], sys.argv[2]; v = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
pts = mc.world_points(mc.read_dump(dump))
key = np.floor(pts / v).astype(np.int64); _, idx = np.unique(key, axis=0, return_index=True)
p = pts[np.sort(idx)].astype(np.float32)
mc.write_pcd(p, __import__('pathlib').Path(out))
print(f'{dump}: {len(pts)} points -> {len(p)} after {v} m voxel; x {p[:,0].min():.0f}..{p[:,0].max():.0f}, y {p[:,1].min():.0f}..{p[:,1].max():.0f}, z {p[:,2].min():.1f}..{p[:,2].max():.1f}')

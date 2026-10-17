"""Split a PCD map (binary x y z float32, as written by make_map_pcd.py) into square tiles with an Autoware pointcloud map
metadata file (x_resolution, y_resolution, '<file>: [x_min, y_min]'). Analysis tooling, not product code.
usage: python3 tile_pcd.py <map.pcd> <out_dir> [tile_m=20]"""
import sys, os, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
from pathlib import Path


def read_pcd(path):
    b = open(path, 'rb').read(); i = b.index(b'DATA binary\n') + len(b'DATA binary\n')
    return np.frombuffer(b[i:], dtype=np.float32).reshape(-1, 3)


src, out = sys.argv[1], Path(sys.argv[2]); tile = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0
out.mkdir(parents=True, exist_ok=True); p = read_pcd(src)
ij = np.floor(p[:, :2] / tile).astype(int); keys, inv = np.unique(ij, axis=0, return_inverse=True)
lines = [f'x_resolution: {tile}', f'y_resolution: {tile}']
for n, (ix, iy) in enumerate(keys):
    name = f'tile_{ix}_{iy}.pcd'; mc.write_pcd(p[inv.ravel() == n], out / name)
    lines.append(f'{name}: [{int(round(ix * tile))}, {int(round(iy * tile))}]')
(out / 'metadata.yaml').write_text('\n'.join(lines) + '\n')
print(f'{src}: {len(p)} points -> {len(keys)} tiles of {tile} m in {out}')

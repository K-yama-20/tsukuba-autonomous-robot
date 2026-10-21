"""Analysis re-conversion for plan C (DEC-210, REV-131; TS-44 real-data part). Analysis tooling, not product code: the result is
NOT registered in the map database. The given /config is used for the IMU mounting and recorded (for sources without a /config
snapshot this is the analysis-only use that DEC-212 has not decided for the product).

usage: python3 corridor_analysis.py <source_dir> <sensor_config.json> <params_dir> <out_dir>
Writes <out_dir>/ (the conversion products) and <out_dir>/overlay.png on the corridor grid:
  white = corridor free; black = an occupied cell of the current classification map (map.pgm, ground band) inside the corridor;
  dark red = occupied outside the corridor; light green = free in map.pgm but unknown in the corridor; grey = unknown in both.
Prints a JSON summary.
"""
import json
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'gouda_core'))
from gouda_core import map_convert as mc  # noqa: E402
from gouda_core import png as pngmod  # noqa: E402
from gouda_core.monitor_core import SensorConfig  # noqa: E402


def read_map(out, name):
    meta = yaml.safe_load((out / f'{name}.yaml').read_text())
    raw = (out / f'{name}.pgm').read_bytes(); w, h = [int(v) for v in raw.split(b'\n')[1].split()]
    img = np.frombuffer(raw.split(b'\n', 3)[3], dtype=np.uint8).reshape(h, w)[::-1, :]   # row 0 = lowest y
    return img, float(meta['resolution']), float(meta['origin'][0]), float(meta['origin'][1])


def main():
    src, cfg, params, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    s = {}
    for f in ('gouda_map_creator.yaml', 'gouda_map_creator.trial.yaml'):
        p = params / f
        if p.is_file():
            s.update(((yaml.safe_load(p.read_text()) or {}).get('gouda_map_creator') or {}).get('ros__parameters') or {})
    conf = SensorConfig(cfg)
    stats = mc.convert(src, out, s, {'values': dict(conf.values), 'source': f'{cfg} (config_revision {conf.config_revision}; analysis only, not the mapping run snapshot)'})
    rec = json.loads((out / mc.CORRIDOR_RECORD).read_text()) if stats['swept_corridor']['made'] else stats['swept_corridor']
    summary = {'source': str(src), 'corridor': rec, 'settings_used': {k: s.get(k) for k in mc.CORRIDOR_KEYS + ['map_resolution_m']}}
    if stats['swept_corridor']['made']:
        cor, res, ox, oy = read_map(out, mc.CORRIDOR_MAP)
        band, bres, box, boy = read_map(out, 'map')
        h, w = cor.shape
        ii, jj = np.meshgrid(np.arange(w), np.arange(h))
        bx = np.floor((ox + (ii * 2 + 1) * res / 2 - box) / bres).astype(int); by = np.floor((oy + (jj * 2 + 1) * res / 2 - boy) / bres).astype(int)
        inside = (bx >= 0) & (bx < band.shape[1]) & (by >= 0) & (by < band.shape[0])
        bv = np.full(cor.shape, 205, dtype=np.uint8); bv[inside] = band[by[inside], bx[inside]]
        free = cor == 254
        rgb = np.empty(cor.shape + (3,), dtype=np.uint8); rgb[:] = (205, 205, 205)
        rgb[(bv == 254) & ~free] = (190, 230, 190)
        rgb[free] = (255, 255, 255)
        rgb[(bv == 0) & ~free] = (140, 0, 0)
        rgb[(bv == 0) & free] = (0, 0, 0)
        img = rgb[::-1, :, :]
        (out / 'overlay.png').write_bytes(pngmod.encode_rgb(img.shape[1], img.shape[0], img.tobytes()))
        summary['cells'] = {'corridor_free': int(free.sum()), 'band_occupied_inside_corridor': int(((bv == 0) & free).sum()),
                            'band_free_outside_corridor': int(((bv == 254) & ~free).sum()), 'band_occupied_outside_corridor': int(((bv == 0) & ~free).sum())}
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()

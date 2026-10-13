"""Run the Python firmware model (esp32_sim) on a pseudo-terminal so vehicle_bridge can be tested without hardware.

Stub for software tests only (TS-13, TS-19 PC side on Ubuntu). Prints the slave device path (pass it as serial_port) and
the boot token. The configuration starts EMPTY unless --config-from <params_dir> [--trial] is given; the bridge is expected to
register it with SET_CONFIG, exactly as with the device. Optional scripted gamepad input (--bt "t_ms:x:y,...") exercises
manual priority. The model's wall clock is time.monotonic(); the periodic tick runs every --tick-ms.

Usage: python3 -m gouda_core.esp32_sim_pty [--config-from design/generated/params --trial] [--log file]
"""
from __future__ import annotations

import argparse
import os
import pty
import random
import select
import sys
import time
import tty

from gouda_core import esp32_protocol as p
from gouda_core import esp32_sim as sim


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--config-from', default=None, help='params dir with firmware_config.yaml (start configured; default: unconfigured)')
    ap.add_argument('--trial', action='store_true', help='also read firmware_config.trial.yaml (software trial values)')
    ap.add_argument('--tick-ms', type=int, default=5)
    ap.add_argument('--bt', default='', help='scripted gamepad: "t_ms:x_q:y_q,..." (connect at first entry; x right+, y forward+)')
    ap.add_argument('--log', default=None, help='append applied source/reason transitions and events here')
    ap.add_argument('--path-file', default=None, help='write the slave pty path here')
    a = ap.parse_args(argv)
    cfg = None
    if a.config_from:
        from gouda_core.vehicle_bridge_node import load_firmware_config
        cfg = load_firmware_config(a.config_from, a.trial) or None
    fw = sim.Esp32Sim(boot_token=random.getrandbits(32) or 1, config=cfg)
    master, slave = pty.openpty(); tty.setraw(master); tty.setraw(slave)
    path = os.ttyname(slave)
    if a.path_file: open(a.path_file, 'w').write(path + '\n')
    print(f'esp32_sim pty={path} boot_token=0x{fw.boot_token:08x} config_valid={fw.cfg_valid}', flush=True)
    log = open(a.log, 'a') if a.log else None
    bt = [tuple(int(v) for v in e.split(':')) for e in a.bt.split(',') if e]
    t0 = time.monotonic(); now = lambda: int((time.monotonic() - t0) * 1000)
    os.write(master, fw.drain())
    last_applied = None; bt_i = 0; nev = 0
    try:
        while True:
            r, _, _ = select.select([master], [], [], a.tick_ms / 1000)
            t = now()
            if r:
                data = os.read(master, 4096)
                os.write(master, fw.feed(data, t))
            if bt_i < len(bt) and t >= bt[bt_i][0]:
                if bt_i == 0: fw.bt_connect(t)
                fw.bt_report(bt[bt_i][1], bt[bt_i][2], t); bt_i += 1
            os.write(master, fw.tick(t))
            ap_ = fw.applied(); key = (ap_.source, ap_.reason, ap_.target_mv)
            if key != last_applied:
                line = f'{t} ms applied source={ap_.source} reason={ap_.reason} target_mv={ap_.target_mv} pc_enabled={fw.pc_enabled}'
                print(line, flush=True); last_applied = key
                if log: log.write(line + '\n'); log.flush()
            while nev < len(fw.events):
                e = fw.events[nev]; nev += 1
                line = f'{e[2]} ms event {p.EVENT_NAMES.get(e[0], e[0])} arg={e[1]}'
                print(line, flush=True)
                if log: log.write(line + '\n'); log.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if log: log.close()
        os.close(master); os.close(slave)


if __name__ == '__main__':
    sys.exit(main())

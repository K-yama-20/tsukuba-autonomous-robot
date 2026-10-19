"""Record the receiver's stream and port settings before and after the first driver start (REV-071; the human's instruction with
DEC-140: "最初の起動の前後で gso と getDataInOut を記録すること"). Test and maintenance tool; never started by gouda.sh.

Follows the human's notes (reports/mosaic-G5_P6_取扱上の注意事項.md):
- §3 / DEC-141: the port is given only by its /dev/serial/by-id/ name.
- §7: refused when another process has the port open (the driver, a diagnostic cat, ...).
- §2: the port is put in raw mode with echo, canonical input, CR/LF conversion and software flow control off, and the settings
  are read back and recorded before anything is sent.
- §4: reading starts before sending; every byte sent and received is kept raw with its time; the result is judged from the
  replies ($R: / $R; accepted, $R? error), never from the send alone. A CR is sent first so that a half line left in the
  receiver is processed and its reply recorded.
Only the read-only queries below can be sent (no setting is changed; no Boot save: §5 / §6 stay the rules of manual work).
The wait for the replies is given by the person running it (no default value).
"""
from __future__ import annotations

import json
import os
import termios
import threading
import time
from pathlib import Path
from typing import Optional

from gouda_core import device_watch as dw

QUERIES = ('lif,Identification', 'gso', 'getDataInOut')   # read-only (the human's notes §4)
REPLY_MARKS = {b'$R:': 'accepted', b'$R;': 'accepted', b'$R?': 'error'}


def make_raw(fd: int) -> dict:
    """Raw, no echo, no canonical input, no CR/LF conversion, no software flow control; returns the settings read back."""
    a = termios.tcgetattr(fd)
    a[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON | termios.IXOFF)
    a[1] &= ~termios.OPOST
    a[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    a[2] &= ~(termios.CSIZE | termios.PARENB); a[2] |= termios.CS8 | termios.CREAD | termios.CLOCAL
    a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, a)
    b = termios.tcgetattr(fd)
    flags = {'echo': bool(b[3] & termios.ECHO), 'icanon': bool(b[3] & termios.ICANON), 'icrnl': bool(b[0] & termios.ICRNL),
             'ixon': bool(b[0] & termios.IXON), 'ixoff': bool(b[0] & termios.IXOFF), 'opost': bool(b[1] & termios.OPOST)}
    return flags


def replies(data: bytes) -> list:
    """[(mark, judgement, the line)] of the receiver's reply lines in the received bytes."""
    out = []
    for raw in data.replace(b'\r', b'\n').split(b'\n'):
        for mark, judgement in REPLY_MARKS.items():
            if raw.startswith(mark):
                out.append((mark.decode(), judgement, raw.decode('ascii', errors='replace')))
    return out


def query(port: str, out_path: Path, reply_wait_s: float, label: str, queries=QUERIES, require_by_id: bool = True,
          proc_root: str = '/proc') -> dict:
    """Send the queries on port and write a JSON record (raw bytes as hex and text). Raises ValueError when refused."""
    if require_by_id and dw.by_id_problem(port):
        raise ValueError(dw.by_id_problem(port))
    bad = [q for q in queries if q not in QUERIES]
    if bad:
        raise ValueError(f'only the read-only queries {QUERIES} are allowed, not {bad}')
    users = dw.tty_users(port, proc_root=proc_root, exclude=(os.getpid(),))
    if users:
        raise ValueError(f'{port} is open by pid {users} (the driver or another reader): the query is not sent (notes §7)')
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    record = {'label': label, 'port': port, 'realpath': os.path.realpath(port), 'started_at': time.time(), 'reply_wait_s': reply_wait_s, 'events': []}
    try:
        flags = make_raw(fd)
        record['tty_after_raw'] = flags
        if any(flags.values()):
            raise ValueError(f'the port did not take the raw settings: {flags}; nothing is sent (notes §2)')
        received = bytearray(); stop = threading.Event(); lock = threading.Lock()

        def reader():
            while not stop.is_set():
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    chunk = b''
                if chunk:
                    with lock:
                        received.extend(chunk); record['events'].append({'t': time.time(), 'dir': 'rx', 'hex': chunk.hex()})
                else:
                    time.sleep(0.01)
        th = threading.Thread(target=reader, daemon=True); th.start()
        for text in [''] + list(queries):          # a bare CR first (notes §4)
            data = (text + '\r').encode('ascii')
            with lock:
                start = len(received)
                record['events'].append({'t': time.time(), 'dir': 'tx', 'text': text, 'hex': data.hex()})
            os.write(fd, data)
            time.sleep(reply_wait_s)
            with lock:
                part = bytes(received[start:])
            record.setdefault('replies', []).append({'sent': text, 'reply_lines': replies(part), 'bytes_after': len(part),
                                                     'text_after': part.decode('ascii', errors='replace')})
        stop.set(); th.join()
        record['received_total'] = len(received)
    finally:
        os.close(fd)
        record['ended_at'] = time.time()
        Path(out_path).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Record gso / getDataInOut of the Septentrio receiver (read-only queries)')
    ap.add_argument('--port', required=True, help='/dev/serial/by-id/... of the port to query (the notes suggest USB2 for queries)')
    ap.add_argument('--out', required=True); ap.add_argument('--label', required=True, help='e.g. before_first_start / after_first_start')
    ap.add_argument('--reply-wait-s', type=float, required=True, help='wait after each query (no default: given by the person running it)')
    a = ap.parse_args(argv)
    try:
        r = query(a.port, Path(a.out), a.reply_wait_s, a.label)
    except ValueError as e:
        print('REFUSED:', e); return 2
    for q in r['replies']:
        print(f"[{q['sent'] or 'CR'}] {len(q['reply_lines'])} reply line(s): {[x[1] for x in q['reply_lines']]}; {q['bytes_after']} bytes")
    print('written', a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

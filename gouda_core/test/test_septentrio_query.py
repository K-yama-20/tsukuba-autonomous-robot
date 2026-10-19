"""Unit tests of septentrio_query (REV-071) with a pseudo terminal standing in for the receiver (no hardware).
Checked: only by-id names and only the read-only queries; the port is raw with echo off before anything is sent (read back);
a bare CR is sent first; replies are judged from $R: / $R; / $R?; every byte is recorded."""
import json
import os
import pty
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import septentrio_query as sq  # noqa: E402


class FakeReceiver:
    """Answers the queries like the receiver did in the human's notes §4 (reply texts are test texts)."""

    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)   # the slave stays open: on Linux the master read fails (EIO) while no slave is open
        self.got = bytearray(); self.stop = threading.Event()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        buf = b''
        while not self.stop.is_set():
            try:
                c = os.read(self.master, 1024)
            except OSError:
                return
            self.got.extend(c); buf += c
            while b'\r' in buf:
                line, buf = buf.split(b'\r', 1)
                if line == b'lif,Identification': os.write(self.master, b'$R; lif,Identification\r\n  Identification ...\r\nUSB2>')
                elif line == b'gso': os.write(self.master, b'$R: gso\r\n  SBFOutput, Stream1, none, none, off\r\nUSB2>')
                elif line == b'getDataInOut': os.write(self.master, b'$R: gdio\r\n  DataInOut, USB2, auto, NMEA, connected\r\nUSB2>')
                elif line == b'': os.write(self.master, b'USB2>')
                else: os.write(self.master, b'$R? ' + line + b': Invalid command!\r\nUSB2>')


class QueryTests(unittest.TestCase):
    def test_refusals(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): sq.query('/dev/ttyACM1', Path(d) / 'o.json', 0.01, 'x')
            with self.assertRaises(ValueError): sq.query('/dev/serial/by-id/usb-X-if02', Path(d) / 'o.json', 0.01, 'x', queries=('sso,Stream1,USB1,PVTGeodetic,sec1',))

    def test_query_records_replies(self):
        rx = FakeReceiver()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'before.json'
            r = sq.query(rx.path, out, 0.2, 'before_first_start', require_by_id=False, proc_root=str(Path(d) / 'no_proc'))
            rx.stop.set()
            self.assertFalse(any(r['tty_after_raw'].values()), 'raw, echo off, no flow control before sending')
            self.assertEqual([x['sent'] for x in r['replies']], ['', 'lif,Identification', 'gso', 'getDataInOut'])
            j = {x['sent']: [m[1] for m in x['reply_lines']] for x in r['replies']}
            self.assertEqual(j['gso'], ['accepted']); self.assertEqual(j['getDataInOut'], ['accepted']); self.assertEqual(j['lif,Identification'], ['accepted'])
            self.assertTrue(bytes(rx.got).startswith(b'\rlif,Identification\r'), 'a bare CR first, then the query')
            saved = json.loads(out.read_text())
            self.assertGreater(saved['received_total'], 0); self.assertTrue(any(e['dir'] == 'tx' for e in saved['events']))

    def test_reply_judgement(self):
        r = sq.replies(b'$R? GPGSV,1,1,00,,,*37: Invalid command!\r\n$R: gso\r\n  x\r\n$R; lif\r\n')
        self.assertEqual([x[1] for x in r], ['error', 'accepted', 'accepted'])


if __name__ == '__main__':
    unittest.main()

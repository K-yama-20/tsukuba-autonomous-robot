"""NTRIP relay (DEC-139 option B1, DEC-151 step 3, DEC-156). No ROS dependency.

RTKLIB's str2str relays the Point One caster to the receiver's USB2 (PRM-76) and sends the receiver's GGA back (-b 1). The
receiver computes RTK itself; the relay does not interpret the data. The NTRIP connection data is secret (DEC-139: never in
logs, rosbag or records):
- relay_commands() returns two command lines: the one that is started (holds the secret, kept only in memory) and a public
  one with the ntrip URL replaced by <redacted>, which is the only one that may be recorded.
- str2str's status lines on stderr are reduced to the state characters, byte count and bps; the message field (which holds
  caster:port/mountpoint for an NTRIP stream) is dropped, and a line that cannot be parsed is only counted.
str2str's own timeout, reconnect interval and status interval stay at its defaults (DEC-156).
"""
from __future__ import annotations

import re
import time
from typing import Callable, Iterable, Optional

from gouda_core.device_watch import BY_ID_DIR, REDACTED

# "<date> <time> [<state chars>] <bytes> B <bps> bps <msg>": state chars are the input stream then each output stream
STATUS = re.compile(r'\[([EWCA-]+)\]\s+(\d+)\s+B\s+(\d+)\s+bps')
STATE_NAMES = {'E': 'error', '-': 'closed', 'W': 'waiting', 'C': 'connected', 'A': 'active'}


def serial_path(device: str) -> Optional[str]:
    """'serial:/dev/serial/by-id/<name>' -> 'serial/by-id/<name>' (str2str's serial:// takes the part after /dev/)."""
    if not isinstance(device, str) or not device.startswith('serial:' + BY_ID_DIR):
        return None
    return device[len('serial:/dev/'):]


def relay_commands(exe: str, ntrip: dict, device: str, baud) -> tuple:
    """(command to start, public command to record). The first one holds the secret: never log or record it."""
    path = serial_path(device)
    url = f"ntrip://{ntrip['user']}:{ntrip['password']}@{ntrip['caster']}:{ntrip['port']}/{ntrip['mountpoint']}"
    out = f'serial://{path}:{baud}'
    launch = [exe, '-in', url, '-out', out, '-b', '1']
    public = [exe, '-in', f'ntrip://{REDACTED}', '-out', out, '-b', '1']
    return launch, public


def parse_status(line: str) -> Optional[dict]:
    """{'input': state, 'outputs': [states], 'bytes': n, 'bps': n} from one str2str status line; None if it is not one.
    The message field is never returned."""
    m = STATUS.search(line or '')
    if not m:
        return None
    chars = m.group(1)
    return {'input': STATE_NAMES[chars[0]], 'outputs': [STATE_NAMES[c] for c in chars[1:]], 'bytes': int(m.group(2)), 'bps': int(m.group(3))}


class StatusTracker:
    """Keeps the last status; feed() returns the new status when the states changed (None otherwise)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.last: Optional[dict] = None
        self.unparsed = 0
        self.callback_errors = 0
        self.bytes_changed_at: Optional[float] = None   # monotonic time the received byte count last grew

    def feed(self, line: str) -> Optional[dict]:
        st = parse_status(line)
        if st is None:
            if line.strip():
                self.unparsed += 1
            return None
        prev, self.last = self.last, st
        if prev is None or st['bytes'] > prev['bytes']:
            self.bytes_changed_at = self.clock()
        if prev is None or (prev['input'], prev['outputs']) != (st['input'], st['outputs']):
            return st
        return None


def read_status(lines: Iterable[str], tracker: StatusTracker, on_change: Callable[[dict], None]) -> None:
    """Read str2str's stderr until it closes; call on_change(status) on every state change. The stream is always drained to
    the end: an error in on_change is counted (tracker.callback_errors) and reading goes on, because a pipe nobody reads
    fills up and str2str then blocks on its status line and stops relaying."""
    for line in lines:
        try:
            st = tracker.feed(line)
            if st is not None:
                on_change(st)
        except Exception:   # noqa: BLE001 - keep draining whatever happens
            tracker.callback_errors += 1


def build_relay(exe: Optional[str], ntrip: Optional[dict], device: Optional[str], baud, driver_started: bool) -> dict:
    """Decide the relay from its inputs (DEC-156). Returns {'launch', 'public', 'serial_path', 'reason'}: launch holds the
    secret (start only, never record); public and reason never contain NTRIP data."""
    out = {'launch': None, 'public': None, 'serial_path': None, 'reason': None}
    if not driver_started:
        out['reason'] = 'the GNSS driver is not started, so the receiver is not set up for corrections'
    elif ntrip is None:
        out['reason'] = 'no RTK corrections (see the GNSS settings record)'
    elif serial_path(device or '') is None:
        out['reason'] = f'rtk_relay_device (PRM-76) is unresolved or not a serial:{BY_ID_DIR} name (DEC-141)'
    elif exe is None:
        out['reason'] = 'str2str is not installed (rtklib: setup.sh, DEC-151 step 4)'
    elif baud is None:
        out['reason'] = 'rtk_settings.serial_1.baud_rate is missing in the driver template'
    else:
        out['launch'], out['public'] = relay_commands(exe, ntrip, device, baud)
        out['serial_path'] = device[len('serial:'):]
    return out

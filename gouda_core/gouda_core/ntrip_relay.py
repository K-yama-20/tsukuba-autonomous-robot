"""NTRIP relay (DEC-139 option B1, DEC-151 step 3, DEC-156, DEC-361). No ROS dependency.

RTKLIB's str2str relays the Point One caster to the receiver's USB2 (PRM-76) and sends the receiver's GGA back (-b 1). The
receiver computes RTK itself; the relay does not interpret the data. The caster takes connections only over TLS and str2str
has no TLS (第145便), so str2str talks to stunnel4 on a loopback port and stunnel4 reaches the caster over TLS with the
certificate checked (DEC-361 option a; ntrip_relay_runner starts both). There is no plaintext path to the caster: without
stunnel4 the relay is not started. The NTRIP connection data is secret (DEC-139: never in logs, rosbag or records):
- relay_commands() returns two command lines: the one that is started (holds the secret, kept only in memory) and a public
  one with the ntrip URL replaced by <redacted>, which is the only one that may be recorded.
- stunnel4 gets its configuration (it names the caster) on its stdin, never in a file or its argv; its log names the caster
  and its addresses, so it is reduced to TLS event categories (tls_event) and its text is dropped.
- str2str's status lines on stderr are reduced to the state characters, byte count and bps; the message field (which holds
  caster:port/mountpoint for an NTRIP stream) is dropped, and a line that cannot be parsed is only counted.
str2str's own timeout, reconnect interval and status interval stay at its defaults (DEC-156).
"""
from __future__ import annotations

import json
import re
import socket
import sys
import time
from typing import Callable, Iterable, Optional

from gouda_core.device_watch import BY_ID_DIR, REDACTED

LOOPBACK = '127.0.0.1'
CA_FILE = '/etc/ssl/certs/ca-certificates.crt'   # the system CA bundle (package ca-certificates, setup.sh)
SERVICE = 'ntrip'                                 # the stunnel service name (a name, not a setting)
# stunnel 5.72 (Ubuntu 24.04) logs "Service [ntrip] (FD=n) bound to <address>:<port>" at level 6 once the loopback port
# listens (checked on the VM, 第147便); the runner starts str2str only after this line
STUNNEL_BOUND = f'Service [{SERVICE}] (FD='
STUNNEL_BOUND_WORDS = ') bound to '
TLS_PREFIX = '[TLS] '
# stunnel log line -> category (first match wins). Only the category is passed on; the line names the caster
TLS_EVENTS = (
    ('certificate_rejected', ('Rejected by CERT', 'certificate verify failed', 'Certificate check failed')),
    ('connected', ('connected remote server',)),
    ('connect_failed', ('s_connect: connect ', 'No remote host resolved', 'Error resolving', 'getaddrinfo')),
    ('tls_failed', ('SSL_connect', 'TLS fatal alert', 'handshake failure')),
    ('closed', ('Connection closed', 'Connection reset')),
)
STUNNEL_EXITED = 'stunnel_exited'                 # written by the runner when stunnel ends before it listens
TLS_CATEGORIES = {c for c, _ in TLS_EVENTS} | {STUNNEL_EXITED}

# "<date> <time> [<state chars>] <bytes> B <bps> bps <msg>": state chars are the input stream then each output stream
STATUS = re.compile(r'\[([EWCA-]+)\]\s+(\d+)\s+B\s+(\d+)\s+bps')
STATE_NAMES = {'E': 'error', '-': 'closed', 'W': 'waiting', 'C': 'connected', 'A': 'active'}


def serial_path(device: str) -> Optional[str]:
    """'serial:/dev/serial/by-id/<name>' -> 'serial/by-id/<name>' (str2str's serial:// takes the part after /dev/)."""
    if not isinstance(device, str) or not device.startswith('serial:' + BY_ID_DIR):
        return None
    return device[len('serial:/dev/'):]


def relay_commands(exe: str, ntrip: dict, device: str, baud, local_port: int) -> tuple:
    """(str2str command to start, public command to record). str2str connects to stunnel4 on the loopback local_port, never
    to the caster itself. The first one holds the secret (user, password, mountpoint): never log or record it."""
    path = serial_path(device)
    url = f"ntrip://{ntrip['user']}:{ntrip['password']}@{LOOPBACK}:{local_port}/{ntrip['mountpoint']}"
    out = f'serial://{path}:{baud}'
    launch = [exe, '-in', url, '-out', out, '-b', '1']
    public = [exe, '-in', f'ntrip://{REDACTED}', '-out', out, '-b', '1']
    return launch, public


def stunnel_config(ntrip: dict, local_port: int) -> str:
    """stunnel4's configuration (holds the caster's name: pass it on stunnel's stdin only, -fd 0). Client mode, loopback
    listener, TLS to the caster with the certificate chain and the host name checked; the name is resolved per connection."""
    caster = ntrip['caster']
    return '\n'.join(['foreground = yes', 'pid =', 'debug = 6', f'[{SERVICE}]', 'client = yes', f'accept = {LOOPBACK}:{local_port}',
                      f"connect = {caster}:{ntrip['port']}", f'sni = {caster}', 'verifyChain = yes', f'CAfile = {CA_FILE}',
                      f'checkHost = {caster}', 'delay = yes', ''])


def stunnel_bound(line: str) -> bool:
    """True for stunnel's line saying the loopback service listens."""
    return STUNNEL_BOUND in (line or '') and STUNNEL_BOUND_WORDS in line


def tls_event(line: str) -> Optional[str]:
    """Category of one stunnel log line, or None. The line itself is never returned (it names the caster)."""
    for category, needles in TLS_EVENTS:
        if any(n in (line or '') for n in needles):
            return category
    return None


def parse_tls(line: str) -> Optional[str]:
    """The category of a '[TLS] <category>' line written by ntrip_relay_runner, or None."""
    if not (line or '').startswith(TLS_PREFIX):
        return None
    category = line[len(TLS_PREFIX):].strip()
    return category if category in TLS_CATEGORIES else None


def free_loopback_port() -> int:
    """A loopback TCP port that is free now (the kernel picks it)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((LOOPBACK, 0))
        return s.getsockname()[1]
    finally:
        s.close()


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
        self.tls: Optional[str] = None                  # last TLS event category from the runner
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


def read_status(lines: Iterable[str], tracker: StatusTracker, on_change: Callable[[dict], None],
                on_tls: Optional[Callable[[str], None]] = None) -> None:
    """Read the relay's stderr until it closes; call on_change(status) on every str2str state change and on_tls(category)
    on every change of the TLS event category (lines '[TLS] <category>' from ntrip_relay_runner). The stream is always
    drained to the end: an error in a callback is counted (tracker.callback_errors) and reading goes on, because a pipe
    nobody reads fills up and str2str then blocks on its status line and stops relaying."""
    for line in lines:
        try:
            tls = parse_tls(line)
            if tls is not None:
                if tls != tracker.tls:
                    tracker.tls = tls
                    if on_tls is not None:
                        on_tls(tls)
                continue
            st = tracker.feed(line)
            if st is not None:
                on_change(st)
        except Exception:   # noqa: BLE001 - keep draining whatever happens
            tracker.callback_errors += 1


def build_relay(exe: Optional[str], ntrip: Optional[dict], device: Optional[str], baud, driver_started: bool,
                stunnel: Optional[str]) -> dict:
    """Decide the relay from its inputs (DEC-156, DEC-361). Returns {'launch', 'launch_input', 'public', 'serial_path',
    'reason'}: launch starts ntrip_relay_runner and launch_input (its stdin) holds the secret (start only, never record);
    public and reason never contain NTRIP data. Without stunnel4 nothing is started: the credentials never go out in
    plaintext (the caster takes TLS only)."""
    out = {'launch': None, 'launch_input': None, 'public': None, 'serial_path': None, 'reason': None}
    if serial_path(device or '') is not None:
        out['serial_path'] = device[len('serial:'):]   # watched even when the relay is not started (presence is recorded)
    if not driver_started:
        out['reason'] = 'the GNSS driver is not started, so the receiver is not set up for corrections'
    elif ntrip is None:
        out['reason'] = 'no RTK corrections (see the GNSS settings record)'
    elif serial_path(device or '') is None:
        out['reason'] = f'rtk_relay_device (PRM-76) is unresolved or not a serial:{BY_ID_DIR} name (DEC-141)'
    elif exe is None:
        out['reason'] = 'str2str is not installed (rtklib: setup.sh, DEC-151 step 4)'
    elif stunnel is None:
        out['reason'] = ('stunnel4 is not installed: the caster is reached only over TLS and the credentials are never sent '
                         'in plaintext (DEC-361; bash setup.sh)')
    elif baud is None:
        out['reason'] = 'rtk_settings.serial_1.baud_rate is missing in the driver template'
    else:
        _launch, public = relay_commands(exe, ntrip, device, baud, 0)
        out['launch'] = [sys.executable, '-m', 'gouda_core.ntrip_relay_runner']
        out['launch_input'] = json.dumps({'str2str': exe, 'stunnel': stunnel, 'ntrip': ntrip, 'device': device, 'baud': baud})
        out['public'] = ['gouda_core.ntrip_relay_runner:', stunnel, '-fd', '0', '(TLS to the caster)', '+'] + public
    return out

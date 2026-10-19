"""Device identity and the restart rule of the sensor supervisor (ND-18). No ROS dependency. Design: docs/sensor_supervision.md.

A device is found by its NAME, never by a kernel number (DEC-081):
  - IMU: the /dev/serial/by-id/... name (PRM-54). Its identity is the USB enumeration behind the name: tty name + USB bus and
    device number (sysfs). The USB device number increases on every enumeration, so a re-plug or a passthrough hand-over
    gives a new identity even when the same ttyACMn is reused.
  - XT-32: the network interface that holds the PC address of the LiDAR link (PRM-51). Its identity is interface name +
    ifindex; a re-registered USB-LAN adapter gets a new ifindex.
Restart rule (DEC-088): a driver is (re)created ONLY when the identity of its device changes (first appearance, or a new
enumeration). The same identity never causes a restart, even if the driver exited, because restarting the IMU driver without a
re-plug leaves the IMU unresponsive (FILE-VEHICLE-PC-GLIM-START). A device that disappears has its driver stopped.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

BY_ID_DIR = '/dev/serial/by-id/'   # serial devices are named only by their by-id link (DEC-081, DEC-141)


def by_id_problem(path: str) -> Optional[str]:
    """None when path is a /dev/serial/by-id/<name> link name; otherwise why it is refused. ttyACM / ttyUSB numbers swap with
    the plug order and on re-connection (the IMU and the mosaic-go are both ttyACM), so they are never accepted (DEC-141)."""
    if not isinstance(path, str) or not path.startswith(BY_ID_DIR):
        return f'{path!r} is not a {BY_ID_DIR} name (ttyACM numbers swap with the plug order; DEC-141)'
    name = path[len(BY_ID_DIR):]
    if not name or '/' in name or name in ('.', '..'):
        return f'{path!r} does not name one device under {BY_ID_DIR}'
    return None


ACTION_NONE = 'none'
ACTION_START = 'start'        # device appeared (first time, or after being absent)
ACTION_RESTART = 'restart'    # device re-enumerated while present: new identity
ACTION_STOP = 'stop'          # device disappeared


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return None


def tty_identity(by_id_path: str, sys_root: str = '/sys') -> Optional[str]:
    """'ttyACM1 usb 2-25' for the device behind a by-id name, or None when the name does not exist (device absent)."""
    if not os.path.exists(by_id_path):
        return None
    tty = os.path.basename(os.path.realpath(by_id_path))
    iface = os.path.realpath(os.path.join(sys_root, 'class', 'tty', tty, 'device'))   # the USB interface directory (2-2.2:<config>.<interface>)
    usbdev = os.path.dirname(iface)                                                      # .../2-2.2 (USB device)
    bus, dev = _read(os.path.join(usbdev, 'busnum')), _read(os.path.join(usbdev, 'devnum'))
    return f'{tty} usb {bus}-{dev}' if bus and dev else f'{tty} usb ?'


def net_identity(host_ip: str, ip_addr_json: str) -> Optional[str]:
    """'enx6c6e0754b24a #6' for the interface that holds host_ip (from `ip -j -4 addr` output), or None."""
    try:
        links = json.loads(ip_addr_json or '[]')
    except ValueError:
        return None
    for link in links:
        for a in link.get('addr_info', []):
            if a.get('local') == host_ip:
                return f"{link.get('ifname')} #{link.get('ifindex')}"
    return None


@dataclass
class WatchedDevice:
    """One device and the identity its driver was created for (SO-12)."""
    name: str
    identity: Optional[str] = None      # identity the current driver was started for (None: no driver for it)
    seen: Optional[str] = None          # identity observed at the last evaluation
    evaluated: bool = False             # False until the first evaluation (so that an absent device is reported at start too)

    def presence_changed(self, observed: Optional[str]) -> bool:
        """True at the first evaluation and whenever the observed identity differs from the last one."""
        return (not self.evaluated) or observed != self.seen

    def decide(self, observed: Optional[str]) -> str:
        """The action for a newly observed identity. Does not change state (apply() does)."""
        if observed is None:
            return ACTION_STOP if self.identity is not None else ACTION_NONE
        if self.identity is None:
            return ACTION_START
        return ACTION_RESTART if observed != self.identity else ACTION_NONE

    def apply(self, observed: Optional[str], action: str) -> None:
        self.seen = observed; self.evaluated = True
        if action in (ACTION_START, ACTION_RESTART):
            self.identity = observed
        elif action == ACTION_STOP:
            self.identity = None


def _fd_targets(proc_root: str, exclude: tuple):
    """(pid, link target) of every open file descriptor readable in proc_root, except the excluded pids."""
    try:
        names = os.listdir(proc_root)
    except OSError:
        return
    for name in names:
        if not name.isdigit() or int(name) in exclude:
            continue
        fd_dir = os.path.join(proc_root, name, 'fd')
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                yield int(name), os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue


def tty_users(device_path: str, proc_root: str = '/proc', exclude: tuple = ()) -> list:
    """PIDs that have the serial device open (by-id names are resolved), except the excluded ones (G-DUP-START: a second
    driver on the same IMU port splits its bytes)."""
    target = os.path.realpath(device_path)
    return sorted({pid for pid, link in _fd_targets(proc_root, exclude) if link.startswith('/') and os.path.realpath(link) == target})


def udp_port_users(port: int, proc_root: str = '/proc', exclude: tuple = ()) -> list:
    """PIDs holding a UDP socket bound to the local port (from <proc_root>/net/udp and udp6), except the excluded ones
    (G-DUP-START: a second LiDAR driver on the same port)."""
    inodes = set()
    for table in ('net/udp', 'net/udp6'):
        text = _read(os.path.join(proc_root, table))
        for line in (text or '').splitlines()[1:]:
            f = line.split()
            if len(f) > 9 and ':' in f[1] and int(f[1].rsplit(':', 1)[1], 16) == int(port):
                inodes.add(f[9])
    if not inodes:
        return []
    sockets = {f'socket:[{i}]' for i in inodes}
    return sorted({pid for pid, link in _fd_targets(proc_root, exclude) if link in sockets})


def merge_opened(previous: dict, current: dict) -> dict:
    """Identities of the devices whose driver was opened, kept across sessions: a device for which no driver was started in
    this session keeps the identity opened earlier (so re-opening the same enumeration is still recognised)."""
    out = dict(previous or {})
    for k, v in current.items():
        if v is not None:
            out[k] = v
    return out

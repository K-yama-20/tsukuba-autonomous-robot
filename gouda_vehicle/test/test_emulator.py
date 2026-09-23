import os
from pathlib import Path
import select
import subprocess
import time
import pytest
from gouda_vehicle.protocol import Frame, Parser, COMMAND, ARM, STATUS


def test_shared_core_wire_watchdog_and_epoch():
    binary=Path(os.environ.get('GOUDA_WORKSPACE',str(Path.home()/'gouda_ws')))/'build/gouda_core/emulator'
    if not binary.exists():pytest.skip('build native core emulator first')
    p=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    parser=Parser();status=None
    def read_for(seconds):
        nonlocal status
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if select.select([p.stdout],[],[],.01)[0]:
                frames=parser.feed(os.read(p.stdout.fileno(),4096))
                if frames:status=frames[-1]
        return status
    def send(f):p.stdin.write(f.encode());p.stdin.flush()
    try:
        s=read_for(.1);assert s and not s.flags
        epoch=s.token
        send(Frame(ARM,epoch,1,0,1));s=read_for(.06);assert s.flags
        send(Frame(COMMAND,epoch,2,1,1));s=read_for(.06);assert s.motion==1
        # Repeated valid-CRC stale packets cannot extend the deadline.
        for _ in range(5):send(Frame(COMMAND,epoch,2,1,1));read_for(.06)
        assert not status.flags and status.motion==0 and status.token!=epoch
        send(Frame(ARM,epoch,3,0,1));read_for(.06);assert not status.flags
        send(Frame(ARM,status.token,1,0,1));read_for(.06);assert status.flags
        # Corrupt frames cannot renew watchdog either.
        bad=bytearray(Frame(COMMAND,status.token,2,1,1).encode());bad[-1]^=1
        for _ in range(5):p.stdin.write(bad);p.stdin.flush();read_for(.06)
        assert not status.flags and status.fault==1
    finally:
        p.terminate();p.wait(timeout=2)

"""NTRIP relay runner (DEC-361 option a): stunnel4 carries the caster connection over TLS, str2str relays through it.

Started by gouda_sensor_supervisor as the NTRIP relay (ND-19) with `python3 -m gouda_core.ntrip_relay_runner`. The connection
data arrives on stdin as JSON {str2str, stunnel, ntrip, device, baud}: it is in no argv of this process and is never logged.
1. A free loopback port is taken. stunnel4 gets its configuration on its own stdin (-fd 0), so the caster's name is in no
   file and no argv (ntrip_relay.stunnel_config: client mode, certificate chain and host name checked).
2. When stunnel4's log says the loopback service listens, str2str is started with ntrip://user:pass@127.0.0.1:<port>/<mount>:
   the request with the credentials reaches only stunnel4 and leaves the PC only inside TLS. There is no plaintext path.
3. str2str's stderr is copied unchanged to this process's stderr (the supervisor reduces it, ntrip_relay.read_status).
   stunnel4's log names the caster and its addresses, so only its event categories are written ('[TLS] <category>').
4. When either child ends, the other is stopped; the exit code is str2str's (stunnel4's when str2str was never started).
   SIGINT / SIGTERM stop both. The children stay in the supervisor's process group, so gouda.sh stop reaches them too.
No time value is set here: the waits end on the children's own events (the bound line, their exit).
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading

from gouda_core import ntrip_relay as nr


def exit_code(code: int) -> int:
    """A child's return code as an exit status (killed by signal n -> 128 + n, as a shell reports it)."""
    return code if code >= 0 else 128 - code


class Runner:
    def __init__(self, cfg: dict, err=sys.stderr):
        self.cfg, self.err = cfg, err
        self._err_lock = threading.Lock()
        self.ended = threading.Event()
        self.bound = threading.Event()      # set when stunnel listens, or when its output ended (listening tells which)
        self.listening = False
        self.stunnel = None
        self.relay = None
        self.stopping = False

    def emit(self, line: str) -> None:
        with self._err_lock:
            self.err.write(line + '\n'); self.err.flush()

    def _read_stunnel(self, proc):
        for line in proc.stdout:   # drained to the end, or stunnel blocks on its log
            if nr.stunnel_bound(line):
                self.listening = True
                self.bound.set()
            category = nr.tls_event(line)
            if category is not None:
                self.emit(nr.TLS_PREFIX + category)
        self.bound.set()   # stunnel ended before or after binding: whoever waits looks at its exit

    def _copy_relay(self, proc):
        for line in proc.stderr:
            self.emit(line.rstrip('\n'))

    def _watch(self, proc):
        proc.wait()
        self.ended.set()

    def stop(self, *_):
        self.stopping = True
        for proc in (self.relay, self.stunnel):
            if proc is not None and proc.poll() is None:
                try: proc.send_signal(signal.SIGTERM)
                except ProcessLookupError: pass
        self.ended.set()

    def run(self) -> int:
        cfg = self.cfg
        port = nr.free_loopback_port()
        self.stunnel = subprocess.Popen([cfg['stunnel'], '-fd', '0'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, errors='replace')
        self.stunnel.stdin.write(nr.stunnel_config(cfg['ntrip'], port)); self.stunnel.stdin.close()
        threading.Thread(target=self._read_stunnel, args=(self.stunnel,), daemon=True).start()
        threading.Thread(target=self._watch, args=(self.stunnel,), daemon=True).start()
        self.bound.wait()
        if not self.listening:   # stunnel ended before listening (e.g. a configuration error): str2str is never started
            if not self.stopping:
                self.emit(nr.TLS_PREFIX + nr.STUNNEL_EXITED)
            return exit_code(self.stunnel.wait())
        if self.stopping:
            self.stop()
            return exit_code(self.stunnel.wait())
        launch, _public = nr.relay_commands(cfg['str2str'], cfg['ntrip'], cfg['device'], cfg['baud'], port)
        self.relay = subprocess.Popen(launch, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                      text=True, errors='replace')
        copier = threading.Thread(target=self._copy_relay, args=(self.relay,), daemon=True)
        copier.start()
        threading.Thread(target=self._watch, args=(self.relay,), daemon=True).start()
        self.ended.wait()
        self.stop()   # whichever ended first, the other follows
        code = self.relay.wait()
        self.stunnel.wait()
        copier.join()
        return exit_code(code)


def main() -> int:
    runner = Runner(json.loads(sys.stdin.read()))
    signal.signal(signal.SIGINT, runner.stop)
    signal.signal(signal.SIGTERM, runner.stop)
    return runner.run()


if __name__ == '__main__':
    sys.exit(main())

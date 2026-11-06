"""TEST ONLY (一時停止線, DEC-482): drive_sim_fixture.py with some waypoints of kind stop, plus a watcher (drive_sim_stop_watch.py)
that records the hold and presses 再開 through the monitor API (/api/command/resume) after a while. Used by drive_sim.sh through
SIM_FIXTURE; the scenario and the original fixture are unchanged.
usage: SIM_FIXTURE=<this file> SIM_STOP_MARKS=6 SIM_STOP_HOLD_S=25 SIM_STOP_OUT=<out_dir> bash drive_sim.sh <scenario> <out_dir>
  SIM_STOP_MARKS: comma-separated indices of the waypoint set (route[1:] of the scenario) that become kind stop
  SIM_STOP_HOLD_S: how long the watcher waits after the hold before it presses 再開 (empty: it never presses)"""
import os
import runpy
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parents[0]))
sys.path.insert(0, str(here))
from gouda_core import waypoints as wp  # noqa: E402

marks = {int(x) for x in os.environ.get('SIM_STOP_MARKS', '').split(',') if x.strip()}
_publish = wp.RouteDatabase.publish


def publish(self, set_id, revision, tmp, ws, *args, **kwargs):
    for i in marks:   # before the hash: the manifest's content hash includes the kind
        ws.waypoints[i].kind, ws.waypoints[i].skip_allowed = 'stop', False
    assert not ws.validate(), ws.validate()
    return _publish(self, set_id, revision, tmp, ws, *args, **kwargs)


wp.RouteDatabase.publish = publish
runpy.run_path(str(here / 'drive_sim_fixture.py'), run_name='__main__')   # prints the StartAutonomy request (stdout of drive_sim.sh's REQ)
sys.stdout.flush()
out = Path(os.environ.get('SIM_STOP_OUT') or sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
log = open(out / 'stop_watch.out', 'w')
subprocess.Popen([sys.executable, str(here / 'drive_sim_stop_watch.py'), sys.argv[1], sys.argv[2], str(out), os.environ.get('SIM_STOP_HOLD_S', '')],
                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)   # not on the REQ pipe

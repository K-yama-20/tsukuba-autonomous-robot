"""TEST COPY ONLY: put the ND-11 speed-feedback layer (REV-241 draft) between cmd_vel and the plant of drive_sim_node.py.
--ffpi KPV,KIV,ILV,KPW,KIW,ILW,TIMEOUT  enables it; --odom-delay D  delays the odometry given to the layer (10 Hz samples).
Without --ffpi the node is unchanged (cmd_vel goes straight to the plant: today's ND-11 with the compensation unset)."""
import sys
node = sys.argv[1]
n = open(node).read()
n = n.replace("import drive_sim_core as ds\n", """import drive_sim_core as ds
from collections import deque
from gouda_core.motion_core import MotionCore, MotionSettings, Feedback, Feedforward, FeedforwardAxis
# DEC-445 feedforward (FILE-MIN-SPEED-20261107) and PRM-08/39/40/42/78 as in the generated file; test copy only
FF_MAXV, FF_MAXW, FF_MAXR = 1.25, 0.97, 0.472
FF_TABLE = Feedforward(FeedforwardAxis(0.185, 0.21, 0.09, FF_MAXV), FeedforwardAxis(0.215, 0.24, 0.075, FF_MAXR),
                       FeedforwardAxis(0.184, 0.195, 0.075, FF_MAXW, 0.28, 0.19))
""", 1)
n = n.replace("        self.scorer = ds.Scorer(self.sc)\n", """        self.scorer = ds.Scorer(self.sc)
        self.ffpi = None
        if a.ffpi:
            self.ffpi = MotionCore(MotionSettings(0.7, FF_MAXV, FF_MAXW, 0.5, FF_MAXR), FF_TABLE)
            assert not self.ffpi.set_feedback(Feedback(True, *a.ffpi))
        self.odom_delay = a.odom_delay; self.odq = deque(); self.next_odom = 0.0; self.next_ctrl = 0.0
        self.stick = (0.0, 0.0); self.ffo = None; self.cmd_t = None
        self.fftrace = open(os.path.join(os.path.dirname(a.report) or '.', 'ffpi.csv'), 'w', encoding='utf-8') if a.ffpi else None
        if self.fftrace: self.fftrace.write('t,cmd_v,cmd_w,v,w,meas_v,meas_w,mode,f_ff,f_p,f_i,f_out,t_ff,t_p,t_i,t_out\\n')
""", 1)
n = n.replace("""        self.cmd_v, self.cmd_w = m.twist.linear.x, m.twist.angular.z
        self.commands += 1""", """        self.cmd_v, self.cmd_w = m.twist.linear.x, m.twist.angular.z
        self.commands += 1
        if self.ffpi: self.ffpi.on_cmd_vel(self.cmd_v, self.cmd_w, self._now())""", 1)
n = n.replace("        p.step(t, dt, self.cmd_v, self.cmd_w)\n", """        if self.ffpi:
            c = self.ffpi
            self.odq.append((t, p.v, p.w))
            while self.odq and self.odq[0][0] < t - self.odom_delay - 1: self.odq.popleft()
            if t >= self.next_odom:
                old = [x for x in self.odq if x[0] <= t - self.odom_delay]
                if old: c.on_odometry(old[-1][1], old[-1][2], t)
                self.next_odom = t + 0.1
            if t >= self.next_ctrl:
                c.on_motion_hold(False, 'sim', 3, t)
                o = c.output(t); self.stick = (o.forward, o.turn); self.ffo = o
                self.next_ctrl = t + 0.05
                ft, tt = o.forward_terms, o.turn_terms
                g = lambda x, k: '' if x is None else f'{getattr(x, k):.4f}'
                self.fftrace.write(f'{t:.2f},{self.cmd_v:.3f},{self.cmd_w:.3f},{p.v:.3f},{p.w:.3f},{g(ft, "measured")},{g(tt, "measured")},{o.feedback_mode},'
                                   f'{g(ft, "ff")},{g(ft, "p")},{g(ft, "i")},{o.forward:.4f},{g(tt, "ff")},{g(tt, "p")},{g(tt, "i")},{o.turn:.4f}\\n')
            f, s = self.stick
            p.step(t, dt, f * (FF_MAXV if f >= 0 else FF_MAXR), s * FF_MAXW)
        else:
            p.step(t, dt, self.cmd_v, self.cmd_w)
""", 1)
n = n.replace("        self.trace.flush()\n", "        self.trace.flush()\n        if self.fftrace: self.fftrace.flush()\n", 1)
n = n.replace("'m1107': self.plant.m1107,", "'m1107': self.plant.m1107, 'ffpi': self._ffpi_args, 'odom_delay': self.odom_delay,", 1)
n = n.replace("        self.scorer = ds.Scorer(self.sc)\n", "        self.scorer = ds.Scorer(self.sc)\n        self._ffpi_args = a.ffpi\n", 1)
n = n.replace("    ap.add_argument('--m1107', action='store_true')\n", """    ap.add_argument('--m1107', action='store_true')
    ap.add_argument('--ffpi', type=lambda s: [float(x) for x in s.split(',')], default=None)
    ap.add_argument('--odom-delay', type=float, default=0.0)
""", 1)
assert n.count('self.ffpi') >= 4 and "'--ffpi'" in n and 'ffpi.csv' in n, 'patch failed'
open(node, 'w').write(n)
print('patched')

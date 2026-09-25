import math


class Follower:
    def __init__(self, lookahead=.45, tolerance=.16, enter=.21, leave=.07, stop_time=1.5, yaw_tolerance=.15):
        if not all(math.isfinite(v) and v>0 for v in (lookahead,tolerance,enter,leave,stop_time,yaw_tolerance)) or leave>=enter:
            raise ValueError('invalid follower parameters')
        self.lookahead, self.tolerance = lookahead, tolerance
        self.enter, self.leave, self.stop_time = enter, leave, stop_time
        # Five-state steering has a minimum turn impulse plus braking travel.
        # Keep terminal tolerance separate from path-following hysteresis.
        self.yaw_tolerance=yaw_tolerance
        self.path = []
        self.mode = 0
        self.state = 'IDLE'
        self.index = 0
        self.stopped_since = None
        self.final_yaw = None

    def set_path(self, path, final_yaw=None):
        if not path or not all(math.isfinite(x) and math.isfinite(y) for x,y in path):
            self.cancel('INVALID_PATH');return
        self.path, self.index = list(path), 0
        if final_yaw is not None and not math.isfinite(final_yaw):
            self.cancel('INVALID_PATH');return
        self.final_yaw=final_yaw
        self.mode, self.state, self.stopped_since = 0, 'TRACKING', None

    def cancel(self, state='CANCELLED'):
        self.path=[];self.mode=0;self.state=state;self.stopped_since=None;self.final_yaw=None

    def update(self, x, y, yaw, vx, wz, now, healthy=True):
        if not healthy or not all(map(math.isfinite,(x,y,yaw,vx,wz,now))):
            self.cancel('FAULT');return 0
        if not self.path:return 0
        speed=abs(vx)
        if speed < .01 and abs(wz)<.01:
            if self.stopped_since is None:self.stopped_since=now
        else:self.stopped_since=None
        remaining=math.hypot(self.path[-1][0]-x,self.path[-1][1]-y)
        if remaining<=self.tolerance and speed<.01 and self.final_yaw is not None:
            error=math.atan2(math.sin(self.final_yaw-yaw),math.cos(self.final_yaw-yaw))
            if abs(error)<=self.yaw_tolerance and abs(wz)<.01:
                self.cancel('REACHED');return 0
            self.state='ALIGNING'
            desired=3 if error>0 else 4
            if abs(error)<abs(wz)*self.stop_time*.5+self.leave:desired=0
            if desired!=self.mode and abs(wz)>=.01:self.mode=0;return 0
            if self.mode==0 and desired and (self.stopped_since is None or now-self.stopped_since<.2):return 0
            self.mode=desired;return desired
        if remaining <= self.tolerance + .5*speed*self.stop_time:
            self.mode=0
            if speed<.01 and abs(wz)<.01:
                self.cancel('REACHED' if remaining<=self.tolerance else 'STOPPING')
            return 0
        nearest=min(range(self.index,len(self.path)),key=lambda i:(self.path[i][0]-x)**2+(self.path[i][1]-y)**2)
        self.index=nearest
        target=self.path[-1]
        for p in self.path[nearest:]:
            if math.hypot(p[0]-x,p[1]-y)>=self.lookahead:target=p;break
        error=math.atan2(math.sin(math.atan2(target[1]-y,target[0]-x)-yaw),math.cos(math.atan2(target[1]-y,target[0]-x)-yaw))
        desired=3 if error>self.enter else 4 if error < -self.enter else 1
        if self.mode in (3,4) and abs(error)>self.leave and (error>0)==(self.mode==3):desired=self.mode
        # Brake a turn before crossing the target heading, using observed twist.
        if self.mode in (3,4) and abs(error)<abs(wz)*self.stop_time*.5+self.leave:desired=0
        if desired!=self.mode and (speed>=.01 or abs(wz)>=.01):
            self.mode=0;return 0
        if self.mode==0 and desired and (self.stopped_since is None or now-self.stopped_since<.2):return 0
        self.mode=desired;return desired

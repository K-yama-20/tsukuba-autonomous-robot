import json,csv,sys,statistics as st,bisect
def load(R):
    r=json.load(open(R+'/result.json')); ev=[json.loads(l) for l in open(R+'/events.jsonl')]
    I=list(csv.DictReader(open(R+'/imu.csv'))); It=[float(x['t']) for x in I]; A=[float(x['signal_accel']) for x in I]; Y=[float(x['signal_yaw']) for x in I]
    S=list(csv.DictReader(open(R+'/status.csv'))); C=list(csv.DictReader(open(R+'/command.csv')))
    return r,ev,It,A,Y,S,C
def win(It,V,a,b):
    i,j=bisect.bisect_left(It,a),bisect.bisect_right(It,b); return V[i:j]
for R in sys.argv[1:]:
    r,ev,It,A,Y,S,C=load(R); print('==',R,'clock',{k:round(v,6) if isinstance(v,float) else v for k,v in (r.get('clock') or {}).items()})
    dt=0.01
    print(' dac neutral',S[0]['dac_x'],S[0]['dac_y'],'set',sorted({(s['dac_x'],s['dac_y']) for s in S[:3]})[:2],'first status',S[0]['source'],S[0]['reason'],'seq',S[0]['last_pc_seq'])
    prev=None
    for s in S:
        k=(s['source'],s['reason'])
        if k!=prev: print('  status',round(float(s['t_rx'])-float(S[0]['t_rx']),2),k,'seq',s['last_pc_seq'],'pc_age',s['pc_age_ms']); prev=k
    by={}
    for e in ev:
        if 'trial' in e: by.setdefault(e['trial'],[]).append(e)
    for row in r['rows']:
        if not row.get('ran'): continue
        E=by[row['trial']]; st0=next(e['t'] for e in E if e['event']=='segment_start'); end=next(e['t'] for e in E if e['event']=='trial_end')
        pre=win(It,A,st0-1.0,st0); pre_y=win(It,Y,st0-1.0,st0)
        yaw=win(It,Y,st0,end+1.5); acc=win(It,A,st0,end+1.5); ma=st.fmean(pre) if pre else 0; my=st.fmean(pre_y) if pre_y else 0
        rot=sum(y-my for y in yaw)*dt*57.3; v=0;vmax=0;dist=0
        for a in acc:
            v+=(a-ma)*dt; vmax=max(vmax,abs(v)); dist+=v*dt
        segs=[(s['label'],round(s.get('first_s',-1),2) if 'first_s' in s else None,round(s.get('motion_s',-1),2) if 'motion_s' in s else None) for s in row['segments'] if 'first_s' in s or 'motion_s' in s or s['label'] in('step',)]
        print(' ',row['trial'].ljust(16),'dur',round(end-st0,2),'dac_s',round(row['dac_s'],3) if row.get('dac_s') is not None else None,'seg',segs[:3],'rot°',round(rot,1),'maxyaw',round(max((abs(y-my) for y in yaw),default=0),2),'maxacc',round(max((abs(a-ma) for a in acc),default=0),2),'est v',round(vmax,2),'dist',round(dist,2),'preσ',round(st.pstdev(pre),3) if len(pre)>1 else None,round(st.pstdev(pre_y),4) if len(pre_y)>1 else None)

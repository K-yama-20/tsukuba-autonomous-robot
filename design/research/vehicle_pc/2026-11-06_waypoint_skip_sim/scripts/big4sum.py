import glob,json,os,collections,statistics as st
os.chdir(os.path.expanduser('~/big4')); R=collections.defaultdict(list); bad=[]
for d in glob.glob("*_*_[1234]"):
    m,s,_=d.rsplit('_',2)
    f=d+"/result.json"
    if not os.path.exists(f): continue
    r=json.load(open(f))
    sk=sum(1 for _ in open(d+"/skip.log")) if os.path.exists(d+"/skip.log") else 0
    if not r.get('duration_s'): bad.append(d)
    R[(m,s)].append((r,sk))
M=[m+"-"+l for m in ["base","k10h0","k10h3"] for l in ["D30","D60","G20","G100","D30G20"]]; S=sorted({k[1] for k in R})
print('total',sum(map(len,R.values())),'bad',bad[:10],len(bad))
def cell(v): return "%d/%d c%d s%.1f p%.2f"%(sum(r['end']=='pause:goal_reached' for r,_ in v),len(v),sum(bool(r.get('contacts')) for r,_ in v),st.mean(k for _,k in v),st.mean(r.get('progress') or 0 for r,_ in v))
for s in S:
    print(s,' | '.join(m+':'+(cell(R[(m,s)]) if R[(m,s)] else '-') for m in M))
for m in M:
    v=[x for s in S for x in R[(m,s)]]
    if v: print(m,'n',len(v),'goal',sum(r['end']=='pause:goal_reached' for r,_ in v),'prog>=.95',sum((r.get('progress') or 0)>=.95 for r,_ in v),'contact',sum(bool(r.get('contacts')) for r,_ in v),'v %.2f'%st.mean(r.get('avg_speed_mps') or 0 for r,_ in v))

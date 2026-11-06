import pickle,math,collections
o,G=pickle.load(open('/tmp/bag_02.pkl','rb'))
T0=o['/cmd_vel'][0][0]; pos=o['P']['/localization/odometry']; E=o['E']; imu=o['/sensors/imu/data']
def at(a,t): return min(a,key=lambda x:abs(x[0]-t))
FP=[(x,y) for x in (0.55,-0.24) for y in (0.3,-0.3)]
def ana(rel):
    t=T0+rel; g=at(G,t); p=at(pos,t); _,W,H,r,ox,oy,d=g
    x0,y0,th=p[1],p[2],p[3]; ct,sn=math.cos(th),math.sin(th)
    val=lambda x,y:(lambda c,w:d[w*W+c] if 0<=c<W and 0<=w<H else None)(int((x-ox)/r),int((y-oy)/r))
    # footprint cells
    mx=0; n=collections.Counter()
    for i in range(-24,56):
        for j in range(-30,31):
            v=val(x0+ct*i/100-sn*j/100,y0+sn*i/100+ct*j/100)
            if v is None: continue
            n[v if v in(0,255) else ('100' if v>=100 else ('99' if v>=99 else ('>=50' if v>=50 else '<50')))]+=1
    def ray(dx,dy,th0):  # distance from center to first cell >=99 along body direction
        for s in range(0,300):
            a=th0+math.atan2(dy,dx); v=val(x0+math.cos(a)*s/100,y0+math.sin(a)*s/100)
            if v is not None and v!=255 and v>=99: return s/100
        return None
    rays={k:ray(*v,th) for k,v in {'前':(1,0),'左':(0,1),'右':(0,-1),'後':(-1,0)}.items()}
    # lethal distance anywhere
    near=min(((math.hypot(ox+(c+.5)*r-x0,oy+(w+.5)*r-y0)) for w in range(H) for c in range(W) if d[w*W+c]!=255 and d[w*W+c]==100),default=None)
    near99=min(((math.hypot(ox+(c+.5)*r-x0,oy+(w+.5)*r-y0)) for w in range(H) for c in range(W) if d[w*W+c]!=255 and d[w*W+c]>=99),default=None)
    print('t',rel,'pose',round(x0,2),round(y0,2),round(math.degrees(th)),'fp',dict(n),'rays>=99',rays,'near100',round(near,2) if near else None,'near99',round(near99,2) if near99 else None)
for rel in (3,20,39,45,60,80,100,125,160): ana(rel)
# backup speed and spin details
for a,b,name in ((64,72,'backup1'),(139,147,'backup2')):
    P=[x for x in pos if T0+a<=x[0]<T0+b]
    s=[(round(x[0]-T0,1),round(math.hypot(x[1]-P[0][1],x[2]-P[0][2]),3)) for x in P[::10]]
    print(name,s)
    e=[x for x in E if T0+a<=x[0]<T0+b and abs(x[3])>1000]; print(' stick',e[0][3] if e else None,'from',round(e[0][0]-T0,2) if e else None,'to',round(e[-1][0]-T0,2) if e else None)
for a,b,name in ((38,44,'spin1'),(112,118,'spin2')):
    e=[x for x in E if T0+a<=x[0]<T0+b and abs(x[2])>1000]; i=[x for x in imu if T0+a<=x[0]<T0+b and abs(x[3])>0.05]
    print(name,'stick from',round(e[0][0]-T0,2),'to',round(e[-1][0]-T0,2),'first values',[x[2] for x in e[:6]],'gz from',round(i[0][0]-T0,2),'to',round(i[-1][0]-T0,2),'max',round(max(abs(x[3]) for x in i),3))
# plan
pl=o['/plan']; print('plan first',pl[0][2],[(round(x,2),round(y,2)) for x,y in pl[0][1]][:10]); 
L=o["tf('map', 'odom')"]; print('map->odom',[round(v,3) for v in L[0][1:]],[round(v,3) for v in L[-1][1:]])
# v stats phases
for a,b,name in ((0,40,'発進前'),(75,110,'旋回後1'),(120,139,'旋回後2')):
    c=[x for x in o['/cmd_vel'] if T0+a<=x[0]<T0+b]; print(name,'v mean',round(sum(x[1] for x in c)/len(c),3),'w mean',round(sum(x[2] for x in c)/len(c),3))

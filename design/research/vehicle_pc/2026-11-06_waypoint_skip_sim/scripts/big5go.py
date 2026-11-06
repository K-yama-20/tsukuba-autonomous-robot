import random,subprocess,os
M=[m+d+"-"+l for m in ["base","k10h0"] for d in ["dn2","dn4"] for l in ["G0","G20","G100"]]; S=["W01","W02","W03","W05","W06","N10","N11","N12"]
J=[f"{m}:{s}:{r}" for r in range(1,5) for s in S for m in M]; random.seed(5); random.shuffle(J)
for i in range(5):
    subprocess.Popen(["nohup",os.path.expanduser("~/big5.sh"),os.path.expanduser("~/big5"),str(81+i),str(40*i)]+J[i::5],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(len(J))

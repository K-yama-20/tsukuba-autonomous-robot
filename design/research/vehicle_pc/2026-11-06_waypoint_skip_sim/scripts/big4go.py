import random,subprocess,os
M=[m+"-"+l for m in ["base","k10h0","k10h3"] for l in ["D30","D60","G20","G100","D30G20"]]; S=["W01","W02","W03","W05","W06","N10","N11","N12"]
J=[f"{m}:{s}:{r}" for r in range(1,5) for s in S for m in M]; random.seed(4); random.shuffle(J)
for i in range(5):
    subprocess.Popen(["nohup",os.path.expanduser("~/big4.sh"),os.path.expanduser("~/big4"),str(81+i),str(40*i)]+J[i::5],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(len(J))

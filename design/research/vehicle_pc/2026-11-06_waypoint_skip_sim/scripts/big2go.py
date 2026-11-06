import random,subprocess,os
M=["k10h0","k10h3","k10h10","k07h3","k10n3h3"]; S=["W%02d"%i for i in range(1,10)]+["N10","N11","N12"]
J=[f"{m}:{s}:{r}" for r in range(1,5) for s in S for m in M]; random.seed(2); random.shuffle(J)
for i in range(5):
    subprocess.Popen(["nohup",os.path.expanduser("~/big2.sh"),os.path.expanduser("~/big2"),str(81+i),str(40*i)]+J[i::5],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(len(J))

import numpy as np
from itertools import combinations
from scipy.optimize import least_squares
L=np.array([
 [0.90,0.70,0.30,0.20],[0.50,0.60,0.70,0.80],[0.85,0.00,0.00,0.10],
 [0.75,0.00,0.00,0.05],[0.80,0.00,0.00,0.00],[0.70,0.05,0.05,0.30],
 [0.20,0.10,0.05,0.85],[0.00,0.90,0.10,0.00],[0.10,0.20,0.85,0.05]])
SIG=np.array([0.6,0.4,0.5,0.5,0.9,1.1,0.7,0.3,0.8])
print("識別條件 K(K-1)/2 >= K*M - M(M-1)/2 :")
for M in (1,2,3,4):
    print(f"   M={M} -> K >=", next(K for K in range(2,16) if K*(K-1)/2>=K*M-M*(M-1)/2))
def gen(N,share,K,M,seed,tau=(40.,300.,200.,20.)):
    r=np.random.default_rng(seed); X=np.zeros((N,M))
    for m in range(M):
        rho=np.exp(-30./tau[m]); x=np.zeros(N)
        for t in range(1,N): x[t]=rho*x[t-1]+r.normal(0,np.sqrt(1-rho**2))
        X[:,m]=x*np.sqrt(share[m])
    return X@L[:K,:M].T + r.normal(0,1,(N,K))*SIG[:K]
def fit(Y,M,ns=3,seed=0):
    C=np.cov(Y.T); K=C.shape[0]; idx=list(combinations(range(K),2))
    tgt=np.array([C[a,b] for a,b in idx]); r=np.random.default_rng(seed); best=None
    f=lambda p:np.array([p.reshape(K,M)[a]@p.reshape(K,M)[b] for a,b in idx])-tgt
    for s in range(ns):
        sol=least_squares(f,r.normal(0,0.5,K*M),max_nfev=600)
        if best is None or sol.cost<best.cost: best=sol
    Lh=best.x.reshape(K,M); sh=(Lh**2).sum(0)
    return sh/sh.sum()
# 關鍵測試:臨床要的不是精確百分比,是「哪個驅動最大」
print("\n=== 主導驅動判對率(M=3:免疫/代謝/血流動力;K=9通道) ===")
print(f"{'成套次數N':>9} {'主導判對率':>10} {'主導在前二名':>12}")
for N in (12,20,34,60,120):
    ok1=ok2=tot=0
    for s in range(60):
        sh=np.random.default_rng(300+s).dirichlet(np.ones(3)*1.2)
        est=fit(gen(N,sh,9,3,s),3,seed=s)
        if np.argmax(est)==np.argmax(sh): ok1+=1
        if np.argmax(sh) in np.argsort(est)[-2:]: ok2+=1
        tot+=1
    print(f"{N:>9} {ok1/tot*100:>9.0f}% {ok2/tot*100:>11.0f}%")
print("(隨機猜測基準:主導 33%,前二名 67%)")

import numpy as np
from itertools import combinations
from scipy.optimize import nnls
L=np.array([
 [0.90,0.70,0.30],[0.50,0.60,0.70],[0.85,0.00,0.00],[0.75,0.00,0.00],
 [0.80,0.00,0.00],[0.70,0.05,0.05],[0.20,0.10,0.05],[0.00,0.90,0.10],
 [0.10,0.20,0.85]])
SIG=np.array([0.6,0.4,0.5,0.5,0.9,1.1,0.7,0.3,0.8])
NAMES=["免疫","代謝","血流動力"]
def gen(N,share,K,seed,tau=(40.,300.,200.)):
    r=np.random.default_rng(seed); X=np.zeros((N,3))
    for m in range(3):
        rho=np.exp(-30./tau[m]); x=np.zeros(N)
        for t in range(1,N): x[t]=rho*x[t-1]+r.normal(0,np.sqrt(1-rho**2))
        X[:,m]=x*np.sqrt(share[m])
    return X@L[:K].T + r.normal(0,1,(N,K))*SIG[:K]
def solve_shares(Y,K,Lfix):
    """L 由文獻固定 -> 只解各驅動之變異 v,問題變線性且僅用非對角元素"""
    C=np.cov(Y.T); idx=list(combinations(range(K),2))
    A=np.array([[Lfix[a,m]*Lfix[b,m] for m in range(Lfix.shape[1])] for a,b in idx])
    y=np.array([C[a,b] for a,b in idx])
    v,_=nnls(A,y)                      # 非負最小平方:變異不可為負
    s=v*(Lfix**2).sum(0); tot=s.sum()
    return s/tot if tot>0 else np.full(len(v),np.nan)
print("=== 驗證式分解(負載由文獻固定,只解驅動變異) ===")
print(f"{'N':>5} {'主導判對率':>10} {'占比平均絕對誤差':>16} {'不可解比例':>10}")
for N in (8,12,20,34,60,120):
    ok=tot=0; errs=[]; bad=0
    for s in range(200):
        sh=np.random.default_rng(700+s).dirichlet(np.ones(3)*1.2)
        est=solve_shares(gen(N,sh,9,s),9,L)
        if not np.all(np.isfinite(est)): bad+=1; continue
        ok+= int(np.argmax(est)==np.argmax(sh)); errs.append(np.abs(est-sh).mean()); tot+=1
    print(f"{N:>5} {ok/tot*100:>9.0f}% {np.mean(errs):>16.3f} {bad/200*100:>9.0f}%")
print("(隨機猜測基準 33%)")
print("\n=== 通道數的影響(N=20) ===")
for K in (4,5,6,9):
    ok=tot=0
    for s in range(200):
        sh=np.random.default_rng(900+s).dirichlet(np.ones(3)*1.2)
        est=solve_shares(gen(20,sh,K,s),K,L[:K])
        if np.all(np.isfinite(est)):
            ok+=int(np.argmax(est)==np.argmax(sh)); tot+=1
    print(f"  K={K}: 主導判對 {ok/tot*100:.0f}%")
print("\n=== 對照:若用含誤差的對角線(整個共變異數矩陣) ===")
def solve_diag(Y,K,Lfix):
    C=np.cov(Y.T); idx=[(a,b) for a in range(K) for b in range(a,K)]  # 含對角
    A=np.array([[Lfix[a,m]*Lfix[b,m] for m in range(Lfix.shape[1])] for a,b in idx])
    y=np.array([C[a,b] for a,b in idx]); v,_=nnls(A,y)
    s=v*(Lfix**2).sum(0); t=s.sum(); return s/t if t>0 else np.full(len(v),np.nan)
for N in (20,60):
    o1=o2=t1=t2=0
    for s in range(200):
        sh=np.random.default_rng(1100+s).dirichlet(np.ones(3)*1.2); Y=gen(N,sh,9,s)
        e1=solve_shares(Y,9,L); e2=solve_diag(Y,9,L)
        if np.all(np.isfinite(e1)): o1+=int(np.argmax(e1)==np.argmax(sh)); t1+=1
        if np.all(np.isfinite(e2)): o2+=int(np.argmax(e2)==np.argmax(sh)); t2+=1
    print(f"  N={N}: 只用非對角 {o1/t1*100:.0f}%   含對角(受化驗誤差污染) {o2/t2*100:.0f}%")

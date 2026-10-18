"""從原始模擬資料重跑數位雙生（3,200 位虛擬病患）並以中文重畫說明書的四張圖。

原始程式在桌面的研究資料夾（09_數位雙生模擬研究/08_復發預測模擬/code/），這裡原封不動執行，
只把路徑改到本機、輸出改到 outputs/twin_rerun/，再用它算出的結果畫圖；重算數字須與原輸出完全一致。

跑法： PYTHONUTF8=1 python experiments/chronic_recurrence_longitudinal/twin_redraw.py [09_數位雙生模擬研究 路徑]
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as base  # noqa: E402

TWIN = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    r"~\Desktop\01_研究專案\MD_Piece_腎臟研究\AIMD\md_piece\proposal\md.piece\09_數位雙生模擬研究")
CODE = os.path.join(TWIN, "08_復發預測模擬", "code")
ORIG = os.path.join(TWIN, "08_復發預測模擬", "outputs")
OUT = os.path.join(base.OUT, "twin_rerun")
os.makedirs(OUT, exist_ok=True)


def run_original(name):
    src = open(os.path.join(CODE, name), encoding="utf-8").read()
    src = src.replace('"/sessions/inspiring-affectionate-galileo/mnt/md.piece/09_數位雙生模擬研究"', repr(TWIN))
    src = src.replace('f"{BASE}/08_復發預測模擬/outputs", f"{BASE}/08_復發預測模擬/figures"', f"{OUT!r}, {OUT!r}")
    src = src.replace("n_jobs=-1", "n_jobs=1")   # 本機 joblib 與 Python 3.14 不相容；固定 random_state，結果不受影響
    assert repr(TWIN) in src and repr(OUT) in src, name
    ns = {"__name__": "twin"}
    exec(compile(src, name, "exec"), ns)
    return ns


ARMS = ["GROUND_TRUTH", "MDPIECE", "PATIENT_RECALL"]
ZH = {"GROUND_TRUTH": "真相（上限）", "MDPIECE": "MD. Piece 紀錄", "PATIENT_RECALL": "病人回憶"}
COL = {"GROUND_TRUTH": "#3a7d44", "MDPIECE": "#2f6fae", "PATIENT_RECALL": "#b5524a"}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    P = run_original("predict.py")
    C = run_original("previsit_cause.py")

    # 重算須與原輸出一致（說明書表格數字的來源）
    for f in ("prediction_eval.csv", "cause_recovery.csv"):
        a, b = pd.read_csv(os.path.join(OUT, f)), pd.read_csv(os.path.join(ORIG, f))
        num = a.select_dtypes("number").columns
        assert np.allclose(a[num].values, b[num].values, equal_nan=True), f"{f} 重算與原輸出不一致"
    print("重算與原輸出一致")

    base.use_doc_fonts(plt)
    R = P["R"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0), sharey=True)
    for ax, fs, ttl in zip(axes, ["full", "record_only"], ["含完整基線病歷", "只用就診間紀錄"]):
        g = R[R.featureset == fs].set_index("arm")
        mets = ["cox_c_index", "rf_auroc", "lr_auroc"]
        xp = np.arange(len(mets))
        for k, a in enumerate(ARMS):
            ax.bar(xp + (k - 1) * 0.26, [g.loc[a, m] for m in mets], 0.26, label=ZH[a], color=COL[a])
        ax.axhline(0.5, ls="--", c="grey", lw=1)
        ax.set_xticks(xp); ax.set_xticklabels(["Cox C-index", "隨機存活森林 AUROC", "Logistic AUROC"], fontsize=9)
        ax.set_title(ttl)
    axes[0].set_ylabel("鑑別力"); axes[0].set_ylim(0.45, 0.82); axes[1].legend(fontsize=8)
    fig.suptitle("數位雙生 3,200 位虛擬病患：三種紀錄來源的復發預測鑑別力")
    fig.tight_layout(); fig.savefig(os.path.join(base.OUT, "figJ_twin_discrimination.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.4, 4.8))
    ax.plot([0, 1], [0, 1], "--", c="grey", lw=1, label="理想校準")
    for a in ARMS:
        rb = P["calib"][a]
        ax.plot(rb["pm"], rb["ym"], "o-", color=COL[a], label=ZH[a])
    ax.set_xlabel("預測風險"); ax.set_ylabel("實際惡化比例"); ax.set_title("含完整基線病歷模型的校準曲線")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(os.path.join(base.OUT, "figK_twin_calibration.png"), dpi=200); plt.close(fig)

    cs = P["coefs"]["MDPIECE"]
    top = pd.concat([cs.head(8), cs.tail(8)])
    pd.DataFrame({"feature": top.index, "coef": top.values}).to_csv(os.path.join(OUT, "top_features_mdpiece.csv"), index=False)
    fig, ax = plt.subplots(figsize=(6.6, 5))
    ax.barh(range(len(top)), top.values, color=["#b5524a" if v < 0 else "#3a7d44" for v in top.values])
    ax.set_yticks(range(len(top))); ax.set_yticklabels([FEAT.get(n, n) for n in top.index], fontsize=8)
    ax.axvline(0, c="k", lw=0.8); ax.set_xlabel("標準化係數（正值推升風險，負值降低風險）")
    ax.set_title("只用就診間紀錄時影響預測最大的特徵（MD. Piece 紀錄）")
    fig.tight_layout(); fig.savefig(os.path.join(base.OUT, "figL_twin_top_features.png"), dpi=200); plt.close(fig)

    Cd = C["C"]
    fig, ax = plt.subplots(figsize=(7.0, 4.2)); xp = np.arange(len(ARMS))
    ax.bar(xp - 0.27, Cd.short_auroc, 0.27, label="短期惡化預測 AUROC", color="#888888")
    ax.bar(xp, Cd.clue_retention, 0.27, label="感染線索保留率", color="#3a7d44")
    ax.bar(xp + 0.27, Cd.infection_attribution_sensitivity, 0.27, label="模型指認感染為主因的比例", color="#d98ca0")
    for i, v in enumerate(Cd.clue_retention):
        ax.text(i, v + 0.02, f"{v*100:.0f}%", ha="center", fontsize=9)
    ax.set_xticks(xp); ax.set_xticklabels([ZH[a] for a in ARMS]); ax.set_ylim(0, 1.1)
    ax.set_title("由感染引發的惡化：各紀錄來源保留感染線索的比例")
    ax.legend(fontsize=8, loc="upper right"); fig.tight_layout()
    fig.savefig(os.path.join(base.OUT, "figM_twin_cause.png"), dpi=200); plt.close(fig)
    print("圖已輸出")


FEAT = {  # 回看前 90 天紀錄的特徵（定義見原 predict.py arm_features）
    "sev_mean": "平均紀錄嚴重度", "sev_max": "最高紀錄嚴重度", "mean_salience": "事件平均顯著度",
    "n_last30": "最近 30 天紀錄筆數", "n_SYMPTOM": "症狀次數", "n_EMERGENCY_VISIT": "急診次數",
    "n_FLARE": "發作次數", "n_INFECTION": "感染次數", "n_TREATMENT": "治療次數", "n_HOSPITALIZATION": "住院次數",
    "n_PROCEDURE": "處置次數", "n_APPOINTMENT": "門診次數", "n_IMAGING": "影像檢查次數", "n_LAB": "抽血檢驗次數",
    "n_MEDICATION_CHANGE": "換藥次數", "n_REFILL": "領藥次數"}

if __name__ == "__main__":
    main()

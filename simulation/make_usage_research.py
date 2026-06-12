"""使用率 / 使用心聲 / 使用結果 整合分析（Usage · Sentiment · Outcome）.

Derives patient-reported outcomes (satisfaction / trust / NPS / continuation) from a completed
run, then renders the usage + sentiment + integrated-outcome figures. The sentiment model is
EXPERT JUDGMENT anchored to the structure of two PubMed sources:

  * MAUQ (Mustafa 2021, JMIR Mhealth Uhealth, PMID 33538704): mHealth-app usability =
    {ease-of-use, interface/satisfaction, usefulness}.
  * Kruse 2015 (J Med Internet Res, PMID 25707035): top positive theme = patient-provider
    COMMUNICATION (37%); top negatives = usability & security, worst for the tech-unfamiliar (41%).

So: satisfaction = f(usefulness=record quality, ease=tech-literacy(+caregiver), communication=
doctor understanding). Non-adopters score low. Sentiment is NOT a deterministic engine output —
it is a derived, literature-structured PRO layer, flagged validation_required. Quotes are
SIMULATED illustrative, not real patients.

    python -m simulation.make_usage_research [--hash 713d8a608280]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).parent
FIGDIR = HERE / "docs" / "figures"
TEAL, PURPLE, CORAL, GOLD, INK, MUTED = "#2A9D8F", "#7B6CD6", "#E76F51", "#E9C46A", "#22333B", "#6B7B7E"
PORDER = ["PERFECT_LOGGER", "CAREGIVER_MANAGED", "ANXIOUS", "SYMPTOM_DRIVEN",
          "NORMAL", "ELDERLY_LOW_LITERACY", "LOW_ENGAGEMENT", "TECH_AVOIDANT"]
RET = ["d1", "w1", "m1", "m3", "m6", "m12"]

# Simulated illustrative voices (grounded in Kruse 2015 themes: communication+, usability/dropout-)
VOICES = {
    "CAREGIVER_MANAGED": "幫我把媽媽每次回診、用藥變化都記下來，醫師一看就懂，省下很多重複解釋的時間。",
    "PERFECT_LOGGER": "我每天都記，回診時直接給醫師看，溝通順很多、也比較安心。",
    "ANXIOUS": "焦慮時會一直記，雖然有時記過頭，但至少跟醫師討論時有依據。",
    "SYMPTOM_DRIVEN": "不舒服或發作時才會打開來記，平常其實用得少。",
    "NORMAL": "還算方便，醫師也說資料有幫助，但一忙起來就忘了記。",
    "ELDERLY_LOW_LITERACY": "字有點小、操作不太會，常常要請家人幫忙才弄得起來。",
    "LOW_ENGAGEMENT": "一開始下載了，但後來幾乎沒在用。",
    "TECH_AVOIDANT": "太複雜了，我還是習慣紙筆，用沒幾次就放著了。",
}


def derive(patients, ev, retention):
    pid = patients["patient_id"]
    mdp = ev[ev.arm == "MDPIECE"].set_index("patient_id")
    rec = ev[ev.arm == "PATIENT_RECALL"].set_index("patient_id")
    df = patients.set_index("patient_id").copy()
    df["usefulness"] = mdp["clinical_reconstruction_score"].reindex(pid).values            # 紀錄品質
    df["communication"] = mdp["doctor_understanding"].reindex(pid).values                  # 溝通效益
    df["logging_intensity"] = mdp["event_recall_rate"].reindex(pid).values                 # 記錄強度
    df["d_crs"] = (mdp["clinical_reconstruction_score"].reindex(pid).values
                   - rec["clinical_reconstruction_score"].reindex(pid).values)
    # retention rows align with patients by generation order
    ret = retention.reset_index(drop=True)
    df = df.reset_index()
    df["adopted"] = ret["onboarded"].values
    for c in RET:
        df[c + "_active"] = (ret[c] & ret["onboarded"]).values
    df["ease"] = np.clip(df["tech_literacy"] + 0.2 * df["caregiver_support"], 0, 1)

    rng = np.random.default_rng(20260606)
    noise = rng.normal(0, 0.06, len(df))
    # Satisfaction is a UX construct (MAUQ-style), NOT the raw fidelity score. Adopters start at a
    # moderate baseline and move with how much the app HELPED them (d_crs), ease-of-use, and the
    # communication benefit. Non-adopters (never got value) score low. This yields a face-valid
    # crossover rather than equating satisfaction with the 0-1 fidelity metric.
    raw = 0.55 + 0.55 * df["d_crs"] + 0.15 * (df["ease"] - 0.5) + 0.12 * (df["communication"] - 0.3) + noise
    raw = np.where(df["adopted"], raw, 0.18 + 0.07 * rng.random(len(df)))  # non-adopters: low
    df["satisfaction"] = np.clip(raw, 0, 1) * 100                                            # MAUQ-style 0-100
    df["trust"] = np.clip(0.5 + 0.30 * (df["usefulness"] - 0.5) + 0.30 * (df["communication"] - 0.5)
                          + rng.normal(0, 0.05, len(df)), 0, 1)
    df["nps"] = np.where(df["satisfaction"] >= 80, "推薦者", np.where(df["satisfaction"] >= 60, "中立", "貶損者"))
    df["continue"] = np.clip((df["satisfaction"] / 100) * 1.05, 0, 1)                        # 續用意願
    return df


def fig_usage(df, out):
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.5))
    fig.suptitle("使用率（Usage / 採用 · 留存 · 記錄強度）", fontsize=15, fontweight="bold")
    g = df.groupby("persona")
    ad = g["adopted"].mean().reindex(PORDER)
    ax[0].barh(range(len(ad)), ad.values, color=TEAL); ax[0].set_yticks(range(len(ad))); ax[0].set_yticklabels(ad.index, fontsize=8)
    ax[0].invert_yaxis(); ax[0].set_xlim(0, 1); ax[0].set_title("採用率（過 Day-1 啟用）")
    for i, v in enumerate(ad.values): ax[0].text(v + 0.01, i, f"{v:.0%}", va="center", fontsize=8)
    cmap = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, p in enumerate(PORDER):
        sub = df[df.persona == p]
        ax[1].plot(range(len(RET)), [sub[c + "_active"].mean() for c in RET], "-o", color=cmap[i], lw=1.8, label=p)
    ax[1].set_xticks(range(len(RET))); ax[1].set_xticklabels([r.upper() for r in RET]); ax[1].set_ylim(0, 1)
    ax[1].set_title("活躍留存（依人格）"); ax[1].legend(fontsize=6.5, ncol=2)
    li = g["logging_intensity"].mean().reindex(PORDER)
    ax[2].barh(range(len(li)), li.values, color=PURPLE); ax[2].set_yticks(range(len(li))); ax[2].set_yticklabels(li.index, fontsize=8)
    ax[2].invert_yaxis(); ax[2].set_xlim(0, 1); ax[2].set_title("記錄強度（捕捉真實事件比例）")
    fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_sentiment(df, out):
    fig, ax = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("使用心聲（量化）— 滿意度 · 信任 · NPS（PRO，錨定 MAUQ / Kruse）", fontsize=15, fontweight="bold")
    ax[0, 0].hist(df["satisfaction"], bins=30, color=TEAL, edgecolor="white")
    ax[0, 0].axvline(df["satisfaction"].mean(), color=CORAL, ls="--", lw=2, label=f"平均 {df['satisfaction'].mean():.0f}")
    ax[0, 0].set_title("滿意度分布（MAUQ 式 0–100）"); ax[0, 0].set_xlabel("satisfaction"); ax[0, 0].legend(fontsize=8)
    sat = df.groupby("persona")["satisfaction"].mean().reindex(PORDER)
    cols = [TEAL if v >= 60 else CORAL for v in sat.values]
    ax[0, 1].barh(range(len(sat)), sat.values, color=cols); ax[0, 1].set_yticks(range(len(sat))); ax[0, 1].set_yticklabels(sat.index, fontsize=8)
    ax[0, 1].invert_yaxis(); ax[0, 1].axvline(60, color=MUTED, ls=":"); ax[0, 1].set_xlim(0, 100); ax[0, 1].set_title("平均滿意度（依人格）")
    for i, v in enumerate(sat.values): ax[0, 1].text(v + 1, i, f"{v:.0f}", va="center", fontsize=8)
    # NPS by persona
    def nps(s): return 100 * ((s == "推薦者").mean() - (s == "貶損者").mean())
    npv = df.groupby("persona")["nps"].apply(nps).reindex(PORDER)
    cols2 = [TEAL if v >= 0 else CORAL for v in npv.values]
    ax[1, 0].barh(range(len(npv)), npv.values, color=cols2); ax[1, 0].set_yticks(range(len(npv))); ax[1, 0].set_yticklabels(npv.index, fontsize=8)
    ax[1, 0].invert_yaxis(); ax[1, 0].axvline(0, color="k", lw=0.8); ax[1, 0].set_title("淨推薦值 NPS（依人格）")
    for i, v in enumerate(npv.values): ax[1, 0].text(v + (2 if v >= 0 else -2), i, f"{v:+.0f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    # satisfaction vs benefit
    ax[1, 1].scatter(df["d_crs"], df["satisfaction"], s=7, alpha=0.4, color=TEAL)
    ax[1, 1].axvline(0, color=MUTED, ls=":"); ax[1, 1].set_xlabel("Δ 臨床重建分數（受益程度）"); ax[1, 1].set_ylabel("滿意度")
    r = np.corrcoef(df["d_crs"], df["satisfaction"])[0, 1]
    ax[1, 1].set_title(f"受益越多、越滿意（r={r:.2f}）")
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_voices(df, out):
    fig, ax = plt.subplots(figsize=(15, 8)); ax.axis("off")
    fig.suptitle("使用心聲（質性，模擬示意）— 正向主題：醫病溝通　負向主題：操作門檻／流失（Kruse 2015）",
                 fontsize=14, fontweight="bold")
    sat = df.groupby("persona")["satisfaction"].mean()
    for i, p in enumerate(PORDER):
        y = 0.92 - i * 0.112
        s = sat.get(p, 0)
        col = TEAL if s >= 60 else CORAL
        ax.add_patch(plt.Rectangle((0.02, y - 0.05), 0.96, 0.095, transform=ax.transAxes,
                                   facecolor="#F4F7F6", edgecolor="#E3E9E8"))
        ax.text(0.035, y, p, transform=ax.transAxes, fontsize=11, fontweight="bold", va="center", color=INK)
        ax.text(0.22, y, f"「{VOICES[p]}」", transform=ax.transAxes, fontsize=11.5, va="center", color=INK)
        ax.add_patch(plt.Rectangle((0.83, y - 0.018), 0.13 * s / 100, 0.036, transform=ax.transAxes, facecolor=col))
        ax.text(0.965, y, f"{s:.0f}", transform=ax.transAxes, fontsize=11, fontweight="bold", va="center", ha="right", color=col)
    ax.text(0.83, 0.985, "平均滿意度", transform=ax.transAxes, fontsize=9, color=MUTED, ha="left")
    fig.savefig(out, dpi=130); plt.close(fig);


def fig_integrated(df, out):
    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("使用結果整合：採用 → 留存 → 滿意 → 推薦（漏斗）＋ 使用面 vs 紀錄面", fontsize=15, fontweight="bold")
    n = len(df)
    funnel = [("下載/分派", 1.0),
              ("Day-1 啟用", df["adopted"].mean()),
              ("M3 仍活躍", df["m3_active"].mean()),
              ("滿意 60+", (df["satisfaction"] >= 60).mean()),
              ("推薦者 80+", (df["satisfaction"] >= 80).mean())]
    for i, (lab, frac) in enumerate(funnel):
        w = frac; x = (1 - w) / 2
        ax[0].barh(len(funnel) - i, w, left=x, color=plt.cm.viridis(0.15 + 0.16 * i), height=0.7)
        ax[0].text(0.5, len(funnel) - i, f"{lab}　{frac:.0%}", ha="center", va="center", fontsize=11, color="white", fontweight="bold")
    ax[0].set_xlim(0, 1); ax[0].axis("off"); ax[0].set_title("使用漏斗（全族群）")
    # usage (logging intensity) vs sentiment, colored by whether record improved
    helped = df["d_crs"] > 0
    ax[1].scatter(df[~helped]["logging_intensity"], df[~helped]["satisfaction"], s=7, alpha=0.35, color=CORAL, label="紀錄變差")
    ax[1].scatter(df[helped]["logging_intensity"], df[helped]["satisfaction"], s=7, alpha=0.35, color=TEAL, label="紀錄變好")
    ax[1].set_xlabel("記錄強度（使用面）"); ax[1].set_ylabel("滿意度（心聲）"); ax[1].set_title("使用越深 → 越受益 → 越滿意")
    ax[1].legend(fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(out, dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hash", default="713d8a608280")
    args = ap.parse_args()
    FIGDIR.mkdir(parents=True, exist_ok=True)
    hd = HERE / "outputs" / args.hash
    patients = pd.read_csv(hd / "patients.csv")
    ev = pd.read_csv(hd / "evaluation_metrics.csv")
    retention = pd.read_csv(hd / "retention.csv")
    df = derive(patients, ev, retention)

    fig_usage(df, FIGDIR / "usage_rate.png")
    fig_sentiment(df, FIGDIR / "usage_sentiment.png")
    fig_voices(df, FIGDIR / "usage_voices.png")
    fig_integrated(df, FIGDIR / "usage_integrated.png")
    df.to_csv(hd / "usage_sentiment.csv", index=False)

    # headline numbers for the integration write-up
    print("adoption: %.0f%%  | M3 active: %.0f%%  | satisfied>=60: %.0f%%  | promoters>=80: %.0f%%"
          % (df["adopted"].mean()*100, df["m3_active"].mean()*100,
             (df["satisfaction"]>=60).mean()*100, (df["satisfaction"]>=80).mean()*100))
    print("mean satisfaction: %.0f  | overall NPS: %+.0f  | corr(benefit, satisfaction): %.2f"
          % (df["satisfaction"].mean(),
             100*((df["nps"]=="推薦者").mean()-(df["nps"]=="貶損者").mean()),
             np.corrcoef(df["d_crs"], df["satisfaction"])[0,1]))
    print("satisfaction by persona:")
    print(df.groupby("persona")["satisfaction"].mean().reindex(PORDER).round(0).to_string())
    print("\nwrote 4 figures + usage_sentiment.csv")


if __name__ == "__main__":
    main()

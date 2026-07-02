"""Render a 'data atlas' — comprehensive figures covering every output table of a run.

    python -m simulation.make_data_figures            # uses the literature-anchored run
    python -m simulation.make_data_figures --hash <config_hash>

Writes PNGs to simulation/docs/figures/. Complements make_figures.py (which renders the
headline result figures); this one visualizes the raw population, events, and per-arm tables.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# CJK font so Traditional-Chinese titles/labels render (Windows fonts)
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).parent
FIGDIR = HERE / "docs" / "figures"
TEAL, PURPLE, CORAL, INK, MUTED = "#2A9D8F", "#7B6CD6", "#E76F51", "#22333B", "#6B7B7E"
PERSONA_ORDER = ["PERFECT_LOGGER", "CAREGIVER_MANAGED", "ANXIOUS", "SYMPTOM_DRIVEN",
                 "NORMAL", "ELDERLY_LOW_LITERACY", "LOW_ENGAGEMENT", "TECH_AVOIDANT"]
DISEASES = ["NMOSD", "MS", "SLE", "RA", "CROHN", "MG", "OTHER"]


def fig_population(pts, out):
    fig, ax = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle("虛擬病患族群（L1）— 3,200 人", fontsize=15, fontweight="bold")
    ax[0, 0].hist(pts["age"], bins=30, color=TEAL, edgecolor="white")
    ax[0, 0].set_title("年齡分布"); ax[0, 0].set_xlabel("age"); ax[0, 0].set_ylabel("patients")
    dc = pts["disease"].value_counts().reindex(DISEASES)
    ax[0, 1].bar(dc.index, dc.values, color=PURPLE); ax[0, 1].set_title("疾病組成（專科門診）"); ax[0, 1].tick_params(axis="x", rotation=30)
    sv = pts["severity"].value_counts().sort_index()
    ax[0, 2].bar(sv.index.astype(str), sv.values, color=CORAL); ax[0, 2].set_title("基線嚴重度（0–4）"); ax[0, 2].set_xlabel("severity")
    pc = pts["persona"].value_counts().reindex(PERSONA_ORDER)
    ax[1, 0].barh(range(len(pc)), pc.values, color=TEAL); ax[1, 0].set_yticks(range(len(pc))); ax[1, 0].set_yticklabels(pc.index, fontsize=8)
    ax[1, 0].invert_yaxis(); ax[1, 0].set_title("行為人格分布")
    hb = ax[1, 1].hexbin(pts["health_literacy"], pts["tech_literacy"], gridsize=24, cmap="viridis", mincnt=1)
    ax[1, 1].set_xlabel("health literacy"); ax[1, 1].set_ylabel("tech literacy")
    r = np.corrcoef(pts["health_literacy"], pts["tech_literacy"])[0, 1]
    ax[1, 1].set_title(f"識讀能力耦合（r={r:.2f}，可分離）"); fig.colorbar(hb, ax=ax[1, 1], shrink=0.8)
    cg = pd.cut(pts["caregiver_support"], [-0.1, 0.01, 0.6, 1.01], labels=["無", "部分", "全代理"]).value_counts().reindex(["無", "部分", "全代理"])
    ax[1, 2].bar(cg.index, cg.values, color=PURPLE); ax[1, 2].set_title("照顧者支援")
    fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_events(gt, pts, out):
    fig, ax = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("真實事件流（L2+L3）— 135,246 events", fontsize=15, fontweight="bold")
    et = gt["event_type"].value_counts()
    ax[0, 0].barh(range(len(et)), et.values, color=TEAL); ax[0, 0].set_yticks(range(len(et))); ax[0, 0].set_yticklabels(et.index, fontsize=8)
    ax[0, 0].invert_yaxis(); ax[0, 0].set_title("事件類型頻次")
    epp = gt.groupby("patient_id").size()
    dmap = pts.set_index("patient_id")["disease"]
    by_dis = epp.groupby(epp.index.map(dmap)).mean().reindex(DISEASES)
    ax[0, 1].bar(by_dis.index, by_dis.values, color=PURPLE); ax[0, 1].set_title("每人事件數（依疾病）"); ax[0, 1].tick_params(axis="x", rotation=30)
    inf = gt[gt.event_type == "INFECTION"]["event_date_true"]
    fla = gt[gt.event_type == "FLARE"]["event_date_true"]
    bins = np.arange(0, 366, 30)
    ax[1, 0].hist(inf, bins=bins, color=CORAL, alpha=0.8, label="感染（季節性）")
    ax[1, 0].axvline(15, color="k", ls="--", lw=1, label="冬季高峰 (day 15)")
    ax[1, 0].set_title("感染的季節性"); ax[1, 0].set_xlabel("day of year"); ax[1, 0].legend(fontsize=8)
    ax[1, 1].hist(epp, bins=30, color=TEAL, edgecolor="white"); ax[1, 1].axvline(epp.mean(), color=CORAL, ls="--", lw=2, label=f"mean {epp.mean():.0f}")
    ax[1, 1].set_title("每人事件數分布"); ax[1, 1].set_xlabel("events / patient"); ax[1, 1].legend(fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.96]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_metrics(ev, out):
    mets = [("information_completeness", "資訊完整度"), ("event_recall_rate", "事件捕捉率"),
            ("precision", "精確度"), ("f1", "F1"), ("medication_recall_accuracy", "用藥準確度"),
            ("timeline_accuracy", "時間軸準確度"), ("ordering_tau", "順序 τ"),
            ("clinical_reconstruction_score", "臨床重建分數"), ("doctor_understanding", "醫師理解度")]
    rec = ev[ev.arm == "PATIENT_RECALL"]; mdp = ev[ev.arm == "MDPIECE"]
    fig, ax = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.7, 1]})
    fig.suptitle("評估指標全覽（逐人逐組 vs 真實）", fontsize=15, fontweight="bold")
    y = np.arange(len(mets))
    ax[0].barh(y + 0.2, [rec[m].mean() for m, _ in mets], 0.38, color=PURPLE, label="病患回憶")
    ax[0].barh(y - 0.2, [mdp[m].mean() for m, _ in mets], 0.38, color=TEAL, label="MD.Piece")
    ax[0].set_yticks(y); ax[0].set_yticklabels([n for _, n in mets], fontsize=9); ax[0].invert_yaxis()
    ax[0].set_xlim(0, 1); ax[0].legend(); ax[0].set_title("各指標平均（回憶 vs MD.Piece）")
    for yi, (m, _) in enumerate(mets):
        ax[0].text(rec[m].mean() + 0.01, yi + 0.2, f"{rec[m].mean():.2f}", va="center", fontsize=7)
        ax[0].text(mdp[m].mean() + 0.01, yi - 0.2, f"{mdp[m].mean():.2f}", va="center", fontsize=7)
    ax[1].hist(rec["clinical_reconstruction_score"], bins=40, alpha=0.6, color=PURPLE, label="病患回憶")
    ax[1].hist(mdp["clinical_reconstruction_score"], bins=40, alpha=0.6, color=TEAL, label="MD.Piece")
    ax[1].set_title("臨床重建分數分布"); ax[1].set_xlabel("score"); ax[1].legend(fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_friction(fr, out):
    comp = [("omission", "事件遺漏", lambda d: 1 - d["event_recall_rate"]),
            ("med", "用藥錯誤", lambda d: 1 - d["medication_recall_accuracy"]),
            ("temporal", "日期錯誤", lambda d: 1 - d["timeline_accuracy"]),
            ("severity", "嚴重度錯誤", lambda d: d["severity_error_rate"]),
            ("unreviewed", "未審閱", lambda d: d["unreviewed_fraction"])]
    rec = fr[fr.arm == "PATIENT_RECALL"]; mdp = fr[fr.arm == "MDPIECE"]
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("資訊摩擦組成（L5+L8）— 越低越好", fontsize=15, fontweight="bold")
    x = np.arange(len(comp))
    ax[0].bar(x - 0.2, [f(rec).mean() for _, _, f in comp], 0.38, color=PURPLE, label="病患回憶")
    ax[0].bar(x + 0.2, [f(mdp).mean() for _, _, f in comp], 0.38, color=TEAL, label="MD.Piece")
    ax[0].set_xticks(x); ax[0].set_xticklabels([n for _, n, _ in comp], fontsize=9); ax[0].legend()
    ax[0].set_title("各摩擦組成（加權前）"); ax[0].set_ylabel("loss fraction")
    ax[1].hist(rec["information_friction_score"], bins=40, alpha=0.6, color=PURPLE, label=f"回憶 (mean {rec['information_friction_score'].mean():.2f})")
    ax[1].hist(mdp["information_friction_score"], bins=40, alpha=0.6, color=TEAL, label=f"MD.Piece (mean {mdp['information_friction_score'].mean():.2f})")
    ax[1].set_title("資訊摩擦分數分布"); ax[1].set_xlabel("friction score (↓ better)"); ax[1].legend(fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_doctor(doc, out):
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.5))
    fig.suptitle("醫師互動引擎（L8）", fontsize=15, fontweight="bold")
    order = ["HIGHLY_ENGAGED", "DATA_ORIENTED", "MODERATELY_ENGAGED", "SKEPTICAL", "TRADITIONAL", "TIME_CONSTRAINED"]
    rev = doc[doc.reviewed]
    u = rev.groupby("physician_persona")["doctor_understanding"].mean().reindex(order)
    ax[0].barh(range(len(u)), u.values, color=TEAL); ax[0].set_yticks(range(len(u))); ax[0].set_yticklabels(u.index, fontsize=8)
    ax[0].invert_yaxis(); ax[0].set_title("醫師理解度（依醫師人格）"); ax[0].set_xlim(0, 1)
    rr = doc.groupby("physician_persona")["reviewed"].mean().reindex(order)
    ax[1].barh(range(len(rr)), rr.values, color=PURPLE); ax[1].set_yticks(range(len(rr))); ax[1].set_yticklabels(rr.index, fontsize=8)
    ax[1].invert_yaxis(); ax[1].set_title("審閱機率"); ax[1].set_xlim(0, 1)
    for arm, c, lab in [("PATIENT_RECALL", PURPLE, "病患回憶"), ("MDPIECE", TEAL, "MD.Piece")]:
        rt = doc[(doc.arm == arm) & doc.reviewed]["reading_time_sec"]
        ax[2].hist(rt, bins=30, alpha=0.6, color=c, label=lab)
    ax[2].set_title("閱讀時間分布"); ax[2].set_xlabel("seconds"); ax[2].legend(fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94]); fig.savefig(out, dpi=130); plt.close(fig)


def fig_retention(ret, out):
    cols = ["d1", "w1", "m1", "m3", "m6", "m12"]
    labels = ["D1", "W1", "M1", "M3", "M6", "M12"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    cmap = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, p in enumerate(PERSONA_ORDER):
        sub = ret[ret.persona == p]
        if not len(sub):
            continue
        vals = [(sub[c] & sub["onboarded"]).mean() for c in cols]
        ax.plot(range(len(cols)), vals, "-o", color=cmap[i], label=p, lw=2)
    allv = [(ret[c] & ret["onboarded"]).mean() for c in cols]
    ax.plot(range(len(cols)), allv, "--", color="black", lw=2.5, label="全體")
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(labels)
    ax.set_ylabel("仍活躍的比例"); ax.set_ylim(0, 1)
    ax.set_title("App 留存曲線（依人格）— 刻意悲觀（D3/A09）")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", default="713d8a608280")
    args = ap.parse_args()
    FIGDIR.mkdir(parents=True, exist_ok=True)
    hd = HERE / "outputs" / args.hash
    pts = pd.read_csv(hd / "patients.csv")
    ev = pd.read_csv(hd / "evaluation_metrics.csv")
    fr = pd.read_csv(hd / "information_friction.csv")
    doc = pd.read_csv(hd / "doctor_interaction.csv")
    ret = pd.read_csv(hd / "retention.csv")
    gt = pd.read_csv(hd / "ground_truth_events.csv", usecols=["patient_id", "event_type", "event_date_true"])

    outs = []
    fig_population(pts, FIGDIR / "data_population.png"); outs.append("data_population.png")
    fig_events(gt, pts, FIGDIR / "data_events.png"); outs.append("data_events.png")
    fig_metrics(ev, FIGDIR / "data_metrics.png"); outs.append("data_metrics.png")
    fig_friction(fr, FIGDIR / "data_friction.png"); outs.append("data_friction.png")
    fig_doctor(doc, FIGDIR / "data_doctor.png"); outs.append("data_doctor.png")
    fig_retention(ret, FIGDIR / "data_retention.png"); outs.append("data_retention.png")
    print("\n".join(f"wrote {FIGDIR / o}" for o in outs))


if __name__ == "__main__":
    main()

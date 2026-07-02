"""Design-response arms — quantify each design pillar's marginal benefit (roadmap ranking).

Maps the five design pillars (from docs/11_patient_usage_problems.md) to config interventions,
runs the full pipeline under each (and all combined) vs baseline, and reports the marginal gain
on the primary fidelity estimand (ΔCRS), patient satisfaction, and M3 retention.

    python -m simulation.run_design_arms [--n 900]
"""
from __future__ import annotations

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

from simulation.common import load_config, OUTPUT_DIR
from simulation.evaluation import arm_metrics
from simulation.run_study import generate, _doctor_and_friction
from simulation.run_sensitivity import variant
from simulation.make_usage_research import derive

R = "probability_registry"
PILLARS = {
    "A 降門檻\n(onboarding↑)": {f"{R}.usage.retention.onboarding_completion.value": 0.92},
    "B 降負擔\n(OCR 被動擷取)": {f"{R}.friction.mdpiece.ocr_capture.enabled": True},
    "C 智慧提醒\n(notif↑)": {f"{R}.friction.mdpiece.notification_recovery.max_recovered_frac.value": 0.50},
    "D 醫病閉環\n(snapshot)": {
        f"{R}.doctor.review_probability.base.value": 0.75,
        f"{R}.doctor.reading_budget_base_sec.value": 320,
        f"{R}.doctor.understanding.noise_penalty.value": 0.30},
    "E 信任與留存\n(retention↑)": {f"{R}.usage.retention.median_lifetime_days.value": 130},
}
TEAL, PURPLE, GOLD, CORAL = "#2A9D8F", "#7B6CD6", "#E9C46A", "#E76F51"


def evaluate(cfg, n):
    patients, truth, recall, mdp, phys, doc_rngs, retention = generate(cfg, n, parity=False)
    rec = _doctor_and_friction(arm_metrics(patients, truth, recall, cfg), phys, doc_rngs, cfg, "PATIENT_RECALL")
    mdp = _doctor_and_friction(arm_metrics(patients, truth, mdp, cfg), phys, doc_rngs, cfg, "MDPIECE")
    df = derive(patients, pd.concat([rec, mdp], ignore_index=True), retention)
    return {
        "dcrs": float(df["d_crs"].mean()),
        "helped": float((df["d_crs"] > 0).mean() * 100),
        "sat": float(df["satisfaction"].mean()),
        "m3": float(df["m3_active"].mean() * 100),
        "adopt": float(df["adopted"].mean() * 100),
        "und": float(df["communication"].mean()),  # mdpiece doctor understanding (the L8 last-mile)
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=900)
    args = ap.parse_args(); n = args.n
    base_cfg = load_config()

    print(f"[design-arms] n={n}/scenario")
    rows = {"baseline": evaluate(base_cfg, n)}
    for name, ov in PILLARS.items():
        rows[name] = evaluate(variant(base_cfg, ov), n)
        print(f"  done: {name.splitlines()[0]}")
    all_ov = {k: v for ov in PILLARS.values() for k, v in ov.items()}
    rows["ALL 全部組合"] = evaluate(variant(base_cfg, all_ov), n)
    print("  done: ALL")

    b = rows["baseline"]
    order = list(PILLARS) + ["ALL 全部組合"]
    print(f"\nbaseline: ΔCRS={b['dcrs']:+.3f} helped={b['helped']:.0f}% sat={b['sat']:.0f} M3={b['m3']:.0f}% und={b['und']:.3f}")
    print(f"{'pillar':<22}{'ΔΔCRS':>9}{'Δ理解':>8}{'Δsat':>8}{'ΔM3%':>8}")
    recs = []
    for name in order:
        r = rows[name]
        d = {"pillar": name.replace("\n", " "), "ddcrs": r["dcrs"] - b["dcrs"], "dsat": r["sat"] - b["sat"],
             "dm3": r["m3"] - b["m3"], "dhelped": r["helped"] - b["helped"], "dund": (r["und"] - b["und"]) * 100,
             "dcrs": r["dcrs"], "sat": r["sat"], "m3": r["m3"], "und": r["und"]}
        recs.append(d)
        print(f"{d['pillar']:<22}{d['ddcrs']:>+9.3f}{d['dund']:>+8.1f}{d['dsat']:>+8.1f}{d['dm3']:>+8.1f}")

    # ---- figure: marginal gain per pillar (sorted by ΔΔCRS, pillars only) ----
    pill = [r for r in recs if r["pillar"].startswith(("A", "B", "C", "D", "E"))]
    pill.sort(key=lambda r: r["ddcrs"])
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("設計回應 arm — 各支柱的邊際效益（vs 基準；roadmap 排序）", fontsize=14, fontweight="bold")
    names = [r["pillar"].split(" ")[0] + " " + r["pillar"].split(" ")[1] for r in pill]
    ax[0].barh(range(len(pill)), [r["ddcrs"] for r in pill], color=TEAL)
    ax[0].set_yticks(range(len(pill))); ax[0].set_yticklabels(names, fontsize=10)
    ax[0].axvline(0, color="k", lw=0.8); ax[0].set_xlabel("Δ ΔCRS（紀錄保真度邊際增益）")
    ax[0].set_title("① 對 ΔCRS 的邊際效益")
    for i, r in enumerate(pill):
        ax[0].text(r["ddcrs"] + 0.001, i, f"{r['ddcrs']:+.3f}", va="center", fontsize=9)
    x = np.arange(len(pill))
    ax[1].bar(x - 0.28, [r["dund"] for r in pill], 0.26, color=TEAL, label="Δ醫師理解度(×100)")
    ax[1].bar(x, [r["dsat"] for r in pill], 0.26, color=PURPLE, label="Δ滿意度")
    ax[1].bar(x + 0.28, [r["dm3"] for r in pill], 0.26, color=GOLD, label="Δ M3 留存(%)")
    ax[1].set_xticks(x); ax[1].set_xticklabels([n.split(" ")[0] for n in names], fontsize=10)
    ax[1].axhline(0, color="k", lw=0.8); ax[1].legend(fontsize=9); ax[1].set_title("② 對理解度／滿意度／留存的邊際效益")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = HEREFIG = (OUTPUT_DIR.parent / "docs" / "figures" / "design_arms.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130); plt.close(fig)
    pd.DataFrame(recs).to_csv(OUTPUT_DIR / base_cfg.config_hash / "design_arms.csv", index=False)
    print(f"\nwrote {out} and design_arms.csv")


if __name__ == "__main__":
    main()

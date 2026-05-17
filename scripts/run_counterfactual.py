"""Counterfactual / what-if 模擬：MD.Piece App 對患者結果的真實影響。

每位虛擬患者跑兩次（相同 seed、相同患者畫像）：
  Arm A (control)   — 沒用 App
  Arm B (treatment) — 用 MD.Piece App（含智慧提醒、AI 早期預警、衛教）

輸出：
  - output/counterfactual_<timestamp>/cohort_with_app.json
  - output/counterfactual_<timestamp>/cohort_no_app.json
  - output/counterfactual_<timestamp>/intervention_effect.md
  - output/counterfactual_<timestamp>/per_patient_delta.csv
  - output/counterfactual_<timestamp>/figures/*.png

Usage:
  PYTHONPATH=. python scripts/run_counterfactual.py --n 200 --days 180

  --n      patients per disease per arm (default 50; 用 200 對應主 demo)
  --days   simulation horizon (default 180)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics as S
import sys
import time
from datetime import datetime
from pathlib import Path

# 允許從 repo root 直接執行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from md_piece.disease_loader import load_disease  # noqa: E402
from md_piece.patient import simulate_patient  # noqa: E402
from ml.intervention import AppIntervention  # noqa: E402


DISEASES = [
    "anca_vasculitis", "ankylosing_spondylitis", "asthma", "behcet_disease",
    "chronic_urticaria", "gout", "idiopathic_pulmonary_fibrosis",
    "igg4_related_disease", "inflammatory_bowel_disease", "multiple_sclerosis",
    "osteoarthritis", "psoriatic_arthritis", "rheumatoid_arthritis",
    "sjogren_syndrome", "systemic_lupus_erythematosus", "systemic_sclerosis",
]

DISEASE_NAME_TC = {
    "anca_vasculitis": "ANCA 血管炎",
    "ankylosing_spondylitis": "僵直性脊椎炎",
    "asthma": "氣喘",
    "behcet_disease": "貝歇氏病",
    "chronic_urticaria": "慢性蕁麻疹",
    "gout": "痛風",
    "idiopathic_pulmonary_fibrosis": "特發性肺纖維化",
    "igg4_related_disease": "IgG4 相關疾病",
    "inflammatory_bowel_disease": "發炎性腸道疾病",
    "multiple_sclerosis": "多發性硬化症",
    "osteoarthritis": "退化性關節炎",
    "psoriatic_arthritis": "乾癬性關節炎",
    "rheumatoid_arthritis": "類風濕關節炎",
    "sjogren_syndrome": "修格蘭氏症候群",
    "systemic_lupus_erythematosus": "紅斑性狼瘡",
    "systemic_sclerosis": "全身性硬化症",
}


def _summarise(patients):
    """Aggregate per-arm metrics."""
    return {
        "n": len(patients),
        "flare_count_mean": S.mean(p.flare_count for p in patients),
        "flare_count_median": S.median(p.flare_count for p in patients),
        "activity_mean": S.mean(p.timeseries["activity"].mean() for p in patients),
        "skip_days_mean": S.mean(p.timeseries["dose_any_skipped"].sum() for p in patients),
        "pain_vas_mean": (
            S.mean(p.timeseries["pain_vas"].mean()
                   for p in patients if "pain_vas" in p.timeseries.columns)
            if any("pain_vas" in p.timeseries.columns for p in patients) else None
        ),
        "in_flare_days_mean": S.mean((p.timeseries["in_flare"]==1).sum() for p in patients),
    }


def _patient_row(disease_id, pc, pa):
    """One row per patient: control vs app deltas + key covariates."""
    sp = pc.social_profile
    return {
        "patient_id": pc.patient_id,
        "disease_id": disease_id,
        "age": pc.age,
        "sex": pc.sex,
        "subtype": pc.subtype,
        "responder_class": pc.responder_class,
        "is_elderly": int(pc.age_profile.is_elderly) if pc.age_profile else 0,
        # social
        "health_literacy": sp.health_behavior.health_literacy,
        "education": sp.socioeconomic.education,
        "income": sp.socioeconomic.income_tier,
        "family_support": sp.social.family_support,
        "living_alone": int(sp.social.living_arrangement == "alone"),
        "neuroticism": round(sp.personality.neuroticism, 3),
        "conscientiousness": round(sp.personality.conscientiousness, 3),
        "phq9": sp.mental_health.phq9_score,
        # engagement (only meaningful for App arm)
        "engagement": round(pa.engagement, 3),
        # outcomes
        "flare_ctrl": pc.flare_count,
        "flare_app": pa.flare_count,
        "flare_delta": pa.flare_count - pc.flare_count,
        "activity_ctrl": round(pc.timeseries["activity"].mean(), 3),
        "activity_app": round(pa.timeseries["activity"].mean(), 3),
        "activity_delta": round(
            pa.timeseries["activity"].mean() - pc.timeseries["activity"].mean(), 3
        ),
        "skip_days_ctrl": int(pc.timeseries["dose_any_skipped"].sum()),
        "skip_days_app": int(pa.timeseries["dose_any_skipped"].sum()),
        "skip_days_delta": int(
            pa.timeseries["dose_any_skipped"].sum() - pc.timeseries["dose_any_skipped"].sum()
        ),
        "in_flare_days_ctrl": int((pc.timeseries["in_flare"] == 1).sum()),
        "in_flare_days_app": int((pa.timeseries["in_flare"] == 1).sum()),
    }


def run(n_per_disease: int, sim_days: int, base_seed: int, outdir: Path) -> None:
    intervention = AppIntervention()

    print(f"\n{'='*70}")
    print(f"MD.Piece Counterfactual Run")
    print(f"  n_per_disease = {n_per_disease}, sim_days = {sim_days}")
    print(f"  diseases      = {len(DISEASES)} → total {len(DISEASES)*n_per_disease*2} simulations")
    print(f"  base_seed     = {base_seed}")
    print(f"  output        = {outdir}")
    print(f"{'='*70}\n")

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "figures").mkdir(exist_ok=True)

    by_disease_summary: dict[str, dict] = {}
    rows: list[dict] = []
    t0 = time.time()

    for di, did in enumerate(DISEASES, 1):
        dc = load_disease(did)
        t_d = time.time()
        ctrl, app = [], []
        for i in range(n_per_disease):
            seed = base_seed * 100_000 + i
            pid = f"{dc.short}_{i:04d}"
            pc = simulate_patient(pid, dc, sim_days, seed)
            pa = simulate_patient(pid, dc, sim_days, seed, intervention=intervention)
            ctrl.append(pc)
            app.append(pa)
            rows.append(_patient_row(did, pc, pa))

        s_ctrl = _summarise(ctrl)
        s_app = _summarise(app)
        by_disease_summary[did] = {"ctrl": s_ctrl, "app": s_app}

        dt = time.time() - t_d
        flare_red = s_ctrl["flare_count_mean"] - s_app["flare_count_mean"]
        pct_reduction = 100 * flare_red / max(s_ctrl["flare_count_mean"], 0.01)
        print(f"[{di:2d}/16] {did:<36s} flare {s_ctrl['flare_count_mean']:5.2f} → "
              f"{s_app['flare_count_mean']:5.2f} (↓ {pct_reduction:5.1f}%)  "
              f"act {s_ctrl['activity_mean']:.2f}→{s_app['activity_mean']:.2f}  "
              f"({dt:5.1f}s)")

    total_dt = time.time() - t0
    print(f"\nTotal {total_dt/60:.1f} min")

    # ─── Write per-patient delta CSV ──────────────────────────────────────────
    csv_path = outdir / "per_patient_delta.csv"
    if rows:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n→ per_patient_delta.csv  ({len(rows)} rows, {os.path.getsize(csv_path)//1024} KB)")

    # ─── Write aggregate JSON ────────────────────────────────────────────────
    agg_path = outdir / "intervention_effect.json"

    def _overall(arm: str):
        return {
            "flare_count_mean": S.mean(r[f"flare_{arm}"] for r in rows),
            "activity_mean": S.mean(r[f"activity_{arm}"] for r in rows),
            "skip_days_mean": S.mean(r[f"skip_days_{arm}"] for r in rows),
            "in_flare_days_mean": S.mean(r[f"in_flare_days_{arm}"] for r in rows),
        }
    agg = {
        "config": {
            "n_per_disease": n_per_disease,
            "sim_days": sim_days,
            "base_seed": base_seed,
            "intervention": {
                "adherence_boost": intervention.adherence_boost,
                "avoidable_trigger_reduction": intervention.avoidable_trigger_reduction,
                "early_warning_threshold_ratio": intervention.early_warning_threshold_ratio,
                "early_warning_trigger_dampening": intervention.early_warning_trigger_dampening,
                "placebo_boost": intervention.placebo_boost,
                "base_engagement": intervention.base_engagement,
            },
            "generated_at": datetime.now().isoformat(),
        },
        "overall": {"ctrl": _overall("ctrl"), "app": _overall("app"),
                    "mean_engagement": round(S.mean(r["engagement"] for r in rows), 3)},
        "by_disease": by_disease_summary,
    }
    with open(agg_path, "w") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2, default=str)
    print(f"→ intervention_effect.json  ({os.path.getsize(agg_path)//1024} KB)")

    # ─── Generate markdown report ────────────────────────────────────────────
    _generate_markdown_report(outdir, agg, rows)
    print(f"→ intervention_effect.md")

    # ─── Generate figures ────────────────────────────────────────────────────
    try:
        _generate_figures(outdir, agg, rows)
        print(f"→ figures/ generated")
    except ImportError as e:
        print(f"  (skipped figures: {e})")


def _generate_markdown_report(outdir: Path, agg: dict, rows: list[dict]) -> None:
    """產出 intervention_effect.md（人類可讀的對照表）。"""
    md: list[str] = []
    cfg = agg["config"]
    md.append(f"# MD.Piece App 反事實效果報告\n")
    md.append(f"**Generated**: {cfg['generated_at']}")
    md.append(f"**Cohort**: {cfg['n_per_disease']} 患者 × 16 疾病 × 2 arms × {cfg['sim_days']} 天 "
              f"= {16 * cfg['n_per_disease'] * 2 * cfg['sim_days']:,} patient-days\n")

    o = agg["overall"]
    md.append(f"\n## 整體（{cfg['n_per_disease']*16} 患者）\n")
    md.append("| 指標 | Control（沒用 App） | Treatment（用 MD.Piece App） | Δ | Δ% |")
    md.append("|---|---|---|---|---|")
    for label, key in [
        (f"Flare 次數 / 患者 / {cfg['sim_days']}天", "flare_count_mean"),
        ("Flare 在身上天數", "in_flare_days_mean"),
        ("平均疾病活動度", "activity_mean"),
        ("漏吃藥天數 / 患者", "skip_days_mean"),
    ]:
        c, a = o["ctrl"][key], o["app"][key]
        d = a - c
        pct = 100 * d / c if c else 0
        md.append(f"| {label} | {c:.2f} | {a:.2f} | {d:+.2f} | **{pct:+.1f}%** |")

    md.append(f"\n**平均 engagement** = {o['mean_engagement']:.3f}（介入效應 attenuate by engagement）")

    md.append(f"\n## 按疾病拆解\n")
    md.append("| 疾病 | flare ctrl | flare app | Δ% | activity Δ | 漏藥 Δ |")
    md.append("|---|---|---|---|---|---|")
    by_d = agg["by_disease"]
    sorted_diseases = sorted(by_d.keys(),
        key=lambda k: (by_d[k]["app"]["flare_count_mean"] - by_d[k]["ctrl"]["flare_count_mean"])
                      / max(by_d[k]["ctrl"]["flare_count_mean"], 0.01))
    for did in sorted_diseases:
        c = by_d[did]["ctrl"]
        a = by_d[did]["app"]
        d_flare = a["flare_count_mean"] - c["flare_count_mean"]
        d_pct = 100 * d_flare / max(c["flare_count_mean"], 0.01)
        d_act = a["activity_mean"] - c["activity_mean"]
        d_skip = a["skip_days_mean"] - c["skip_days_mean"]
        name = DISEASE_NAME_TC.get(did, did)
        md.append(f"| {name} (`{did}`) | {c['flare_count_mean']:.2f} | "
                  f"{a['flare_count_mean']:.2f} | **{d_pct:+.1f}%** | "
                  f"{d_act:+.2f} | {d_skip:+.1f} |")

    md.append(f"\n## 按亞群拆解（介入效應的不平等）\n")

    def _subgroup(filter_fn, label):
        sub = [r for r in rows if filter_fn(r)]
        if not sub:
            return None
        c_flare = S.mean(r["flare_ctrl"] for r in sub)
        a_flare = S.mean(r["flare_app"] for r in sub)
        d_pct = 100 * (a_flare - c_flare) / max(c_flare, 0.01)
        return f"| {label} | {len(sub)} | {c_flare:.2f} | {a_flare:.2f} | **{d_pct:+.1f}%** |"

    md.append("| 亞群 | n | flare ctrl | flare app | Δ% |")
    md.append("|---|---|---|---|---|")
    subgroups = [
        (lambda r: r["health_literacy"] == "高", "健康識讀 = 高"),
        (lambda r: r["health_literacy"] == "中", "健康識讀 = 中"),
        (lambda r: r["health_literacy"] == "低", "健康識讀 = 低"),
        (lambda r: r["is_elderly"] == 1, "老年 (≥70)"),
        (lambda r: r["is_elderly"] == 0, "非老年 (<70)"),
        (lambda r: r["is_elderly"] == 1 and r["living_alone"] == 1, "老年獨居"),
        (lambda r: r["is_elderly"] == 1 and r["family_support"] == "高", "老年高家庭支持"),
        (lambda r: r["income"] in ("低收", "中下"), "低收入 (低收/中下)"),
        (lambda r: r["income"] in ("中上", "高收"), "高收入 (中上/高收)"),
        (lambda r: r["neuroticism"] >= 0.65, "高神經質 (≥0.65)"),
        (lambda r: r["conscientiousness"] <= 0.35, "低盡責性 (≤0.35)"),
        (lambda r: r["phq9"] >= 10, "PHQ-9 ≥ 10（中度以上憂鬱）"),
        (lambda r: r["responder_class"] == "non_responder", "Non-responder"),
        (lambda r: r["responder_class"] == "super", "Super-responder"),
    ]
    for fn, label in subgroups:
        line = _subgroup(fn, label)
        if line:
            md.append(line)

    md.append(f"\n## 個別患者勝率\n")
    n_helped = sum(1 for r in rows if r["flare_delta"] < 0)
    n_neutral = sum(1 for r in rows if r["flare_delta"] == 0)
    n_hurt = sum(1 for r in rows if r["flare_delta"] > 0)
    total = len(rows)
    md.append(f"- 用了 App **flare 減少** 的：{n_helped} / {total}（{100*n_helped/total:.1f}%）")
    md.append(f"- 用了 App **flare 不變** 的：{n_neutral} / {total}（{100*n_neutral/total:.1f}%）")
    md.append(f"- 用了 App **flare 增加**（RNG 干擾）的：{n_hurt} / {total}（{100*n_hurt/total:.1f}%）")

    md.append(f"\n## 介入設定\n```json")
    md.append(json.dumps(cfg["intervention"], ensure_ascii=False, indent=2))
    md.append("```")

    md.append(f"\n## 註解\n")
    md.append("- **Intent-to-treat 分析**：不論 engagement 高低，所有患者都被分配到 App 組。")
    md.append("- **個別差異來源**：每位患者的 trigger / life event RNG 在介入後會分歧，所以個案層級會有正負噪音；cohort 平均才反映系統效應。")
    md.append("- **App 效應通道**：（1）智慧提醒→提升 adherence；（2）AI 早期預警→ activity 接近 flare 閾值時減弱觸發；（3）行為觸發降低→可避免類 trigger（飲食、運動、環境）prob 下降；（4）衛教→提升 placebo 與治療可近性。")
    md.append("- **不可避免 trigger**：感染、生理週期、手術、季節變化、社會事件不受 App 影響。")
    md.append("- **engagement 模型**：健康識讀低 / 老年獨居無家屬支持 / 低盡責性 → engagement↓，介入效應 attenuated。")

    (outdir / "intervention_effect.md").write_text("\n".join(md), encoding="utf-8")


def _generate_figures(outdir: Path, agg: dict, rows: list[dict]) -> None:
    """產出對照圖：per-disease flare reduction、subgroup effect、scatter。"""
    import matplotlib  # type: ignore
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore

    # 自動偵測可用 CJK 字型（容器 / mac / Linux 各有不同）
    from matplotlib import font_manager
    cjk_candidates = [
        "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans CJK",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
        "PingFang TC", "Heiti TC", "Microsoft JhengHei",
        "SimHei", "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    cjk_picked = [f for f in cjk_candidates if f in available]
    plt.rcParams["font.family"] = cjk_picked + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    figdir = outdir / "figures"

    # 1. Per-disease flare reduction bar chart
    by_d = agg["by_disease"]
    diseases = list(by_d.keys())
    deltas = []
    for did in diseases:
        c = by_d[did]["ctrl"]["flare_count_mean"]
        a = by_d[did]["app"]["flare_count_mean"]
        deltas.append(100 * (a - c) / max(c, 0.01))
    order = sorted(range(len(diseases)), key=lambda i: deltas[i])
    diseases_sorted = [DISEASE_NAME_TC.get(diseases[i], diseases[i]) for i in order]
    deltas_sorted = [deltas[i] for i in order]
    colors = ["#2ecc71" if d < 0 else "#e74c3c" for d in deltas_sorted]

    fig, ax = plt.subplots(figsize=(9, 7))
    bars = ax.barh(diseases_sorted, deltas_sorted, color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Flare 次數變化 %（負 = App 減少 flare）")
    ax.set_title("MD.Piece App 對各疾病 flare 次數的影響（n=200/疾病）")
    for bar, d in zip(bars, deltas_sorted):
        ax.text(d + (1 if d>=0 else -1), bar.get_y() + bar.get_height()/2,
                f"{d:+.0f}%", va="center",
                ha="left" if d>=0 else "right", fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / "01_flare_reduction_by_disease.png", dpi=120)
    plt.close(fig)

    # 2. Adherence improvement
    fig, ax = plt.subplots(figsize=(8, 4))
    skip_c = [r["skip_days_ctrl"] for r in rows]
    skip_a = [r["skip_days_app"] for r in rows]
    ax.hist([skip_c, skip_a], bins=20, label=["沒用 App", "用 MD.Piece App"],
            color=["#e74c3c", "#2ecc71"], alpha=0.7)
    ax.set_xlabel("180 天內漏吃藥天數")
    ax.set_ylabel("患者數")
    ax.set_title(f"漏吃藥天數分布：平均 {S.mean(skip_c):.1f} → {S.mean(skip_a):.1f} 天")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "02_adherence_distribution.png", dpi=120)
    plt.close(fig)

    # 3. Subgroup effect (health literacy)
    fig, ax = plt.subplots(figsize=(8, 5))
    levels = ["高", "中", "低"]
    ctrl_means, app_means = [], []
    for lev in levels:
        sub = [r for r in rows if r["health_literacy"] == lev]
        if sub:
            ctrl_means.append(S.mean(r["flare_ctrl"] for r in sub))
            app_means.append(S.mean(r["flare_app"] for r in sub))
    x = list(range(len(levels)))
    w = 0.35
    ax.bar([i-w/2 for i in x], ctrl_means, w, label="沒用 App", color="#e74c3c")
    ax.bar([i+w/2 for i in x], app_means, w, label="用 MD.Piece App", color="#2ecc71")
    ax.set_xticks(x)
    ax.set_xticklabels([f"健康識讀={l}" for l in levels])
    ax.set_ylabel("平均 flare 次數 / 患者 / 180天")
    ax.set_title("App 對不同健康識讀群體的效果（同樣分到 App，效應不同）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "03_subgroup_health_literacy.png", dpi=120)
    plt.close(fig)

    # 4. Elderly living alone vs supported
    fig, ax = plt.subplots(figsize=(8, 5))
    groups = [
        ("老年獨居+低家庭支持", lambda r: r["is_elderly"]==1 and r["living_alone"]==1 and r["family_support"]=="低"),
        ("老年獨居+中/高家庭支持", lambda r: r["is_elderly"]==1 and r["living_alone"]==1 and r["family_support"]!="低"),
        ("老年同住", lambda r: r["is_elderly"]==1 and r["living_alone"]==0),
        ("非老年", lambda r: r["is_elderly"]==0),
    ]
    labels, ctrl_means, app_means = [], [], []
    for label, fn in groups:
        sub = [r for r in rows if fn(r)]
        if sub:
            labels.append(f"{label}\n(n={len(sub)})")
            ctrl_means.append(S.mean(r["flare_ctrl"] for r in sub))
            app_means.append(S.mean(r["flare_app"] for r in sub))
    x = list(range(len(labels)))
    ax.bar([i-w/2 for i in x], ctrl_means, w, label="沒用 App", color="#e74c3c")
    ax.bar([i+w/2 for i in x], app_means, w, label="用 MD.Piece App", color="#2ecc71")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("平均 flare 次數")
    ax.set_title("老年+家屬支持的關鍵（App 家屬模式價值）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "04_elderly_family_support.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="patients per disease per arm")
    ap.add_argument("--days", type=int, default=180, help="simulation horizon")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.outdir) if args.outdir else (ROOT / "output" / f"counterfactual_{ts}")
    run(args.n, args.days, args.seed, out)

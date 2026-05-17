"""MD. Piece — Full Demo Runner（一鍵跑 16 疾病 + AI 心得 + 6 報表）

執行：
    PYTHONPATH=. python scripts/run_full_demo.py --n 200
    PYTHONPATH=. python scripts/run_full_demo.py --n 500 --skip-retrain
    PYTHONPATH=. python scripts/run_full_demo.py --n 150 --quick   # 略過 ML 完整訓練

產出：
    output/full_run_YYYYMMDD_HHMMSS/
      ├── 00_index.md                        # 入口 + 摘要
      ├── 01_cohort_overview.md              # 總覽（疾病 / 年齡 / 反應者）
      ├── 02_per_disease/{disease_id}.md     # 每個疾病的詳細報告（16 個）
      ├── 03_model_performance.md            # 模型 overall + per-disease 指標
      ├── 04_ai_users_log.md                 # 5 個 AI 角色使用心得
      ├── 05_patient_samples.md              # 每疾病 3 位代表性患者 + AI 心得
      ├── 06_sanity_tests.md                 # 自動驗證測試結果
      ├── cohort.json                        # 原始資料
      └── figures/                           # PNG 圖
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean

import numpy as np

# Make sure the project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from md_piece.cohort_generator import generate_cohort  # noqa: E402
from md_piece.disease_loader import list_diseases, load_disease  # noqa: E402
from md_piece.visualize import (  # noqa: E402
    plot_cohort_overlay, plot_flare_distribution, plot_single_patient,
)


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _print_section(title: str) -> None:
    print()
    print("━" * 72)
    print(f"▶ {title}")
    print("━" * 72)


def _fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%"


# ------------------ Step 1: cohort generation -------------------------------

def step_generate(
    n_per_disease: int,
    sim_days: int,
    base_seed: int,
    out_dir: Path,
) -> dict:
    """Generate cohorts for all 16 diseases. Returns cohort dict + figures path."""
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    diseases = list_diseases()
    cohort_json = {
        "version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {
            "n_patients_per_disease": n_per_disease,
            "sim_days": sim_days,
            "seed": base_seed,
            "n_diseases": len(diseases),
        },
        "diseases": {},
    }

    all_patients = []
    print(f"Simulating {len(diseases)} diseases × {n_per_disease} patients × {sim_days} days …")
    for i, did in enumerate(diseases, 1):
        t0 = time.time()
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_per_disease, sim_days, base_seed=base_seed)
        dt = time.time() - t0
        cohort_json["diseases"][did] = {
            "name": cfg.name,
            "dynamics_type": cfg.dynamics_type,
            "patients": cohort.patients,    # in-memory objects; serialized later
            "_cfg": cfg,
        }
        all_patients.extend(cohort.patients)

        plot_single_patient(cohort.patients[0], fig_dir / f"{did}_single.png")
        plot_cohort_overlay(cohort, fig_dir / f"{did}_cohort.png")
        plot_flare_distribution(cohort, fig_dir / f"{did}_flares.png")

        elderly = sum(1 for p in cohort.patients
                      if p.age_profile and p.age_profile.is_elderly)
        print(f"  [{i:2d}/{len(diseases)}] {did:35s} {dt:4.1f}s | "
              f"flares={mean(p.flare_count for p in cohort.patients):.2f} | "
              f"elderly={elderly}/{n_per_disease}")

    return cohort_json, all_patients


# ------------------ Step 2: ML retrain (optional) ---------------------------

def step_retrain(quick: bool) -> tuple[bool, dict]:
    """Retrain Layer-3 model on the new 16-disease config.

    Returns (success, report_dict_or_empty).
    """
    if quick:
        print("Quick mode — skipping ML retrain. Model predictions/心得 unavailable.")
        return False, {}
    try:
        from ml.train import train_from_config
        print("Retraining Layer-3 model with all 16 diseases (≈ 15–25 min CPU)…")
        rep = train_from_config()
        return True, rep
    except Exception as e:
        print(f"  [warn] retrain failed: {e}")
        return False, {}


# ------------------ Step 3: model inference + insights ----------------------

def step_predict_and_insight(
    all_patients: list, ckpt: Path, quick: bool,
) -> tuple[dict, dict]:
    """Run model on every patient. Returns (per-patient insight dict, per-disease metrics)."""
    if quick or not ckpt.exists():
        print("Skipping per-patient model inference (quick mode or no checkpoint).")
        return {}, {}

    from ml.insights import generate_insight
    from ml.predict import load_checkpoint, predict_from_patient

    print(f"Loading checkpoint {ckpt} and running inference on {len(all_patients)} patients…")
    load_checkpoint(ckpt)

    insights = {}
    per_disease_metrics = {}
    t0 = time.time()
    for i, p in enumerate(all_patients, 1):
        try:
            pred = predict_from_patient(p, ckpt)
            ins = generate_insight(p, pred)
            insights[p.patient_id] = ins
            per_disease_metrics.setdefault(p.disease_id, []).append({
                "mae": ins.mae,
                "flare_recall": ins.flare_recall,
                "flare_precision": ins.flare_precision,
            })
        except Exception as e:
            pass  # patient too short etc.
        if i % 200 == 0:
            elapsed = time.time() - t0
            print(f"  {i}/{len(all_patients)} done ({elapsed:.0f}s)")
    print(f"  inference complete: {len(insights)}/{len(all_patients)} patients ({time.time()-t0:.0f}s)")
    return insights, per_disease_metrics


# ------------------ Step 4: serialize cohort.json ---------------------------

def step_serialize_cohort(cohort_json: dict, insights: dict, out_dir: Path) -> Path:
    """Convert Patient objects to JSON-friendly dicts and write cohort.json."""
    serial = {
        k: v for k, v in cohort_json.items() if k != "diseases"
    }
    serial["diseases"] = {}
    for did, info in cohort_json["diseases"].items():
        serial["diseases"][did] = {
            "name": info["name"],
            "dynamics_type": info["dynamics_type"],
            "patients": [_patient_to_dict(p, insights.get(p.patient_id))
                         for p in info["patients"]],
        }
    out = out_dir / "cohort.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(serial, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"  cohort.json written ({size_mb:.1f} MB)")
    return out


def _patient_to_dict(p, insight) -> dict:
    df = p.timeseries
    sp = p.social_profile
    d = {
        "patient_id": p.patient_id,
        "disease_id": p.disease_id,
        "age": p.age,
        "sex": p.sex,
        "age_bin": p.age_profile.age_bin if p.age_profile else "",
        "is_elderly": bool(p.age_profile.is_elderly) if p.age_profile else False,
        "subtype": p.subtype,
        "responder_class": p.responder_class,
        "placebo_shift": p.placebo_shift,
        "comorbidities": p.comorbidities,
        "treatments": [
            {"id": t["id"], "start_day": t.get("start_day"),
             "effect_magnitude": t["effect_magnitude"]}
            for t in p.treatments
        ],
        "life_events": [
            {"id": e.id, "onset_day": e.onset_day,
             "duration_days": e.duration_days, "activity_bump": e.activity_bump}
            for e in p.life_events
        ],
        "long_tail_event": p.long_tail_event,
        "flare_count": p.flare_count,
        "timeseries": df.to_dict(orient="records"),
    }
    # ⭐ social profile (9th unpredictability source)
    if sp is not None:
        d["social_profile"] = {
            "personality": {
                "conscientiousness": round(sp.personality.conscientiousness, 2),
                "neuroticism":       round(sp.personality.neuroticism, 2),
                "optimism":          round(sp.personality.optimism, 2),
                "self_efficacy":     round(sp.personality.self_efficacy, 2),
                "pain_catastrophizing": round(sp.personality.pain_catastrophizing, 2),
            },
            "behavioral": {
                "smoking_status": sp.behavioral.smoking_status,
                "pack_years":     round(sp.behavioral.pack_years, 1),
                "alcohol_units_per_week": round(sp.behavioral.alcohol_units_per_week, 1),
                "exercise_sessions_per_week": sp.behavioral.exercise_sessions_per_week,
                "sleep_hours_avg": round(sp.behavioral.sleep_hours_avg, 1),
                "sleep_quality":   sp.behavioral.sleep_quality,
                "diet_type":       sp.behavioral.diet_type,
            },
            "social": {
                "marital_status":   sp.social.marital_status,
                "children_count":   sp.social.children_count,
                "family_support":   sp.social.family_support,
                "social_isolation": round(sp.social.social_isolation, 2),
                "living_arrangement": sp.social.living_arrangement,
            },
            "socioeconomic": {
                "education":       sp.socioeconomic.education,
                "income_tier":     sp.socioeconomic.income_tier,
                "insurance_type":  sp.socioeconomic.insurance_type,
                "employment_status": sp.socioeconomic.employment_status,
                "urban_rural":     sp.socioeconomic.urban_rural,
            },
            "health_behavior": {
                "health_literacy": sp.health_behavior.health_literacy,
                "trust_in_medicine": round(sp.health_behavior.trust_in_medicine, 2),
                "uses_tcm":        sp.health_behavior.uses_tcm,
                "appointment_adherence": round(sp.health_behavior.appointment_adherence, 2),
            },
            "mental_health": {
                "phq9_score": sp.mental_health.phq9_score,
                "gad7_score": sp.mental_health.gad7_score,
                "perceived_stress": round(sp.mental_health.perceived_stress, 2),
            },
            "modifiers": {
                "adherence":  round(sp.adherence_multiplier, 2),
                "subjective": round(sp.subjective_amplification, 2),
                "placebo":    round(sp.placebo_amplification, 2),
            },
        }
    if insight is not None:
        d["model_predictions"] = insight.predictions
        d["model_mae"] = round(insight.mae, 4)
        d["model_flare_recall"] = (
            round(insight.flare_recall, 3) if insight.flare_recall is not None else None
        )
        d["model_flare_precision"] = (
            round(insight.flare_precision, 3) if insight.flare_precision is not None else None
        )
        d["ai_insight"] = insight.insight_zh
        d["ai_insight_lines"] = insight.insight_lines
    return d


# ------------------ Step 5: generate reports --------------------------------

def report_index(out_dir: Path, cohort_json: dict, has_model: bool) -> None:
    n_patients = sum(len(info["patients"]) for info in cohort_json["diseases"].values())
    md = f"""# MD. Piece — Full Demo Report

**Generated**: {cohort_json['generated_at']}
**Config**: {cohort_json['config']}
**Total patients**: {n_patients} across {len(cohort_json['diseases'])} diseases
**Model used**: {'✅ retrained Layer-3 (LSTM + attention)' if has_model else '❌ no model predictions (quick mode)'}

## 📑 報告目錄

1. [`01_cohort_overview.md`](01_cohort_overview.md) — 全 cohort KPI、疾病 / 年齡 / 反應者分布
2. [`02_per_disease/`](02_per_disease/) — 16 個疾病各自的詳細摘要
3. [`03_model_performance.md`](03_model_performance.md) — 模型整體 + per-disease 指標
4. [`04_ai_users_log.md`](04_ai_users_log.md) — 5 位 AI 角色的使用心得
5. [`05_patient_samples.md`](05_patient_samples.md) — 每疾病代表性患者 + AI 心得
6. [`06_sanity_tests.md`](06_sanity_tests.md) — 自動驗證測試結果

## 📂 附件
- `cohort.json` — 完整原始資料（含模型預測 + 心得）
- `figures/` — PNG 圖檔（per-disease 軌跡 / 直方圖）

## ⚠️ 倫理聲明
本報告完全為**合成資料**，僅用於科展研究、教學示範。不構成任何醫療建議。
"""
    (out_dir / "00_index.md").write_text(md, encoding="utf-8")


def report_cohort_overview(out_dir: Path, cohort_json: dict) -> None:
    ps = []
    for info in cohort_json["diseases"].values():
        ps.extend(info["patients"])
    n = len(ps)
    elderly = sum(1 for p in ps if p.age_profile and p.age_profile.is_elderly)
    by_d = Counter(p.disease_id for p in ps)
    by_resp = Counter(p.responder_class for p in ps)
    by_bin = Counter(p.age_profile.age_bin for p in ps if p.age_profile)
    by_sex = Counter(p.sex for p in ps)
    age_mean = mean(p.age for p in ps)
    long_tail_pct = sum(1 for p in ps if p.long_tail_event is not None) / n

    md = [
        "# 1. Cohort Overview\n",
        f"- 總共 **{n}** 位虛擬患者，跨 **{len(by_d)}** 種疾病",
        f"- 平均年齡 **{age_mean:.1f}** 歲，老年（≥70）佔 **{elderly}/{n}** ({_fmt_pct(elderly/n)})",
        f"- 性別：女 {by_sex.get('F',0)} / 男 {by_sex.get('M',0)}",
        f"- 罕見 long-tail 事件出現率：**{_fmt_pct(long_tail_pct)}**（合 ~3% 預期）",
        "\n## 疾病分布",
        "| 疾病 | n |",
        "|---|---|",
    ]
    for did, c in sorted(by_d.items(), key=lambda x: -x[1]):
        md.append(f"| {did} | {c} |")

    md.append("\n## 反應者分群")
    md.append("| Class | n | % |")
    md.append("|---|---|---|")
    for cls, c in by_resp.most_common():
        md.append(f"| {cls} | {c} | {_fmt_pct(c/n)} |")

    md.append("\n## 年齡分布")
    md.append("| Bin | n | % |")
    md.append("|---|---|---|")
    for b in ["20-35","35-55","55-70","70-90"]:
        c = by_bin.get(b, 0)
        md.append(f"| {b} | {c} | {_fmt_pct(c/n)} |")

    (out_dir / "01_cohort_overview.md").write_text("\n".join(md), encoding="utf-8")


def report_per_disease(out_dir: Path, cohort_json: dict, metrics: dict) -> None:
    pd_dir = out_dir / "02_per_disease"
    pd_dir.mkdir(parents=True, exist_ok=True)

    index_lines = ["# 2. 各疾病詳細報告\n", "| 疾病 | dynamics | n | flare 均值 | 老年 | 模型 MAE |", "|---|---|---|---|---|---|"]

    for did, info in cohort_json["diseases"].items():
        ps = info["patients"]
        n = len(ps)
        elderly = sum(1 for p in ps if p.age_profile and p.age_profile.is_elderly)
        flares_mean = mean(p.flare_count for p in ps)
        age_mean = mean(p.age for p in ps)
        by_sub = Counter(p.subtype for p in ps)
        by_resp = Counter(p.responder_class for p in ps)
        tx_counts = Counter(t["id"] for p in ps for t in p.treatments)

        m = metrics.get(did, [])
        mae_mean = mean(x["mae"] for x in m) if m else None
        mae_str = f"{mae_mean:.3f}" if mae_mean is not None else "—"

        index_lines.append(
            f"| [{did}]({did}.md) | {info['dynamics_type']} | {n} | "
            f"{flares_mean:.1f} | {elderly} | {mae_str} |"
        )

        md = [
            f"# {info['name']} (`{did}`)\n",
            f"- 動力學類型：`{info['dynamics_type']}`",
            f"- 患者數：**{n}**，平均年齡 {age_mean:.1f} 歲，老年 {elderly} 位",
            f"- 90 天 flare 平均：**{flares_mean:.2f}**",
        ]
        if mae_mean is not None:
            recalls = [x["flare_recall"] for x in m if x["flare_recall"] is not None]
            precs = [x["flare_precision"] for x in m if x["flare_precision"] is not None]
            md.append(f"- 模型 MAE 平均：**{mae_mean:.3f}**"
                      + (f"，flare 召回平均 {mean(recalls)*100:.0f}%" if recalls else "")
                      + (f"，準確率平均 {mean(precs)*100:.0f}%" if precs else ""))

        md.append("\n## 亞型分布")
        md.append("| Subtype | n |")
        md.append("|---|---|")
        for sub, c in by_sub.most_common():
            md.append(f"| {sub} | {c} |")

        md.append("\n## 反應者分布")
        md.append("| Class | n |")
        md.append("|---|---|")
        for r, c in by_resp.most_common():
            md.append(f"| {r} | {c} |")

        md.append("\n## 處方治療頻率")
        md.append("| Treatment | n |")
        md.append("|---|---|")
        for t, c in tx_counts.most_common():
            md.append(f"| {t} | {c} |")

        md.append(f"\n## 圖")
        md.append(f"- [活動度軌跡 (cohort)](../figures/{did}_cohort.png)")
        md.append(f"- [Flare 直方圖](../figures/{did}_flares.png)")
        md.append(f"- [單一患者範例](../figures/{did}_single.png)")

        (pd_dir / f"{did}.md").write_text("\n".join(md), encoding="utf-8")

    (out_dir / "02_per_disease.md").write_text("\n".join(index_lines), encoding="utf-8")
    (pd_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")


def report_model_performance(
    out_dir: Path, metrics: dict, train_report: dict, has_model: bool,
) -> None:
    if not has_model:
        (out_dir / "03_model_performance.md").write_text(
            "# 3. 模型表現\n\n（quick 模式 — 未跑模型推論）\n", encoding="utf-8"
        )
        return

    md = ["# 3. Layer-3 模型表現\n"]
    if train_report:
        reg = train_report.get("test_regression", {})
        cls = train_report.get("test_classification", {})
        md += [
            "## 整體 test 指標（80/10/10 patient-level split）",
            f"- 訓練資料：{train_report.get('n_train','—')} / val {train_report.get('n_val','—')} / test {train_report.get('n_test','—')} 個 sliding window",
            f"- 最佳 epoch：{train_report.get('best_epoch','—')}（val loss {train_report.get('best_val_loss','—'):.4f}）" if train_report.get('best_val_loss') else "",
            f"- 模型參數：{train_report.get('model_params','—')}",
            f"- 特徵數：{train_report.get('n_features','—')}",
            "",
            "### Activity 回歸",
            f"- MAE  = {reg.get('mae',{}).get('point','—'):.3f}  CI95={reg.get('mae',{}).get('ci95','—')}",
            f"- RMSE = {reg.get('rmse',{}).get('point','—'):.3f}",
            f"- R²   = {reg.get('r2',{}).get('point','—'):.3f}",
            f"- baseline (mean predictor) MAE = {reg.get('baseline_mean_predictor_mae','—'):.3f}",
            "",
            "### Flare 分類",
        ]
        if cls.get("auroc") is None:
            md.append("（單一類別，無 AUROC）")
        else:
            md += [
                f"- AUROC = {cls['auroc']['point']:.3f}  CI95={cls['auroc']['ci95']}",
                f"- AUPRC = {cls['auprc']['point']:.3f}",
                f"- F1@0.5 = {cls['f1@0.5']['point']:.3f}",
                f"- positive rate = {cls.get('positive_rate','—')}",
            ]

    md.append("\n## 各疾病平均 MAE / 召回 / 準確率")
    md.append("| 疾病 | n | MAE | flare 召回 | 準確 |")
    md.append("|---|---|---|---|---|")
    for did, lst in sorted(metrics.items()):
        if not lst:
            continue
        mae_m = mean(x["mae"] for x in lst)
        recalls = [x["flare_recall"] for x in lst if x["flare_recall"] is not None]
        precs = [x["flare_precision"] for x in lst if x["flare_precision"] is not None]
        rec_s = f"{mean(recalls)*100:.0f}%" if recalls else "—"
        prec_s = f"{mean(precs)*100:.0f}%" if precs else "—"
        md.append(f"| {did} | {len(lst)} | {mae_m:.3f} | {rec_s} | {prec_s} |")

    (out_dir / "03_model_performance.md").write_text("\n".join(md), encoding="utf-8")


def report_ai_users(out_dir: Path, cohort_json_path: Path) -> None:
    from ml.ai_users import PERSONAS, simulate_session
    cohort = json.loads(cohort_json_path.read_text())
    lines = ["# 4. AI 角色扮演使用 PWA — 5 位使用者心得\n"]
    for persona in PERSONAS:
        lines.extend(simulate_session(persona, cohort))
    (out_dir / "04_ai_users_log.md").write_text("\n".join(lines), encoding="utf-8")


def report_patient_samples(out_dir: Path, cohort_json: dict, insights: dict, k: int = 3) -> None:
    """Pick k representative patients per disease and dump their full AI insight."""
    md = ["# 5. 代表性患者樣本（每疾病 k=3）\n",
          "（依模型 MAE 由低到高排序，呈現模型對各疾病最有把握的案例）\n"]

    for did, info in cohort_json["diseases"].items():
        md.append(f"\n## {info['name']} (`{did}`)\n")
        scored = []
        for p in info["patients"]:
            ins = insights.get(p.patient_id)
            if ins is None:
                continue
            scored.append((ins.mae, p, ins))
        scored.sort(key=lambda x: x[0])
        picked = scored[:k]
        if not picked:
            md.append("- （無模型預測可用）")
            continue
        for mae, p, ins in picked:
            md.append(f"\n### {p.patient_id} — MAE {mae:.3f}")
            md.append(f"- {p.age} 歲 {p.sex}, subtype={p.subtype}, responder={p.responder_class}")
            md.append("```")
            md.append(ins.insight_zh)
            md.append("```")

    (out_dir / "05_patient_samples.md").write_text("\n".join(md), encoding="utf-8")


def report_sanity_tests(out_dir: Path) -> None:
    """Run pytest and capture results into a markdown report."""
    print("Running sanity tests …")
    cp = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_mdpiece", "-v", "--no-header", "--tb=line"],
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True, text=True,
    )
    md = [
        "# 6. Sanity Tests\n",
        f"- exit code: **{cp.returncode}** ({'PASS' if cp.returncode == 0 else 'FAIL'})",
        "",
        "## stdout",
        "```",
        cp.stdout[-4000:],
        "```",
    ]
    if cp.stderr.strip():
        md += ["## stderr", "```", cp.stderr[-2000:], "```"]
    (out_dir / "06_sanity_tests.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  tests exit code: {cp.returncode}")


# ------------------ orchestrator --------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200, help="patients per disease (150-500)")
    parser.add_argument("--days", type=int, default=90, help="simulation days")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="skip ML retrain + skip per-patient inference (just data + ai_users)")
    parser.add_argument("--skip-retrain", action="store_true",
                        help="skip ML retrain but still run inference on existing checkpoint")
    parser.add_argument("--out", type=Path, default=None,
                        help="output dir (default: output/full_run_TIMESTAMP)")
    parser.add_argument("--ckpt", type=Path,
                        default=Path("output/mdpiece/checkpoints/best.pt"))
    args = parser.parse_args()

    out_dir = args.out or REPO_ROOT / "output" / f"full_run_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"📂 output dir: {out_dir.relative_to(REPO_ROOT)}")

    _print_section("Step 1: generate cohorts (16 diseases)")
    cohort_json, all_patients = step_generate(args.n, args.days, args.seed, out_dir)

    _print_section("Step 2: retrain Layer-3 model")
    has_model = False
    train_report = {}
    if args.quick or args.skip_retrain:
        if args.quick:
            print("Quick mode — skipping retrain entirely")
        else:
            print(f"Skip-retrain — using existing checkpoint: {args.ckpt}")
            has_model = args.ckpt.exists()
    else:
        has_model, train_report = step_retrain(args.quick)

    _print_section("Step 3: per-patient inference + AI insights")
    insights, metrics = step_predict_and_insight(all_patients, args.ckpt, args.quick)
    has_model = has_model and bool(insights)

    _print_section("Step 4: serialize cohort.json")
    cohort_path = step_serialize_cohort(cohort_json, insights, out_dir)

    _print_section("Step 5: generate 6 reports")
    report_index(out_dir, cohort_json, has_model)
    report_cohort_overview(out_dir, cohort_json)
    report_per_disease(out_dir, cohort_json, metrics)
    report_model_performance(out_dir, metrics, train_report, has_model)
    report_ai_users(out_dir, cohort_path)
    report_patient_samples(out_dir, cohort_json, insights)
    report_sanity_tests(out_dir)

    print()
    print("✅ ALL DONE")
    print(f"   → 入口：{(out_dir / '00_index.md').resolve()}")


if __name__ == "__main__":
    main()

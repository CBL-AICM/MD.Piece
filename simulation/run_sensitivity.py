"""Phase 7 — sensitivity & bias analysis (arch §10).

Sweeps the highest-leverage parameters one-at-a-time and asks the headline question:
**which parameters flip the SIGN of the MD.Piece effect?** Those are exactly what a real
future study must measure. Also runs two bias scenarios: uniform-vs-clinical salience (A07)
and a full-adoption upper bound (isolates the dropout/non-adoption penalty, A02).

Every variant runs on the IDENTICAL patient population (same master seed); only the swept
parameter changes — a clean paired contrast. Uses a reduced n for speed (the sweep is about
relative sensitivity, not absolute precision).

    python -m simulation.run_sensitivity --n 900
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json

import numpy as np

from simulation.common import Config, EVENT_TYPES, load_config
from simulation.evaluation import arm_metrics
from simulation.run_study import generate, _doctor_and_friction

_PARTS = ["seeds", "population", "disease_registry", "persona_registry", "probability_registry"]


def variant(cfg: Config, overrides: dict) -> Config:
    """Clone the config and apply nested 'a.b.c' -> value overrides; recompute the hash."""
    parts = {k: copy.deepcopy(getattr(cfg, k)) for k in _PARTS}
    for path, val in overrides.items():
        keys = path.split(".")
        d = parts[keys[0]]
        for k in keys[1:-1]:
            d = d[k]
        d[keys[-1]] = val
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return Config(config_hash=hashlib.sha256(blob).hexdigest()[:12], **parts)


def run_point(cfg: Config, n: int) -> dict:
    patients, truth, recall, mdp, phys, doc_rngs, _ = generate(cfg, n, parity=False)
    rec_m = arm_metrics(patients, truth, recall, cfg)
    mdp_m = arm_metrics(patients, truth, mdp, cfg)
    rec = _doctor_and_friction(rec_m, phys, doc_rngs, cfg, "PATIENT_RECALL")
    mdp = _doctor_and_friction(mdp_m, phys, doc_rngs, cfg, "MDPIECE")
    crs = mdp["clinical_reconstruction_score"].values - rec["clinical_reconstruction_score"].values
    return {
        "d_crs": float(crs.mean()),
        "d_recall": float((mdp["event_recall_rate"] - rec["event_recall_rate"]).mean()),
        "d_if": float((mdp["information_friction_score"] - rec["information_friction_score"]).mean()),
        "d_und": float((mdp["doctor_understanding"] - rec["doctor_understanding"]).mean()),
        "pct_helped": float((crs > 0).mean()),
    }


# parameter -> (config path, grid, base value)
SWEEPS = {
    "retention_median_days": ("probability_registry.usage.retention.median_lifetime_days.value",
                              [30, 50, 75, 110, 150, 180], 75),
    "onboarding_base": ("probability_registry.usage.retention.onboarding_completion.value",
                        [0.40, 0.55, 0.70, 0.85, 0.99], 0.70),
    "recall_tau_days": ("probability_registry.friction.recall.tau_days.value",
                        [60, 90, 120, 180, 240], 120),
    "logged_quality_decay": ("probability_registry.friction.mdpiece.logged_quality_decay.value",
                             [0.0, 0.05, 0.10, 0.20], 0.05),
    "mis_entry_rate": ("probability_registry.friction.mdpiece.mis_entry_rate.value",
                       [0.0, 0.06, 0.15], 0.06),
    "notif_recovery": ("probability_registry.friction.mdpiece.notification_recovery.max_recovered_frac.value",
                       [0.0, 0.30, 0.50], 0.30),
}


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=900)
    args = ap.parse_args()
    n = args.n

    base = load_config()
    L = [f"# Phase 7 — Sensitivity & Bias Analysis\n",
         f"n={n}/variant · base seed {base.master_seed} · paired (same population per variant)\n",
         "Primary estimand = Δ Clinical Reconstruction Score (MD.Piece − Recall). "
         "**Sign flips** mark parameters that decide whether MD.Piece helps or harms.\n"]

    base_pt = run_point(base, n)
    L.append(f"**Baseline** (n={n}): ΔCRS={base_pt['d_crs']:+.3f} · Δrecall={base_pt['d_recall']:+.3f} · "
             f"ΔIF={base_pt['d_if']:+.3f} · Δunderstanding={base_pt['d_und']:+.3f} · "
             f"helped={base_pt['pct_helped']:.0%}\n")

    tornado = []  # (param, lo, hi, flips)
    for pname, (path, grid, baseval) in SWEEPS.items():
        L.append(f"## {pname}  (base={baseval})")
        L.append("| value | ΔCRS | Δrecall | ΔIF (↓) | helped |")
        L.append("|---|---|---|---|---|")
        crs_vals = []
        for v in grid:
            pt = run_point(variant(base, {path: v}), n)
            crs_vals.append(pt["d_crs"])
            flag = "  ← SIGN FLIP" if (pt["d_crs"] * base_pt["d_crs"] < 0) else ""
            L.append(f"| {v} | {pt['d_crs']:+.3f}{flag} | {pt['d_recall']:+.3f} | "
                     f"{pt['d_if']:+.3f} | {pt['pct_helped']:.0%} |")
        lo, hi = min(crs_vals), max(crs_vals)
        flips = lo < 0 < hi
        tornado.append((pname, lo, hi, flips))
        L.append("")

    # ---- bias scenarios ----
    L.append("## Bias scenarios")
    L.append("| scenario | ΔCRS | Δrecall | helped | reads |")
    L.append("|---|---|---|---|---|")
    uniform_sal = {et: 0.6 for et in EVENT_TYPES}
    uniform_sal["validation_required"] = True
    sc_uniform = run_point(variant(base, {"probability_registry.salience_by_event_type": uniform_sal}), n)
    L.append(f"| uniform salience (A07) | {sc_uniform['d_crs']:+.3f} | {sc_uniform['d_recall']:+.3f} | "
             f"{sc_uniform['pct_helped']:.0%} | removes salience weighting; large shift ⇒ result is weight-driven |")
    full_adopt = run_point(variant(base, {
        "probability_registry.usage.retention.onboarding_completion.value": 0.99,
        "probability_registry.usage.retention.onboarding_engagement_spread.value": 0.0,
        "probability_registry.usage.retention.median_lifetime_days.value": 100000,
    }), n)
    L.append(f"| full adoption, no dropout (A02) | {full_adopt['d_crs']:+.3f} | {full_adopt['d_recall']:+.3f} | "
             f"{full_adopt['pct_helped']:.0%} | MD.Piece UPPER BOUND; gap to baseline = the engagement penalty |")
    L.append("")

    # ---- tornado summary ----
    L.append("## Tornado — parameters ranked by influence on ΔCRS (range across sweep)")
    L.append("| parameter | ΔCRS low | ΔCRS high | range | flips sign? |")
    L.append("|---|---|---|---|---|")
    for pname, lo, hi, flips in sorted(tornado, key=lambda t: -(t[2] - t[1])):
        L.append(f"| {pname} | {lo:+.3f} | {hi:+.3f} | {hi-lo:.3f} | {'**YES**' if flips else 'no'} |")
    L.append("")
    L.append("## Takeaways")
    flip_params = [p for p, lo, hi, f in tornado if f]
    if flip_params:
        L.append(f"- The MD.Piece conclusion is **not robust**: its sign flips within the plausible range of "
                 f"**{', '.join(flip_params)}**. These must be measured in a real study before any claim.")
    else:
        L.append("- No single swept parameter flips the aggregate sign within its plausible range "
                 "(the direction is locally robust — but see the full-adoption gap and salience scenario).")
    L.append(f"- The full-adoption upper bound (ΔCRS={full_adopt['d_crs']:+.3f}) vs baseline "
             f"(ΔCRS={base_pt['d_crs']:+.3f}) shows how much of MD.Piece's potential is lost to "
             "non-adoption + dropout — the engagement penalty, and the main lever for real-world value.")

    report = "\n".join(L)
    print("\n" + report + "\n")
    out = base.__class__  # noqa
    from simulation.common import OUTPUT_DIR
    p = OUTPUT_DIR / base.config_hash / "sensitivity_report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report, encoding="utf-8")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()

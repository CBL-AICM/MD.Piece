"""Phase 7 (global) — variance-based Sobol sensitivity via the Saltelli estimator.

One-at-a-time sweeps (run_sensitivity.py) miss INTERACTIONS. This does a global, variance-based
decomposition over the 4 influential parameters using a Sobol/Saltelli design built on
scipy.stats.qmc.Sobol (no external dependency). Reports:

  * S1  (first-order)  — share of output variance explained by a parameter ALONE.
  * ST  (total-order)  — share including ALL its interactions. ST >> S1 ⇒ the parameter acts
                         mostly THROUGH interactions with others.

Model output = ΔCRS (MD.Piece − Recall). Total model evaluations = N·(D+2).

    python -m simulation.run_sobol --N 64 --n 250
"""
from __future__ import annotations

import argparse

import numpy as np
from scipy.stats import qmc

from simulation.common import OUTPUT_DIR, load_config
from simulation.run_sensitivity import variant, run_point

# name, config path, low, high
PARAMS = [
    ("notif_recovery", "probability_registry.friction.mdpiece.notification_recovery.max_recovered_frac.value", 0.0, 0.5),
    ("recall_tau_days", "probability_registry.friction.recall.tau_days.value", 60.0, 240.0),
    ("onboarding_base", "probability_registry.usage.retention.onboarding_completion.value", 0.40, 0.99),
    ("retention_median_days", "probability_registry.usage.retention.median_lifetime_days.value", 30.0, 180.0),
]


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=64, help="base samples (power of 2)")
    ap.add_argument("--n", type=int, default=250, help="patients per model run")
    args = ap.parse_args()
    N, n = args.N, args.n
    D = len(PARAMS)
    base = load_config()

    sampler = qmc.Sobol(d=2 * D, scramble=True, seed=base.master_seed)
    pts = sampler.random(N)            # N x 2D in [0,1]
    A, B = pts[:, :D], pts[:, D:]

    def overrides(row):
        return {path: float(lo + row[j] * (hi - lo)) for j, (_, path, lo, hi) in enumerate(PARAMS)}

    total_runs = N * (D + 2)
    done = 0

    def model(row):
        nonlocal done
        y = run_point(variant(base, overrides(row)), n)["d_crs"]
        done += 1
        if done % 25 == 0 or done == total_runs:
            print(f"  ... {done}/{total_runs} model runs", flush=True)
        return y

    print(f"[sobol] N={N} n={n} D={D} -> {total_runs} model runs", flush=True)
    yA = np.array([model(A[i]) for i in range(N)])
    yB = np.array([model(B[i]) for i in range(N)])
    yAB = np.zeros((D, N))
    for j in range(D):
        ABj = A.copy()
        ABj[:, j] = B[:, j]
        yAB[j] = np.array([model(ABj[i]) for i in range(N)])

    var_y = np.var(np.concatenate([yA, yB]), ddof=1)
    rows = []
    for j, (name, *_rest) in enumerate(PARAMS):
        s1 = float(np.mean(yB * (yAB[j] - yA)) / var_y)          # Saltelli/Jansen first-order
        st = float(0.5 * np.mean((yA - yAB[j]) ** 2) / var_y)    # Jansen total-order
        rows.append((name, s1, st))

    L = ["# Phase 7 (global) — Sobol variance-based sensitivity\n",
         f"output = ΔCRS (MD.Piece − Recall) · N={N} · n={n}/run · {total_runs} model runs · "
         f"Var(ΔCRS)={var_y:.5f}\n",
         "S1 = first-order (alone); ST = total (incl. interactions). ST≫S1 ⇒ acts via interactions.\n",
         "| parameter | S1 | ST | ST−S1 (interaction) |", "|---|---|---|---|"]
    for name, s1, st in sorted(rows, key=lambda r: -r[2]):
        L.append(f"| {name} | {s1:+.3f} | {st:.3f} | {max(0.0, st-s1):.3f} |")
    sum_s1 = sum(max(0.0, r[1]) for r in rows)
    L.append("")
    L.append(f"- Σ S1 ≈ {sum_s1:.2f} ⇒ ~{sum_s1:.0%} of ΔCRS variance is first-order (additive); "
             f"the remainder (~{max(0.0,1-sum_s1):.0%}) is interactions + sampling noise.")
    top = max(rows, key=lambda r: r[2])
    L.append(f"- Highest total-order influence: **{top[0]}** (ST={top[2]:.3f}) — the parameter a real "
             "study should pin down first; its effect compounds with the others.")
    L.append("- Cross-check vs the one-at-a-time tornado (sensitivity_report.md): agreement on the top "
             "driver corroborates the finding; a parameter with ST≫S1 there would have looked weak in OAT.")

    report = "\n".join(L)
    print("\n" + report + "\n")
    p = OUTPUT_DIR / base.config_hash / "sobol_report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report, encoding="utf-8")
    print(f"wrote {p}", flush=True)


if __name__ == "__main__":
    main()

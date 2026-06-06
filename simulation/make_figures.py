"""Render research figures from a completed study run (arch §8 outputs).

    python -m simulation.make_figures            # uses the literature-anchored run
    python -m simulation.make_figures --hash <config_hash>

Writes PNGs to simulation/docs/figures/. Sensitivity/Sobol panels use the committed
Phase-7 results (docs/06,07); all other panels are computed live from the run's CSVs.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
FIGDIR = HERE / "docs" / "figures"
C_RECALL, C_MDP, C_POS, C_NEG = "#7b6cd6", "#2a9d8f", "#2a9d8f", "#e76f51"

# Phase-7 results (from docs/06_sensitivity.md, docs/07_sobol.md)
TORNADO = [  # param, low, high
    ("notification recovery", -0.020, 0.155),
    ("recall memory (tau)", 0.038, 0.164),
    ("onboarding completion", 0.064, 0.144),
    ("retention median", 0.088, 0.133),
    ("mis-entry rate", 0.109, 0.110),
    ("logged-quality decay", 0.109, 0.109),
]
SOBOL = [  # param, S1, ST
    ("notification recovery", 0.378, 0.397),
    ("recall memory (tau)", 0.325, 0.281),
    ("onboarding completion", 0.253, 0.236),
    ("retention median", 0.059, 0.034),
]
LIT_FLARE = {"NMOSD": 0.50, "MS": 0.30, "SLE": 0.45, "RA": 0.40, "CROHN": 0.45, "MG": 0.35}


def load(hash_dir: Path):
    ev = pd.read_csv(hash_dir / "evaluation_metrics.csv")
    pts = pd.read_csv(hash_dir / "patients.csv")
    ret = pd.read_csv(hash_dir / "retention.csv")
    wide = ev.pivot_table(index="patient_id", columns="arm",
                          values=["clinical_reconstruction_score", "event_recall_rate",
                                  "information_friction_score", "doctor_understanding"])
    wide.columns = [f"{a}_{m}" for m, a in wide.columns]
    wide = wide.merge(pts[["patient_id", "persona", "disease"]], on="patient_id")
    wide["d_crs"] = (wide["MDPIECE_clinical_reconstruction_score"]
                     - wide["PATIENT_RECALL_clinical_reconstruction_score"])
    return ev, pts, ret, wide


def dashboard(ev, pts, ret, wide, hash_str):
    fig, ax = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"MD.Piece Digital-Twin Simulation — 3,200 patients × 12 months  "
                 f"(literature-anchored, config {hash_str})", fontsize=15, fontweight="bold")

    # A — primary estimand
    a = ax[0, 0]
    mets = [("clinical_reconstruction_score", "Clinical\nReconstruction"),
            ("event_recall_rate", "Event\nRecall"),
            ("information_friction_score", "Info Friction\n(lower=better)"),
            ("doctor_understanding", "Doctor\nUnderstanding")]
    x = np.arange(len(mets))
    rec = [ev[ev.arm == "PATIENT_RECALL"][m].mean() for m, _ in mets]
    mdp = [ev[ev.arm == "MDPIECE"][m].mean() for m, _ in mets]
    a.bar(x - 0.2, rec, 0.38, label="Patient Recall", color=C_RECALL)
    a.bar(x + 0.2, mdp, 0.38, label="MD.Piece", color=C_MDP)
    for xi, (r, m) in enumerate(zip(rec, mdp)):
        a.text(xi - 0.2, r + 0.01, f"{r:.2f}", ha="center", fontsize=8)
        a.text(xi + 0.2, m + 0.01, f"{m:.2f}", ha="center", fontsize=8)
    a.set_xticks(x); a.set_xticklabels([n for _, n in mets], fontsize=8)
    a.set_ylabel("score [0–1]"); a.set_title("A. Primary estimand (paired)"); a.legend(fontsize=8)
    a.set_ylim(0, 0.75)

    # B — crossover by persona
    b = ax[0, 1]
    wide["d_crs"] = wide["MDPIECE_clinical_reconstruction_score"] - wide["PATIENT_RECALL_clinical_reconstruction_score"]
    g = wide.groupby("persona")["d_crs"].mean().sort_values()
    cols = [C_POS if v > 0 else C_NEG for v in g.values]
    b.barh(range(len(g)), g.values, color=cols)
    b.set_yticks(range(len(g))); b.set_yticklabels(g.index, fontsize=8)
    b.axvline(0, color="k", lw=0.8)
    b.set_xlabel("Δ Clinical Reconstruction Score (MD.Piece − Recall)")
    b.set_title("B. The crossover by persona (H2)")
    for i, v in enumerate(g.values):
        b.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:+.2f}", va="center",
               ha="left" if v >= 0 else "right", fontsize=7)

    # C — per-patient ΔCRS distribution
    c = ax[0, 2]
    helped = (wide["d_crs"] > 0).mean()
    c.hist(wide["d_crs"], bins=45, color="#888", edgecolor="white")
    c.axvline(0, color="k", lw=1)
    c.axvline(wide["d_crs"].mean(), color=C_MDP, lw=2, ls="--",
              label=f"mean {wide['d_crs'].mean():+.3f}")
    c.set_xlabel("Δ Clinical Reconstruction Score (per patient)")
    c.set_ylabel("patients"); c.set_title(f"C. Distribution — {helped:.0%} of patients helped")
    c.legend(fontsize=8)

    # D — retention curve
    d = ax[1, 0]
    labels = ["D1", "W1", "M1", "M3", "M6", "M12"]
    cols_ret = [k.lower() for k in labels]
    onb = ret["onboarded"]
    vals = [(ret[cl] & onb).mean() for cl in cols_ret]
    d.plot(range(len(labels)), vals, "-o", color=C_MDP, lw=2)
    for i, v in enumerate(vals):
        d.text(i, v + 0.02, f"{v:.0%}", ha="center", fontsize=8)
    d.set_xticks(range(len(labels))); d.set_xticklabels(labels)
    d.set_ylim(0, 0.8); d.set_ylabel("fraction active")
    d.set_title(f"D. App retention (onboarded {onb.mean():.0%}) — deliberately pessimistic")

    # E — sensitivity tornado
    e = ax[1, 1]
    names = [t[0] for t in TORNADO][::-1]
    los = np.array([t[1] for t in TORNADO][::-1]); his = np.array([t[2] for t in TORNADO][::-1])
    e.barh(range(len(names)), his - los, left=los, color="#bbb", edgecolor="#555")
    e.axvline(0, color=C_NEG, lw=1.2, ls="--")
    e.set_yticks(range(len(names))); e.set_yticklabels(names, fontsize=8)
    e.set_xlabel("Δ CRS across parameter's plausible range")
    e.set_title("E. Sensitivity tornado (← red line = sign flip)")

    # F — Sobol indices
    f = ax[1, 2]
    sn = [s[0] for s in SOBOL]; s1 = [s[1] for s in SOBOL]; st = [s[2] for s in SOBOL]
    y = np.arange(len(sn))
    f.barh(y + 0.18, s1, 0.34, label="S1 (first-order)", color=C_RECALL)
    f.barh(y - 0.18, st, 0.34, label="ST (total)", color=C_MDP)
    f.set_yticks(y); f.set_yticklabels(sn, fontsize=8)
    f.set_xlabel("Sobol variance share of Δ CRS")
    f.set_title("F. Global Sobol — what drives the result"); f.legend(fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = FIGDIR / "research_dashboard.png"
    fig.savefig(out, dpi=130); plt.close(fig)
    return out


def flare_calibration(hash_dir: Path, pts):
    gt = pd.read_csv(hash_dir / "ground_truth_events.csv", usecols=["patient_id", "event_type"])
    fl = gt[gt.event_type == "FLARE"].groupby("patient_id").size()
    df = pts[["patient_id", "disease"]].assign(f=pts["patient_id"].map(fl).fillna(0))
    sim = df.groupby("disease")["f"].mean()  # per patient-year (horizon = 1y)
    diseases = [d for d in LIT_FLARE]
    fig, a = plt.subplots(figsize=(9, 5))
    x = np.arange(len(diseases))
    a.bar(x - 0.2, [LIT_FLARE[d] for d in diseases], 0.38, label="Literature (PubMed)", color=C_RECALL)
    a.bar(x + 0.2, [sim.get(d, 0) for d in diseases], 0.38, label="Simulated (ground truth)", color=C_MDP)
    a.set_xticks(x); a.set_xticklabels(diseases)
    a.set_ylabel("flares / patient-year"); a.legend()
    a.set_title("Disease flare rates: PubMed literature vs simulated (auto-calibration check)")
    for xi, d in enumerate(diseases):
        a.text(xi - 0.2, LIT_FLARE[d] + 0.01, f"{LIT_FLARE[d]:.2f}", ha="center", fontsize=8)
        a.text(xi + 0.2, sim.get(d, 0) + 0.01, f"{sim.get(d, 0):.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    out = FIGDIR / "disease_flare_calibration.png"
    fig.savefig(out, dpi=130); plt.close(fig)
    return out


def population_outcome(wide, hash_str):
    """Every one of the 3,200 patients: the MD.Piece outcome after processing their data."""
    personas = ["PERFECT_LOGGER", "CAREGIVER_MANAGED", "ANXIOUS", "SYMPTOM_DRIVEN",
                "NORMAL", "ELDERLY_LOW_LITERACY", "LOW_ENGAGEMENT", "TECH_AVOIDANT"]
    cmap = {p: c for p, c in zip(personas, plt.cm.tab10(np.linspace(0, 1, 10)))}

    fig = plt.figure(figsize=(17, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.28, wspace=0.22)
    n = len(wide)
    fig.suptitle(f"MD.Piece outcome for ALL {n:,} patients — record fidelity vs unaided recall "
                 f"(config {hash_str})", fontsize=15, fontweight="bold")

    # A — waterfall: every patient ranked by how much MD.Piece helped/hurt
    axA = fig.add_subplot(gs[0, :])
    d = wide.sort_values("d_crs").reset_index(drop=True)
    x = np.arange(n)
    delta = d["d_crs"].values
    axA.fill_between(x, 0, delta, where=delta >= 0, color=C_POS, interpolate=True, label="MD.Piece improved the record")
    axA.fill_between(x, 0, delta, where=delta < 0, color=C_NEG, interpolate=True, label="MD.Piece degraded the record")
    n_harm = int((delta < 0).sum()); n_help = n - n_harm
    axA.axhline(0, color="k", lw=0.8)
    axA.axvline(n_harm, color="k", ls="--", lw=1)
    axA.set_xlim(0, n); axA.set_xlabel("patients ranked by outcome (each vertical slice = 1 patient)")
    axA.set_ylabel("Δ Clinical Reconstruction Score\n(MD.Piece − recall)")
    axA.set_title(f"A. Per-patient outcome waterfall — {n_help:,} helped ({n_help/n:.0%}),  "
                  f"{n_harm:,} harmed ({n_harm/n:.0%}),  mean {delta.mean():+.3f}")
    axA.legend(loc="upper left", fontsize=9)
    axA.text(n_harm + 60, delta.max() * 0.7, f"← crossover at patient {n_harm:,}", fontsize=9)

    # B — before vs after scatter: every patient, recall fidelity (x) vs MD.Piece fidelity (y)
    axB = fig.add_subplot(gs[1, 0])
    for p in personas:
        s = wide[wide.persona == p]
        axB.scatter(s["PATIENT_RECALL_clinical_reconstruction_score"],
                    s["MDPIECE_clinical_reconstruction_score"],
                    s=9, alpha=0.45, color=cmap[p], label=p, linewidths=0)
    axB.plot([0, 1], [0, 1], "k--", lw=1.2)
    axB.text(0.62, 0.9, "above line:\nMD.Piece better", fontsize=8, color=C_POS)
    axB.text(0.7, 0.42, "below line:\nrecall better", fontsize=8, color=C_NEG)
    axB.set_xlim(0, 1); axB.set_ylim(0, 1)
    axB.set_xlabel("Patient-recall reconstruction score"); axB.set_ylabel("MD.Piece reconstruction score")
    axB.set_title("B. Before → after, every patient (colour = persona)")
    axB.legend(fontsize=6.5, markerscale=1.6, loc="lower right", ncol=2)

    # C — absolute outcome distributions for the whole population
    axC = fig.add_subplot(gs[1, 1])
    axC.hist(wide["PATIENT_RECALL_clinical_reconstruction_score"], bins=40, alpha=0.55,
             color=C_RECALL, label=f"Patient recall (mean {wide['PATIENT_RECALL_clinical_reconstruction_score'].mean():.2f})")
    axC.hist(wide["MDPIECE_clinical_reconstruction_score"], bins=40, alpha=0.55,
             color=C_MDP, label=f"MD.Piece (mean {wide['MDPIECE_clinical_reconstruction_score'].mean():.2f})")
    axC.set_xlabel("Clinical Reconstruction Score [0–1]"); axC.set_ylabel("patients")
    axC.set_title("C. Outcome distribution across all 3,200"); axC.legend(fontsize=8)

    out = FIGDIR / "population_outcome.png"
    fig.savefig(out, dpi=130); plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", default="713d8a608280")
    args = ap.parse_args()
    FIGDIR.mkdir(parents=True, exist_ok=True)
    hd = HERE / "outputs" / args.hash
    ev, pts, ret, wide = load(hd)
    f1 = dashboard(ev, pts, ret, wide, args.hash)
    f2 = flare_calibration(hd, pts)
    f3 = population_outcome(wide, args.hash)
    print(f"wrote {f1}\nwrote {f2}\nwrote {f3}")


if __name__ == "__main__":
    main()

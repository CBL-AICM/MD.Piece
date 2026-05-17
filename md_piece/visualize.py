"""Visualization helpers — matplotlib only, no data mutation."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for headless runs

import matplotlib.pyplot as plt
import numpy as np

from md_piece.cohort_generator import Cohort
from md_piece.patient import Patient


def plot_single_patient(patient: Patient, out_path: Path, title: str | None = None) -> None:
    """Two-panel chart: activity + key biomarker over time."""
    df = patient.timeseries
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    axes[0].plot(df["day"], df["activity"], lw=1.2, color="steelblue")
    axes[0].axhline(df["activity"].mean(), ls="--", color="gray", alpha=0.5,
                    label=f"mean={df['activity'].mean():.2f}")
    flare_days = df.loc[df["in_flare"] == 1, "day"]
    if len(flare_days) > 0:
        axes[0].scatter(flare_days, df.loc[df["in_flare"] == 1, "activity"],
                        color="red", s=12, alpha=0.6, label="flare")
    axes[0].set_ylabel("immune activity")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].set_title(title or f"{patient.patient_id} ({patient.disease_id})")

    # pick first biomarker for second panel
    bm_cols = [c for c in df.columns if c not in (
        "patient_id", "day", "activity", "irreversible_burden",
        "n_active_triggers", "in_flare"
    )]
    if bm_cols:
        bm = bm_cols[0]
        axes[1].plot(df["day"], df[bm], lw=1.2, color="darkorange", label=bm)
        if "irreversible_burden" in df.columns and df["irreversible_burden"].max() > 0:
            ax2 = axes[1].twinx()
            ax2.plot(df["day"], df["irreversible_burden"], lw=1.0,
                     color="firebrick", alpha=0.7, label="irrev. burden")
            ax2.set_ylabel("irreversible burden", color="firebrick")
        axes[1].set_ylabel(bm)
        axes[1].legend(loc="upper left", fontsize=8)
    axes[1].set_xlabel("day")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_cohort_overlay(cohort: Cohort, out_path: Path, n_show: int = 30) -> None:
    """Overlay activity trajectories of up to n_show patients + cohort mean."""
    fig, ax = plt.subplots(figsize=(10, 5))
    sample = cohort.patients[:n_show]
    for p in sample:
        ax.plot(p.timeseries["day"], p.timeseries["activity"],
                lw=0.6, color="steelblue", alpha=0.25)

    df_all = cohort.to_dataframe()
    mean_by_day = df_all.groupby("day")["activity"].mean()
    p25 = df_all.groupby("day")["activity"].quantile(0.25)
    p75 = df_all.groupby("day")["activity"].quantile(0.75)
    ax.plot(mean_by_day.index, mean_by_day.values, lw=2.0,
            color="navy", label=f"cohort mean (n={len(cohort.patients)})")
    ax.fill_between(mean_by_day.index, p25.values, p75.values,
                    color="navy", alpha=0.15, label="IQR")

    ax.set_title(f"Cohort activity trajectories — {cohort.disease_id}")
    ax.set_xlabel("day")
    ax.set_ylabel("immune activity")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_flare_distribution(cohort: Cohort, out_path: Path) -> None:
    """Histogram of per-patient flare counts."""
    counts = [p.flare_count for p in cohort.patients]
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.arange(0, max(counts) + 2) - 0.5
    ax.hist(counts, bins=bins, color="indianred", edgecolor="white")
    ax.set_xlabel("flare count per patient")
    ax.set_ylabel("# patients")
    ax.set_title(f"Flare distribution — {cohort.disease_id} "
                 f"(mean={np.mean(counts):.1f})")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

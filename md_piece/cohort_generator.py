"""Batch generation of virtual patient cohorts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pandas as pd

from md_piece.disease_loader import DiseaseConfig
from md_piece.patient import Patient, simulate_patient


@dataclass
class Cohort:
    """Container for a batch of simulated patients of one disease."""

    disease_id: str
    patients: list[Patient] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Long-format DataFrame: one row per (patient, day)."""
        if not self.patients:
            return pd.DataFrame()
        return pd.concat([p.timeseries for p in self.patients], ignore_index=True)

    def metadata_dataframe(self) -> pd.DataFrame:
        """Per-patient metadata (age, sex, treatments, flares, v2 fields)."""
        return pd.DataFrame([
            {
                "patient_id": p.patient_id,
                "disease_id": p.disease_id,
                "age": p.age,
                "sex": p.sex,
                "age_bin": p.age_profile.age_bin if p.age_profile else "",
                "is_elderly": bool(p.age_profile.is_elderly) if p.age_profile else False,
                "subtype": p.subtype,
                "responder_class": p.responder_class,
                "placebo_shift": p.placebo_shift,
                "comorbidities": ",".join(p.comorbidities) if p.comorbidities else "",
                "treatments": ",".join(t["id"] for t in p.treatments),
                "n_life_events": len(p.life_events),
                "long_tail_event": p.long_tail_event is not None,
                "flare_count": p.flare_count,
                "seed": p.seed,
            }
            for p in self.patients
        ])


def generate_cohort(
    disease_cfg: DiseaseConfig,
    n_patients: int,
    sim_days: int,
    *,
    base_seed: int = 0,
    n_workers: int = 1,
) -> Cohort:
    """Generate a cohort of virtual patients.

    Parameters
    ----------
    disease_cfg : DiseaseConfig
    n_patients : int
        Cohort size. Recommended 50-150 for downstream ML.
    sim_days : int
        Simulation horizon (days).
    base_seed : int
        Patient i uses seed = base_seed * 100000 + i for reproducibility.
    n_workers : int
        Parallel threads. 1 = sequential (safest for tests).

    Returns
    -------
    Cohort
    """

    def _one(i: int) -> Patient:
        pid = f"{disease_cfg.short}_{i:04d}"
        seed = base_seed * 100_000 + i
        return simulate_patient(pid, disease_cfg, sim_days, seed)

    if n_workers > 1:
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            patients = list(ex.map(_one, range(n_patients)))
    else:
        patients = [_one(i) for i in range(n_patients)]

    return Cohort(disease_id=disease_cfg.id, patients=patients)

"""Shared foundation: config loading, deterministic RNG tree, core types, enums.

Determinism contract (docs/01_architecture.md §3.3):
  * One master seed in config/seeds.yaml.
  * Per-patient RNG spawned via SeedSequence(master_seed).spawn(n_patients) so patient i's
    stream is independent of n_patients and of execution/worker order (parallel-safe).
  * No wall-clock, no global np.random.seed. All randomness threads through these generators.
  * No research constant is hard-coded here — everything comes from config/*.yaml.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR = Path(__file__).parent / "outputs"

# ---------------------------------------------------------------- enums (closed)
DISEASES = ("NMOSD", "MS", "SLE", "RA", "CROHN", "MG", "OTHER")
ARMS = ("GROUND_TRUTH", "PATIENT_RECALL", "MDPIECE")
PERSONAS = (
    "PERFECT_LOGGER", "NORMAL", "SYMPTOM_DRIVEN", "ANXIOUS",
    "LOW_ENGAGEMENT", "TECH_AVOIDANT", "CAREGIVER_MANAGED", "ELDERLY_LOW_LITERACY",
)
SEXES = ("F", "M")
INSURANCE = ("NHI", "NHI_PLUS_PRIVATE", "UNINSURED")


# ---------------------------------------------------------------- config
@dataclass
class Config:
    """All YAML configs + a content hash binding outputs to parameters (arch §3.3)."""
    seeds: dict
    population: dict
    disease_registry: dict
    persona_registry: dict
    probability_registry: dict
    config_hash: str

    @property
    def master_seed(self) -> int:
        return int(self.seeds["run"]["master_seed"])

    @property
    def n_patients(self) -> int:
        return int(self.seeds["run"]["n_patients"])

    @property
    def horizon_days(self) -> int:
        return int(self.seeds["run"]["horizon_days"])

    @property
    def substreams(self) -> list[str]:
        return list(self.seeds["rng"]["substreams"])


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> Config:
    parts = {
        "seeds": _load_yaml("seeds.yaml"),
        "population": _load_yaml("population.yaml"),
        "disease_registry": _load_yaml("disease_registry.yaml"),
        "persona_registry": _load_yaml("persona_registry.yaml"),
        "probability_registry": _load_yaml("probability_registry.yaml"),
    }
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    config_hash = hashlib.sha256(blob).hexdigest()[:12]
    _validate_config(parts)
    return Config(config_hash=config_hash, **parts)


def _validate_config(parts: dict) -> None:
    """Fail loud on config inconsistency (Rule 12) before anything is generated."""
    mix = parts["population"]["disease_mix"]
    if abs(sum(mix.values()) - 1.0) > 1e-6:
        raise ValueError(f"disease_mix must sum to 1.0, got {sum(mix.values())}")
    if set(mix) != set(DISEASES):
        raise ValueError(f"disease_mix keys {set(mix)} != DISEASES {set(DISEASES)}")
    base = parts["persona_registry"]["assignment"]["base_rates"]
    if abs(sum(base.values()) - 1.0) > 1e-6:
        raise ValueError(f"persona base_rates must sum to 1.0, got {sum(base.values())}")
    if set(base) != set(PERSONAS):
        raise ValueError(f"persona base_rates keys != PERSONAS")
    for d in DISEASES:
        sd = parts["disease_registry"][d]["severity_dist"]
        if abs(sum(sd) - 1.0) > 1e-6:
            raise ValueError(f"{d}.severity_dist must sum to 1.0, got {sum(sd)}")


# ---------------------------------------------------------------- RNG tree
def patient_seed_sequences(master_seed: int, n_patients: int) -> list[np.random.SeedSequence]:
    """n independent SeedSequences, one per patient, deterministic & order-independent."""
    return np.random.SeedSequence(master_seed).spawn(n_patients)


def patient_rngs(patient_ss: np.random.SeedSequence, substreams: list[str]) -> dict[str, np.random.Generator]:
    """Named, independent generators for one patient.

    Spawned ONCE from the patient's SeedSequence so each engine's randomness is isolated:
    changing the recall engine cannot perturb a patient's disease draws.
    """
    children = patient_ss.spawn(len(substreams))
    return {name: np.random.default_rng(child) for name, child in zip(substreams, children)}


# ---------------------------------------------------------------- core types
@dataclass
class PatientRow:
    patient_id: str
    age: int
    sex: str
    disease: str
    severity: int
    disease_duration_yrs: float
    comorbidity_count: int
    ses_quintile: int
    education_level: int
    health_literacy: float
    tech_literacy: float
    caregiver_support: float
    clinic_access: int
    insurance: str
    baseline_adherence: float
    latent_advantage_z: float
    persona: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EVENT_TYPES = (
    "SYMPTOM", "MEDICATION_CHANGE", "INFECTION", "APPOINTMENT", "LAB", "IMAGING",
    "HOSPITALIZATION", "EMERGENCY_VISIT", "PROCEDURE", "TREATMENT", "INFUSION",
    "REFILL", "FLARE", "REMISSION",
)
SOURCES = ("scheduled", "hazard", "infection", "flare", "treatment_response", "refill", "relapse")


@dataclass
class Event:
    """One clinical event. Shared by all three arms (arch §6.2).

    In GROUND_TRUTH: *_recorded == *_true, true_event_id == event_id, no error/omission.
    Lossy arms set true_event_id to link back (TP), leave it None for fabricated rows (FP);
    omissions are represented by ABSENCE of the row in that arm (the natural false-negative).
    """
    event_id: str
    patient_id: str
    arm: str
    event_type: str
    event_date_true: int
    source: str
    salience: float
    true_event_id: str | None = None
    event_date_recorded: int | None = None
    severity_true: int | None = None
    severity_recorded: int | None = None
    medication: str | None = None
    dose: str | None = None
    frequency: str | None = None
    is_omitted: bool = False
    is_false: bool = False
    temporal_error_days: int = 0
    logged_lag_days: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def salience_of(event_type: str, cfg: "Config") -> float:
    """Clinical-relevance weight for an event type (probability_registry salience table)."""
    return float(cfg.probability_registry["salience_by_event_type"][event_type])


def pval(node: Any) -> Any:
    """Unwrap a {value:..., range:...} registry node, or pass a scalar through."""
    return node["value"] if isinstance(node, dict) and "value" in node else node

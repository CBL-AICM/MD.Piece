"""YAML disease knowledge base loader with schema validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DISEASES_DIR = Path(__file__).resolve().parent.parent / "diseases"

VALID_DYNAMICS_TYPES = {"chronic_relapsing", "reversible", "progressive"}


@dataclass
class DiseaseConfig:
    """In-memory representation of a disease YAML file."""

    id: str
    name: str
    short: str
    icd10: str
    dynamics_type: str
    time_unit: str
    baseline: dict[str, Any]
    decay: dict[str, float]
    circadian: dict[str, float]
    noise: dict[str, float]
    triggers: list[dict[str, Any]]
    flare: dict[str, float]
    treatments: list[dict[str, Any]]
    biomarkers: dict[str, dict[str, Any]]
    comorbidity: list[dict[str, Any]] = field(default_factory=list)
    demographics: dict[str, Any] = field(default_factory=dict)
    accumulation: dict[str, float] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _validate(cfg: dict[str, Any]) -> None:
    """Minimal schema check — fails fast with a clear message."""
    required_top = ["disease", "baseline", "decay", "circadian", "noise",
                    "triggers", "flare", "treatments", "biomarkers"]
    for key in required_top:
        if key not in cfg:
            raise ValueError(f"YAML missing required top-level key: '{key}'")

    dyn = cfg["disease"].get("dynamics_type")
    if dyn not in VALID_DYNAMICS_TYPES:
        raise ValueError(
            f"Invalid dynamics_type '{dyn}'. Must be one of {VALID_DYNAMICS_TYPES}"
        )
    if dyn == "progressive" and "accumulation" not in cfg:
        raise ValueError("progressive dynamics requires 'accumulation' block")

    # v2 soft validations — warn-style checks for the eight unpredictability blocks.
    # Missing blocks are OK (legacy YAMLs continue to work) but malformed blocks fail.
    if "age_distribution" in cfg:
        total = sum(cfg["age_distribution"].values())
        if not 0.95 <= total <= 1.05:
            raise ValueError(
                f"age_distribution probabilities sum to {total:.3f} (must ≈ 1.0)"
            )
    if "responder_classes" in cfg:
        total = sum(c["probability"] for c in cfg["responder_classes"].values())
        if not 0.95 <= total <= 1.05:
            raise ValueError(
                f"responder_classes probabilities sum to {total:.3f} (must ≈ 1.0)"
            )
    if "subtypes" in cfg:
        total = sum(s["probability"] for s in cfg["subtypes"].values())
        if not 0.95 <= total <= 1.05:
            raise ValueError(
                f"subtypes probabilities sum to {total:.3f} (must ≈ 1.0)"
            )


def load_disease(disease_id: str, diseases_dir: Path | None = None) -> DiseaseConfig:
    """Load and validate a disease YAML by id (filename without extension).

    Parameters
    ----------
    disease_id : str
        Name of YAML file (without extension), e.g. 'rheumatoid_arthritis'.
    diseases_dir : Path | None
        Directory holding YAMLs. Defaults to <repo>/diseases.

    Returns
    -------
    DiseaseConfig
        Parsed dataclass instance.
    """
    base = diseases_dir or DISEASES_DIR
    yaml_path = base / f"{disease_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Disease YAML not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    _validate(cfg)

    meta = cfg["disease"]
    return DiseaseConfig(
        id=meta["id"],
        name=meta["name"],
        short=meta.get("short", meta["id"]),
        icd10=meta.get("icd10", ""),
        dynamics_type=meta["dynamics_type"],
        time_unit=meta.get("time_unit", "day"),
        baseline=cfg["baseline"],
        decay=cfg["decay"],
        circadian=cfg["circadian"],
        noise=cfg["noise"],
        triggers=cfg["triggers"],
        flare=cfg["flare"],
        treatments=cfg["treatments"],
        biomarkers=cfg["biomarkers"],
        comorbidity=cfg.get("comorbidity", []),
        demographics=cfg.get("demographics", {}),
        accumulation=cfg.get("accumulation"),
        raw=cfg,
    )


def list_diseases(diseases_dir: Path | None = None) -> list[str]:
    """Return list of disease ids found in diseases/ directory."""
    base = diseases_dir or DISEASES_DIR
    return sorted(p.stem for p in base.glob("*.yaml"))

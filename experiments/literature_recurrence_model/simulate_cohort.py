"""重跑「過去合成的 3,200 位虛擬患者」（16 病 × 200 人，base_seed=2024），模擬長度延長為 3 年（1,095 天）。

模擬器 md_piece/ 與 diseases/ 來自 claude/train-ai-model-0NYvq 分支，原封不動使用；
這裡只把每位患者每天的潛在疾病活動度、漏服、誘發因子、主觀症狀與客觀檢驗值存成 npz，
後續的復發標記（含文獻校準）全部在 run.py 由活動度重新計算，不再動模擬器。

跑法：
  git archive origin/claude/train-ai-model-0NYvq md_piece diseases | tar -x -C <SIM_DIR>
  PYTHONPATH=<SIM_DIR> python experiments/literature_recurrence_model/simulate_cohort.py <SIM_DIR> <OUT_DIR>
"""
from __future__ import annotations

import os
import sys
from multiprocessing import Pool

import numpy as np

SIM_DIR, OUT_DIR = sys.argv[1], sys.argv[2]
sys.path.insert(0, SIM_DIR)

from md_piece.disease_loader import load_disease  # noqa: E402
from md_piece.patient import simulate_patient  # noqa: E402

N_PER_DISEASE = 200
DAYS = 1095
BASE_SEED = 2024  # 與 docs/mdpiece/recurrence_engine_synth_cohort.md 的 3,200 人同一組 seed


def one_disease(disease_id: str) -> str:
    cfg = load_disease(disease_id)
    subj = [k for k, v in cfg.biomarkers.items() if v.get("subjective")]
    obj = [k for k, v in cfg.biomarkers.items() if not v.get("subjective")]
    offsets = {k: float(v.get("flare_threshold_offset", 0.0)) for k, v in cfg.raw.get("subtypes", {}).items()}
    cols = {"activity": [], "skip": [], "trig": [], "symptom": [], "lab": []}
    meta = {"age": [], "sex": [], "offset": [], "subtype": [], "n_tx": []}
    for i in range(N_PER_DISEASE):
        p = simulate_patient(f"{cfg.short}_{i:04d}", cfg, DAYS, BASE_SEED * 100_000 + i)
        ts = p.timeseries.iloc[:DAYS]
        cols["activity"].append(ts["activity"].to_numpy(np.float32))
        cols["skip"].append(ts["dose_any_skipped"].to_numpy(np.int8))
        cols["trig"].append(ts["n_active_triggers"].to_numpy(np.int8))
        # 患者日記：第一個主觀量表；沒有主觀量表的病（AAV、IgG4-RD）以門診客觀分數代替
        cols["symptom"].append(ts[(subj or obj)[0]].to_numpy(np.float32))
        cols["lab"].append(ts[obj[0]].to_numpy(np.float32))
        meta["age"].append(p.age)
        meta["sex"].append(1 if p.sex == "F" else 0)
        meta["offset"].append(offsets.get(p.subtype, 0.0))
        meta["subtype"].append(p.subtype)
        meta["n_tx"].append(len(p.treatments))
    np.savez_compressed(
        os.path.join(OUT_DIR, f"{disease_id}.npz"),
        **{k: np.stack(v) for k, v in cols.items()},
        **{k: np.array(v) for k, v in meta.items()},
        threshold=cfg.flare["threshold"], refractory=cfg.flare["refractory_days"],
        short=cfg.short, dynamics=cfg.dynamics_type,
        symptom_name=(subj or obj)[0], lab_name=obj[0], lab_higher_worse=_higher_worse(cfg, obj[0]),
    )
    return disease_id


LOWER_IS_WORSE = {"peak_flow_lpm", "fvc_pct_pred"}  # 公式裡 activity 係數為負的檢驗值


def _higher_worse(cfg, name: str) -> bool:
    return name not in LOWER_IS_WORSE


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    ids = sorted(f[:-5] for f in os.listdir(os.path.join(SIM_DIR, "diseases")) if f.endswith(".yaml"))
    with Pool(4) as pool:
        for d in pool.imap_unordered(one_disease, ids):
            print("done", d, flush=True)

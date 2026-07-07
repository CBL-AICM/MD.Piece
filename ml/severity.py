"""嚴重度分級與個人設常數 — 輕量(僅 numpy)，供 enrich_backend 與 world 共用。

抽出來的目的：world.py 的每日 tick 不需要 torch；把不依賴模型的部分集中於此，
讓雲端 cron 只裝輕量依賴即可跑 tick。
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from md_piece.disease_loader import load_disease

BAND_ZH = {"mild": "輕度", "moderate": "中度", "severe": "重度"}
BAND_COLOR = {"mild": "#34a853", "moderate": "#f9ab00", "severe": "#ea4335"}
BLOODS = ["O", "A", "B", "AB"]
BLOOD_P = [0.44, 0.26, 0.24, 0.06]                      # 台灣血型分布近似

COMORBID_ZH = {
    "depression": "憂鬱症", "cardiovascular": "心血管疾病", "sjogren": "乾燥症",
    "hypertension": "高血壓", "diabetes": "糖尿病", "osteoporosis": "骨質疏鬆",
    "ckd": "慢性腎臟病", "hyperlipidemia": "高血脂", "anemia": "貧血",
    "thyroid": "甲狀腺疾病", "gerd": "胃食道逆流", "copd": "慢性阻塞性肺病",
    "cataract": "白內障", "osteoarthritis": "退化性關節炎",
}
DISEASE_ALLERGY = {
    "asthma": "塵蟎、花粉", "chronic_urticaria": "食物/藥物過敏原",
    "anca_vasculitis": "—", "idiopathic_pulmonary_fibrosis": "—",
}

# 疾病固有嚴重度偏移：進展/致命型偏重、發作型偏輕
DISEASE_ACUITY = {
    "idiopathic_pulmonary_fibrosis": 0.26, "systemic_sclerosis": 0.18,
    "anca_vasculitis": 0.18, "igg4_related_disease": 0.12,
    "multiple_sclerosis": 0.10, "systemic_lupus_erythematosus": 0.10,
    "behcet_disease": 0.06, "inflammatory_bowel_disease": 0.05,
    "rheumatoid_arthritis": 0.05, "osteoarthritis": 0.05,
    "ankylosing_spondylitis": 0.0, "psoriatic_arthritis": 0.0,
    "sjogren_syndrome": 0.0, "asthma": 0.0,
    "gout": -0.05, "chronic_urticaria": -0.08,
}


def assign_severity(regs) -> dict[str, tuple[str, int]]:
    """回傳 pid -> (band, score 0-100)。疾病內 z-score 相對排序 + acuity 偏移。

    復發型(burden≈0)看活動度+flare 頻率；進展型看 burden。疾病內各訊號
    z-score 自動加權 → 個人相對嚴重度(保證有分布)；再依疾病 acuity 整體上下移。
    """
    by_dis: dict[str, list] = defaultdict(list)
    for p in regs:
        by_dis[p.disease_id].append(p)

    out: dict[str, tuple[str, int]] = {}
    for did, ps in by_dis.items():
        feats = []
        for p in ps:
            ts = p.timeseries
            ma = float(ts["activity"].mean())
            bu = float(ts["irreversible_burden"].iloc[-1]) if "irreversible_burden" in ts.columns else 0.0
            fc = float(p.flare_count)
            rp = {"non_responder": 1.0, "partial": 0.5,
                  "typical": 0.0, "super": -0.4}.get(p.responder_class, 0.0)
            feats.append((ma, bu, fc, rp))
        A = np.asarray(feats, dtype=float)
        mu, sd = A.mean(0), A.std(0)
        sd[sd < 1e-6] = 1.0
        Z = (A - mu) / sd
        w = np.array([1.0,
                      1.0 if A[:, 1].std() > 1e-3 else 0.0,
                      1.0 if A[:, 2].std() > 1e-3 else 0.0,
                      0.4])
        comp = (Z * w).sum(1) / w.sum()
        order = comp.argsort().argsort()
        pct = order / max(1, len(order) - 1)
        acuity = DISEASE_ACUITY.get(did, 0.0)
        for p, pc in zip(ps, pct):
            eff = pc + acuity
            band = "severe" if eff >= 0.67 else "moderate" if eff >= 0.34 else "mild"
            score = int(np.clip(pc * 68 + acuity * 100 + 16, 1, 100))
            out[p.patient_id] = (band, score)
    return out

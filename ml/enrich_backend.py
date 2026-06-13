"""為 1600 位 prod 帳號跑 ML，讓每個帳號更像「有個人設、有嚴重度」的真人。

對每位註冊患者：
  1. 跑 16 疾病 LSTM 模型(ml/config_enrich.yaml 訓練的 best.pt)做逐窗推論
     → 活動度預測 + flare 機率。
  2. ml/insights.generate_insight 產生個人化中文 AI 健康分析(畫像/家庭社經/
     人格心理/行為/老年機制/治療依從/生活事件/flare 預測/觸發因子/結論)。
  3. 依疾病絕對刻度計算「嚴重度分級」(mild/moderate/severe)，每人不同。
  4. 寫入正式 Supabase：
     - patient_profiles：個人設(性別/生日/血型/身高體重/過敏/共病/現病/用藥/醫師/醫院)
     - memos：一則「🤖 小核 AI 健康分析」(含嚴重度 + ML 分析全文)

user id 與 seed_backend 完全一致(同一批帳號)。可用 seed_backend --cleanup 一併清除。

用法：
  PYTHONPATH=. python -m ml.enrich_backend --canary 5
  PYTHONPATH=. python -m ml.enrich_backend --full
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import torch

from backend.db import get_supabase
from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from ml.app_cohort import DISEASES
from ml.features import make_windows
from ml.insights import DISEASE_NAME, generate_insight
from ml.predict import _patient_to_aligned_frame, load_checkpoint
from ml.seed_backend import COHORT_START, HOSPITALS, SURNAMES, TAG, _name, _uid

CKPT = Path("output/mdpiece/checkpoints_enrich/best.pt")
AI_MEMO_TAG = "🤖 小核 AI 健康分析"
BATCH = 500
NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)         # 分析產生時間(觀察期末)

BAND_ZH = {"mild": "輕度", "moderate": "中度", "severe": "重度"}
BAND_COLOR = {"mild": "#34a853", "moderate": "#f9ab00", "severe": "#ea4335"}
BLOODS = ["O", "A", "B", "AB"]
BLOOD_P = [0.44, 0.26, 0.24, 0.06]                      # 台灣血型分布近似

COMORBID_ZH = {
    "depression": "憂鬱症", "cardiovascular": "心血管疾病", "sjogren": "乾燥症",
    "hypertension": "高血壓", "diabetes": "糖尿病", "osteoporosis": "骨質疏鬆",
    "ckd": "慢性腎臟病", "hyperlipidemia": "高血脂", "anemia": "貧血",
    "thyroid": "甲狀腺疾病", "gerd": "胃食道逆流", "copd": "慢性阻塞性肺病",
}
DISEASE_ALLERGY = {
    "asthma": "塵蟎、花粉", "chronic_urticaria": "食物/藥物過敏原",
    "anca_vasculitis": "—", "idiopathic_pulmonary_fibrosis": "—",
}


# ---------------------------------------------------------------------------
# 取得與 seed_backend 相同的 1600 位(保留完整 Patient 物件供推論/分析)
# ---------------------------------------------------------------------------

def build_registered_patients(n_per, sim_days, n_register, base_seed, n_workers, limit):
    all_patients = []
    for did in DISEASES:
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_per, sim_days, base_seed=base_seed,
                                 n_workers=n_workers)
        all_patients.extend(cohort.patients)
    props = {p.patient_id: au.registration_propensity(p.social_profile, p.age, p.disease_id)
             for p in all_patients}
    reg = au.select_registered(props, n_register, seed=base_seed)
    regs = [p for p in all_patients if p.patient_id in reg]
    return regs[:limit] if limit else regs


# ---------------------------------------------------------------------------
# 推論(模型只載一次)
# ---------------------------------------------------------------------------

class Predictor:
    def __init__(self, ckpt_path: Path):
        self.model, self.feature_names, self.mean, self.std, self.cfg = \
            load_checkpoint(ckpt_path)

    def predict(self, patient) -> dict:
        df = _patient_to_aligned_frame(patient, self.feature_names)
        X, yr, yc, _ = make_windows(
            df, window_size=self.cfg["data"]["window_size"],
            horizon_days=self.cfg["data"]["horizon_days"],
            flare_horizon_days=self.cfg["data"]["flare_horizon_days"])
        if len(X) == 0:
            raise ValueError("patient too short")
        Xn = ((X - self.mean) / self.std).astype(np.float32)
        with torch.no_grad():
            reg, cls = self.model(torch.from_numpy(Xn))
            reg = reg.cpu().numpy()
            prob = torch.sigmoid(cls).cpu().numpy()
        win = self.cfg["data"]["window_size"]
        return {
            "day": np.arange(win, win + len(reg)),
            "activity_pred": reg, "activity_true": yr,
            "flare_prob": prob, "flare_true": yc.astype(int),
        }


# ---------------------------------------------------------------------------
# 嚴重度 — 疾病內相對分布 + 疾病別絕對嚴重度偏移
# ---------------------------------------------------------------------------
# 不同疾病的嚴重度由不同訊號驅動：
#   復發型(RA/痛風/MS…) burden≈0 → 看活動度 + flare 頻率
#   進展型(IPF/SSc/OA…) → 看累積不可逆 burden
# 因此用「疾病內各訊號 z-score 自動加權」取得個人相對嚴重度(保證有分布)，
# 再依疾病固有嚴重度(acuity)整體上下移，讓 IPF 普遍比痛風重。
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
    """回傳 pid -> (band, score 0-100)。疾病內相對排序 + acuity 偏移。"""
    from collections import defaultdict
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
                      1.0 if A[:, 1].std() > 1e-3 else 0.0,   # burden 只在會變動時計入
                      1.0 if A[:, 2].std() > 1e-3 else 0.0,   # flare 同上
                      0.4])
        comp = (Z * w).sum(1) / w.sum()
        order = comp.argsort().argsort()
        pct = order / max(1, len(order) - 1)                  # 疾病內百分位 0..1
        acuity = DISEASE_ACUITY.get(did, 0.0)
        for p, pc in zip(ps, pct):
            eff = pc + acuity
            band = "severe" if eff >= 0.67 else "moderate" if eff >= 0.34 else "mild"
            score = int(np.clip(pc * 68 + acuity * 100 + 16, 1, 100))
            out[p.patient_id] = (band, score)
    return out


# ---------------------------------------------------------------------------
# 由 Patient 組 patient_profiles 個人設
# ---------------------------------------------------------------------------

def build_profile(patient, rng) -> dict:
    sex = patient.sex
    age = patient.age
    birth_year = NOW.year - age
    bmonth = int(rng.integers(1, 13))
    bday = int(rng.integers(1, 29))
    if sex == "F":
        height = float(np.clip(rng.normal(159, 5.5), 145, 178))
    else:
        height = float(np.clip(rng.normal(170, 6.0), 152, 190))
    bmi = float(np.clip(rng.normal(23.5, 3.2), 16, 35))
    weight = round(bmi * (height / 100) ** 2, 1)
    comorbid = [COMORBID_ZH.get(c, c) for c in patient.comorbidities]
    meds = ", ".join(t["id"] for t in patient.treatments) or "—"
    allergy = DISEASE_ALLERGY.get(patient.disease_id, "無已知過敏")
    return {
        "user_id": _uid(patient.patient_id),
        "gender": "female" if sex == "F" else "male",
        "birthday": f"{birth_year:04d}-{bmonth:02d}-{bday:02d}",
        "blood": str(rng.choice(BLOODS, p=BLOOD_P)),
        "height_cm": round(height, 1),
        "weight_kg": weight,
        "allergies": allergy,
        "conditions": "、".join(comorbid) if comorbid else "無共病",
        "current_disease": DISEASE_NAME.get(patient.disease_id, patient.disease_id),
        "meds": meds,
        "doctor_name": str(rng.choice(SURNAMES)) + "醫師",
        "hospital": str(rng.choice(HOSPITALS)),
        "updated_at": NOW.isoformat(),
    }


def build_ai_memo(patient, insight, band, score) -> dict:
    risk = "高" if score >= 66 else "中" if score >= 40 else "低"
    header = (f"{AI_MEMO_TAG}（{DISEASE_NAME.get(patient.disease_id, patient.disease_id)}）\n"
              f"嚴重度分級：{BAND_ZH[band]}（{score}/100）｜近 12 個月 flare 風險：{risk}\n\n")
    return {
        "patient_id": _uid(patient.patient_id),
        "kind": "text",
        "content": header + insight.insight_zh +
                   "\n\n— 由 MD.Piece 16 疾病 LSTM 模型分析",
        "created_at": NOW.isoformat(),
    }


# ---------------------------------------------------------------------------
# 寫入 / 清除
# ---------------------------------------------------------------------------

def _flush(sb, table, rows):
    for i in range(0, len(rows), BATCH):
        sb.table(table).insert(rows[i:i + BATCH]).execute()


def enrich(regs):
    sb = get_supabase()
    pred = Predictor(CKPT)
    sev = assign_severity(regs)                        # 疾病內相對 + acuity，一次算完
    profiles, memos, avatars = [], [], []
    bands = {"mild": 0, "moderate": 0, "severe": 0}
    skipped = 0

    for p in regs:
        prng = np.random.default_rng(p.seed ^ 0xD0C7)
        try:
            res = pred.predict(p)
            insight = generate_insight(p, res)
        except Exception as e:
            skipped += 1
            print(f"  skip {p.patient_id}: {e}")
            continue
        band, score = sev[p.patient_id]
        bands[band] += 1
        profiles.append(build_profile(p, prng))
        memos.append(build_ai_memo(p, insight, band, score))
        # 修正暱稱：依真實性別重新產生(舊資料有男名配女性的不一致)
        nickname = _name(p.sex, np.random.default_rng(p.seed ^ 0xA11CE))
        avatars.append((_uid(p.patient_id), BAND_COLOR[band], nickname))

    ids = [pr["user_id"] for pr in profiles]
    # 冪等：先刪本腳本既有產物(patient_profiles + AI memo)，daily memo 不動
    print(f"清除既有 {len(ids)} 筆 patient_profiles / AI memo …")
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        sb.table("patient_profiles").delete().in_("user_id", chunk).execute()
        sb.table("memos").delete().in_("patient_id", chunk).like("content", AI_MEMO_TAG + "%").execute()

    print(f"寫入 patient_profiles {len(profiles)} 筆、AI memo {len(memos)} 筆 …")
    _flush(sb, "patient_profiles", profiles)
    _flush(sb, "memos", memos)

    # 依嚴重度上色頭像 + 修正性別一致的暱稱
    for uid, color, nickname in avatars:
        sb.table("users").update({"avatar_color": color, "nickname": nickname}).eq("id", uid).execute()

    print("=" * 56)
    print(f"完成 ML 強化：{len(profiles)} 位帳號")
    print(f"  嚴重度分布  輕度 {bands['mild']} / 中度 {bands['moderate']} / 重度 {bands['severe']}")
    print(f"  跳過(資料過短) {skipped}")
    print("=" * 56)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--canary", type=int, metavar="N")
    g.add_argument("--full", action="store_true")
    ap.add_argument("--base-seed", type=int, default=2024)
    ap.add_argument("--n-workers", type=int, default=4)
    a = ap.parse_args()

    if not CKPT.exists():
        raise SystemExit(f"找不到模型 {CKPT}；請先訓練：\n"
                         "  PYTHONPATH=. python -c \"from pathlib import Path; "
                         "from ml.train import train_from_config; "
                         "train_from_config(Path('ml/config_enrich.yaml'))\"")

    if a.canary is not None:
        regs = build_registered_patients(20, 365, 160, a.base_seed, a.n_workers, a.canary)
        print(f"[canary] 強化前 {len(regs)} 位…")
    else:
        regs = build_registered_patients(200, 365, 1600, a.base_seed, a.n_workers, None)
        print(f"[full] 強化 {len(regs)} 位…")
    enrich(regs)


if __name__ == "__main__":
    main()

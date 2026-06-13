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
from ml.severity import (  # 嚴重度與個人設常數(輕量、無 torch，與 world 共用)
    BAND_COLOR, BAND_ZH, BLOOD_P, BLOODS, COMORBID_ZH, DISEASE_ALLERGY,
    assign_severity,
)

CKPT = Path("output/mdpiece/checkpoints_enrich/best.pt")
AI_MEMO_TAG = "🤖 小核 AI 健康分析"
BATCH = 500
NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)         # 分析產生時間(觀察期末)


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


# 嚴重度分級 assign_severity 已移至 ml/severity.py(輕量、與 world 共用)。


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

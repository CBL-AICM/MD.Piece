"""把 1600 位註冊者寫入正式後台(Supabase) — 真實帳號 + 12 個月逐筆紀錄。

⚠️  本腳本會寫入 **production Supabase**(backend/db.py 的預設專案)。
    每一筆資料都帶 `sim3200_` 標記，可用 `--cleanup` 一次全部刪除。
    這是經使用者明確授權的真實後台填充；非 in silico 檔案。

用法：
  PYTHONPATH=. python -m ml.seed_backend --canary 5    # 先寫 5 位驗證(快)
  PYTHONPATH=. python -m ml.seed_backend --full         # 寫滿 1600 位
  PYTHONPATH=. python -m ml.seed_backend --cleanup      # 刪除所有 sim3200 資料

身分模型：一位「註冊患者」= users 表一列(role='patient')；各紀錄表以
patient_id = users.id 關聯(text 欄位存字串、uuid 欄位存同一個 uuid)。
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from backend.db import get_supabase
from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from ml.app_cohort import DISEASES

TAG = "sim3200_"                              # username 前綴；cleanup 依此刪除
COHORT_START = datetime(2025, 6, 1, tzinfo=timezone.utc)   # 12 個月觀察起點
NS = uuid.UUID("3200a000-0000-4000-8000-000000000000")     # 決定論 user id 命名空間
BATCH = 500
PATIENT_CHUNK = 40                           # 每批處理的患者數(控制記憶體 + FK 順序)

# 共用密碼雜湊(所有 sim 帳號可用同一密碼登入；synthetic 帳號可接受)
try:
    from backend.routers.auth import _hash_password
    SHARED_PW_HASH = _hash_password("Sim3200demo")
except Exception:
    SHARED_PW_HASH = None

# 疾病 → 主症狀類別 / 科別 / 代表檢驗
DISEASE_SYMPTOM = {
    "rheumatoid_arthritis": "關節疼痛", "asthma": "呼吸困難",
    "systemic_sclerosis": "皮膚緊繃", "systemic_lupus_erythematosus": "疲倦/關節痛",
    "inflammatory_bowel_disease": "腹痛/腹瀉", "multiple_sclerosis": "肢體麻木無力",
    "gout": "關節紅腫痛", "ankylosing_spondylitis": "下背痛/晨僵",
    "psoriatic_arthritis": "關節腫痛", "sjogren_syndrome": "乾眼乾口",
    "behcet_disease": "口腔潰瘍", "anca_vasculitis": "倦怠/血尿",
    "igg4_related_disease": "腺體腫脹", "chronic_urticaria": "蕁麻疹搔癢",
    "osteoarthritis": "關節僵硬疼痛", "idiopathic_pulmonary_fibrosis": "喘/乾咳",
}
DISEASE_DEPT = {
    "rheumatoid_arthritis": "風濕免疫科", "asthma": "胸腔內科",
    "systemic_sclerosis": "風濕免疫科", "systemic_lupus_erythematosus": "風濕免疫科",
    "inflammatory_bowel_disease": "胃腸肝膽科", "multiple_sclerosis": "神經內科",
    "gout": "風濕免疫科", "ankylosing_spondylitis": "風濕免疫科",
    "psoriatic_arthritis": "風濕免疫科", "sjogren_syndrome": "風濕免疫科",
    "behcet_disease": "風濕免疫科", "anca_vasculitis": "腎臟內科",
    "igg4_related_disease": "風濕免疫科", "chronic_urticaria": "過敏免疫科",
    "osteoarthritis": "骨科", "idiopathic_pulmonary_fibrosis": "胸腔內科",
}
DISEASE_LAB = {
    "rheumatoid_arthritis": ("CRP", "mg/L"), "asthma": ("FeNO", "ppb"),
    "systemic_sclerosis": ("ANA titer", ""), "systemic_lupus_erythematosus": ("C3", "mg/dL"),
    "inflammatory_bowel_disease": ("Fecal calprotectin", "µg/g"),
    "multiple_sclerosis": ("EDSS", ""), "gout": ("Uric acid", "mg/dL"),
    "ankylosing_spondylitis": ("CRP", "mg/L"), "psoriatic_arthritis": ("ESR", "mm/hr"),
    "sjogren_syndrome": ("anti-SSA", ""), "behcet_disease": ("ESR", "mm/hr"),
    "anca_vasculitis": ("Creatinine", "mg/dL"), "igg4_related_disease": ("IgG4", "mg/dL"),
    "chronic_urticaria": ("Total IgE", "IU/mL"), "osteoarthritis": ("ESR", "mm/hr"),
    "idiopathic_pulmonary_fibrosis": ("FVC", "%"),
}
HOSPITALS = ["臺大醫院", "榮總", "長庚紀念醫院", "馬偕醫院", "成大醫院", "中國醫藥大學附醫"]
SURNAMES = list("陳林黃張李王吳劉蔡楊許鄭謝郭洪曾邱廖賴周葉蘇莊呂江何蕭羅高")
GIVEN_F = ["淑芬", "美玲", "雅婷", "怡君", "詩涵", "欣怡", "心怡", "佳穎", "宜蓁", "曉雯",
           "麗華", "秀英", "惠雯", "佩珊", "靜宜", "雅雯", "品妤", "思綺", "婉婷", "玉珍"]
GIVEN_M = ["志明", "建宏", "俊傑", "家豪", "冠廷", "宗翰", "承恩", "柏翰", "彥廷", "明哲",
           "文雄", "國強", "正雄", "宏偉", "智偉", "信宏", "志豪", "偉誠", "孟翰", "瑞祥"]


def _ts(day: int, hour: int, minute: int = 0) -> str:
    return (COHORT_START + timedelta(days=int(day), hours=hour, minutes=minute)).isoformat()


def _date(day: int) -> str:
    return (COHORT_START + timedelta(days=int(day))).date().isoformat()


def _uid(pid: str) -> str:
    return str(uuid.uuid5(NS, TAG + pid))


def _name(sex: str, rng) -> str:
    given = GIVEN_F if sex == "F" else GIVEN_M
    return str(rng.choice(SURNAMES)) + str(rng.choice(given))


# ---------------------------------------------------------------------------
# 取得 1600 位註冊者(含 timeseries 與 treatments)
# ---------------------------------------------------------------------------

def build_registered(n_per, sim_days, n_register, base_seed, n_workers, limit):
    cands = []
    for did in DISEASES:
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_per, sim_days, base_seed=base_seed,
                                 n_workers=n_workers)
        for p in cohort.patients:
            ts = p.timeseries.sort_values("day")
            act = ts["activity"].to_numpy(dtype=np.float32)
            fl = ts["in_flare"].to_numpy(dtype=np.int8)
            if len(act) < sim_days:
                act = np.pad(act, (0, sim_days - len(act)), "edge")
                fl = np.pad(fl, (0, sim_days - len(fl)), "edge")
            cands.append({
                "pid": p.patient_id, "disease": p.disease_id, "age": p.age,
                "sex": p.sex, "profile": p.social_profile,
                "comorbidities": list(p.comorbidities),
                "treatments": [t["id"] for t in p.treatments],
                "act": act[:sim_days], "fl": fl[:sim_days], "seed": p.seed,
            })
    props = {c["pid"]: au.registration_propensity(c["profile"], c["age"], c["disease"])
             for c in cands}
    reg = au.select_registered(props, n_register, seed=base_seed)
    regs = [c for c in cands if c["pid"] in reg]
    return regs[:limit] if limit else regs


# ---------------------------------------------------------------------------
# 由模擬事件產生各表的列
# ---------------------------------------------------------------------------

def build_rows(c, sim_days):
    """回傳 dict[table] -> list[row]（單一患者）。"""
    rng = np.random.default_rng(c["seed"] ^ 0xA11CE)
    join_rng = np.random.default_rng(c["seed"] ^ 0x5EED)
    join_day = int(join_rng.integers(0, 46))
    rec = au.simulate_patient_usage(
        patient_id=c["pid"], disease_id=c["disease"], age=c["age"], sex=c["sex"],
        profile=c["profile"], comorbidities=c["comorbidities"],
        has_treatments=bool(c["treatments"]), activity=c["act"], in_flare=c["fl"],
        registered=True, join_day=join_day, sim_days=sim_days,
        seed=c["seed"] + 999983, collect_days=True,
    )
    uid = _uid(c["pid"])
    ev = rec.event_days
    act = c["act"]
    did = c["disease"]
    out: dict[str, list] = {t: [] for t in (
        "users", "symptom_entries", "medications", "medication_logs", "emotions",
        "vital_entries", "sleep_sessions", "diet_records", "follow_ups",
        "reminders", "memos", "labs", "menstrual_cycles")}

    # users（帳號）
    out["users"].append({
        "id": uid, "username": (TAG + c["pid"]).lower(),
        "nickname": _name(c["sex"], rng), "role": "patient",
        "email": (TAG + c["pid"]).lower() + "@cohort.invalid",
        "password_hash": SHARED_PW_HASH,
        "created_at": _ts(join_day, 9, int(rng.integers(0, 59))),
    })

    # symptoms
    cat = DISEASE_SYMPTOM.get(did, "不適")
    for d in ev.get("symptoms", []):
        intensity = int(np.clip(round(float(act[d]) / 10 * 5), 1, 5))
        out["symptom_entries"].append({
            "patient_id": uid, "client_id": str(uuid.uuid4()), "category_id": cat,
            "intensity": intensity, "frequency": int(rng.integers(1, 4)),
            "recorded_at": _ts(d, int(rng.integers(7, 22))),
        })

    # medications（處方）+ medication_logs（服藥紀錄）
    med_ids = []
    for drug in c["treatments"]:
        mid = str(uuid.uuid4())
        med_ids.append(mid)
        out["medications"].append({
            "id": mid, "patient_id": uid, "name": drug,
            "frequency": "每日", "active": 1,
            "prescribed_date": _date(join_day),
        })
    if med_ids:
        for d in ev.get("medications", []):
            out["medication_logs"].append({
                "patient_id": uid, "medication_id": str(rng.choice(med_ids)),
                "taken": 1, "taken_at": _ts(d, 8, int(rng.integers(0, 59))),
            })

    # emotions（情緒；活動度高→分數低）
    for d in ev.get("emotions", []):
        score = int(np.clip(5 - round(float(act[d]) / 10 * 3) + int(rng.integers(-1, 2)), 1, 5))
        out["emotions"].append({
            "patient_id": uid, "score": score,
            "created_at": _ts(d, int(rng.integers(8, 23))),
        })

    # vitals
    for d in ev.get("vitals", []):
        metric = str(rng.choice(["blood_pressure_sys", "heart_rate", "weight"]))
        val = {"blood_pressure_sys": float(rng.normal(125, 12)),
               "heart_rate": float(rng.normal(76, 8)),
               "weight": float(rng.normal(62, 10))}[metric]
        out["vital_entries"].append({
            "patient_id": uid, "client_id": str(uuid.uuid4()), "metric_id": metric,
            "value": round(val, 1), "recorded_at": _ts(d, int(rng.integers(6, 22))),
        })

    # sleep（注意：欄位是 user_id）
    sh = c["profile"].behavioral.sleep_hours_avg
    for d in ev.get("sleep", []):
        total = int(np.clip(rng.normal(sh * 60, 45), 180, 600))
        out["sleep_sessions"].append({
            "user_id": uid, "bed_time": _ts(d, 23), "wake_time": _ts(d + 1, 7),
            "total_sleep_minutes": total, "source": "manual",
        })

    # diet（meal_type 受 check 限制為英文 enum）
    for d in ev.get("diet", []):
        meal = str(rng.choice(["breakfast", "lunch", "dinner"]))
        out["diet_records"].append({
            "patient_id": uid, "meal_type": meal, "foods": "正常飲食",
            "eaten_at": _ts(d, {"breakfast": 8, "lunch": 12, "dinner": 19}[meal]),
            "calories": int(rng.normal(600, 150)),
        })

    # follow_ups（回診）
    dept = DISEASE_DEPT.get(did, "內科")
    hosp = str(rng.choice(HOSPITALS))
    today_day = (datetime.now(timezone.utc) - COHORT_START).days
    for d in ev.get("follow_ups", []):
        out["follow_ups"].append({
            "patient_id": uid, "scheduled_date": _date(d), "department": dept,
            "hospital": hosp, "doctor_name": str(rng.choice(SURNAMES)) + "醫師",
            "status": "completed" if d <= today_day else "scheduled",
        })

    # reminders（智慧提醒設定）
    for d in ev.get("reminders", []):
        out["reminders"].append({
            "patient_id": uid, "reminder_type": "medication", "title": "服藥提醒",
            "frequency": "daily", "scheduled_at": _ts(d, 8),
            "next_fire_at": _ts(d + 1, 8), "source": "manual",
        })

    # memos
    for d in ev.get("memos", []):
        out["memos"].append({
            "patient_id": uid, "kind": "text",
            "content": f"今天{cat}還好，持續記錄中。", "created_at": _ts(d, 21),
        })

    # labs
    lab_name, unit = DISEASE_LAB.get(did, ("CRP", "mg/L"))
    for d in ev.get("labs", []):
        out["labs"].append({
            "patient_id": uid, "name": lab_name,
            "value": str(round(float(act[d]) * float(rng.uniform(1.5, 3.0)) + 1, 1)),
            "unit": unit, "status": "abnormal" if act[d] > 5 else "normal",
            "source": "manual", "recorded_at": _ts(d, 10),
        })

    # menstrual（僅育齡女性）
    if c["sex"] == "F" and 13 <= c["age"] <= 52:
        last = -99
        for d in sorted(ev.get("menstrual", [])):
            if d - last < 20:
                continue
            last = d
            out["menstrual_cycles"].append({
                "patient_id": uid, "start_date": _date(d), "end_date": _date(d + 4),
                "flow": str(rng.choice(["少", "中", "多"])),
            })
    return out


# ---------------------------------------------------------------------------
# 寫入 / 清除
# ---------------------------------------------------------------------------

INSERT_ORDER = ["users", "medications", "medication_logs", "symptom_entries",
                "emotions", "vital_entries", "sleep_sessions", "diet_records",
                "follow_ups", "reminders", "memos", "labs", "menstrual_cycles"]


def _flush(sb, table, rows):
    for i in range(0, len(rows), BATCH):
        sb.table(table).insert(rows[i:i + BATCH]).execute()


def seed(regs, sim_days):
    sb = get_supabase()
    totals = {t: 0 for t in INSERT_ORDER}
    n = len(regs)
    for start in range(0, n, PATIENT_CHUNK):
        chunk = regs[start:start + PATIENT_CHUNK]
        buf: dict[str, list] = {t: [] for t in INSERT_ORDER}
        for c in chunk:
            rows = build_rows(c, sim_days)
            for t in INSERT_ORDER:
                buf[t].extend(rows[t])
        for t in INSERT_ORDER:        # 依相依順序寫入(users→medications→logs→其餘)
            if buf[t]:
                _flush(sb, t, buf[t])
                totals[t] += len(buf[t])
        print(f"  …已寫入 {min(start+PATIENT_CHUNK, n)}/{n} 位")
    return totals


def cleanup():
    sb = get_supabase()
    users = sb.table("users").select("id").like("username", TAG + "%").execute().data
    ids = [u["id"] for u in users]
    print(f"找到 {len(ids)} 位 sim3200 帳號，開始刪除其紀錄…")
    record_tables = ["medication_logs", "medications", "symptom_entries", "emotions",
                     "vital_entries", "diet_records", "follow_ups", "reminders",
                     "memos", "labs", "menstrual_cycles"]
    for t in record_tables:
        for i in range(0, len(ids), 100):
            sb.table(t).delete().in_("patient_id", ids[i:i + 100]).execute()
    for i in range(0, len(ids), 100):     # sleep_sessions / patient_profiles 用 user_id
        sb.table("sleep_sessions").delete().in_("user_id", ids[i:i + 100]).execute()
        sb.table("patient_profiles").delete().in_("user_id", ids[i:i + 100]).execute()
    sb.table("users").delete().like("username", TAG + "%").execute()
    # 專屬 sim 表(含未註冊候選者)整張清掉
    for t in ("sim_persona", "sim_world_state"):
        try:
            sb.table(t).delete().neq("patient_id", "").execute()
        except Exception:
            pass
    print(f"已刪除 {len(ids)} 位帳號與其所有紀錄(含 persona/world 狀態)。")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--canary", type=int, metavar="N", help="先寫 N 位驗證(小池快)")
    g.add_argument("--full", action="store_true", help="寫滿 1600 位")
    g.add_argument("--cleanup", action="store_true", help="刪除所有 sim3200 資料")
    ap.add_argument("--base-seed", type=int, default=2024)
    ap.add_argument("--n-workers", type=int, default=4)
    a = ap.parse_args()

    if a.cleanup:
        cleanup()
        return

    if a.canary is not None:
        n_per, n_register, sim_days, limit = 20, 160, 365, a.canary
        print(f"[canary] 小池 {len(DISEASES)}×{n_per}，寫入前 {limit} 位…")
    else:
        n_per, n_register, sim_days, limit = 200, 1600, 365, None
        print("[full] 先清除既有 sim3200 資料以確保冪等…")
        cleanup()
        print(f"[full] 生成 {len(DISEASES)}×{n_per} 並寫入 {n_register} 位…")

    regs = build_registered(n_per, sim_days, n_register, a.base_seed, a.n_workers, limit)
    print(f"準備寫入 {len(regs)} 位註冊者的 12 個月紀錄…")
    totals = seed(regs, sim_days)
    print("=" * 56)
    print(f"完成：寫入 {len(regs)} 位帳號")
    for t, n in totals.items():
        print(f"  {t:18s} {n:>8d} 筆")
    print(f"  合計紀錄 {sum(v for k,v in totals.items() if k!='users'):>8d} 筆")
    print("=" * 56)


if __name__ == "__main__":
    main()

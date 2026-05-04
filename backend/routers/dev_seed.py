"""開發用：一鍵建立完整測試病患資料（vitals 30 天 + 用藥 + 服藥紀錄 + 症狀分析 + 就診紀錄）。
僅為了 demo / 醫師端 dashboard 視覺驗證用，正式部署應移除或鎖權限。"""
import hashlib
import os
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import get_supabase

router = APIRouter()


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


class SeedRequest(BaseModel):
    username: str = "demo_patient"
    nickname: str = "示範病患"
    password: str = "demo1234"


@router.post("/seed_patient")
def seed_patient(body: SeedRequest):
    """建立或重置一個示範病患，注入 30 天測試資料。"""
    sb = get_supabase()

    # 1. 取得或建立 user
    existing = sb.table("users").select("*").eq("username", body.username).execute()
    if existing.data:
        user = existing.data[0]
        if user.get("role") != "patient":
            raise HTTPException(status_code=400, detail=f"已有非患者帳號占用此 username: {body.username}")
    else:
        payload = {
            "username": body.username,
            "nickname": body.nickname,
            "role": "patient",
            "avatar_color": "#5B9FE8",
            "password_hash": _hash_password(body.password),
        }
        try:
            res = sb.table("users").insert(payload).execute()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"建立 user 失敗：{e}")
        user = res.data[0]

    pid = user["id"]

    # 2. 確保 patients 表有 row（給 medications FK）
    try:
        if not sb.table("patients").select("id").eq("id", pid).execute().data:
            sb.table("patients").insert({"id": pid, "name": body.nickname, "age": 58, "gender": "male"}).execute()
    except Exception:
        pass

    # 3. 清掉舊資料
    for tbl in ("vital_signs", "medication_logs", "medications", "symptoms_log", "medical_records"):
        try:
            sb.table(tbl).delete().eq("patient_id", pid).execute()
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    rng = random.Random(42)

    # 4. 30 天 vitals
    vital_rows = []
    for d in range(30, -1, -1):
        ts = (now - timedelta(days=d)).isoformat()
        # 體重 70±1.5 緩慢下降
        vital_rows.append({
            "patient_id": pid, "metric_id": "weight", "metric_name": "體重", "unit": "kg",
            "value": round(72 - d * 0.04 + rng.uniform(-0.4, 0.4), 1),
            "recorded_at": ts,
        })
        # 血壓 (雙值)
        vital_rows.append({
            "patient_id": pid, "metric_id": "bp", "metric_name": "血壓", "unit": "mmHg",
            "value": round(128 + rng.uniform(-8, 12) + (d / 6 if d > 18 else 0)),
            "value2": round(82 + rng.uniform(-6, 8)),
            "recorded_at": ts,
        })
        # 血糖
        if d % 2 == 0:
            vital_rows.append({
                "patient_id": pid, "metric_id": "glucose", "metric_name": "血糖", "unit": "mg/dL",
                "value": round(105 + rng.uniform(-12, 18)),
                "recorded_at": ts,
            })
        # 心率
        vital_rows.append({
            "patient_id": pid, "metric_id": "heart", "metric_name": "心率", "unit": "bpm",
            "value": round(72 + rng.uniform(-6, 8)),
            "recorded_at": ts,
        })
        # 血氧（每三天一次）
        if d % 3 == 0:
            vital_rows.append({
                "patient_id": pid, "metric_id": "spo2", "metric_name": "血氧", "unit": "%",
                "value": round(97 + rng.uniform(-1.5, 1.5), 1),
                "recorded_at": ts,
            })
    try:
        sb.table("vital_signs").insert(vital_rows).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"插入 vital_signs 失敗（請先在 Supabase 跑 docs/migration_vital_signs.sql）：{e}")

    # 5. 藥物
    meds_payload = [
        {"patient_id": pid, "name": "Amlodipine 5mg", "dosage": "5 mg", "frequency": "每日 1 次", "purpose": "高血壓控制", "instructions": "早餐後服用"},
        {"patient_id": pid, "name": "Metformin 500mg", "dosage": "500 mg", "frequency": "每日 2 次", "purpose": "血糖控制", "instructions": "早晚餐後"},
        {"patient_id": pid, "name": "Atorvastatin 10mg", "dosage": "10 mg", "frequency": "每晚 1 次", "purpose": "降膽固醇", "instructions": "睡前服用"},
        {"patient_id": pid, "name": "Aspirin 100mg", "dosage": "100 mg", "frequency": "每日 1 次", "purpose": "心血管預防", "instructions": "早餐後"},
    ]
    inserted_meds = []
    for m in meds_payload:
        try:
            r = sb.table("medications").insert(m).execute()
            if r.data:
                inserted_meds.append(r.data[0])
        except Exception:
            pass

    # 6. 服藥紀錄（30 天 × 每藥；85% 有服用）
    log_rows = []
    for med in inserted_meds:
        for d in range(30, -1, -1):
            ts = (now - timedelta(days=d, hours=rng.randint(7, 21))).isoformat()
            taken = 1 if rng.random() < 0.85 else 0
            log_rows.append({
                "patient_id": pid,
                "medication_id": med["id"],
                "taken": taken,
                "taken_at": ts,
                "skip_reason": "忘記" if taken == 0 else None,
            })
    if log_rows:
        try:
            # 分批避免 payload 太大
            for i in range(0, len(log_rows), 100):
                sb.table("medication_logs").insert(log_rows[i:i + 100]).execute()
        except Exception:
            pass

    # 7. 症狀分析歷史（含緊急程度）
    symptom_samples = [
        (28, ["頭痛", "頭暈"],     "low",       "家醫科"),
        (24, ["疲勞", "失眠"],     "low",       "家醫科"),
        (20, ["胸悶", "心悸"],     "medium",    "心臟內科"),
        (16, ["腰痠", "關節痛"],   "low",       "復健科"),
        (12, ["咳嗽", "喉嚨痛"],   "medium",    "耳鼻喉科"),
        (8,  ["胸痛", "呼吸困難"], "high",      "心臟內科"),
        (5,  ["頭暈", "視力模糊"], "medium",    "神經內科"),
        (2,  ["持續胸痛", "冒冷汗"], "emergency","急診"),
        (1,  ["輕微頭痛"],         "low",       "家醫科"),
    ]
    sym_rows = []
    for d, syms, urg, dept in symptom_samples:
        sym_rows.append({
            "patient_id": pid,
            "symptoms": syms,
            "ai_response": {
                "urgency": urg,
                "recommended_department": dept,
                "advice": "如症狀持續或加劇，請就醫評估。",
                "conditions": [{"name": syms[0] + " 相關", "likelihood": "中等"}],
            },
            "created_at": (now - timedelta(days=d)).isoformat(),
        })
    try:
        sb.table("symptoms_log").insert(sym_rows).execute()
    except Exception:
        pass

    # 8. 就診紀錄（兩筆）
    record_rows = [
        {
            "patient_id": pid,
            "visit_date": (now - timedelta(days=22)).isoformat(),
            "symptoms": ["胸悶", "高血壓"],
            "diagnosis": "原發性高血壓 (I10)",
            "prescription": "Amlodipine 5mg qd",
            "notes": "建議低鹽飲食、規律運動，1 個月後回診。",
        },
        {
            "patient_id": pid,
            "visit_date": (now - timedelta(days=4)).isoformat(),
            "symptoms": ["胸痛", "呼吸困難"],
            "diagnosis": "穩定性心絞痛 (I20.9)",
            "prescription": "Aspirin 100mg qd, Atorvastatin 10mg qhs",
            "notes": "已加開 Aspirin 與 Statin，安排心電圖追蹤。",
        },
    ]
    try:
        sb.table("medical_records").insert(record_rows).execute()
    except Exception:
        pass

    return {
        "ok": True,
        "patient": {
            "id": pid,
            "username": user["username"],
            "nickname": user["nickname"],
        },
        "summary": {
            "vitals": len(vital_rows),
            "medications": len(inserted_meds),
            "medication_logs": len(log_rows),
            "symptoms": len(sym_rows),
            "records": len(record_rows),
        },
        "tip": f"用醫師帳號登入後，輸入序號「{user['username']}」即可看到完整 dashboard。",
    }

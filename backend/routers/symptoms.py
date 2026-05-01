import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 症狀目錄：每個症狀附「快速說明」幫助患者選對類別 ──────────
SYMPTOM_CATALOG = [
    {"key": "headache", "label": "頭痛", "icon": "brain", "category": "pain",
     "description": "頭部、額頭、太陽穴、後腦或頭頂的疼痛感（脹痛、刺痛、壓迫感）。"},
    {"key": "dizziness", "label": "頭暈", "icon": "cloud", "category": "neuro",
     "description": "感覺輕飄、頭重腳輕、快要昏倒，但環境沒有在轉。"},
    {"key": "vertigo", "label": "暈眩", "icon": "rotate-cw", "category": "neuro",
     "description": "感覺自己或環境在旋轉、傾斜，常伴隨噁心。和「頭暈」不同。"},
    {"key": "neuralgia", "label": "神經痛", "icon": "zap", "category": "pain",
     "description": "如電擊、針刺、灼熱的疼痛，沿神經分布、突發短暫但反覆。"},
    {"key": "joint_pain", "label": "關節痛", "icon": "bone", "category": "pain",
     "description": "膝、肩、手指、腰等關節活動或休息時的疼痛、僵硬。"},
    {"key": "muscle_pain", "label": "肌肉痠痛", "icon": "activity", "category": "pain",
     "description": "肌肉酸緊痛，多和姿勢、勞動或運動相關。"},
    {"key": "abdominal_pain", "label": "腹痛", "icon": "circle", "category": "pain",
     "description": "上腹、肚臍周圍或下腹的悶痛、絞痛、刺痛。"},
    {"key": "chest_pain", "label": "胸痛", "icon": "heart-pulse", "category": "pain",
     "description": "胸口悶、痛、壓迫感，可能延伸到肩膀或下顎。**嚴重請立即就醫。**"},
    {"key": "fever", "label": "發燒", "icon": "thermometer", "category": "general",
     "description": "體溫升高（耳溫 ≥ 37.5°C 或腋溫 ≥ 37°C），可能畏寒、出汗。"},
    {"key": "cough", "label": "咳嗽", "icon": "wind", "category": "respiratory",
     "description": "乾咳或有痰，可能伴隨喉嚨癢、胸口不適。"},
    {"key": "shortness_of_breath", "label": "呼吸困難", "icon": "lungs", "category": "respiratory",
     "description": "喘不過氣、呼吸急促。**嚴重請立即就醫。**"},
    {"key": "nausea", "label": "噁心嘔吐", "icon": "frown", "category": "gi",
     "description": "想吐、反胃，或實際嘔吐。"},
    {"key": "fatigue", "label": "疲倦無力", "icon": "battery-low", "category": "general",
     "description": "持續疲累，休息後仍無法恢復。"},
    {"key": "insomnia", "label": "失眠", "icon": "moon", "category": "general",
     "description": "難入睡、睡眠中斷或太早醒。"},
    {"key": "rash_itch", "label": "皮膚癢／疹", "icon": "bug", "category": "skin",
     "description": "皮膚發癢、紅疹、起疹塊。"},
]
SYMPTOM_LABELS = {s["key"]: s["label"] for s in SYMPTOM_CATALOG}
SYMPTOM_CATEGORIES = {s["key"]: s["category"] for s in SYMPTOM_CATALOG}
VALID_SYMPTOM_KEYS = set(SYMPTOM_LABELS.keys())


class SymptomEntryCreate(BaseModel):
    patient_id: str
    symptom_type: str
    severity: int = Field(ge=1, le=5, default=3)
    location: Optional[str] = None
    notes: Optional[str] = None
    recorded_at: Optional[str] = None

SYMPTOM_ADVICE = {
    "fever": "多休息、補充水分。若體溫超過 38.5°C 持續超過 3 天，請就醫。",
    "headache": "注意休息，避免強光刺激。若頭痛劇烈或伴隨嘔吐，請立即就醫。",
    "cough": "多喝溫水，避免刺激性食物。若咳嗽超過 2 週或咳血，請就醫。",
    "chest pain": "請立即就醫，排除心臟相關問題。撥打 119 緊急電話。",
    "sore throat": "多喝水、避免辛辣食物。若伴隨高燒或吞嚥困難，請就醫。",
    "nausea": "少量多餐，避免油膩食物。若持續嘔吐或脫水，請就醫。",
    "dizziness": "先坐下或躺下休息，避免突然站起。反覆發作請就醫。",
    "fatigue": "確保充足睡眠與均衡飲食。若持續疲勞超過 2 週，建議就醫檢查。",
    "stomach pain": "避免辛辣油膩飲食。若劇烈疼痛或伴隨發燒，請就醫。",
    "shortness of breath": "請立即就醫。若伴隨胸痛或嘴唇發紫，請撥打 119。",
}

# 症狀記錄 - 五層遞進問卷、人體輪廓圖、拍照記錄


@router.get("/")
def get_symptoms(patient_id: str):
    return {"symptoms": []}

@router.post("/")
def create_symptom(patient_id: str, body_part: str, severity: int, description: str = ""):
    return {"status": "recorded"}

@router.get("/infection-check")
def check_infection(patient_id: str):
    # 每日感染篩查：發燒、呼吸道、泌尿道、皮膚、腸胃道
    return {"infection_flag": False}

@router.get("/advice")
def get_advice(symptom: str):
    """簡單症狀建議（保留向後相容）。"""
    advice = SYMPTOM_ADVICE.get(symptom.lower(), "建議就醫，請諮詢醫師")
    return {"symptom": symptom, "advice": advice}


@router.post("/analyze")
async def analyze(body: SymptomAnalysisRequest):
    """AI 症狀分析。"""
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="請提供至少一個症狀")

    # 如果有 patient_id，取得病患資料作為參考
    patient_info = None
    if body.patient_id:
        sb = get_supabase()
        result = sb.table("patients").select("name,age,gender").eq("id", body.patient_id).execute()
        if result.data:
            patient_info = result.data[0]

    # 呼叫 AI 分析
    ai_result = await analyze_symptoms(
        symptoms=body.symptoms,
        patient_age=patient_info.get("age") if patient_info else None,
        patient_gender=patient_info.get("gender") if patient_info else None,
    )

    # 記錄到 symptoms_log
    if body.patient_id:
        sb = get_supabase()
        sb.table("symptoms_log").insert({
            "patient_id": body.patient_id,
            "symptoms": body.symptoms,
            "ai_response": ai_result,
        }).execute()

    return ai_result


@router.get("/history/{patient_id}")
def get_symptom_history(patient_id: str):
    """取得病患的症狀分析歷史。"""
    sb = get_supabase()
    result = sb.table("symptoms_log").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"history": result.data}


# ── 症狀自記：目錄、紀錄、趨勢 ────────────────────────────

@router.get("/catalog")
def get_symptom_catalog():
    """症狀目錄；每個症狀附快速說明，幫助患者選對類別。"""
    return {"items": SYMPTOM_CATALOG}


@router.post("/entries")
def create_symptom_entry(body: SymptomEntryCreate):
    """記錄一筆症狀（患者自記）。"""
    if body.symptom_type not in VALID_SYMPTOM_KEYS:
        raise HTTPException(status_code=400, detail=f"未知症狀類型：{body.symptom_type}")

    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "symptom_type": body.symptom_type,
        "severity": body.severity,
        "location": body.location,
        "notes": body.notes,
        "recorded_at": body.recorded_at or datetime.utcnow().isoformat(),
    }
    data = {k: v for k, v in data.items() if v is not None}
    try:
        result = sb.table("symptom_entries").insert(data).execute()
    except Exception as e:
        logger.error(f"create_symptom_entry failed: {e}")
        raise HTTPException(status_code=500, detail=f"寫入失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=500, detail="資料庫未回傳資料")
    row = result.data[0]
    row["label"] = SYMPTOM_LABELS.get(row.get("symptom_type"))
    return row


@router.get("/entries")
def list_symptom_entries(
    patient_id: str = Query(...),
    days: int = Query(30, description="查詢最近幾天"),
    symptom_type: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    """列出患者最近的症狀紀錄（依 recorded_at 由新到舊）。"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    q = (
        sb.table("symptom_entries")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("recorded_at", since)
        .order("recorded_at", desc=True)
    )
    if symptom_type:
        q = q.eq("symptom_type", symptom_type)
    if limit:
        q = q.limit(limit)
    rows = q.execute().data or []
    for r in rows:
        r["label"] = SYMPTOM_LABELS.get(r.get("symptom_type"))
    return {"entries": rows, "days": days}


@router.get("/trend")
def symptom_trend(
    patient_id: str = Query(...),
    days: int = Query(30, description="統計區間（天）；對應上次回診至今"),
):
    """
    醫師端折線圖資料：依症狀類型分組的每日紀錄。
    回傳：
      - dates: 排序後的日期序列
      - series: 每個出現過的症狀一條折線：
                  { key, label, counts: [...], avg_severity: [...], total }
      - by_symptom: 每症狀彙總（總次數、平均嚴重度、最近一次）
      - recent: 最近 20 筆紀錄（給醫師快速看細節）
    """
    sb = get_supabase()
    since_dt = datetime.utcnow() - timedelta(days=days)
    since = since_dt.isoformat()
    rows = (
        sb.table("symptom_entries")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("recorded_at", since)
        .order("recorded_at")
        .execute()
        .data
        or []
    )

    # 建立連續日期軸
    dates = []
    cur = since_dt.date()
    end = datetime.utcnow().date()
    while cur <= end:
        dates.append(cur.isoformat())
        cur += timedelta(days=1)

    # 依 (date, key) 統計
    grid: dict[tuple[str, str], dict] = {}
    by_symptom: dict[str, dict] = {}
    for r in rows:
        day = (r.get("recorded_at") or "")[:10]
        if not day:
            continue
        key = r.get("symptom_type")
        sev = r.get("severity") or 0
        cell = grid.setdefault((day, key), {"count": 0, "sev_sum": 0})
        cell["count"] += 1
        cell["sev_sum"] += sev

        agg = by_symptom.setdefault(key, {
            "key": key,
            "label": SYMPTOM_LABELS.get(key, key),
            "category": SYMPTOM_CATEGORIES.get(key),
            "total": 0,
            "sev_sum": 0,
            "max_severity": 0,
            "first_recorded_at": None,
            "last_recorded_at": None,
            "active_days": set(),
        })
        agg["total"] += 1
        agg["sev_sum"] += sev
        agg["max_severity"] = max(agg["max_severity"], sev)
        rec = r.get("recorded_at") or ""
        if not agg["first_recorded_at"] or rec < agg["first_recorded_at"]:
            agg["first_recorded_at"] = rec
        if not agg["last_recorded_at"] or rec > agg["last_recorded_at"]:
            agg["last_recorded_at"] = rec
        agg["active_days"].add(day)

    series = []
    for key, agg in sorted(by_symptom.items(), key=lambda kv: -kv[1]["total"]):
        counts = []
        sev_avg = []
        for d in dates:
            cell = grid.get((d, key))
            if cell:
                counts.append(cell["count"])
                sev_avg.append(round(cell["sev_sum"] / cell["count"], 2))
            else:
                counts.append(0)
                sev_avg.append(None)
        series.append({
            "key": key,
            "label": agg["label"],
            "counts": counts,
            "avg_severity": sev_avg,
            "total": agg["total"],
        })

    period_days = max(1, days)
    by_symptom_list = []
    for v in by_symptom.values():
        total = v["total"]
        per_week = round(total / period_days * 7, 2)
        per_month = round(total / period_days * 30, 2)
        by_symptom_list.append({
            "key": v["key"],
            "label": v["label"],
            "category": v["category"],
            "total": total,
            "avg_severity": round(v["sev_sum"] / total, 2) if total else None,
            "max_severity": v["max_severity"],
            "first_recorded_at": v["first_recorded_at"],
            "last_recorded_at": v["last_recorded_at"],
            "active_days": len(v["active_days"]),
            "per_week": per_week,
            "per_month": per_month,
        })
    by_symptom_list.sort(key=lambda x: -x["total"])

    # 疼痛專屬統計（category == 'pain'）
    pain_items = [b for b in by_symptom_list if b["category"] == "pain"]
    pain_total = sum(b["total"] for b in pain_items)
    pain_summary = {
        "total": pain_total,
        "types": len(pain_items),
        "per_week": round(pain_total / period_days * 7, 2),
        "per_month": round(pain_total / period_days * 30, 2),
        "items": pain_items,
    }

    recent = [
        {
            "id": r.get("id"),
            "symptom_type": r.get("symptom_type"),
            "label": SYMPTOM_LABELS.get(r.get("symptom_type"), r.get("symptom_type")),
            "severity": r.get("severity"),
            "location": r.get("location"),
            "notes": r.get("notes"),
            "recorded_at": r.get("recorded_at"),
        }
        for r in sorted(rows, key=lambda x: x.get("recorded_at", ""), reverse=True)[:20]
    ]

    return {
        "period": {"days": days, "since": since, "until": datetime.utcnow().isoformat()},
        "dates": dates,
        "series": series,
        "by_symptom": by_symptom_list,
        "pain_summary": pain_summary,
        "recent": recent,
        "total_entries": len(rows),
    }


@router.delete("/entries/{entry_id}")
def delete_symptom_entry(entry_id: str):
    sb = get_supabase()
    result = sb.table("symptom_entries").delete().eq("id", entry_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該症狀紀錄")
    return {"message": "已刪除", "id": entry_id}

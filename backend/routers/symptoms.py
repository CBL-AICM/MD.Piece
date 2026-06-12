import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.security import current_user_optional, enforce_patient_scope
from backend.services.ai_analyzer import analyze_symptoms

router = APIRouter()

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
async def analyze(body: SymptomAnalysisRequest, me: dict | None = Depends(current_user_optional)):
    """AI 症狀分析。"""
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="請提供至少一個症狀")
    # 已登入時，分析所附的 patient_id 必須是自己（症狀會寫入 symptoms_log）。
    enforce_patient_scope(body.patient_id, me)

    # 如果有 patient_id，取得病患資料作為參考（DB 失敗就略過，不擋分析）
    patient_info = None
    if body.patient_id:
        try:
            sb = get_supabase()
            result = sb.table("patients").select("name,age,gender").eq("id", body.patient_id).execute()
            if result.data:
                patient_info = result.data[0]
            else:
                # 匿名 demo 用戶 — 補一筆最小 patients 列，避免 symptoms_log FK 違反
                try:
                    sb.table("patients").insert({"id": body.patient_id, "name": "匿名", "age": 0}).execute()
                except Exception as e2:
                    import logging
                    logging.getLogger(__name__).warning(f"建立匿名 patient 失敗（不阻擋分析）：{e2}")
        except Exception as e:
            # patients 表查不到 / RLS / DB offline 都不阻擋分析；patient_info 就空著
            import logging
            logging.getLogger(__name__).warning(f"取病患資料失敗（不阻擋分析）：{e}")

    # 呼叫 AI 分析
    ai_result = await analyze_symptoms(
        symptoms=body.symptoms,
        patient_age=patient_info.get("age") if patient_info else None,
        patient_gender=patient_info.get("gender") if patient_info else None,
    )

    # 記錄到 symptoms_log（FK 缺失 / RLS / 表沒建都不該擋住分析回傳）
    if body.patient_id:
        try:
            sb = get_supabase()
            sb.table("symptoms_log").insert({
                "patient_id": body.patient_id,
                "symptoms": body.symptoms,
                "ai_response": ai_result,
            }).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"寫入 symptoms_log 失敗（不阻擋回傳）：{e}")

    return ai_result


@router.get("/history/{patient_id}")
def get_symptom_history(patient_id: str, me: dict | None = Depends(current_user_optional)):
    """取得病患的症狀分析歷史。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    result = sb.table("symptoms_log").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"history": result.data}


@router.delete("/history/{patient_id}/{log_id}")
def delete_symptom_history(patient_id: str, log_id: str, me: dict | None = Depends(current_user_optional)):
    """刪除單筆症狀分析紀錄；patient_id 對得上才刪。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    result = (
        sb.table("symptoms_log")
        .delete()
        .eq("id", log_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到這筆紀錄或不屬於該病患")
    return {"deleted": log_id}


# ─── 症狀日記條目（病患自記的症狀，原本只存在前端 localStorage）────────────
# 對應 symptom_entries 表；以 (patient_id, client_id) 幂等 upsert，
# 讓前端既有條目能補傳、不重複。與上面的 symptoms_log（AI 分析紀錄）分開存。

class SymptomEntryUpsert(BaseModel):
    patient_id: str
    client_id: str
    category_id: str = ""
    intensity: int | None = None
    frequency: int | None = None
    notes: str = ""
    proxy_for: str | None = None
    recorded_at: str | None = None


def _public_entry(row: dict) -> dict:
    """DB 列 → 前端 symptom entry 形狀（與 localStorage 內結構一致）。"""
    return {
        "id": row.get("client_id") or row.get("id"),
        "categoryId": row.get("category_id") or "",
        "intensity": row.get("intensity"),
        "frequency": row.get("frequency"),
        "notes": row.get("notes") or "",
        "proxy_for": row.get("proxy_for"),
        "recordedAt": row.get("recorded_at"),
    }


@router.get("/entries")
def list_symptom_entries(patient_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    res = (
        sb.table("symptom_entries")
        .select("*")
        .eq("patient_id", patient_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    return {"entries": [_public_entry(r) for r in (res.data or [])]}


@router.post("/entries")
def upsert_symptom_entry(body: SymptomEntryUpsert, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
    sb = get_supabase()
    existing = (
        sb.table("symptom_entries")
        .select("id")
        .eq("patient_id", body.patient_id)
        .eq("client_id", body.client_id)
        .execute()
    )
    fields = {
        "category_id": body.category_id,
        "intensity": body.intensity,
        "frequency": body.frequency,
        "notes": body.notes,
        "proxy_for": body.proxy_for,
    }
    if existing.data:
        (
            sb.table("symptom_entries")
            .update(fields)
            .eq("patient_id", body.patient_id)
            .eq("client_id", body.client_id)
            .execute()
        )
    else:
        payload = {"patient_id": body.patient_id, "client_id": body.client_id, **fields}
        if body.recorded_at:
            payload["recorded_at"] = body.recorded_at
        sb.table("symptom_entries").insert(payload).execute()
    return {"status": "ok", "client_id": body.client_id}


@router.delete("/entries/{patient_id}/{client_id}")
def delete_symptom_entry(patient_id: str, client_id: str, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    (
        sb.table("symptom_entries")
        .delete()
        .eq("patient_id", patient_id)
        .eq("client_id", client_id)
        .execute()
    )
    return {"deleted": client_id}

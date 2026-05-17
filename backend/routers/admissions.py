"""
住院 / 長期療程 router。

涵蓋兩種情境：
  - acute：急性住院（有 admit_date、discharge_date、ward）
  - chronic_infusion：長期週期性給藥（例如生物製劑每 4 週一次）

本檔只負責「療程本體」的 CRUD 與排定給藥節奏 / 紀錄施打。
提醒（誰 / 何時叮咚）交給 reminders / bell_reminders 模組去讀
admission_medications.next_due_date，這邊不重做一套。
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_patient_exists(sb, patient_id: str) -> None:
    """
    確保 patients 表裡有對應的 row，避免 admissions.patient_id FK 失敗。
    與 medications.py 同 pattern：找不到就用 users.nickname 建 stub，
    再不行就用 "訪客"。
    """
    try:
        existing = sb.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        if existing.data:
            return
        name = "訪客"
        try:
            u = sb.table("users").select("nickname").eq("id", patient_id).limit(1).execute()
            if u.data and u.data[0].get("nickname"):
                name = u.data[0]["nickname"]
        except Exception:
            pass
        sb.table("patients").insert({"id": patient_id, "name": name, "age": 0}).execute()
    except Exception as e:
        logger.warning(f"ensure_patient_exists skipped for {patient_id}: {e}")


# ── Models ────────────────────────────────────────────────

class AdmissionCreate(BaseModel):
    patient_id: str
    type: str = "acute"  # acute | chronic_infusion
    admit_date: Optional[str] = None
    discharge_date: Optional[str] = None
    attending_doctor_id: Optional[str] = None
    diagnosis: Optional[str] = None
    diagnosis_icd10: Optional[str] = None
    ward: Optional[str] = None
    notes: Optional[str] = None


class AdmissionUpdate(BaseModel):
    type: Optional[str] = None
    admit_date: Optional[str] = None
    discharge_date: Optional[str] = None
    attending_doctor_id: Optional[str] = None
    diagnosis: Optional[str] = None
    diagnosis_icd10: Optional[str] = None
    ward: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AdmissionMedicationCreate(BaseModel):
    admission_id: str
    name: str
    medication_id: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    next_due_date: Optional[str] = None
    notes: Optional[str] = None


class AdmissionMedicationUpdate(BaseModel):
    name: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    next_due_date: Optional[str] = None
    notes: Optional[str] = None


class DoseRecord(BaseModel):
    admission_medication_id: str
    given_at: Optional[str] = None
    actual_dose: Optional[str] = None
    given_by: Optional[str] = None
    notes: Optional[str] = None
    # 完成這次施打後，下次預定日（前端依 frequency 自行算好送上來，
    # 後端不解析 "每 4 週" 這種自由文字字串）
    next_due_date: Optional[str] = None


_ALLOWED_TYPES = {"acute", "chronic_infusion"}
_ALLOWED_STATUS = {"active", "discharged", "cancelled"}


# ── 住院 / 療程 CRUD ──────────────────────────────────────

@router.get("/")
def list_admissions(
    patient_id: str = Query(...),
    status: Optional[str] = Query(None, description="active / discharged / cancelled"),
):
    sb = get_supabase()
    q = sb.table("admissions").select("*").eq("patient_id", patient_id)
    if status:
        q = q.eq("status", status)
    result = q.order("admit_date", desc=True).execute()
    return {"admissions": result.data or []}


@router.get("/{admission_id}")
def get_admission(admission_id: str):
    sb = get_supabase()
    result = sb.table("admissions").select("*").eq("id", admission_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    admission = result.data[0]
    meds = (
        sb.table("admission_medications")
        .select("*")
        .eq("admission_id", admission_id)
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )
    admission["medications"] = meds
    return admission


@router.post("/")
def create_admission(body: AdmissionCreate):
    if body.type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"type 必須是 {_ALLOWED_TYPES} 之一")
    sb = get_supabase()
    _ensure_patient_exists(sb, body.patient_id)
    data = body.model_dump(exclude_none=True)
    if not data.get("admit_date"):
        data["admit_date"] = datetime.utcnow().isoformat()
    try:
        result = sb.table("admissions").insert(data).execute()
    except Exception as e:
        logger.error(f"Create admission failed: {e}")
        raise HTTPException(status_code=400, detail="新增住院/療程失敗")
    if not result.data:
        raise HTTPException(status_code=400, detail="新增失敗（資料庫未回傳資料）")
    return result.data[0]


@router.put("/{admission_id}")
def update_admission(admission_id: str, body: AdmissionUpdate):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "type" in data and data["type"] not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"type 必須是 {_ALLOWED_TYPES} 之一")
    if "status" in data and data["status"] not in _ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail=f"status 必須是 {_ALLOWED_STATUS} 之一")
    sb = get_supabase()
    result = sb.table("admissions").update(data).eq("id", admission_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    return result.data[0]


@router.delete("/{admission_id}")
def delete_admission(admission_id: str):
    """整筆住院 / 療程砍掉。
    順手把底下 admission_medications + admission_medication_doses 一起清掉，
    避免 schema 沒設 FK cascade 時殘留孤兒列。"""
    sb = get_supabase()
    parent = sb.table("admissions").select("id").eq("id", admission_id).limit(1).execute()
    if not parent.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")

    med_rows = (
        sb.table("admission_medications")
        .select("id")
        .eq("admission_id", admission_id)
        .execute()
        .data
        or []
    )
    med_ids = [m["id"] for m in med_rows]
    if med_ids:
        try:
            sb.table("admission_medication_doses").delete().in_("admission_medication_id", med_ids).execute()
        except Exception as e:
            logger.warning(f"Cleanup doses for {admission_id} skipped: {e}")
        try:
            sb.table("admission_medications").delete().eq("admission_id", admission_id).execute()
        except Exception as e:
            logger.warning(f"Cleanup admission_medications for {admission_id} skipped: {e}")

    sb.table("admissions").delete().eq("id", admission_id).execute()
    return {"deleted": admission_id, "medications_deleted": len(med_ids)}


@router.post("/{admission_id}/discharge")
def discharge_admission(admission_id: str, discharge_date: Optional[str] = None):
    """出院 / 結案：把 status 改成 discharged 並寫入 discharge_date。"""
    sb = get_supabase()
    data = {
        "status": "discharged",
        "discharge_date": discharge_date or datetime.utcnow().isoformat(),
    }
    result = sb.table("admissions").update(data).eq("id", admission_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    return result.data[0]


# ── 排定給藥（住院期間 / 療程內）─────────────────────────

@router.post("/medications")
def add_admission_medication(body: AdmissionMedicationCreate):
    """在某次住院 / 療程下排定一筆給藥節奏。"""
    sb = get_supabase()

    parent = sb.table("admissions").select("id").eq("id", body.admission_id).limit(1).execute()
    if not parent.data:
        raise HTTPException(status_code=404, detail="找不到對應的住院/療程紀錄")

    data = body.model_dump(exclude_none=True)
    try:
        result = sb.table("admission_medications").insert(data).execute()
    except Exception as e:
        logger.error(f"Add admission medication failed: {e}")
        raise HTTPException(status_code=400, detail="新增療程藥物失敗")
    return result.data[0]


@router.put("/medications/{admission_medication_id}")
def update_admission_medication(admission_medication_id: str, body: AdmissionMedicationUpdate):
    """改一筆排定給藥（藥名 / 劑量 / 頻率 / 下次預定日）。"""
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    sb = get_supabase()
    result = (
        sb.table("admission_medications")
        .update(data)
        .eq("id", admission_medication_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到對應的療程藥物")
    return result.data[0]


@router.delete("/medications/{admission_medication_id}")
def delete_admission_medication(admission_medication_id: str):
    """刪掉一筆排定給藥，連同它的施打紀錄一起清掉。"""
    sb = get_supabase()
    parent = (
        sb.table("admission_medications")
        .select("id")
        .eq("id", admission_medication_id)
        .limit(1)
        .execute()
    )
    if not parent.data:
        raise HTTPException(status_code=404, detail="找不到對應的療程藥物")
    try:
        sb.table("admission_medication_doses").delete().eq("admission_medication_id", admission_medication_id).execute()
    except Exception as e:
        logger.warning(f"Cleanup doses for med {admission_medication_id} skipped: {e}")
    sb.table("admission_medications").delete().eq("id", admission_medication_id).execute()
    return {"deleted": admission_medication_id}


@router.get("/medications/upcoming")
def upcoming_doses(
    patient_id: str = Query(...),
    days: int = Query(14, ge=1, le=90, description="未來幾天內到期的給藥"),
):
    """
    取得該病患未來 N 天內到期的給藥。

    供 reminders 模組消費：reminders.py 可定期 poll 這個端點，
    把到期項目轉成提醒訊息，避免本 router 自己再做一套提醒系統。
    """
    sb = get_supabase()
    admissions = (
        sb.table("admissions")
        .select("id, type, diagnosis, status")
        .eq("patient_id", patient_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    if not admissions:
        return {"upcoming": []}

    admission_by_id = {a["id"]: a for a in admissions}
    now_iso = datetime.utcnow().isoformat()
    upcoming: list[dict] = []
    for adm_id in admission_by_id:
        meds = (
            sb.table("admission_medications")
            .select("*")
            .eq("admission_id", adm_id)
            .execute()
            .data
            or []
        )
        for m in meds:
            due = m.get("next_due_date")
            if not due:
                continue
            if due >= now_iso:
                # 簡單時間比較：ISO 8601 字串可直接字典序比較
                upcoming.append({
                    **m,
                    "admission": admission_by_id[adm_id],
                })

    upcoming.sort(key=lambda x: x.get("next_due_date") or "")
    return {"upcoming": upcoming, "days": days}


@router.post("/medications/{admission_medication_id}/dose")
def record_dose(admission_medication_id: str, body: DoseRecord):
    """記錄一次實際施打，並更新 last_given_at / next_due_date。"""
    sb = get_supabase()
    parent = (
        sb.table("admission_medications")
        .select("id")
        .eq("id", admission_medication_id)
        .limit(1)
        .execute()
    )
    if not parent.data:
        raise HTTPException(status_code=404, detail="找不到對應的療程藥物")

    given_at = body.given_at or datetime.utcnow().isoformat()
    dose_row = {
        "admission_medication_id": admission_medication_id,
        "given_at": given_at,
        "actual_dose": body.actual_dose,
        "given_by": body.given_by,
        "notes": body.notes,
    }
    try:
        result = sb.table("admission_medication_doses").insert(dose_row).execute()
    except Exception as e:
        logger.error(f"Record dose failed: {e}")
        raise HTTPException(status_code=400, detail="記錄施打失敗")

    update = {"last_given_at": given_at}
    if body.next_due_date:
        update["next_due_date"] = body.next_due_date
    sb.table("admission_medications").update(update).eq("id", admission_medication_id).execute()

    return {"dose": result.data[0] if result.data else dose_row, "updated": update}


@router.get("/medications/{admission_medication_id}/doses")
def list_doses(admission_medication_id: str):
    sb = get_supabase()
    result = (
        sb.table("admission_medication_doses")
        .select("*")
        .eq("admission_medication_id", admission_medication_id)
        .order("given_at", desc=True)
        .execute()
    )
    return {"doses": result.data or []}

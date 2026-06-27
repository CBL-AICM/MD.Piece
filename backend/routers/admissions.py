"""
住院 / 長期療程 router。

涵蓋兩種情境：
  - acute：急性住院（有 admit_date、discharge_date、ward）
  - chronic_infusion：長期週期性給藥（例如生物製劑每 4 週一次）

本檔只負責「療程本體」的 CRUD 與排定給藥節奏 / 紀錄施打。
提醒（誰 / 何時叮咚）交給 reminders / bell_reminders 模組去讀
admission_medications.next_due_date，這邊不重做一套。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import logging
import math

from backend.db import get_supabase
from backend.data.taiwan_hospitals import TAIWAN_HOSPITALS
from backend.security import current_user_optional, enforce_patient_scope

logger = logging.getLogger(__name__)
router = APIRouter()


def _assert_owns_admission(sb, admission_id: str, me) -> dict:
    """以 admission_id 操作時的擁有權檢查：已登入則該筆 patient_id 必須是自己。"""
    res = sb.table("admissions").select("*").eq("id", admission_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    enforce_patient_scope(res.data[0].get("patient_id"), me)
    return res.data[0]


def _assert_owns_admission_medication(sb, admission_medication_id: str, me) -> dict:
    """以 admission_medication_id 操作時的擁有權檢查：
    先由藥物列反查其 admission_id，再由 admission 反查 patient_id 做 scope 驗證。
    （admission_medications 沒有自己的 patient_id 欄位，只能透過 parent admission 反查。）"""
    res = (
        sb.table("admission_medications")
        .select("*")
        .eq("id", admission_medication_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到對應的療程藥物")
    _assert_owns_admission(sb, res.data[0].get("admission_id"), me)
    return res.data[0]

# 地理圍欄半徑（公尺）— 涵蓋一般院區 + GPS 抖動容差。
GEOFENCE_RADIUS_M = 300


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
    hospital_name: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None


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
    hospital_name: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None


class LocationCheck(BaseModel):
    lat: float
    lng: float


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


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """兩點間球面距離（公尺）。地球半徑取 6_371_000m。"""
    r = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ── 醫院清單（前端 picker 用）─────────────────────────────

@router.get("/hospitals")
def list_hospitals(q: Optional[str] = Query(None, description="醫院名稱關鍵字（模糊比對）")):
    """
    回傳預建的台灣醫院清單供前端 picker 使用。
    不存在 DB，每次直接從 backend/data/taiwan_hospitals.py 讀；
    維護方便，未來增刪不必跑 migration。
    """
    items = TAIWAN_HOSPITALS
    if q:
        key = q.strip()
        if key:
            items = [h for h in items if key in h["name"]]
    return {"hospitals": items, "geofence_radius_m": GEOFENCE_RADIUS_M}


# ── 住院 / 療程 CRUD ──────────────────────────────────────

@router.get("/")
def list_admissions(
    patient_id: str = Query(...),
    status: Optional[str] = Query(None, description="active / discharged / cancelled"),
    me: dict | None = Depends(current_user_optional),
):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    q = sb.table("admissions").select("*").eq("patient_id", patient_id)
    if status:
        q = q.eq("status", status)
    result = q.order("admit_date", desc=True).execute()
    return {"admissions": result.data or []}


@router.get("/{admission_id}")
def get_admission(admission_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    admission = _assert_owns_admission(sb, admission_id, me)
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
def create_admission(body: AdmissionCreate, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
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
def update_admission(admission_id: str, body: AdmissionUpdate, me: dict | None = Depends(current_user_optional)):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "type" in data and data["type"] not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"type 必須是 {_ALLOWED_TYPES} 之一")
    if "status" in data and data["status"] not in _ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail=f"status 必須是 {_ALLOWED_STATUS} 之一")
    sb = get_supabase()
    _assert_owns_admission(sb, admission_id, me)
    result = sb.table("admissions").update(data).eq("id", admission_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    return result.data[0]


@router.delete("/{admission_id}")
def delete_admission(admission_id: str, me: dict | None = Depends(current_user_optional)):
    """整筆住院 / 療程砍掉。
    順手把底下 admission_medications + admission_medication_doses 一起清掉，
    避免 schema 沒設 FK cascade 時殘留孤兒列。"""
    sb = get_supabase()
    _assert_owns_admission(sb, admission_id, me)

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
def discharge_admission(admission_id: str, discharge_date: Optional[str] = None,
                        me: dict | None = Depends(current_user_optional)):
    """出院 / 結案：把 status 改成 discharged 並寫入 discharge_date。"""
    sb = get_supabase()
    _assert_owns_admission(sb, admission_id, me)
    data = {
        "status": "discharged",
        "discharge_date": discharge_date or datetime.utcnow().isoformat(),
    }
    result = sb.table("admissions").update(data).eq("id", admission_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    return result.data[0]


@router.post("/{admission_id}/check-location")
def check_location(admission_id: str, body: LocationCheck, me: dict | None = Depends(current_user_optional)):
    """
    依使用者目前 GPS 位置自動判定是否該結案。

    觸發時機由前端負責：建議在 discharge_date 當天 App 開啟時呼叫一次。
    後端只負責「距離 + 日期」邏輯（規則 5：確定性任務用程式碼，不丟 LLM）。

    回傳：
      in_hospital   : 是否仍在醫院 GEOFENCE_RADIUS_M 內
      distance_m    : 到醫院的距離（公尺，None 表沒登記醫院座標）
      discharge_due : discharge_date 是否已到（含當日）
      action        : auto_discharged | prompt_delay | none
      admission     : 若 action=auto_discharged 則回傳更新後 row
    """
    sb = get_supabase()
    row = sb.table("admissions").select("*").eq("id", admission_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="找不到該住院/療程紀錄")
    adm = row.data[0]
    enforce_patient_scope(adm.get("patient_id"), me)

    # 非 active 的住院不參與自動判定。
    if adm.get("status") != "active":
        return {
            "in_hospital": None,
            "distance_m": None,
            "discharge_due": False,
            "action": "none",
            "reason": "admission_not_active",
        }

    hlat = adm.get("hospital_lat")
    hlng = adm.get("hospital_lng")
    distance_m: Optional[float] = None
    in_hospital: Optional[bool] = None
    if hlat is not None and hlng is not None:
        distance_m = _haversine_m(float(hlat), float(hlng), body.lat, body.lng)
        in_hospital = distance_m <= GEOFENCE_RADIUS_M

    discharge_due = False
    dd = adm.get("discharge_date")
    if dd:
        # discharge_date 可能是 'YYYY-MM-DDTHH:MM:SS' 或 'YYYY-MM-DD'；只比日期。
        try:
            planned = date.fromisoformat(str(dd)[:10])
            discharge_due = date.today() >= planned
        except ValueError:
            discharge_due = False

    # 沒登記醫院座標 → 沒辦法做地理判定，直接返回（前端可選擇 fallback 行為）。
    if in_hospital is None:
        return {
            "in_hospital": None,
            "distance_m": None,
            "discharge_due": discharge_due,
            "action": "none",
            "reason": "no_hospital_coords",
        }

    # 主邏輯：到了預定出院日 + 已離開醫院 → 自動結案。
    if discharge_due and not in_hospital:
        now_iso = datetime.utcnow().isoformat()
        update = {
            "status": "discharged",
            "auto_discharged_at": now_iso,
        }
        # 若使用者沒手動填過 discharge_date 的時段，補上實際結案時間，
        # 方便日後在「我的健康時間軸」（場景 C）顯示真正離院時間。
        if len(str(dd)) <= 10:
            update["discharge_date"] = now_iso
        updated = (
            sb.table("admissions")
            .update(update)
            .eq("id", admission_id)
            .execute()
        )
        return {
            "in_hospital": False,
            "distance_m": distance_m,
            "discharge_due": True,
            "action": "auto_discharged",
            "admission": updated.data[0] if updated.data else None,
        }

    # 到了預定出院日但人還在 → 提示使用者，不自動改 status（規則 12：不暗改）。
    if discharge_due and in_hospital:
        return {
            "in_hospital": True,
            "distance_m": distance_m,
            "discharge_due": True,
            "action": "prompt_delay",
        }

    return {
        "in_hospital": in_hospital,
        "distance_m": distance_m,
        "discharge_due": False,
        "action": "none",
    }


# ── 排定給藥（住院期間 / 療程內）─────────────────────────

@router.post("/medications")
def add_admission_medication(body: AdmissionMedicationCreate, me: dict | None = Depends(current_user_optional)):
    """在某次住院 / 療程下排定一筆給藥節奏。"""
    sb = get_supabase()

    # 擁有權檢查：只能在自己的住院/療程下排藥（順帶確認 parent 存在）。
    _assert_owns_admission(sb, body.admission_id, me)

    data = body.model_dump(exclude_none=True)
    try:
        result = sb.table("admission_medications").insert(data).execute()
    except Exception as e:
        logger.error(f"Add admission medication failed: {e}")
        raise HTTPException(status_code=400, detail="新增療程藥物失敗")
    return result.data[0]


@router.put("/medications/{admission_medication_id}")
def update_admission_medication(admission_medication_id: str, body: AdmissionMedicationUpdate,
                                me: dict | None = Depends(current_user_optional)):
    """改一筆排定給藥（藥名 / 劑量 / 頻率 / 下次預定日）。"""
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    sb = get_supabase()
    # 反查 parent admission 做擁有權檢查，避免改到別人的療程藥物。
    _assert_owns_admission_medication(sb, admission_medication_id, me)
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
def delete_admission_medication(admission_medication_id: str, me: dict | None = Depends(current_user_optional)):
    """刪掉一筆排定給藥，連同它的施打紀錄一起清掉。"""
    sb = get_supabase()
    # 反查 parent admission 做擁有權檢查（同時確認該藥物存在）。
    _assert_owns_admission_medication(sb, admission_medication_id, me)
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
    me: dict | None = Depends(current_user_optional),
):
    """
    取得該病患未來 N 天內到期的給藥。

    供 reminders 模組消費：reminders.py 可定期 poll 這個端點，
    把到期項目轉成提醒訊息，避免本 router 自己再做一套提醒系統。
    """
    enforce_patient_scope(patient_id, me)
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
def record_dose(admission_medication_id: str, body: DoseRecord,
                me: dict | None = Depends(current_user_optional)):
    """記錄一次實際施打，並更新 last_given_at / next_due_date。"""
    sb = get_supabase()
    # 反查 parent admission 做擁有權檢查（同時確認該藥物存在），避免替別人偽造施打。
    _assert_owns_admission_medication(sb, admission_medication_id, me)

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
def list_doses(admission_medication_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    # 反查 parent admission 做擁有權檢查，避免讀到別人的施打紀錄。
    _assert_owns_admission_medication(sb, admission_medication_id, me)
    result = (
        sb.table("admission_medication_doses")
        .select("*")
        .eq("admission_medication_id", admission_medication_id)
        .order("given_at", desc=True)
        .execute()
    )
    return {"doses": result.data or []}

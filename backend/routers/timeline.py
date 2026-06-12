"""我的健康時間軸 — 場景 C：跨次就診整合視圖。

GET /api/timeline?patient_id=...
回傳 list[{date, type, title, summary, icd10, source, importance}]

importance 用來決定前端 Bento Grid 卡片大小：
  - 'high'   → span 2 column
  - 'normal' → span 1 column

資料來源（依序合併）：
  1. patient_records / records（就診紀錄）
  2. lab_results（檢驗報告）
  3. medications（用藥變動）
  4. admissions（住院）

若資料庫尚未連線（Supabase 環境變數缺失），回傳空陣列 + meta.db_offline=true，
讓前端可以平滑 fallback 到既有的 localStorage 時間軸。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user_optional, enforce_patient_scope

logger = logging.getLogger(__name__)
router = APIRouter()


# 時間軸事件型別 → 嚴重度顏色（對齊 docs/research/ui_color_research.md §4）
# 注意：與 triage.severity_color_for 同一套 token，前端用 data-severity
_TYPE_TO_SEVERITY = {
    "admission":   "er",        # 住院事件
    "lab":         "regional",  # 檢驗報告
    "visit":       "clinic",    # 一般就診
    "medication":  "self",      # 用藥變動
    "self_report": "self",      # 自我上傳
}


class TimelineEntry(BaseModel):
    id: str
    date: str            # ISO 日期：YYYY-MM-DD
    type: str            # admission / lab / visit / medication / self_report
    title: str
    summary: str = ""
    icd10: Optional[str] = None
    source: str = ""     # 醫院 / 上傳檔名
    importance: str = "normal"   # normal | high
    severity_color: str = "self"


def _classify_importance(entry_type: str, icd10: Optional[str]) -> str:
    """高重要性 = 住院 / 急性 ICD-10 / 報告含異常值。
    前端 Bento Grid 會把 high 卡片做成 span-2。
    """
    if entry_type == "admission":
        return "high"
    if icd10 and icd10[0] in ("I", "C"):  # I = 循環系統、C = 腫瘤
        return "high"
    return "normal"


def _normalize_date(raw: Optional[str]) -> str:
    """把各路欄位來的日期都標準化為 YYYY-MM-DD。"""
    if not raw:
        return ""
    return str(raw)[:10]


def _fetch_safely(sb, table: str, patient_id: str):
    try:
        result = sb.table(table).select("*").eq("patient_id", patient_id).execute()
        return getattr(result, "data", None) or []
    except Exception as e:
        logger.info(f"timeline: table {table} unavailable: {e}")
        return []


@router.get("")
def get_timeline(
    patient_id: str = Query(..., description="病患 ID"),
    limit: int = Query(100, ge=1, le=500, description="最多回傳幾筆"),
    me: dict | None = Depends(current_user_optional),
):
    """取得患者的健康事件時間軸（時間倒序）。"""
    enforce_patient_scope(patient_id, me)
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"timeline: DB offline: {e}")
        return {"entries": [], "meta": {"db_offline": True, "count": 0}}

    entries: list[dict] = []

    # 1. 就診紀錄（visit）
    for r in _fetch_safely(sb, "records", patient_id):
        icd = r.get("icd10") or r.get("diagnosis_code")
        entries.append(
            {
                "id": f"rec-{r.get('id')}",
                "date": _normalize_date(r.get("visit_date") or r.get("created_at")),
                "type": "visit",
                "title": r.get("diagnosis") or r.get("title") or "就診紀錄",
                "summary": r.get("notes") or r.get("summary") or "",
                "icd10": icd,
                "source": r.get("hospital") or r.get("source") or "",
                "importance": _classify_importance("visit", icd),
                "severity_color": _TYPE_TO_SEVERITY["visit"],
            }
        )

    # 2. 檢驗報告（lab）
    for r in _fetch_safely(sb, "lab_results", patient_id):
        is_abnormal = bool(r.get("is_abnormal") or r.get("flagged"))
        entries.append(
            {
                "id": f"lab-{r.get('id')}",
                "date": _normalize_date(r.get("test_date") or r.get("created_at")),
                "type": "lab",
                "title": r.get("test_name") or "檢驗報告",
                "summary": r.get("summary") or r.get("interpretation") or "",
                "icd10": None,
                "source": r.get("lab_name") or r.get("hospital") or "",
                "importance": "high" if is_abnormal else "normal",
                "severity_color": _TYPE_TO_SEVERITY["lab"],
            }
        )

    # 3. 住院（admission）
    for r in _fetch_safely(sb, "admissions", patient_id):
        entries.append(
            {
                "id": f"adm-{r.get('id')}",
                "date": _normalize_date(r.get("admit_date") or r.get("created_at")),
                "type": "admission",
                "title": r.get("reason") or "住院事件",
                "summary": r.get("notes") or "",
                "icd10": r.get("icd10"),
                "source": r.get("hospital") or "",
                "importance": "high",
                "severity_color": _TYPE_TO_SEVERITY["admission"],
            }
        )

    # 4. 用藥變動（medication_changes）
    for r in _fetch_safely(sb, "medication_changes", patient_id):
        entries.append(
            {
                "id": f"med-{r.get('id')}",
                "date": _normalize_date(r.get("change_date") or r.get("created_at")),
                "type": "medication",
                "title": r.get("medication_name") or "用藥調整",
                "summary": r.get("change_reason") or r.get("notes") or "",
                "icd10": None,
                "source": r.get("prescribed_by") or "",
                "importance": "normal",
                "severity_color": _TYPE_TO_SEVERITY["medication"],
            }
        )

    # 排序：時間倒序，無日期者沉到尾
    entries.sort(key=lambda e: e.get("date") or "0000-00-00", reverse=True)
    truncated = entries[:limit]

    return {
        "entries": truncated,
        "meta": {
            "db_offline": False,
            "count": len(truncated),
            "total": len(entries),
        },
    }

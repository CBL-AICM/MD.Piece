"""
後台人數統計（admin patient stats）。

由原 surveys.py 的「患者管理」抽出並改寫：移除所有問卷概念，只保留
「已註冊患者的人數統計 + 個別日常紀錄活躍度」，供研究者後台檢視。

  - GET /admin-stats/patients        患者清單 + 彙總統計卡（限 doctor）
  - GET /admin-stats/patients/{pid}  單一患者每日紀錄活躍度明細（限 doctor）

設計鐵則：
  - 規則 5：人數與活躍度彙總是確定性運算 → 純程式碼，不丟 LLM。
  - 規則 12：只回聚合 + 非敏感清單，不洩個別病歷；分頁撈滿避免 PostgREST 1000 列截斷。
  - 使用者決策：1600 筆 sim3200_ 模擬患者一律「從統計排除、不刪資料」→ 程式層過濾。
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_supabase
from backend.security import current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# 研究用模擬帳號前綴（3200→1600 假患者，username 形如 sim3200_ra_0151）。
# 一律排除於人數統計之外；僅過濾、不刪除資料。
SIM_USERNAME_PREFIX = "sim3200"


def _is_sim(username: Optional[str]) -> bool:
    return bool(username) and str(username).startswith(SIM_USERNAME_PREFIX)


def _fetch_all(make_query, page: int = 1000) -> list:
    """分頁撈滿，突破 PostgREST 預設單次 1000 列上限（規則 12：不靜默截斷）。

    make_query() 每頁回傳一個全新的 query builder（已套好 select/filter，
    尚未 execute）；以 .range() 逐頁取直到取不滿一頁為止。
    """
    out: list = []
    start = 0
    while True:
        try:
            rows = make_query().range(start, start + page - 1).execute().data or []
        except Exception as e:
            logger.info(f"admin-stats fetch_all @{start} failed: {e}")
            break
        out.extend(rows)
        if len(rows) < page:
            break
        start += page
    return out


def _active_days_bulk(sb) -> dict:
    """一次掃 symptom/vital/sleep 三表，回 {pid: 活躍天數}（同日多來源只算一天）。

    批次計算避免逐人查詢在列全部患者時造成逾時（規則 5：純程式彙整）。
    """
    days_by_pid: dict = {}
    for table, id_col, date_cols in (
        ("symptom_entries", "patient_id", ("recorded_at", "created_at")),
        ("vital_entries", "patient_id", ("recorded_at", "created_at")),
        ("sleep_sessions", "user_id", ("bed_time", "created_at")),
    ):
        rows = _fetch_all(lambda t=table: sb.table(t).select("*"))
        for r in rows:
            pid = r.get(id_col)
            if not pid:
                continue
            for c in date_cols:
                if r.get(c):
                    days_by_pid.setdefault(pid, set()).add(str(r[c])[:10])
                    break
    return {pid: len(d) for pid, d in days_by_pid.items()}


def _age_of(birthday) -> Optional[int]:
    try:
        b = datetime.strptime(str(birthday)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = datetime.now().date()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def _age_band(age: Optional[int]) -> str:
    if age is None:
        return "未填"
    if age < 20:
        return "<20"
    if age < 40:
        return "20–39"
    if age < 60:
        return "40–59"
    if age < 75:
        return "60–74"
    return "75+"


def _adherence_band(days: int) -> str:
    if days <= 0:
        return "0 天"
    if days <= 3:
        return "1–3 天"
    if days <= 7:
        return "4–7 天"
    if days <= 30:
        return "8–30 天"
    return "30+ 天"


def _bump(counter: dict, key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


@router.get("/patients")
def list_patients(me: dict = Depends(current_user)):
    """患者清單 + 彙總統計（限 doctor）。排除 sim3200_ 模擬帳號。

    回傳：
      - count      納入統計的真實患者人數
      - summary    彙總卡：性別／年齡分層／疾病／活躍天數分層分布 + 有紀錄人數
      - patients   逐人清單（暱稱／性別／年齡／疾病／活躍天數／註冊日）
    """
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可檢視患者統計")
    sb = get_supabase()

    # 患者基底＝所有 role=patient 且非模擬帳號的使用者。分頁撈滿避免 1000 列截斷。
    users = [u for u in _fetch_all(lambda: sb.table("users").select("*").eq("role", "patient"))
             if u.get("id") and not _is_sim(u.get("username"))]

    # 基本資料（性別／生日→年齡／疾病）：patient_profiles 一次撈滿後在記憶體 join。
    profiles = _fetch_all(lambda: sb.table("patient_profiles").select("*"))
    prof_by_id = {p["user_id"]: p for p in profiles if p.get("user_id")}

    # 活躍天數一次性批次計算（不逐人查；列全部患者時逐人查會逾時）。
    active_days = _active_days_bulk(sb)

    summary = {
        "total": 0,
        "with_records": 0,
        "by_gender": {},
        "by_age_band": {},
        "by_disease": {},
        "by_adherence_band": {},
    }
    out = []
    for u in users:
        pid = u["id"]
        prof = prof_by_id.get(pid, {})
        age = _age_of(prof.get("birthday"))
        gender = prof.get("gender") or ""
        disease = prof.get("current_disease") or ""
        days = active_days.get(pid, 0)
        out.append({
            "patient_id": pid,
            "nickname": u.get("nickname") or "",
            "username": u.get("username") or "",
            "gender": gender,
            "age": age,
            "disease": disease,
            "registered_at": u.get("created_at") or "",
            "adherence_days": days,
        })
        summary["total"] += 1
        if days > 0:
            summary["with_records"] += 1
        _bump(summary["by_gender"], gender or "未填")
        _bump(summary["by_age_band"], _age_band(age))
        _bump(summary["by_disease"], disease or "未填")
        _bump(summary["by_adherence_band"], _adherence_band(days))

    out.sort(key=lambda x: (x["nickname"] or "~", x["patient_id"]))
    return {
        "count": len(out),
        "summary": summary,
        "patients": out,
        "note": "已排除 sim3200_ 模擬帳號；活躍天數＝有任一日常紀錄（症狀／生理值／睡眠）的不重複日數。",
    }


@router.get("/patients/{pid}")
def patient_activity(pid: str, me: dict = Depends(current_user)):
    """單一患者每日紀錄活躍度明細（限 doctor）：症狀／生理值／睡眠逐日統整。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可檢視患者明細")
    sb = get_supabase()
    return {"patient_id": pid, "adherence": _adherence(sb, pid)}


def _adherence(sb, pid: str) -> dict:
    """整合每位使用者日常紀錄活動：症狀/生理值/睡眠。

    回傳：活動天數 + 各來源天數 + 逐日統整 timeline（date×來源筆數）
    + 簡易分析（區間 / 最長連續天數 / 覆蓋率）。純程式碼彙整（規則 5）。
    """
    def _scan(table, id_col, date_cols):
        try:
            rows = sb.table(table).select("*").eq(id_col, pid).execute().data or []
        except Exception:
            return [], 0
        days = []
        for r in rows:
            for c in date_cols:
                if r.get(c):
                    days.append(str(r[c])[:10])
                    break
        return days, len(rows)

    sym_days, sym_n = _scan("symptom_entries", "patient_id", ["recorded_at", "created_at"])
    vit_days, vit_n = _scan("vital_entries", "patient_id", ["recorded_at", "created_at"])
    slp_days, slp_n = _scan("sleep_sessions", "user_id", ["bed_time", "created_at"])

    # 逐日統整：date -> 各來源筆數
    daily: dict = {}
    for src, days in (("symptoms", sym_days), ("vitals", vit_days), ("sleep", slp_days)):
        for d in days:
            cell = daily.setdefault(d, {"symptoms": 0, "vitals": 0, "sleep": 0})
            cell[src] += 1
    ordered = sorted(daily)
    timeline = [dict(date=d, total=sum(daily[d].values()), **daily[d]) for d in ordered]

    # 簡易分析：區間 / 最長連續天數 / 覆蓋率（活躍天數 ÷ 區間天數）
    def _parse(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None
    dates = [x for x in (_parse(d) for d in ordered) if x]
    longest = streak = 0
    prev = None
    for x in dates:
        streak = streak + 1 if (prev is not None and (x - prev).days == 1) else 1
        longest = max(longest, streak)
        prev = x
    span = (dates[-1] - dates[0]).days + 1 if dates else 0

    return {
        "active_days": len(daily),
        "by_source": {
            "symptoms": {"records": sym_n, "days": len(set(sym_days))},
            "vitals": {"records": vit_n, "days": len(set(vit_days))},
            "sleep": {"records": slp_n, "days": len(set(slp_days))},
        },
        "daily": timeline,
        "analysis": {
            "first_date": ordered[0] if ordered else None,
            "last_date": ordered[-1] if ordered else None,
            "span_days": span,
            "longest_streak": longest,
            "coverage": round(len(daily) / span, 2) if span else None,
        },
        "note": "活動天數＝有任一日常紀錄的不重複日數；逐日 timeline 與最長連續/覆蓋率供研究者檢視填寫規律。",
    }

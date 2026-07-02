"""
健康積分／獎勵中心 API。

把使用者「已經在做的事」換算成積分、等級、徽章與可兌換獎勵：
  - 每日打卡、連續打卡、情緒/服藥紀錄 → 自動累積積分（唯讀換算，不需新操作）
  - 兌換獎勵 → 記一筆兌換意願（status='requested'），實品由院方線下發放

事件流：
  GET  /rewards/summary      唯讀彙整：earned/available、等級、連續、徽章、加分明細
  GET  /rewards/catalog      兌換清單（標出目前是否買得起）
  GET  /rewards/redemptions  我的兌換紀錄
  POST /rewards/redeem       兌換一項（檢查餘額 → 寫入 reward_redemptions）

設計鐵則：
  - 規則 5：得分／等級／徽章／可否兌換都在 rewards_rules.py 用純算術算，零 LLM。
  - 規則 2/3：積分是對既有紀錄表的唯讀換算，不改任何既有功能或寫入流程。
  - 規則 7：讀取端沿用 sibling 日常紀錄 router（emotions/symptoms/vitals）「帶
    patient_id、不強制登入」的慣例（那些底層資料本來就這樣讀，demo 帳號也能用）。
    若日後全 App 改走 patients.py 的 JWT 自存取模式，本 router 應一起改、勿混用。
  - 規則 12：唯一新增的寫入（兌換）若因 reward_redemptions 尚未建表而失敗，
    明確回報並指向 migration，不靜默吞掉。
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user, current_user_optional, enforce_patient_scope
from backend.utils import rewards_rules as rules

logger = logging.getLogger(__name__)
router = APIRouter()

# 哪些表算「打卡」：(table, id 欄, 取日期的候選欄, 來源標籤)。
# 注意 sleep_sessions 用 user_id，其餘用 patient_id（兩者皆＝user.id）。
_CHECKIN_SOURCES = [
    ("symptom_entries", "patient_id", ["recorded_at", "created_at"], "symptom"),
    ("vital_entries", "patient_id", ["recorded_at", "created_at"], "vital"),
    ("emotions", "patient_id", ["created_at"], "emotion"),
    ("sleep_sessions", "user_id", ["bed_time", "created_at"], "sleep"),
    ("medication_logs", "patient_id", ["taken_at", "created_at"], "medication"),
    ("diet_records", "patient_id", ["eaten_at", "created_at"], "diet"),
]

# 來源標籤 → 中文（給前端 ledger 顯示「為什麼得分」；憲法 2 可解釋）。
_SOURCE_ZH = {
    "symptom": "症狀", "vital": "生理", "emotion": "情緒",
    "sleep": "睡眠", "medication": "服藥", "diet": "飲食",
}


class RedeemRequest(BaseModel):
    patient_id: str
    reward_id: str


# 各紀錄表的時間戳都以 UTC 存（如 medications.py 的 datetime.utcnow()）。積分／連續／
# 拼圖都是以「使用者所在時區的日曆日」計，台灣為 UTC+8，直接切 UTC 字串前 10 碼會把
# 早上 8 點前的紀錄算到前一天。沿用 repo 既有慣例（diet.py 的 utcnow()+timedelta(hours=8)）。
_TW_OFFSET = timedelta(hours=8)


def _local_day(raw):
    """把資料表存的 UTC 時間戳換算成台灣（+8）的日曆日 'YYYY-MM-DD'。
    純日期字串（無時間部分）無時區可調，原樣取前 10 碼；解析失敗亦退回前 10 碼（不丟例外）。"""
    s = str(raw)
    head = s[:10]
    if len(s) <= 10 or s[10] not in ("T", " "):
        return head
    try:
        dt = datetime.strptime(s[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return head
    return (dt + _TW_OFFSET).strftime("%Y-%m-%d")


def _norm_month(ym):
    """把 'YYYY-M' / 'YYYY-MM' 正規化成零補位的 'YYYY-MM'；格式不對回原字串前 7 碼。
    避免 month=2026-6 這種未補位字串比不到零補位的日期鍵而回傳全鎖拼圖。"""
    parts = str(ym).split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}"
    return str(ym)[:7]


def _scan_days(sb, table, id_col, date_cols, pid):
    """撈某表屬於該使用者的紀錄，回 (該表每列的台灣打卡日清單, 總列數)。
    表不存在或讀取失敗就回 ([], 0)（唯讀換算的容錯：缺一張表不該讓整頁掛掉）。"""
    try:
        rows = sb.table(table).select("*").eq(id_col, pid).execute().data or []
    except Exception as exc:
        logger.info("rewards scan %s failed: %s", table, type(exc).__name__)
        return [], 0
    days = []
    for r in rows:
        for c in date_cols:
            if r.get(c):
                days.append(_local_day(r[c]))
                break
    return days, len(rows)


def _gather_activity(sb, pid):
    """從各既有資料表組出 rewards_rules 需要的 activity dict，外加可解釋用的
    逐日來源（day_sources）。純彙整、不寫入任何資料。"""
    day_sources: dict[str, set] = {}
    emotion_days: set[str] = set()
    medication_log_count = 0
    for table, id_col, date_cols, label in _CHECKIN_SOURCES:
        days, nrows = _scan_days(sb, table, id_col, date_cols, pid)
        for d in days:
            day_sources.setdefault(d, set()).add(label)
            if label == "emotion":
                emotion_days.add(d)
        if label == "medication":
            # 服藥打卡次數＝該表列數，沿用上面那次掃描，免再對 medication_logs 多查一次
            medication_log_count = nrows

    active_days = sorted(day_sources.keys())
    longest, current = rules.compute_streaks(active_days)
    triple_day = any({"symptom", "vital", "emotion"} <= s for s in day_sources.values())

    activity = {
        "active_day_count": len(active_days),
        "longest_streak": longest,
        "current_streak": current,
        "emotion_days": len(emotion_days),
        "medication_log_count": medication_log_count,
        "triple_day": triple_day,
    }
    return activity, day_sources


def _month_activity(day_sources, year_month):
    """把全量的 day_sources 過濾到指定月份（'YYYY-MM'），組出
    rewards_rules.puzzle_board 需要的 month-scoped activity dict。純過濾＋重算，
    不另外讀 DB（沿用 summary 已撈好的逐日來源；規則 2/3：不重複查表）。"""
    prefix = _norm_month(year_month)
    month_days = {d: s for d, s in day_sources.items() if str(d)[:7] == prefix}
    active_days = sorted(month_days.keys())
    longest, _current = rules.compute_streaks(active_days)
    emotion_days = sum(1 for s in month_days.values() if "emotion" in s)
    triple_day = any({"symptom", "vital", "emotion"} <= s for s in month_days.values())
    return {
        "active_days": len(active_days),
        "emotion_days": emotion_days,
        "longest_streak": longest,
        "triple_day": triple_day,
    }


def _completed_puzzle_months(day_sources):
    """掃所有「有任何紀錄的月份」，回傳已集滿 9 片的月份清單（收藏冊用）。
    純函式組合，唯讀。每個月各自用 month-scoped activity 判 complete。"""
    months = {str(d)[:7] for d in day_sources}
    done = []
    for ym in sorted(months):
        board = rules.puzzle_board(ym, _month_activity(day_sources, ym))
        if board["complete"]:
            done.append({"year_month": ym, "theme": board["theme"]})
    return done


def _build_ledger(day_sources, points, limit=12):
    """組「最近加分明細」，讓使用者看得到分數怎麼來的（憲法 2 可解釋）。"""
    events = []
    for d, srcs in day_sources.items():
        zh = "、".join(_SOURCE_ZH.get(s, s) for s in sorted(srcs))
        events.append({"date": d, "type": "checkin", "label": f"每日打卡（{zh}）",
                       "points": rules.PER_ACTIVE_DAY})
    for threshold in points.get("streak_milestones_reached", []):
        pts = dict(rules.STREAK_MILESTONES)[threshold]
        events.append({"date": None, "type": "streak",
                       "label": f"連續打卡 {threshold} 天", "points": pts})
    # 有日期的新到舊排前面，里程碑（無日期）排後
    events.sort(key=lambda e: (e["date"] is not None, e["date"] or ""), reverse=True)
    return events[:limit]


def _spent_points(sb, pid):
    """已兌換扣掉的點數＝兌換紀錄 cost 加總。表不存在就視為 0（規則 12：summary
    仍可顯示 earned，只是還沒有任何兌換）。"""
    try:
        rows = sb.table("reward_redemptions").select("*").eq("patient_id", pid).execute().data or []
    except Exception as exc:
        logger.info("rewards redemptions read failed: %s", type(exc).__name__)
        return 0, []
    spent = rules.spent_from_rows(rows)
    return spent, rows


@router.get("/summary")
def get_summary(patient_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """唯讀彙整：earned/spent/available、等級進度、連續天數、徽章、加分明細。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    activity, day_sources = _gather_activity(sb, patient_id)
    points = rules.compute_points(activity)
    earned = points["earned"]
    spent, _ = _spent_points(sb, patient_id)
    available = max(0, earned - spent)

    return {
        "patient_id": patient_id,
        "points": {"earned": earned, "spent": spent, "available": available},
        "breakdown": points["breakdown"],
        "level": rules.level_for(earned),
        "streak": {
            "current": activity["current_streak"],
            "longest": activity["longest_streak"],
            "active_days": activity["active_day_count"],
        },
        "badges": rules.evaluate_badges(activity),
        "ledger": _build_ledger(day_sources, points),
    }


@router.get("/puzzle")
def get_puzzle(patient_id: str = Query(...), month: str = Query(None, description="YYYY-MM；省略＝本月"),
               me: dict | None = Depends(current_user_optional)):
    """療程拼圖（每月主題收藏）：回當月 9 片解鎖狀態＋歷史已完成清單。
    純唯讀換算，沿用 _gather_activity 的逐日來源、不另外讀表（規則 2/5）。"""
    enforce_patient_scope(patient_id, me)
    # 「本月」以台灣（+8）日曆月為準，與前端首頁入口卡（app.js 用瀏覽器本地月）一致，
    # 避免每月頭 8 小時後端還停在上個月。帶入的 month 一律正規化成零補位 'YYYY-MM'。
    ym = _norm_month(month) if month else (datetime.utcnow() + _TW_OFFSET).strftime("%Y-%m")
    sb = get_supabase()
    _activity, day_sources = _gather_activity(sb, patient_id)
    board = rules.puzzle_board(ym, _month_activity(day_sources, ym))
    return {
        "patient_id": patient_id,
        "board": board,
        "collection": _completed_puzzle_months(day_sources),
    }


@router.get("/catalog")
def get_catalog(patient_id: str = Query(None), me: dict | None = Depends(current_user_optional)):
    """兌換清單。帶 patient_id 時順便標出每項目前是否買得起。"""
    enforce_patient_scope(patient_id, me)
    available = 0
    if patient_id:
        sb = get_supabase()
        activity, _ = _gather_activity(sb, patient_id)
        earned = rules.compute_points(activity)["earned"]
        spent, _ = _spent_points(sb, patient_id)
        available = max(0, earned - spent)
    return {"available": available, "catalog": rules.catalog_with_affordability(available)}


@router.get("/redemptions")
def get_redemptions(patient_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """我的兌換紀錄（最新在前）。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    _, rows = _spent_points(sb, patient_id)
    rows = sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)
    return {"redemptions": rows}


@router.post("/redeem")
def redeem(body: RedeemRequest, me: dict | None = Depends(current_user_optional)):
    """兌換一項獎勵：純程式碼檢查餘額 → 寫入一筆 status='requested' 待院方發放。"""
    enforce_patient_scope(body.patient_id, me)
    reward = rules.get_reward(body.reward_id)
    if not reward:
        raise HTTPException(status_code=404, detail="找不到該兌換品項")

    sb = get_supabase()
    activity, _ = _gather_activity(sb, body.patient_id)
    earned = rules.compute_points(activity)["earned"]
    spent, _ = _spent_points(sb, body.patient_id)
    available = max(0, earned - spent)
    if available < reward["cost"]:
        raise HTTPException(
            status_code=400,
            detail=f"點數不足：需 {reward['cost']} 點，目前可用 {available} 點",
        )

    row = {
        "patient_id": body.patient_id,
        "reward_id": reward["id"],
        "reward_name": reward["name"],
        "cost": reward["cost"],
        "status": "requested",
    }
    try:
        saved = sb.table("reward_redemptions").insert(row).execute()
    except Exception as exc:
        # 規則 12：不靜默吞掉，但也別硬指一個可能錯的原因。寫入失敗常見有二：
        # (1) reward_redemptions 尚未建表；(2) 表已建但 anon 角色被 RLS 擋下
        # （缺 stopgap_anon_all policy）。兩者都靠套用同一份 migration 修復。
        logger.error("redeem insert failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="兌換暫時無法完成（寫入未成功；請確認 reward_redemptions "
                   "資料表與 RLS policy 已套用 docs/migration_reward_redemptions.sql）。",
        )
    saved_id = saved.data[0].get("id") if saved.data else None
    return {
        "id": saved_id,
        "reward": reward,
        "status": "requested",
        "redeemed_at": datetime.now(timezone.utc).isoformat(),
        "available_after": available - reward["cost"],
        "message": "兌換已登記，將由院方安排發放。",
    }


# ── 後台發放（限 doctor）─────────────────────────────────────
# 兌換意願由病患端 redeem 寫入（status='requested'），院方在後台核發或退回：
#   requested → fulfilled  已實際發放（仍扣點）
#   requested → cancelled  退回並退點（spent_from_rows 不計 cancelled）
# 後台端點：Depends(current_user) + 檢查 role=doctor。

def _require_doctor(me):
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可管理兌換")


@router.get("/admin/redemptions")
def admin_list_redemptions(
    status: str = Query(None, description="可選 requested/fulfilled/cancelled 過濾"),
    limit: int = Query(200, ge=1, le=1000),
    me: dict = Depends(current_user),
):
    """後台：列出所有兌換申請（最新在前），可依 status 過濾，並附各狀態計數。"""
    _require_doctor(me)
    sb = get_supabase()
    try:
        q = sb.table("reward_redemptions").select("*")
        if status:
            q = q.eq("status", status)
        rows = q.order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        logger.error("admin list redemptions failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="兌換清單暫時無法載入（reward_redemptions 資料表是否已建立？"
                   "見 docs/migration_reward_redemptions.sql）。",
        )
    # counts 要反映全表各狀態總數，與 status 過濾 / limit 截斷無關，故另外只撈 status 欄統計，
    # 不能從已被過濾又截斷的 rows 算（否則帶 status 過濾時其他狀態全變 0、資料量 >limit 時失真）。
    counts = {"requested": 0, "fulfilled": 0, "cancelled": 0}
    try:
        all_status = sb.table("reward_redemptions").select("status").execute().data or []
        for r in all_status:
            st = r.get("status") or "requested"
            counts[st] = counts.get(st, 0) + 1
    except Exception as exc:
        logger.info("rewards admin counts failed: %s", type(exc).__name__)
    return {"redemptions": rows, "counts": counts}


def _set_redemption_status(redemption_id, new_status, allowed_from, me):
    """把某筆兌換改成 new_status；只允許從 allowed_from 的狀態轉換。限 doctor。

    更新用 compare-and-swap（UPDATE ... WHERE status=舊值）確保併發下只有一方生效——
    避免兩位醫護同時對同一筆按「核發」「退回」時後寫覆蓋前寫（已發放的獎勵又被退點）。
    因 SQLite/PostgREST 兩種 shim 對 update 回傳語意不同，一律以更新後重讀的實際狀態為準。
    """
    _require_doctor(me)
    sb = get_supabase()
    try:
        cur = sb.table("reward_redemptions").select("*").eq("id", redemption_id).limit(1).execute().data
    except Exception as exc:
        logger.error("redemption fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail="兌換資料暫時無法存取")
    if not cur:
        raise HTTPException(status_code=404, detail="找不到該兌換紀錄")
    old = cur[0].get("status") or "requested"
    if old not in allowed_from:
        raise HTTPException(status_code=409, detail=f"目前狀態為「{old}」，無法執行此操作")
    try:
        (
            sb.table("reward_redemptions")
            .update({"status": new_status})
            .eq("id", redemption_id)
            .eq("status", old)  # 原子條件：狀態自讀取後被他人改動就命中 0 列
            .execute()
        )
        after = sb.table("reward_redemptions").select("*").eq("id", redemption_id).limit(1).execute().data
    except Exception as exc:
        logger.error("redemption status update failed: %s", exc)
        raise HTTPException(status_code=503, detail="兌換狀態更新暫時無法完成")
    row = after[0] if after else None
    if not row or row.get("status") != new_status:
        raise HTTPException(status_code=409, detail="兌換狀態剛被更新，請重新整理後再試")
    return row


@router.post("/admin/redemptions/{redemption_id}/fulfill")
def admin_fulfill(redemption_id: str, me: dict = Depends(current_user)):
    """後台：標記某兌換為已發放（requested → fulfilled）。限 doctor。"""
    row = _set_redemption_status(redemption_id, "fulfilled", ("requested",), me)
    return {"redemption": row, "status": "fulfilled"}


@router.post("/admin/redemptions/{redemption_id}/cancel")
def admin_cancel(redemption_id: str, me: dict = Depends(current_user)):
    """後台：取消兌換並退回點數（requested → cancelled）。限 doctor。"""
    row = _set_redemption_status(redemption_id, "cancelled", ("requested",), me)
    return {"redemption": row, "status": "cancelled", "refunded": row.get("cost")}

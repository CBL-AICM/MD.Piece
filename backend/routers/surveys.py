"""
通用問卷（survey）引擎 — 讓任何問卷都能「定義 → 收集作答 → 後台統計分析」。

定位：eHEALS（health_literacy.py）是寫死在程式碼裡的單一量表；本 router 則是
讓使用者（醫護端）自行「定義任意問卷」並把作答接進後台統計，用來整合自家的
研究 / 實驗問卷。兩者共存，互不影響。

事件流：
  1. POST /surveys                  定義一份問卷（醫護端）
  2. GET  /surveys                  列出可用問卷
  3. GET  /surveys/{key}            取單一問卷定義（前端據此渲染）
  4. POST /surveys/{key}/responses  提交作答（計分為純程式碼）
  5. GET  /surveys/{key}/stats      後台聚合統計分析（醫護端）

設計鐵則：
  - 規則 5：計分與統計是確定性任務 → 純程式碼，不丟 LLM。
  - 規則 12：格式不對就明確 400；統計只回聚合、不洩個別作答。
  - 規則 7：作答端沿用 eHEALS（同領域 sibling）的「帶 patient_id、不強制登入」
    慣例；統計端比照 /health-literacy/stats 限 role=doctor。
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_ITEM_TYPES = {"likert", "single", "multi", "text"}
# 會被納入「數值總分」與題目統計的型別（text 不計分、不做分布）
_NUMERIC_TYPES = {"likert"}


# ── Models ────────────────────────────────────────────────

class SurveyCreate(BaseModel):
    key: str                       # slug，URL 用，全 app 唯一
    title: str
    description: Optional[str] = None
    # items: [{id, text, type: likert|single|multi|text, options?: [...], min?, max?}]
    items: list[dict]
    # scoring: {"method": "sum_likert"} 或 {"method": "none"}（預設 sum_likert）
    scoring: Optional[dict] = None


class ResponseCreate(BaseModel):
    patient_id: str
    # answers: {item_id: value}；likert→int、single→option、multi→list、text→str
    answers: dict


# ── Helpers ───────────────────────────────────────────────

def _median(nums: list[float]) -> Optional[float]:
    if not nums:
        return None
    s = sorted(nums)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else round((s[mid - 1] + s[mid]) / 2, 1)


def _coerce_json(v):
    """SQLite 以字串存 JSON，Supabase 回原生型別；統一還原成 Python 物件。"""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, ValueError):
            return v
    return v


def _load_survey(sb, key: str) -> Optional[dict]:
    try:
        rows = sb.table("surveys").select("*").eq("key", key).limit(1).execute().data or []
    except Exception as e:
        logger.info(f"survey load failed: {e}")
        return None
    if not rows:
        return None
    s = dict(rows[0])
    s["items"] = _coerce_json(s.get("items")) or []
    s["scoring"] = _coerce_json(s.get("scoring")) or {}
    return s


def _score_response(survey: dict, answers: dict) -> Optional[int]:
    """純程式碼計分（規則 5）。method=sum_likert：加總所有 likert 題的整數作答。"""
    method = (survey.get("scoring") or {}).get("method", "sum_likert")
    if method != "sum_likert":
        return None
    total = 0
    counted = 0
    for item in survey.get("items") or []:
        if item.get("type") != "likert":
            continue
        val = answers.get(str(item.get("id"))) if str(item.get("id")) in answers else answers.get(item.get("id"))
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            total += val
            counted += 1
    return total if counted else None


# ── Endpoints ─────────────────────────────────────────────

@router.post("")
def create_survey(body: SurveyCreate, me: dict = Depends(current_user)):
    """定義一份問卷（限 role=doctor）。key 必須唯一、為合法 slug。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可建立問卷")
    if not _KEY_RE.fullmatch(body.key or ""):
        raise HTTPException(status_code=400, detail="key 需為 2–64 字的小寫英數 / -/_ slug")
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="title 不可為空")
    if not isinstance(body.items, list) or not body.items:
        raise HTTPException(status_code=400, detail="items 需為非空陣列")
    seen_ids = set()
    for it in body.items:
        if not isinstance(it, dict) or "id" not in it or "type" not in it:
            raise HTTPException(status_code=400, detail="每題需含 id 與 type")
        if it["type"] not in _ITEM_TYPES:
            raise HTTPException(status_code=400, detail=f"題型需為 {_ITEM_TYPES}")
        iid = str(it["id"])
        if iid in seen_ids:
            raise HTTPException(status_code=400, detail=f"題目 id 重複：{iid}")
        seen_ids.add(iid)

    sb = get_supabase()
    if _load_survey(sb, body.key):
        raise HTTPException(status_code=409, detail=f"key 已存在：{body.key}")

    row = {
        "key": body.key,
        "title": body.title.strip(),
        "description": (body.description or "").strip() or None,
        "items": body.items,
        "scoring": body.scoring or {"method": "sum_likert"},
        "created_by": me.get("id"),
        "active": 1,
    }
    try:
        saved = sb.table("surveys").insert(row).execute()
    except Exception as e:
        logger.error(f"create survey failed: {e}")
        raise HTTPException(status_code=400, detail=f"建立問卷失敗：{e}")
    out = dict(saved.data[0]) if saved.data else row
    out["items"] = _coerce_json(out.get("items"))
    out["scoring"] = _coerce_json(out.get("scoring"))
    return out


@router.get("")
def list_surveys():
    """列出可用問卷（只回基本資料，供選單）。"""
    sb = get_supabase()
    try:
        rows = sb.table("surveys").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        logger.info(f"list surveys failed: {e}")
        rows = []
    out = []
    for r in rows:
        if not r.get("active", 1):
            continue
        items = _coerce_json(r.get("items")) or []
        out.append({
            "key": r.get("key"),
            "title": r.get("title"),
            "description": r.get("description"),
            "item_count": len(items),
            "created_at": r.get("created_at"),
        })
    return {"surveys": out}


@router.get("/{key}")
def get_survey(key: str):
    """取單一問卷定義（前端用來渲染題目）。"""
    sb = get_supabase()
    s = _load_survey(sb, key)
    if not s or not s.get("active", 1):
        raise HTTPException(status_code=404, detail="找不到該問卷")
    return {
        "key": s.get("key"),
        "title": s.get("title"),
        "description": s.get("description"),
        "items": s.get("items"),
        "scoring": s.get("scoring"),
    }


@router.post("/{key}/responses")
def submit_response(key: str, body: ResponseCreate):
    """提交一份作答。計分為純程式碼（規則 5）；存檔失敗會 loud-fail（規則 12）。"""
    if not isinstance(body.answers, dict) or not body.answers:
        raise HTTPException(status_code=400, detail="answers 需為非空物件 {item_id: value}")
    sb = get_supabase()
    survey = _load_survey(sb, key)
    if not survey or not survey.get("active", 1):
        raise HTTPException(status_code=404, detail="找不到該問卷")

    score = _score_response(survey, body.answers)
    row = {
        "survey_key": key,
        "patient_id": body.patient_id,
        "answers": body.answers,
        "score": score,
    }
    try:
        saved = sb.table("survey_responses").insert(row).execute()
        saved_id = saved.data[0].get("id") if saved.data else None
    except Exception as e:
        logger.error(f"submit survey response failed: {e}")
        raise HTTPException(status_code=400, detail=f"作答儲存失敗：{e}")
    return {"id": saved_id, "survey_key": key, "score": score, "_persisted": True}


@router.get("/{key}/stats")
def survey_stats(key: str, me: dict = Depends(current_user)):
    """
    後台聚合統計分析（限 role=doctor）。

    回傳填答人數、數值總分 avg/min/max/median，以及逐題分析：
      - likert：count / avg / min / max / 分布
      - single / multi：各選項計數
      - text：只回 count（不彙總自由文字）
    只回聚合數字、不含任何個別作答（規則 12 / 憲法 7 隱私）。
    """
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可檢視問卷統計")
    sb = get_supabase()
    survey = _load_survey(sb, key)
    if not survey:
        raise HTTPException(status_code=404, detail="找不到該問卷")

    try:
        rows = sb.table("survey_responses").select("*").eq("survey_key", key).execute().data or []
    except Exception as e:
        logger.info(f"survey stats fetch failed: {e}")
        rows = []

    responses = [{"answers": _coerce_json(r.get("answers")) or {}, "score": r.get("score")} for r in rows]
    respondents = len(responses)

    scores = [r["score"] for r in responses if isinstance(r["score"], int)]

    def _ans(answers: dict, iid):
        if str(iid) in answers:
            return answers[str(iid)]
        return answers.get(iid)

    per_item = []
    for item in survey.get("items") or []:
        iid = item.get("id")
        itype = item.get("type")
        vals = [_ans(r["answers"], iid) for r in responses]
        vals = [v for v in vals if v is not None]
        entry = {"id": iid, "text": item.get("text"), "type": itype, "answered": len(vals)}
        if itype == "likert":
            nums = [v for v in vals if isinstance(v, int) and not isinstance(v, bool)]
            dist: dict[str, int] = {}
            for v in nums:
                dist[str(v)] = dist.get(str(v), 0) + 1
            entry.update({
                "avg": round(sum(nums) / len(nums), 2) if nums else None,
                "min": min(nums) if nums else None,
                "max": max(nums) if nums else None,
                "distribution": dist,
            })
        elif itype in ("single", "multi"):
            counts: dict[str, int] = {}
            for v in vals:
                opts = v if isinstance(v, list) else [v]
                for o in opts:
                    counts[str(o)] = counts.get(str(o), 0) + 1
            entry["option_counts"] = counts
        per_item.append(entry)

    return {
        "key": key,
        "title": survey.get("title"),
        "respondents": respondents,
        "score": {
            "avg": round(sum(scores) / len(scores), 1) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "median": _median(scores),
            "scored_responses": len(scores),
        },
        "per_item": per_item,
    }

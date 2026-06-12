"""
健康識能（eHealth Literacy）篩檢 router — 住院模式 v2 之 M07。

依《住院模式 PWA 設計計畫 v2.0》：
  啟動時 8 題 eHEALS 簡版 → 低分自動套用「簡化模式」（大字、3 鍵以內、隱藏進階）。
  eHEALSResult 跨住院期次保存，並對齊計畫書「實驗三」問卷（零額外負擔自動觸發）。

採用 Norman & Skinner (2006) eHEALS 8 題量表（每題 1–5 Likert），繁體中文化。
量表結構不可隨意改動，以維持與既有文獻可比性（研究信效度）。

核心定位（不可動搖）：
  - 這是「讓 App 配合使用者」的介面偏好，不是對人的能力評斷。
    所有對外文案都框成「為了讓您更好用，建議切換大字簡化版」，
    絕不對使用者說「您的健康識能偏低」。尊嚴優先。
  - 規則 5：計分與門檻判定是確定性任務 → 純程式碼，不丟 LLM。
  - 規則 12：計分透明可解釋（回傳 explanation + 各門檻），不做黑箱。
  - 法規：不做診斷、不做認知評估，僅為無障礙介面調整。
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user, current_user_optional, enforce_patient_scope

logger = logging.getLogger(__name__)
router = APIRouter()


# ── eHEALS 8 題（靜態，不入 DB；同 qpl-bank / taiwan_hospitals pattern）────────
# 回傳 i18n key + 預設 zh-TW 文案，前端可用 key 覆寫多語。
_LIKERT_ZH = ["非常不同意", "不同意", "普通", "同意", "非常同意"]

_EHEALS_ITEMS = [
    {"id": 1, "key": "ehl.q1", "text": "我知道網路上有哪些健康資源"},
    {"id": 2, "key": "ehl.q2", "text": "我知道在網路上可以到哪裡找到有幫助的健康資源"},
    {"id": 3, "key": "ehl.q3", "text": "我知道如何在網路上找到有幫助的健康資源"},
    {"id": 4, "key": "ehl.q4", "text": "我知道如何運用網路來回答我的健康問題"},
    {"id": 5, "key": "ehl.q5", "text": "我知道如何運用在網路上找到的健康資訊來幫助自己"},
    {"id": 6, "key": "ehl.q6", "text": "我具備評估網路健康資源所需的能力"},
    {"id": 7, "key": "ehl.q7", "text": "我能分辨網路上健康資源的品質好壞"},
    {"id": 8, "key": "ehl.q8", "text": "對於運用網路資訊來做健康決定，我有信心"},
]

# 計分門檻（透明、可解釋）。總分範圍 8–40。
#   low      : < 26   → 建議簡化模式（常見 low eHealth literacy 切點）
#   adequate : 26–31
#   high     : ≥ 32
_LOW_MAX = 25       # ≤25 視為 low
_HIGH_MIN = 32      # ≥32 視為 high

DISCLAIMER = (
    "本篩檢僅用來調整 App 的顯示方式（字級、步驟簡化），"
    "不是健康或能力的評估，也不會分享給任何醫療機構或第三方。"
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _score(answers: list[int]) -> dict:
    """純程式碼計分（規則 5）。回傳 total / level / recommended_mode + 可解釋說明。

    answers：長度 8、每項 1–5 的整數。caller 已驗證格式。
    """
    total = sum(answers)
    if total <= _LOW_MAX:
        level = "low"
        mode = "simplified"
        explanation = (
            "為了讓您用起來更輕鬆，建議切換成「大字簡化版」："
            "字比較大、步驟比較少、把進階功能先收起來。隨時可以在設定改回來。"
        )
    elif total >= _HIGH_MIN:
        level = "high"
        mode = "standard"
        explanation = "您對使用數位健康資訊很有信心，將維持標準版面；隨時可在設定切換大字版。"
    else:
        level = "adequate"
        mode = "standard"
        explanation = "將維持標準版面；如果覺得字小或步驟多，隨時可在設定切換「大字簡化版」。"
    return {
        "total_score": total,
        "max_score": 40,
        "min_score": 8,
        "literacy_level": level,             # low | adequate | high（研究用，內部欄位）
        "recommended_mode": mode,            # simplified | standard
        "explanation": explanation,
        "thresholds": {"low_max": _LOW_MAX, "high_min": _HIGH_MIN},
    }


# ── Models ────────────────────────────────────────────────

class ScreenSubmit(BaseModel):
    patient_id: str
    answers: list[int]   # 8 個 1–5


# ── Endpoints ─────────────────────────────────────────────

@router.get("/questions")
def get_questions():
    """eHEALS 8 題 + Likert 選項，供前端篩檢畫面渲染。"""
    return {
        "instrument": "eHEALS",
        "reference": "Norman & Skinner, 2006",
        "scale": _LIKERT_ZH,
        "items": _EHEALS_ITEMS,
        "intro": "下面 8 句話，請依您的感覺勾選（大約 1 分鐘）。沒有對錯，只是讓 App 更貼合您。",
        "disclaimer": DISCLAIMER,
    }


@router.get("/latest")
def latest(patient_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """取該病患最近一次 eHEALS 結果；沒有則回 {"result": None}，前端據此決定是否首啟提示。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    try:
        r = (
            sb.table("ehl_results")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(r, "data", None) or []
    except Exception as e:
        logger.info(f"ehl: latest lookup failed: {e}")
        rows = []
    if not rows:
        return {"result": None}
    row = rows[0]
    # answers 在 SQLite 以 JSON 字串存；Supabase 回 list。統一還原成 list。
    ans = row.get("answers")
    if isinstance(ans, str):
        try:
            ans = json.loads(ans)
        except (json.JSONDecodeError, ValueError):
            ans = None
    return {
        "result": {
            "id": row.get("id"),
            "total_score": row.get("total_score"),
            "literacy_level": row.get("literacy_level"),
            "recommended_mode": row.get("recommended_mode"),
            "answers": ans,
            "created_at": row.get("created_at"),
        }
    }


@router.post("/screen")
def screen(body: ScreenSubmit, me: dict | None = Depends(current_user_optional)):
    """提交 8 題作答 → 純程式碼計分 → 存檔 → 回傳結果與建議模式。

    規則 12：格式不對就明確 400，不靜默吞掉或亂猜分數。
    """
    enforce_patient_scope(body.patient_id, me)
    answers = body.answers or []
    if len(answers) != len(_EHEALS_ITEMS):
        raise HTTPException(status_code=400, detail=f"需要 {len(_EHEALS_ITEMS)} 題作答")
    if not all(isinstance(a, int) and 1 <= a <= 5 for a in answers):
        raise HTTPException(status_code=400, detail="每題作答需為 1–5 的整數")

    result = _score(answers)

    sb = get_supabase()
    row = {
        "patient_id": body.patient_id,
        "answers": answers,
        "total_score": result["total_score"],
        "literacy_level": result["literacy_level"],
        "recommended_mode": result["recommended_mode"],
    }
    try:
        saved = sb.table("ehl_results").insert(row).execute()
        saved_id = (saved.data[0].get("id") if saved.data else None)
    except Exception as e:
        # 規則 12：存檔失敗要揭露（_persisted=False），但仍把計分結果回給前端，
        # 讓使用者至少當下能套用建議模式（前端會落地到 localStorage）。
        logger.error(f"ehl: save result failed: {e}")
        return {**result, "_persisted": False, "disclaimer": DISCLAIMER}

    return {**result, "_persisted": True, "id": saved_id, "disclaimer": DISCLAIMER}


# ── 後台聚合統計 ───────────────────────────────────────────

def _level_for_score(total: int) -> str:
    """用與 _score 相同的門檻把總分歸到 level（補存檔缺 literacy_level 的舊資料）。"""
    if total <= _LOW_MAX:
        return "low"
    if total >= _HIGH_MIN:
        return "high"
    return "adequate"


def _median(nums: list[float]) -> Optional[float]:
    if not nums:
        return None
    s = sorted(nums)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else round((s[mid - 1] + s[mid]) / 2, 1)


@router.get("/stats")
def stats(me: dict = Depends(current_user)):
    """
    eHEALS 跨病患聚合統計（後台 / 醫護端）。

    純程式碼彙總（規則 5）：回傳填答人數、總分 avg/min/max/median、
    level 分布（low / adequate / high）與建議模式分布（simplified / standard），
    並附門檻說明（規則 12：可解釋）。

    僅回傳聚合數字、不含任何個別病患資料；且限 role=doctor 檢視，避免問卷母體外洩。
    """
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅限醫護端檢視問卷彙總統計")

    sb = get_supabase()
    try:
        rows = sb.table("ehl_results").select("*").execute().data or []
    except Exception as e:
        logger.info(f"ehl: stats lookup failed: {e}")
        rows = []

    by_level = {"low": 0, "adequate": 0, "high": 0}
    by_mode = {"simplified": 0, "standard": 0}
    scores: list[int] = []
    for r in rows:
        total = r.get("total_score")
        if not isinstance(total, int):
            continue
        scores.append(total)
        level = r.get("literacy_level") or _level_for_score(total)
        if level in by_level:
            by_level[level] += 1
        mode = r.get("recommended_mode")
        if mode not in by_mode:
            # 缺 recommended_mode 的舊資料：low → simplified、其餘 standard
            mode = "simplified" if level == "low" else "standard"
        by_mode[mode] += 1

    respondents = len(scores)

    def _pct(n: int) -> float:
        return round(n / respondents * 100, 1) if respondents else 0.0

    return {
        "instrument": "eHEALS",
        "respondents": respondents,
        "score": {
            "avg": round(sum(scores) / respondents, 1) if respondents else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "median": _median(scores),
            "scale_min": 8,
            "scale_max": 40,
        },
        "by_level": {
            k: {"count": v, "percent": _pct(v)} for k, v in by_level.items()
        },
        "by_mode": {
            k: {"count": v, "percent": _pct(v)} for k, v in by_mode.items()
        },
        "thresholds": {"low_max": _LOW_MAX, "high_min": _HIGH_MIN},
        "disclaimer": DISCLAIMER,
    }

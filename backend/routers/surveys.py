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

import csv
import io
import json
import logging
import math
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
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
    # 研究施測時點（D0/D14/D28/FU48…）；若問卷 scoring.timepoints 有定義則為必填。
    timepoint: Optional[str] = None
    # 選填受試者代號（P01–P12）；姓名對照表仍依文件離線彌封，不進 App。
    participant_code: Optional[str] = None


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


def _ans(answers: dict, iid):
    """取某題作答，相容 int / str key。"""
    if iid is None:
        return None
    if str(iid) in answers:
        return answers[str(iid)]
    return answers.get(iid)


def _to_num(v, na_value=None):
    """把作答轉成數值；bool / na_value / 非數值 → None（視為未計入）。"""
    if v is None:
        return None
    if na_value is not None and v == na_value:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except (TypeError, ValueError):
            return None
    return None


def _construct_item_ids(survey: dict, cfg: dict) -> list:
    """構念計分用的題目 id：likert 題，扣掉 exclude_from_construct 與已歸入 subscale 的題。"""
    exclude = {str(x) for x in (cfg.get("exclude_from_construct") or [])}
    in_sub = {str(i) for ids in (cfg.get("subscales") or {}).values() for i in ids}
    out = []
    for it in survey.get("items") or []:
        if it.get("type") != "likert":
            continue
        iid = str(it.get("id"))
        if iid in exclude or iid in in_sub:
            continue
        out.append(it.get("id"))
    return out


def _collect(answers: dict, item_ids: list, cfg: dict):
    """收集一組題目的數值作答（套用反向題）。回傳 (values, n_items, n_answered, n_missing)。"""
    na = cfg.get("na_value")
    scale = cfg.get("scale") or {}
    smin, smax = scale.get("min"), scale.get("max")
    reverse = {str(x) for x in (cfg.get("reverse_items") or [])}
    vals = []
    for iid in item_ids:
        n = _to_num(_ans(answers, iid), na)
        if n is None:
            continue
        if str(iid) in reverse and smin is not None and smax is not None:
            n = (smin + smax) - n
        vals.append(n)
    n_items = len(item_ids)
    return vals, n_items, len(vals), n_items - len(vals)


def _score_response(survey: dict, answers: dict) -> dict:
    """純程式碼計分（規則 5）。依 scoring.method 回傳結構化 scores。

    method：mean | sum | subscales | top_score | none | sum_likert（既有通用問卷相容）。
    各量表精確規則由 seed 的 scoring config 表達（reverse/exclude/subscales/missing/scale）。
    """
    cfg = survey.get("scoring") or {}
    method = cfg.get("method") or "sum_likert"
    missing = cfg.get("missing") or {}
    max_missing = missing.get("max_missing")
    impute = missing.get("impute", "none")
    base = {"method": method}

    if method == "none":
        return dict(base, valid=True)

    if method == "sum_likert":
        # 既有通用問卷相容：加總所有 likert 整數作答。
        total, counted = 0, 0
        for it in survey.get("items") or []:
            if it.get("type") != "likert":
                continue
            v = _ans(answers, it.get("id"))
            if isinstance(v, bool) or not isinstance(v, int):
                continue
            total += v
            counted += 1
        return dict(base, total=(total if counted else None), valid=bool(counted), n_answered=counted)

    # 量測但不納主構念的題（如 C3 q5 批判性信任）獨立報告。
    extra = {}
    for iid in (cfg.get("exclude_from_construct") or []):
        v = _ans(answers, iid)
        if v is not None:
            extra[str(iid)] = v

    if method == "subscales":
        subs, total_na = {}, 0
        for name, ids in (cfg.get("subscales") or {}).items():
            vals, n_items, n_ans, n_miss = _collect(answers, ids, cfg)
            total_na += n_miss
            subs[name] = {
                "mean": round(sum(vals) / n_ans, 2) if n_ans else None,
                "n": n_ans, "n_items": n_items, "valid": n_ans >= 1,
            }
        out = dict(base, subscales=subs, n_missing=total_na,
                   valid=all(s["valid"] for s in subs.values()) if subs else False)
        if max_missing is not None and total_na > max_missing:
            out["flag"] = f"N/A 題數 {total_na} 超過 {max_missing}，建議標註"
        if extra:
            out["extra"] = extra
        return out

    # mean / sum / top_score 走構念題集
    item_ids = _construct_item_ids(survey, cfg)
    vals, n_items, n_answered, n_missing = _collect(answers, item_ids, cfg)
    out = dict(base, n_items=n_items, n_answered=n_answered, n_missing=n_missing)
    if extra:
        out["extra"] = extra

    # NPS（E2）：config 指定 nps_item 時附 NPS 分類（promoter/passive/detractor）。
    nps_item = cfg.get("nps_item")
    if nps_item is not None:
        nv = _to_num(_ans(answers, nps_item))
        if nv is not None:
            nv = int(nv)
            out["nps"] = {
                "score": nv,
                "class": "promoter" if nv >= 9 else ("passive" if nv >= 7 else "detractor"),
            }

    valid = n_answered >= 1 and (max_missing is None or n_missing <= max_missing)
    out["valid"] = valid

    if method == "mean":
        out["mean"] = round(sum(vals) / n_answered, 2) if (valid and n_answered) else None
    elif method == "sum":
        if not valid:
            out["total"] = None
        elif impute == "mean" and n_answered:
            # 「缺 X 題以平均補」：以已答平均回填後加總，維持與滿分量尺可比。
            out["total"] = round(sum(vals) / n_answered * n_items, 1)
        else:
            out["total"] = round(sum(vals), 1) if n_answered else None
    elif method == "top_score":
        smax = (cfg.get("scale") or {}).get("max")
        out["mean"] = round(sum(vals) / n_answered, 2) if n_answered else None
        out["top_score"] = 1 if (
            n_missing == 0 and n_answered == n_items and smax is not None
            and all(v == smax for v in vals)
        ) else 0
        out["top_score_valid"] = (n_missing == 0)
    return out


def _legacy_score(scores: dict) -> Optional[int]:
    """回填整數 score 欄（相容既有 /stats）。只有 sum / sum_likert 給整數，其餘 None。"""
    if isinstance(scores, dict) and scores.get("method") in ("sum", "sum_likert"):
        t = scores.get("total")
        if isinstance(t, (int, float)):
            return int(round(t))
    return None


# ── 描述統計 / 效應量 / 信度（純程式碼，給 analysis 端點用；規則 5）────────────

def _mean(xs: list) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def _sd(xs: list) -> Optional[float]:
    """樣本標準差（ddof=1）。"""
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _quantile(sorted_xs: list, q: float) -> Optional[float]:
    """線性插值分位數（type-7，同 numpy 預設）。"""
    if not sorted_xs:
        return None
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = (len(sorted_xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_xs[lo]
    return sorted_xs[lo] * (hi - pos) + sorted_xs[hi] * (pos - lo)


def _describe(xs: list) -> dict:
    """n / mean / sd / median / IQR / min / max。"""
    xs = [float(x) for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    s = sorted(xs)
    sd = _sd(xs)
    return {
        "n": len(xs),
        "mean": round(_mean(xs), 2),
        "sd": round(sd, 2) if sd is not None else None,
        "median": round(_quantile(s, 0.5), 2),
        "q1": round(_quantile(s, 0.25), 2),
        "q3": round(_quantile(s, 0.75), 2),
        "min": round(min(xs), 2),
        "max": round(max(xs), 2),
    }


def _avg_ranks(values: list) -> list:
    """回傳各元素的平均秩（1-based，ties 取平均）。"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _rank_biserial(pre: list, post: list) -> Optional[dict]:
    """配對 rank-biserial 效應量（Wilcoxon 基礎，不需 p 值；決策②）。

    r ∈ [-1,1]，r>0 表 post 高於 pre。對齊文件「n=10 以效應量與個別軌跡為主」。
    """
    diffs = [b - a for a, b in zip(pre, post) if a is not None and b is not None]
    nz = [d for d in diffs if d != 0]
    if not nz:
        return None
    ranks = _avg_ranks([abs(d) for d in nz])
    w_pos = sum(r for d, r in zip(nz, ranks) if d > 0)
    w_neg = sum(r for d, r in zip(nz, ranks) if d < 0)
    total = w_pos + w_neg
    if total == 0:
        return None
    r = (w_pos - w_neg) / total
    return {
        "r": round(r, 3),
        "n_pairs": len(nz),
        "n_zero": len(diffs) - len(nz),
        "direction": "increase" if r > 0 else ("decrease" if r < 0 else "none"),
    }


def _cronbach_alpha(rows: list) -> Optional[float]:
    """Cronbach α。rows：每列為某受試者在同一組 k 題的數值（只取完整列）。"""
    if not rows:
        return None
    k0 = len(rows[0])
    complete = [r for r in rows if r and len(r) == k0 and all(x is not None for x in r)]
    if len(complete) < 2 or k0 < 2:
        return None
    item_vars = []
    for j in range(k0):
        sd = _sd([r[j] for r in complete])
        if sd is None:
            return None
        item_vars.append(sd ** 2)
    tv = _sd([sum(r) for r in complete])
    if tv is None or tv == 0:
        return None
    return round((k0 / (k0 - 1)) * (1 - sum(item_vars) / (tv ** 2)), 3)


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

    # 研究問卷需指定施測時點（規則 12：不符就明確 400，不靜默亂存）。
    tps = (survey.get("scoring") or {}).get("timepoints") or []
    tp = (body.timepoint or "").strip() or None
    if tps:
        if not tp:
            raise HTTPException(status_code=400, detail=f"此問卷需指定施測時點，可選：{tps}")
        if tp not in tps:
            raise HTTPException(status_code=400, detail=f"施測時點需為 {tps} 其中之一")

    scores = _score_response(survey, body.answers)
    row = {
        "survey_key": key,
        "patient_id": body.patient_id,
        "answers": body.answers,
        "score": _legacy_score(scores),
        "timepoint": tp,
        "scores": scores,
        "participant_code": (body.participant_code or "").strip() or None,
    }
    try:
        saved = sb.table("survey_responses").insert(row).execute()
        saved_id = saved.data[0].get("id") if saved.data else None
    except Exception as e:
        logger.error(f"submit survey response failed: {e}")
        raise HTTPException(status_code=400, detail=f"作答儲存失敗：{e}")
    return {"id": saved_id, "survey_key": key, "timepoint": tp, "scores": scores, "_persisted": True}


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


# ════════════════════════════════════════════════════════════════════
# 研究問卷整合：跨時點 summary / 後台分析 / CSV 匯出
#   對接《MD_Piece_整合實驗設計與問卷_v2》三實驗可行性研究。
#   - summary  ：單一受試者跨 part×timepoint 整合 + 依從率（本人或 doctor）
#   - analysis ：研究層級聚合（描述統計 + 效應量 + α + MAUQ + collaboRATE + NPS；doctor）
#   - export   ：tidy CSV（long / wide），供 JASP/R/jamovi 跑 Wilcoxon/Friedman（doctor）
# ════════════════════════════════════════════════════════════════════

def _study_surveys(sb, study: str) -> list:
    """取某研究的全部問卷定義（依 scoring.study 過濾、order 排序）。"""
    try:
        rows = sb.table("surveys").select("*").execute().data or []
    except Exception as e:
        logger.info(f"study surveys fetch failed: {e}")
        rows = []
    out = []
    for r in rows:
        sc = _coerce_json(r.get("scoring")) or {}
        if sc.get("study") != study or not r.get("active", 1):
            continue
        out.append({"key": r.get("key"), "title": r.get("title"),
                    "items": _coerce_json(r.get("items")) or [], "scoring": sc})
    out.sort(key=lambda s: s["scoring"].get("order", 999))
    return out


def _responses_for(sb, key: str, patient_id: Optional[str] = None) -> list:
    q = sb.table("survey_responses").select("*").eq("survey_key", key)
    if patient_id:
        q = q.eq("patient_id", patient_id)
    try:
        rows = q.execute().data or []
    except Exception as e:
        logger.info(f"responses fetch failed for {key}: {e}")
        rows = []
    return [{
        "patient_id": r.get("patient_id"),
        "participant_code": r.get("participant_code"),
        "timepoint": r.get("timepoint") or "_",
        "answers": _coerce_json(r.get("answers")) or {},
        "scores": _coerce_json(r.get("scores")) or {},
        "created_at": r.get("created_at") or "",
    } for r in rows]


def _latest_panel(responses: list) -> dict:
    """tp -> {patient_id -> 最新一筆 response}（同人同時點取最新）。"""
    panel: dict = {}
    for r in sorted(responses, key=lambda x: x.get("created_at") or ""):
        panel.setdefault(r["timepoint"], {})[r["patient_id"]] = r
    return panel


def _primary_value(scores: dict):
    """構念代表數值（描述統計/效應量/charting 用）。subscale/none/invalid 回 None。"""
    if not isinstance(scores, dict) or not scores.get("valid", False):
        return None
    m = scores.get("method")
    if m == "mean":
        return scores.get("mean")
    if m == "sum":
        return scores.get("total")
    if m == "top_score":
        return scores.get("mean")
    return None


def _item_vectors(survey: dict, responses: list, ids: list) -> list:
    """把每筆作答取出某組題的數值向量（套反向題、N/A→None），供 Cronbach α。"""
    sc = survey["scoring"]
    na = sc.get("na_value")
    reverse = {str(x) for x in (sc.get("reverse_items") or [])}
    scale = sc.get("scale") or {}
    smin, smax = scale.get("min"), scale.get("max")
    rows = []
    for r in responses:
        vec = []
        for iid in ids:
            n = _to_num(_ans(r["answers"], iid), na)
            if n is not None and str(iid) in reverse and smin is not None and smax is not None:
                n = (smin + smax) - n
            vec.append(n)
        rows.append(vec)
    return rows


def _alpha_for_part(survey: dict, responses: list):
    """自編/可加總量表的 Cronbach α（pool 所有時點有效作答）。MAUQ 回各 subscale α。"""
    sc = survey["scoring"]
    method = sc.get("method")
    if method == "subscales":
        result = {}
        for name, ids in (sc.get("subscales") or {}).items():
            a = _cronbach_alpha(_item_vectors(survey, responses, ids))
            if a is not None:
                result[name] = {"alpha": a, "k": len(ids)}
        return {"subscales": result, "scope": "pooled across timepoints"} if result else None
    if method in ("mean", "sum"):
        ids = _construct_item_ids(survey, sc)
        if len(ids) < 2:
            return None
        a = _cronbach_alpha(_item_vectors(survey, responses, ids))
        return {"alpha": a, "k": len(ids), "scope": "pooled across timepoints"} if a is not None else None
    return None


def _background_dist(survey: dict, responses: list) -> dict:
    """Part A 背景資料：single/multi 各選項計數。"""
    out = {}
    for it in survey["items"]:
        if it.get("type") not in ("single", "multi"):
            continue
        counts: dict = {}
        for r in responses:
            v = _ans(r["answers"], it["id"])
            if v is None:
                continue
            for o in (v if isinstance(v, list) else [v]):
                counts[str(o)] = counts.get(str(o), 0) + 1
        out[str(it["id"])] = {"text": it.get("text"), "counts": counts}
    return out


def _adherence(sb, pid: str) -> dict:
    """整合每位使用者日常紀錄活動（RQ1 依從率 proxy）：症狀/生理值/睡眠的活動天數。"""
    def _scan(table, id_col, date_cols):
        try:
            rows = sb.table(table).select("*").eq(id_col, pid).execute().data or []
        except Exception:
            return set(), 0
        days = set()
        for r in rows:
            for c in date_cols:
                if r.get(c):
                    days.add(str(r[c])[:10])
                    break
        return days, len(rows)

    sym_d, sym_n = _scan("symptom_entries", "patient_id", ["recorded_at", "created_at"])
    vit_d, vit_n = _scan("vital_entries", "patient_id", ["recorded_at", "created_at"])
    slp_d, slp_n = _scan("sleep_sessions", "user_id", ["bed_time", "created_at"])
    return {
        "active_days": len(sym_d | vit_d | slp_d),
        "by_source": {
            "symptoms": {"records": sym_n, "days": len(sym_d)},
            "vitals": {"records": vit_n, "days": len(vit_d)},
            "sleep": {"records": slp_n, "days": len(slp_d)},
        },
        "note": "活動天數＝有任一日常紀錄的不重複日數，作為依從率參考；精確 7 天完成率請依施測時點離線計算。",
    }


@router.get("/study/{study}/participants/{pid}/summary")
def participant_summary(study: str, pid: str, me: dict = Depends(current_user)):
    """單一受試者跨 part×timepoint 整合 + 依從率 + M07 eHEALS。本人或 doctor 可讀。"""
    if me.get("id") != pid and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能檢視自己的問卷彙整")
    sb = get_supabase()
    surveys = _study_surveys(sb, study)
    if not surveys:
        raise HTTPException(status_code=404, detail="找不到該研究問卷組")

    parts = []
    for s in surveys:
        sc = s["scoring"]
        panel = _latest_panel(_responses_for(sb, s["key"], patient_id=pid))
        tps = sc.get("timepoints") or []
        by_tp = {}
        for tp in tps:
            r = panel.get(tp, {}).get(pid)
            by_tp[tp] = ({"completed": True, "scores": r["scores"], "created_at": r["created_at"]}
                         if r else {"completed": False})
        parts.append({"part": sc.get("part"), "key": s["key"], "title": s["title"],
                      "method": sc.get("method"), "timepoints": tps, "by_timepoint": by_tp})

    eheals = None
    try:
        er = (sb.table("ehl_results").select("*").eq("patient_id", pid)
              .order("created_at", desc=True).limit(1).execute().data or [])
        if er:
            eheals = {"total_score": er[0].get("total_score"),
                      "literacy_level": er[0].get("literacy_level"),
                      "created_at": er[0].get("created_at")}
    except Exception:
        pass

    return {"study": study, "patient_id": pid, "parts": parts,
            "eheals_m07": eheals, "adherence": _adherence(sb, pid)}


@router.get("/study/{study}/analysis")
def study_analysis(study: str, me: dict = Depends(current_user)):
    """研究層級聚合分析（限 doctor）。僅回聚合，不洩個別作答（規則 12 / 憲法 7）。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可檢視研究分析")
    sb = get_supabase()
    surveys = _study_surveys(sb, study)
    if not surveys:
        raise HTTPException(status_code=404, detail="找不到該研究問卷組")

    all_patients = set()
    parts_out = []
    for s in surveys:
        sc = s["scoring"]
        method = sc.get("method")
        tps = sc.get("timepoints") or []
        resp = _responses_for(sb, s["key"])
        for r in resp:
            all_patients.add(r["patient_id"])
        panel = _latest_panel(resp)
        entry = {"part": sc.get("part"), "key": s["key"], "title": s["title"],
                 "method": method, "timepoints": tps,
                 "respondents": len({p for tp in panel for p in panel[tp]})}

        if method in ("mean", "sum", "top_score"):
            by_tp = {}
            for tp in tps:
                vals = [v for v in (_primary_value(r["scores"]) for r in panel.get(tp, {}).values()) if v is not None]
                by_tp[tp] = _describe(vals)
            entry["by_timepoint"] = by_tp
            if "D0" in tps and "D28" in tps:
                d0, d28 = panel.get("D0", {}), panel.get("D28", {})
                common = sorted(set(d0) & set(d28))
                rb = _rank_biserial([_primary_value(d0[p]["scores"]) for p in common],
                                    [_primary_value(d28[p]["scores"]) for p in common])
                if rb:
                    entry["paired_D0_D28"] = rb

        if method == "top_score":
            ts = {}
            for tp in tps:
                vs = [r["scores"].get("top_score") for r in panel.get(tp, {}).values()
                      if r["scores"].get("top_score_valid") and isinstance(r["scores"].get("top_score"), int)]
                ts[tp] = {"rate": round(sum(vs) / len(vs), 3) if vs else None, "n": len(vs)}
            entry["top_score_rate"] = ts

        if method == "subscales":
            thr = sc.get("thresholds") or {}
            subs = {}
            for name in (sc.get("subscales") or {}):
                bytp = {}
                for tp in tps:
                    vals = [v for v in (r["scores"].get("subscales", {}).get(name, {}).get("mean")
                                        for r in panel.get(tp, {}).values()) if v is not None]
                    d = _describe(vals)
                    if thr and vals:
                        d["pct_acceptable"] = round(sum(1 for v in vals if v >= thr.get("acceptable", 4.0)) / len(vals) * 100, 1)
                        d["pct_good"] = round(sum(1 for v in vals if v >= thr.get("good", 5.0)) / len(vals) * 100, 1)
                    bytp[tp] = d
                subs[name] = bytp
            entry["subscales"] = subs
            entry["thresholds"] = thr

        if sc.get("nps_item"):
            npsd = {}
            for tp in tps:
                cls = [r["scores"].get("nps", {}).get("class") for r in panel.get(tp, {}).values()]
                cls = [c for c in cls if c]
                if cls:
                    n, pro, det = len(cls), cls.count("promoter"), cls.count("detractor")
                    npsd[tp] = {"n": n, "promoters": pro, "passives": cls.count("passive"),
                                "detractors": det, "nps": round((pro - det) / n * 100, 1)}
            if npsd:
                entry["nps"] = npsd

        alpha = _alpha_for_part(s, resp)
        if alpha:
            entry["cronbach_alpha"] = alpha

        if method == "none" and sc.get("part") == "A":
            entry["background"] = _background_dist(s, resp)

        parts_out.append(entry)

    return {"study": study, "respondents": len(all_patients), "parts": parts_out,
            "note": ("n 小，依文件以效應量 r（rank-biserial，post>pre 為正）與個別軌跡為主；"
                     "p 值請用匯出 CSV 於外部統計軟體（JASP/R/jamovi）計算 Wilcoxon/Friedman。")}


@router.get("/study/{study}/export")
def study_export(study: str, format: str = Query("long"), me: dict = Depends(current_user)):
    """tidy CSV 匯出（限 doctor）。long＝逐題長表；wide＝每受試者一列、construct×timepoint。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅醫護端可匯出研究資料")
    if format not in ("long", "wide"):
        raise HTTPException(status_code=400, detail="format 需為 long 或 wide")
    sb = get_supabase()
    surveys = _study_surveys(sb, study)
    if not surveys:
        raise HTTPException(status_code=404, detail="找不到該研究問卷組")

    buf = io.StringIO()
    w = csv.writer(buf)

    if format == "long":
        w.writerow(["participant_code", "patient_id", "part", "timepoint", "item_id", "value"])
        for s in surveys:
            part = s["scoring"].get("part")
            for r in _responses_for(sb, s["key"]):
                pc = r["participant_code"] or ""
                for iid, val in (r["answers"] or {}).items():
                    if isinstance(val, list):
                        val = "|".join(str(x) for x in val)
                    w.writerow([pc, r["patient_id"], part, r["timepoint"], iid, val])
    else:  # wide
        cols = ["participant_code", "patient_id"]
        colmap = []  # (col, survey_key, tp, (kind, sub_name))
        for s in surveys:
            sc = s["scoring"]
            method = sc.get("method")
            part = (sc.get("part") or "").lower()
            for tp in (sc.get("timepoints") or []):
                if method in ("mean", "sum"):
                    cols.append(f"{part}_{tp}"); colmap.append((f"{part}_{tp}", s["key"], tp, ("primary", None)))
                elif method == "top_score":
                    cols.append(f"{part}_top_{tp}"); colmap.append((f"{part}_top_{tp}", s["key"], tp, ("top", None)))
                    cols.append(f"{part}_mean_{tp}"); colmap.append((f"{part}_mean_{tp}", s["key"], tp, ("primary", None)))
                elif method == "subscales":
                    for name in (sc.get("subscales") or {}):
                        cols.append(f"{part}_{name}_{tp}"); colmap.append((f"{part}_{name}_{tp}", s["key"], tp, ("sub", name)))
                if sc.get("nps_item"):
                    cols.append(f"{part}_nps_{tp}"); colmap.append((f"{part}_nps_{tp}", s["key"], tp, ("nps", None)))

        panels = {s["key"]: _latest_panel(_responses_for(sb, s["key"])) for s in surveys}
        patients, pcodes = set(), {}
        for key, panel in panels.items():
            for tp, d in panel.items():
                for pid, r in d.items():
                    patients.add(pid)
                    if r.get("participant_code"):
                        pcodes[pid] = r["participant_code"]

        w.writerow(cols)
        for pid in sorted(patients):
            row = [pcodes.get(pid, ""), pid]
            for col, key, tp, (kind, name) in colmap:
                r = panels[key].get(tp, {}).get(pid)
                v = ""
                if r:
                    scj = r["scores"]
                    if kind == "primary":
                        v = _primary_value(scj)
                    elif kind == "top":
                        v = scj.get("top_score") if scj.get("top_score_valid") else ""
                    elif kind == "sub":
                        v = scj.get("subscales", {}).get(name, {}).get("mean")
                    elif kind == "nps":
                        v = scj.get("nps", {}).get("score")
                row.append("" if v is None else v)
            w.writerow(row)

    return PlainTextResponse(
        buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{study}_{format}.csv"'},
    )

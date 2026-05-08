"""藥物搜尋（藥物百科）router。

提供「藥名 → 副作用、風險、用法、基礎衛教」的查詢服務。

策略：先查 drug_reference 快取表；沒命中才呼叫 LLM 整理，並把結果寫回快取。
這樣同一個藥再被搜尋時就直接從 DB 拿，省 LLM 成本、也維持回覆一致性。

來源欄位：
- 文字搜尋：GET /drug-search/?q=<藥名>
- 拍照辨識後一鍵查詢：POST /drug-search/from-photo（重用 medications 那一套 OCR）
- 從個人用藥列表查詢：GET /drug-search/from-medication/<medication_id>
- 看單筆快取資料：GET /drug-search/{drug_id}
- 熱門查詢排行（首頁可用）：GET /drug-search/trending
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json
import logging
import uuid

from backend.db import get_supabase
from backend.services.llm_service import (
    lookup_drug_info,
    recognize_medicine_bag,
    extract_medications_from_ocr_text,
)

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_DISCLAIMER = "此資訊由 AI 整理，僅供衛教參考，個別用藥請以醫師處方與藥師說明為準。"


# ── Models ────────────────────────────────────────────────


class DrugPhotoQuery(BaseModel):
    image_base64: str
    media_type: str = "image/jpeg"
    ocr_text: Optional[str] = None  # 前端瀏覽器若已用 Tesseract OCR，可直接送純文字省一次 vision


# ── 內部工具 ──────────────────────────────────────────────


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _decode_jsonish(value):
    """drug_reference 的 JSON 欄位在 Supabase 是 jsonb（已是 dict/list），
    在 SQLite fallback 是 TEXT JSON 字串 — 統一解碼。"""
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _serialize_for_db(value, supabase_native: bool):
    """寫入時：Supabase jsonb 直接吃 dict / list；SQLite TEXT 要 dumps。"""
    if value is None:
        return None
    if supabase_native:
        return value
    return json.dumps(value, ensure_ascii=False)


def _is_supabase_native() -> bool:
    """判斷目前的 client 是否是真實的 Supabase（jsonb 直收 dict），
    還是 SQLite fallback（TEXT 需要 json.dumps）。"""
    try:
        from backend.db import _SqliteSupabase  # type: ignore
        sb = get_supabase()
        return not isinstance(sb, _SqliteSupabase)
    except Exception:
        return True


def _row_to_response(row: dict) -> dict:
    """把 drug_reference 表的一筆 row 轉成前端友善的格式。"""
    return {
        "id": row.get("id"),
        "name_zh": row.get("name_zh"),
        "name_en": row.get("name_en"),
        "aliases": _decode_jsonish(row.get("aliases")) or [],
        "category": row.get("category"),
        "indication": row.get("indication"),
        "usage": row.get("usage"),
        "side_effects": _decode_jsonish(row.get("side_effects")) or {"common": [], "serious": []},
        "risks": _decode_jsonish(row.get("risks")) or {
            "contraindications": [], "warnings": [], "interactions": [],
        },
        "education": row.get("education"),
        "source": row.get("source") or "claude",
        "disclaimer": row.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": row.get("query_count") or 0,
        "cached": True,
        "matched": True,
    }


def _find_cached_by_query(sb, q: str) -> Optional[dict]:
    """以 name_zh / name_en / aliases 找快取。命中即回傳 row。"""
    qn = _norm(q)
    if not qn:
        return None
    try:
        rows = sb.table("drug_reference").select("*").execute().data or []
    except Exception as e:
        logger.warning("drug_reference cache lookup failed: %s", type(e).__name__)
        return None
    for r in rows:
        if _norm(r.get("name_zh")) == qn or _norm(r.get("name_en")) == qn:
            return r
        # aliases 可能是 jsonb (list) 或 TEXT JSON 字串
        aliases = _decode_jsonish(r.get("aliases")) or []
        if isinstance(aliases, list) and any(_norm(a) == qn for a in aliases):
            return r
    return None


def _save_to_cache(sb, info: dict, query_term: str) -> dict:
    """把 LLM 回的 dict 寫進 drug_reference，回傳寫入後的完整 row。
    若 LLM 沒給中英文名，就用使用者查詢字串當 fallback 名字以利之後比對。"""
    native = _is_supabase_native()
    drug_id = str(uuid.uuid4())
    aliases = info.get("aliases") or []
    if query_term and query_term not in aliases and _norm(query_term) not in (
        _norm(info.get("name_zh")), _norm(info.get("name_en"))
    ):
        # 把使用者輸入也加進 aliases，下一次同樣輸入就能命中快取
        aliases = list(aliases) + [query_term]

    payload = {
        "id": drug_id,
        "name_zh": info.get("name_zh"),
        "name_en": info.get("name_en"),
        "aliases": _serialize_for_db(aliases, native),
        "category": info.get("category"),
        "indication": info.get("indication"),
        "usage": info.get("usage"),
        "side_effects": _serialize_for_db(info.get("side_effects") or {}, native),
        "risks": _serialize_for_db(info.get("risks") or {}, native),
        "education": info.get("education"),
        "source": "claude",
        "disclaimer": info.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": 1,
    }
    try:
        sb.table("drug_reference").insert(payload).execute()
    except Exception as e:
        # 快取寫入失敗不影響回給使用者的內容；回傳 in-memory 的版本
        logger.warning("drug_reference insert failed: %s", e)
    # 把序列化版本還原成可以直接回給前端的格式
    payload["aliases"] = aliases
    payload["side_effects"] = info.get("side_effects") or {"common": [], "serious": []}
    payload["risks"] = info.get("risks") or {
        "contraindications": [], "warnings": [], "interactions": [],
    }
    return payload


def _bump_query_count(sb, drug_id: str, current_count: int) -> None:
    """命中快取時把計數 +1，方便做熱門排行。失敗就忽略。"""
    try:
        sb.table("drug_reference").update(
            {"query_count": (current_count or 0) + 1}
        ).eq("id", drug_id).execute()
    except Exception as e:
        logger.debug("drug_reference query_count bump skipped: %s", e)


# ── 文字搜尋 ──────────────────────────────────────────────


@router.get("/")
def search_drug(
    q: str = Query(..., min_length=1, description="藥名（中/英文/商品名）"),
    refresh: bool = Query(False, description="true=略過快取重新讓 AI 整理"),
):
    """以藥名搜尋藥物百科資訊。先查快取 → 沒命中再呼叫 LLM。"""
    sb = get_supabase()

    if not refresh:
        cached = _find_cached_by_query(sb, q)
        if cached:
            _bump_query_count(sb, cached.get("id"), cached.get("query_count") or 0)
            # 把 +1 反映到回傳資料，避免使用者看到舊值
            cached["query_count"] = (cached.get("query_count") or 0) + 1
            return _row_to_response(cached)

    info = lookup_drug_info(q)
    if not info.get("matched"):
        # LLM 表示無法辨識：不寫快取，但把訊息原樣回給前端
        return {
            "matched": False,
            "query": q,
            "name_zh": info.get("name_zh"),
            "name_en": info.get("name_en"),
            "aliases": info.get("aliases") or [],
            "category": None,
            "indication": None,
            "usage": None,
            "side_effects": {"common": [], "serious": []},
            "risks": {"contraindications": [], "warnings": [], "interactions": []},
            "education": None,
            "disclaimer": info.get("disclaimer") or DEFAULT_DISCLAIMER,
            "cached": False,
        }

    saved = _save_to_cache(sb, info, q)
    return {
        "id": saved.get("id"),
        "name_zh": saved.get("name_zh"),
        "name_en": saved.get("name_en"),
        "aliases": saved.get("aliases") or [],
        "category": saved.get("category"),
        "indication": saved.get("indication"),
        "usage": saved.get("usage"),
        "side_effects": saved.get("side_effects") or {"common": [], "serious": []},
        "risks": saved.get("risks") or {
            "contraindications": [], "warnings": [], "interactions": [],
        },
        "education": saved.get("education"),
        "source": "claude",
        "disclaimer": saved.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": 1,
        "cached": False,
        "matched": True,
    }


@router.get("/{drug_id}")
def get_drug(drug_id: str):
    """取得單筆已快取藥物的完整資訊。"""
    sb = get_supabase()
    try:
        rows = sb.table("drug_reference").select("*").eq("id", drug_id).limit(1).execute().data or []
    except Exception as e:
        logger.warning("drug_reference get failed: %s", e)
        raise HTTPException(status_code=500, detail="藥物資料查詢失敗")
    if not rows:
        raise HTTPException(status_code=404, detail=f"找不到藥物：{drug_id}")
    return _row_to_response(rows[0])


@router.get("/trending/list")
def trending_drugs(limit: int = Query(8, ge=1, le=30)):
    """熱門查詢藥物排行（依 query_count 由高到低）。給首頁推薦欄位用。"""
    sb = get_supabase()
    try:
        rows = (
            sb.table("drug_reference")
            .select("*")
            .order("query_count", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as e:
        logger.warning("drug_reference trending failed: %s", e)
        rows = []
    items = []
    for r in rows:
        items.append({
            "id": r.get("id"),
            "name_zh": r.get("name_zh"),
            "name_en": r.get("name_en"),
            "category": r.get("category"),
            "query_count": r.get("query_count") or 0,
        })
    return {"items": items}


# ── 拍照搜尋（重用既有 medication 辨識） ──────────────────


@router.post("/from-photo")
def search_from_photo(body: DrugPhotoQuery):
    """拍藥袋 / 藥單 → 自動把每筆藥名拿去查藥物百科。

    - 先重用 recognize_medicine_bag 抽藥名（或前端送 ocr_text 直接抽）
    - 對每筆藥名呼叫 /drug-search/?q=<name> 同樣的快取邏輯
    - 回傳 [{ recognized: 原始藥名, info: 百科欄位 }] 陣列
    """
    if body.ocr_text:
        rec = extract_medications_from_ocr_text(body.ocr_text)
    else:
        rec = recognize_medicine_bag(body.image_base64, body.media_type)

    parsed = rec.get("medications") or []
    sb = get_supabase()
    results = []
    for med in parsed:
        name = (med.get("name") or "").strip()
        if not name:
            continue
        cached = _find_cached_by_query(sb, name)
        if cached:
            _bump_query_count(sb, cached.get("id"), cached.get("query_count") or 0)
            entry = _row_to_response(cached)
            entry["cached"] = True
        else:
            info = lookup_drug_info(name)
            if info.get("matched"):
                saved = _save_to_cache(sb, info, name)
                entry = {
                    "id": saved.get("id"),
                    "name_zh": saved.get("name_zh"),
                    "name_en": saved.get("name_en"),
                    "aliases": saved.get("aliases") or [],
                    "category": saved.get("category"),
                    "indication": saved.get("indication"),
                    "usage": saved.get("usage"),
                    "side_effects": saved.get("side_effects"),
                    "risks": saved.get("risks"),
                    "education": saved.get("education"),
                    "source": "claude",
                    "disclaimer": saved.get("disclaimer"),
                    "matched": True,
                    "cached": False,
                }
            else:
                entry = {
                    "matched": False,
                    "disclaimer": info.get("disclaimer") or DEFAULT_DISCLAIMER,
                }
        results.append({
            "recognized_name": name,
            "recognized_dosage": med.get("dosage"),
            "recognized_frequency": med.get("frequency"),
            "info": entry,
        })

    # 把辨識階段的錯誤清單脫敏（只留 provider 名 + 是否成功），
    # 不洩漏例外訊息 / stack trace。
    raw_errors = rec.get("errors") or []
    sanitized_errors = [
        {"provider": (e or {}).get("provider"), "failed": True}
        for e in raw_errors if isinstance(e, dict)
    ]
    return {
        "provider": rec.get("provider"),
        "errors": sanitized_errors,
        "results": results,
    }


# ── 從個人用藥清單一鍵查詢 ─────────────────────────────────


@router.get("/from-medication/{medication_id}")
def search_from_medication(medication_id: str):
    """以個人用藥清單裡的某筆 medication_id 查藥物百科。

    用途：使用者在「藥物紀錄」頁的某筆藥旁邊點「查詢詳情」，前端帶 medication_id 過來，
    後端從 medications 表讀出 name 後走同樣的快取邏輯。
    """
    sb = get_supabase()
    try:
        rows = (
            sb.table("medications")
            .select("id,name,dosage")
            .eq("id", medication_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as e:
        logger.warning("medication lookup for drug-search failed: %s", e)
        raise HTTPException(status_code=500, detail="個人用藥資料讀取失敗")
    if not rows:
        raise HTTPException(status_code=404, detail=f"找不到用藥紀錄：{medication_id}")
    name = (rows[0].get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="此用藥紀錄沒有藥名，無法查詢")

    # 重用 search_drug 的邏輯
    return search_drug(q=name, refresh=False)

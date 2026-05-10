"""疾病查詢（疾病百科）router。

提供「疾病名 → 資訊、用藥、風險與併發症、未來發展」的查詢服務，
以及在已查詢疾病脈絡下的對話式追問。

策略：先查 disease_reference 快取表；沒命中才呼叫 LLM 整理，並把結果寫回快取。
所有回覆一律附上免責聲明 + PubMed 文獻來源（每次查 LLM 後即時抓近期 review）。

來源欄位：
- 文字搜尋：GET /diseases/?q=<疾病名>
- 看單筆快取資料：GET /diseases/{disease_id}
- 在脈絡下追問：POST /diseases/chat
- 從症狀分析結果一鍵查：GET /diseases/from-symptom/{symptom_log_id}
- 熱門查詢：GET /diseases/trending/list
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Literal
import json
import logging
import uuid

from backend.db import get_supabase
from backend.services.llm_service import (
    lookup_disease_info,
    pubmed_search,
    disease_chat,
)

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_DISCLAIMER = (
    "此資訊由 AI 整理，僅供衛教參考，不能取代醫師診斷與個別處方。"
    "實際治療請以您的主治醫師建議為準。"
)


# ── Models ────────────────────────────────────────────────


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class DiseaseChatRequest(BaseModel):
    disease_id: Optional[str] = None       # 已查過的疾病 id（優先）
    disease_query: Optional[str] = None    # 或直接給名字（會去查 / 建立快取）
    message: str
    history: Optional[List[ChatTurn]] = None


# ── 內部工具 ──────────────────────────────────────────────


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _decode_jsonish(value):
    """disease_reference 的 JSON 欄位在 Supabase 是 jsonb（已是 dict/list），
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
    if value is None:
        return None
    if supabase_native:
        return value
    return json.dumps(value, ensure_ascii=False)


def _is_supabase_native() -> bool:
    try:
        from backend.db import _SqliteSupabase  # type: ignore
        sb = get_supabase()
        return not isinstance(sb, _SqliteSupabase)
    except Exception:
        return True


def _row_to_response(row: dict) -> dict:
    """把 disease_reference 的一筆 row 轉成前端友善的格式。"""
    return {
        "id": row.get("id"),
        "name_zh": row.get("name_zh"),
        "name_en": row.get("name_en"),
        "aliases": _decode_jsonish(row.get("aliases")) or [],
        "icd10_code": row.get("icd10_code"),
        "icd10_category": row.get("icd10_category"),
        "overview": row.get("overview"),
        "causes": _decode_jsonish(row.get("causes")) or [],
        "symptoms": _decode_jsonish(row.get("symptoms")) or {"common": [], "warning": []},
        "common_medications": _decode_jsonish(row.get("common_medications")) or [],
        "treatments": _decode_jsonish(row.get("treatments")) or [],
        "complications": _decode_jsonish(row.get("complications")) or [],
        "prognosis": row.get("prognosis"),
        "self_care": _decode_jsonish(row.get("self_care")) or [],
        "red_flags": _decode_jsonish(row.get("red_flags")) or [],
        "references": _decode_jsonish(row.get("references_data")) or [],
        "source": row.get("source") or "claude",
        "disclaimer": row.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": row.get("query_count") or 0,
        "cached": True,
        "matched": True,
    }


def _info_has_useful_content(info: dict) -> bool:
    if not (info.get("name_zh") or info.get("name_en")):
        return False
    syms = info.get("symptoms") or {}
    return any([
        info.get("overview"),
        info.get("prognosis"),
        info.get("causes"),
        isinstance(syms, dict) and (syms.get("common") or syms.get("warning")),
        info.get("common_medications"),
        info.get("treatments"),
        info.get("complications"),
        info.get("self_care"),
        info.get("red_flags"),
    ])


def _row_has_useful_content(row: dict) -> bool:
    has_name = bool((row.get("name_zh") or "").strip() or (row.get("name_en") or "").strip())
    if not has_name:
        return False
    syms = _decode_jsonish(row.get("symptoms")) or {}
    return any([
        (row.get("overview") or "").strip(),
        (row.get("prognosis") or "").strip(),
        _decode_jsonish(row.get("causes")) or [],
        _decode_jsonish(row.get("common_medications")) or [],
        _decode_jsonish(row.get("treatments")) or [],
        _decode_jsonish(row.get("complications")) or [],
        _decode_jsonish(row.get("self_care")) or [],
        _decode_jsonish(row.get("red_flags")) or [],
        isinstance(syms, dict) and (syms.get("common") or syms.get("warning")),
    ])


def _find_cached_by_query(sb, q: str) -> Optional[dict]:
    qn = _norm(q)
    if not qn:
        return None
    try:
        rows = sb.table("disease_reference").select("*").execute().data or []
    except Exception as e:
        logger.warning("disease_reference cache lookup failed: %s", type(e).__name__)
        return None
    for r in rows:
        matched_row = (
            _norm(r.get("name_zh")) == qn
            or _norm(r.get("name_en")) == qn
        )
        if not matched_row:
            aliases = _decode_jsonish(r.get("aliases")) or []
            if isinstance(aliases, list) and any(_norm(a) == qn for a in aliases):
                matched_row = True
        if matched_row and _row_has_useful_content(r):
            return r
    return None


def _save_to_cache(sb, info: dict, query_term: str, refs: list) -> dict:
    native = _is_supabase_native()
    disease_id = str(uuid.uuid4())
    aliases = info.get("aliases") or []
    if query_term and query_term not in aliases and _norm(query_term) not in (
        _norm(info.get("name_zh")), _norm(info.get("name_en"))
    ):
        aliases = list(aliases) + [query_term]

    payload = {
        "id": disease_id,
        "name_zh": info.get("name_zh"),
        "name_en": info.get("name_en"),
        "aliases": _serialize_for_db(aliases, native),
        "icd10_code": info.get("icd10_code"),
        "icd10_category": info.get("icd10_category"),
        "overview": info.get("overview"),
        "causes": _serialize_for_db(info.get("causes") or [], native),
        "symptoms": _serialize_for_db(info.get("symptoms") or {"common": [], "warning": []}, native),
        "common_medications": _serialize_for_db(info.get("common_medications") or [], native),
        "treatments": _serialize_for_db(info.get("treatments") or [], native),
        "complications": _serialize_for_db(info.get("complications") or [], native),
        "prognosis": info.get("prognosis"),
        "self_care": _serialize_for_db(info.get("self_care") or [], native),
        "red_flags": _serialize_for_db(info.get("red_flags") or [], native),
        "references_data": _serialize_for_db(refs or [], native),
        "source": "claude",
        "disclaimer": info.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": 1,
    }
    try:
        sb.table("disease_reference").insert(payload).execute()
    except Exception as e:
        logger.warning("disease_reference insert failed: %s", e)

    # 還原成可直接給前端的格式
    payload["aliases"] = aliases
    payload["causes"] = info.get("causes") or []
    payload["symptoms"] = info.get("symptoms") or {"common": [], "warning": []}
    payload["common_medications"] = info.get("common_medications") or []
    payload["treatments"] = info.get("treatments") or []
    payload["complications"] = info.get("complications") or []
    payload["self_care"] = info.get("self_care") or []
    payload["red_flags"] = info.get("red_flags") or []
    payload["references_data"] = refs or []
    return payload


def _bump_query_count(sb, disease_id: str, current_count: int) -> None:
    try:
        sb.table("disease_reference").update(
            {"query_count": (current_count or 0) + 1}
        ).eq("id", disease_id).execute()
    except Exception as e:
        logger.debug("disease_reference query_count bump skipped: %s", e)


def _pubmed_query_for(info: dict, fallback: str) -> str:
    """挑一個最適合丟去 PubMed 搜尋的字串：優先英文名，其次中文名，再不行 fallback。"""
    return (info.get("name_en") or info.get("name_zh") or fallback or "").strip()


# ── 文字搜尋 ──────────────────────────────────────────────


@router.get("/")
def search_disease(
    q: str = Query(..., min_length=1, description="疾病名稱（中/英文）"),
    refresh: bool = Query(False, description="true=略過快取重新讓 AI 整理"),
):
    """以疾病名搜尋疾病百科。先查快取 → 沒命中再呼叫 LLM + PubMed。"""
    sb = get_supabase()

    if not refresh:
        cached = _find_cached_by_query(sb, q)
        if cached:
            _bump_query_count(sb, cached.get("id"), cached.get("query_count") or 0)
            cached["query_count"] = (cached.get("query_count") or 0) + 1
            return _row_to_response(cached)

    info = lookup_disease_info(q)

    if not info.get("matched") or not _info_has_useful_content(info):
        return {
            "matched": False,
            "query": q,
            "name_zh": info.get("name_zh"),
            "name_en": info.get("name_en"),
            "aliases": info.get("aliases") or [],
            "disclaimer": info.get("disclaimer") or DEFAULT_DISCLAIMER,
            "references": [],
        }

    # 拿 PubMed 文獻（失敗就空 list，不影響主流程）
    refs = pubmed_search(_pubmed_query_for(info, q), max_results=3)

    saved = _save_to_cache(sb, info, q, refs)
    out = {
        "id": saved["id"],
        "name_zh": saved.get("name_zh"),
        "name_en": saved.get("name_en"),
        "aliases": saved.get("aliases") or [],
        "icd10_code": saved.get("icd10_code"),
        "icd10_category": saved.get("icd10_category"),
        "overview": saved.get("overview"),
        "causes": saved.get("causes") or [],
        "symptoms": saved.get("symptoms") or {"common": [], "warning": []},
        "common_medications": saved.get("common_medications") or [],
        "treatments": saved.get("treatments") or [],
        "complications": saved.get("complications") or [],
        "prognosis": saved.get("prognosis"),
        "self_care": saved.get("self_care") or [],
        "red_flags": saved.get("red_flags") or [],
        "references": saved.get("references_data") or [],
        "source": "claude",
        "disclaimer": saved.get("disclaimer") or DEFAULT_DISCLAIMER,
        "query_count": saved.get("query_count") or 1,
        "cached": False,
        "matched": True,
    }
    return out


# ── 單筆查詢 ──────────────────────────────────────────────


@router.get("/{disease_id}")
def get_disease_by_id(disease_id: str):
    """看單筆快取的疾病資料。"""
    sb = get_supabase()
    try:
        rows = sb.table("disease_reference").select("*").eq("id", disease_id).limit(1).execute().data or []
    except Exception as e:
        logger.warning("disease_reference get failed: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法連線")
    if not rows:
        raise HTTPException(status_code=404, detail="找不到這筆疾病資料")
    return _row_to_response(rows[0])


# ── 對話式追問 ─────────────────────────────────────────────


@router.post("/chat")
def chat_about_disease(body: DiseaseChatRequest):
    """在已查詢的疾病脈絡下追問。

    任一個 disease_id 或 disease_query 必須給：
    - disease_id：已快取的疾病 id（優先）
    - disease_query：疾病名稱字串；後端會 lazy 查/建立快取
    """
    if not (body.message or "").strip():
        raise HTTPException(status_code=400, detail="請輸入問題")

    sb = get_supabase()
    context_row: Optional[dict] = None

    if body.disease_id:
        try:
            rows = sb.table("disease_reference").select("*").eq("id", body.disease_id).limit(1).execute().data or []
        except Exception as e:
            logger.warning("disease chat lookup failed: %s", e)
            rows = []
        if rows:
            context_row = rows[0]

    if context_row is None and body.disease_query:
        # 沒給 id 或查不到 → 走 search 流程，會把結果寫進快取
        cached = _find_cached_by_query(sb, body.disease_query)
        if cached:
            context_row = cached
        else:
            info = lookup_disease_info(body.disease_query)
            if info.get("matched") and _info_has_useful_content(info):
                refs = pubmed_search(_pubmed_query_for(info, body.disease_query), max_results=3)
                context_row = _save_to_cache(sb, info, body.disease_query, refs)

    if context_row is None:
        raise HTTPException(
            status_code=404,
            detail="找不到這個疾病，請先用 /diseases/?q= 搜尋一次再追問。",
        )

    # context_row 可能是 DB 的原始 row（JSON 欄位是字串）— 先解碼成 Python 結構再餵給 LLM
    decoded_context = {
        "name_zh": context_row.get("name_zh"),
        "name_en": context_row.get("name_en"),
        "icd10_code": context_row.get("icd10_code"),
        "overview": context_row.get("overview"),
        "causes": _decode_jsonish(context_row.get("causes")) or context_row.get("causes") or [],
        "symptoms": _decode_jsonish(context_row.get("symptoms")) or context_row.get("symptoms") or {},
        "common_medications": (
            _decode_jsonish(context_row.get("common_medications"))
            or context_row.get("common_medications") or []
        ),
        "treatments": _decode_jsonish(context_row.get("treatments")) or context_row.get("treatments") or [],
        "complications": (
            _decode_jsonish(context_row.get("complications"))
            or context_row.get("complications") or []
        ),
        "prognosis": context_row.get("prognosis"),
        "self_care": _decode_jsonish(context_row.get("self_care")) or context_row.get("self_care") or [],
        "red_flags": _decode_jsonish(context_row.get("red_flags")) or context_row.get("red_flags") or [],
    }

    hist = None
    if body.history:
        hist = [{"role": t.role, "content": t.content} for t in body.history[-12:]]

    try:
        reply = disease_chat(decoded_context, body.message, history=hist)
    except Exception as e:
        logger.error("disease_chat failed: %s", type(e).__name__)
        reply = (
            "抱歉，疾病助手暫時忙線中，請稍後再試。"
            "若您有不適或緊急狀況，請直接就醫或撥打 119。\n"
            "此回覆由 AI 整理，僅供衛教參考；實際診療請依您的主治醫師為準。"
        )

    references = (
        _decode_jsonish(context_row.get("references_data"))
        or context_row.get("references_data") or []
    )

    return {
        "reply": reply,
        "disease_id": context_row.get("id"),
        "disease_name": (
            context_row.get("name_zh") or context_row.get("name_en") or body.disease_query or ""
        ),
        "references": references,
        "disclaimer": context_row.get("disclaimer") or DEFAULT_DISCLAIMER,
    }


# ── 從症狀分析結果一鍵查詢 ──────────────────────────────────


@router.get("/from-symptom/{symptom_log_id}")
def from_symptom(symptom_log_id: str, disease: Optional[str] = Query(None)):
    """從症狀分析紀錄一鍵查疾病。

    若帶 ?disease=xxx 就直接查那個名字；否則嘗試從 symptoms_log.ai_response 抓
    第一個 likely / possible_conditions 的疾病名。
    """
    sb = get_supabase()

    target = (disease or "").strip()
    if not target:
        try:
            rows = sb.table("symptoms_log").select("ai_response").eq("id", symptom_log_id).limit(1).execute().data or []
        except Exception as e:
            logger.warning("symptoms_log lookup failed: %s", e)
            rows = []
        if rows:
            ai_resp = _decode_jsonish(rows[0].get("ai_response")) or rows[0].get("ai_response")
            if isinstance(ai_resp, dict):
                # 試著從常見欄位拿 disease 名（ai_analyzer 不同版本欄位略有差異）
                for key in ("likely_diseases", "possible_conditions", "differential", "candidates"):
                    val = ai_resp.get(key)
                    if isinstance(val, list) and val:
                        first = val[0]
                        if isinstance(first, str):
                            target = first
                            break
                        if isinstance(first, dict):
                            target = first.get("name") or first.get("disease") or first.get("zh") or ""
                            if target:
                                break

    if not target:
        raise HTTPException(
            status_code=400,
            detail="無法從症狀紀錄解析出疾病名稱，請改用 ?disease= 指定，或直接到疾病百科搜尋。",
        )

    return search_disease(q=target, refresh=False)


# ── 熱門查詢 ──────────────────────────────────────────────


@router.get("/trending/list")
def trending_diseases(limit: int = Query(8, ge=1, le=30)):
    """回最常被查詢的疾病。"""
    sb = get_supabase()
    try:
        result = (
            sb.table("disease_reference")
            .select("id,name_zh,name_en,icd10_code,query_count")
            .order("query_count", desc=True)
            .limit(limit)
            .execute()
        )
        items = result.data or []
    except Exception as e:
        logger.warning("disease_reference trending failed: %s", e)
        items = []
    return {"items": items}

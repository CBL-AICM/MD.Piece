"""TFDA（衛生福利部食品藥物管理署）西藥許可證資料查詢。

把使用者搜尋的藥名比對到台灣的官方藥品許可證，把「中文品名、英文品名、適應症、
主成分、廠商」等官方欄位拿出來給 LLM 當權威依據，避免 LLM 自己翻譯出簡體或翻譯腔
（例如 acetaminophen 被翻成「對乙醯氨基酚」而不是台灣常用的「乙醯胺酚」）。

策略：
1. 第一次被呼叫時下載完整資料集到記憶體（約 3 萬筆，幾 MB），TTL 24h
2. 之後在記憶體做大小寫不敏感的比對（中文／英文／成分名）
3. 任何失敗（網路、解析、找不到）→ 回 None，呼叫端會 fallback 走純 LLM

部署設定：
- 預設 URL 是衛福部食藥署「西藥、醫療器材、含藥化粧品許可證資料集」的 OpenAPI 匯出
- 若預設 URL 失效或要換資料源，設環境變數 `TFDA_DRUG_API_URL` 覆寫
- 若想完全停用 TFDA 查詢（例如本地開發無網），設 `TFDA_DRUG_LOOKUP=disabled`
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 衛福部食藥署 西藥、醫療器材、含藥化粧品許可證資料集（公開、無需金鑰）
# 失效或要切換資源時，用 env var 覆寫即可
DEFAULT_TFDA_URL = (
    "https://data.fda.gov.tw/opendata/exportDataList.do"
    "?method=ExportData&InfoId=36"
)
TFDA_DRUG_API_URL = os.getenv("TFDA_DRUG_API_URL", DEFAULT_TFDA_URL)
TFDA_DISABLED = os.getenv("TFDA_DRUG_LOOKUP", "").lower() == "disabled"

# 資料集 TTL：24 小時（許可證更新頻率約一個月一次，24h 已是極端保守）
_CACHE_TTL_SECONDS = 24 * 60 * 60
_FETCH_TIMEOUT = 30.0

# in-memory cache：{ "records": list[dict], "fetched_at": float }
_cache: dict = {}
_cache_lock = threading.Lock()


def _normalize(s: Optional[str]) -> str:
    """大小寫、去空白、全半形敏感度都拿掉，只比對乾淨字串。"""
    if not s:
        return ""
    return "".join(s.split()).strip().lower()


def _parse_records(raw) -> list[dict]:
    """TFDA 開放資料的 JSON 結構過去出現過幾種版本：
      a) 直接是 list[record]
      b) {"data": list[record]}
      c) {"value": list[record]} (OData 風格)
    把它正規化成統一的欄位名 (name_zh / name_en / ingredient / indication /
    manufacturer / license_no)，後續比對才不會跟著欄位名變動而壞掉。
    """
    if isinstance(raw, dict):
        for key in ("data", "value", "result", "records"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
    if not isinstance(raw, list):
        return []

    records: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # TFDA 欄位中文名（常見）：中文品名、英文品名、有效成分、適應症、製造廠名稱、許可證字號
        # 同時允許英文 key（不同版本資料集會用不同名字）
        name_zh = (
            item.get("中文品名")
            or item.get("ChineseName")
            or item.get("name_zh")
            or ""
        )
        name_en = (
            item.get("英文品名")
            or item.get("EnglishName")
            or item.get("name_en")
            or ""
        )
        ingredient = (
            item.get("有效成分")
            or item.get("成分")
            or item.get("Ingredient")
            or item.get("ingredient")
            or ""
        )
        indication = (
            item.get("適應症")
            or item.get("Indication")
            or item.get("indication")
            or ""
        )
        manufacturer = (
            item.get("製造廠名稱")
            or item.get("廠商名稱")
            or item.get("Manufacturer")
            or item.get("manufacturer")
            or ""
        )
        license_no = (
            item.get("許可證字號")
            or item.get("LicenseNo")
            or item.get("license_no")
            or ""
        )
        if not (name_zh or name_en):
            # 沒有任何藥名 → 留下也比對不到
            continue
        records.append({
            "name_zh": str(name_zh).strip(),
            "name_en": str(name_en).strip(),
            "ingredient": str(ingredient).strip(),
            "indication": str(indication).strip(),
            "manufacturer": str(manufacturer).strip(),
            "license_no": str(license_no).strip(),
        })
    return records


def _fetch_dataset() -> list[dict]:
    """下載 TFDA 開放資料 → 解析。失敗回空 list（呼叫端會 cache 空 list 避免狂抓）。"""
    if TFDA_DISABLED:
        return []
    try:
        resp = httpx.get(TFDA_DRUG_API_URL, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("TFDA dataset fetch failed: %s: %s", type(e).__name__, e)
        return []

    # 內容可能是 JSON / OData JSON / 部分版本是含 BOM 的 UTF-8 JSON
    try:
        data = resp.json()
    except ValueError as e:
        logger.warning("TFDA dataset is not valid JSON: %s", e)
        return []

    records = _parse_records(data)
    logger.info("TFDA dataset loaded: %d records", len(records))
    return records


def _get_records() -> list[dict]:
    """取得記憶體裡的 TFDA 資料；過期或從未抓過就重新下載。"""
    now = time.time()
    with _cache_lock:
        cached = _cache.get("records")
        fetched_at = _cache.get("fetched_at", 0.0)
        if cached is not None and (now - fetched_at) < _CACHE_TTL_SECONDS:
            return cached

    # 釋放鎖才下載（網路 IO 不要卡其他 thread）
    records = _fetch_dataset()

    with _cache_lock:
        # 即使是空 list 也快取，避免每個 request 都重抓打爆 TFDA
        _cache["records"] = records
        _cache["fetched_at"] = now
    return records


def _match_record(records: list[dict], query: str) -> Optional[dict]:
    """以使用者輸入比對：先試完全相等（中文／英文／成分），再試 substring。"""
    q = _normalize(query)
    if not q:
        return None

    # 第一輪：完全相等（大小寫 / 空白後）
    for r in records:
        if (
            _normalize(r.get("name_zh")) == q
            or _normalize(r.get("name_en")) == q
            or _normalize(r.get("ingredient")) == q
        ):
            return r

    # 第二輪：英文成分常見「acetaminophen 500mg」這種 — 比對 q 是否被任一欄位包含
    # （避免 q 太短誤命中：至少 4 字元才允許 substring 比對）
    if len(q) >= 4:
        for r in records:
            haystack = " ".join(filter(None, [
                _normalize(r.get("name_zh")),
                _normalize(r.get("name_en")),
                _normalize(r.get("ingredient")),
            ]))
            if q in haystack:
                return r

    return None


def lookup_drug_in_tfda(drug_name: str) -> Optional[dict]:
    """以使用者查詢字串到 TFDA 西藥許可證找對應的官方資料。

    回傳 dict：{ name_zh, name_en, ingredient, indication, manufacturer, license_no }
    找不到、TFDA 不可用、或 disabled → 回 None（呼叫端 fallback 走純 LLM）。
    """
    if TFDA_DISABLED:
        return None
    if not drug_name or not drug_name.strip():
        return None
    records = _get_records()
    if not records:
        return None
    return _match_record(records, drug_name)

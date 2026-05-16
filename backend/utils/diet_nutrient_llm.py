"""LLM 結構化飲食營養素分類器（方案 C）

把使用者口語化的食物字串（例：「一顆溫泉蛋, 半個雞胸肉, 柳橙綠茶, 泡麵, 舒跑」）
交給 Claude 解析成結構化營養素，回傳 (protein_g, water_ml, fiber_g)。

設計重點：
- 雙層 cache：行程內 LRU（functools）+ Supabase 持久化（diet_nutrient_cache）
- 任何步驟失敗（LLM 例外、JSON parse 失敗、Supabase 不可用）都降回 keyword fallback
- 由 env DIET_NUTRIENT_LLM 控制（預設 1 開啟；設 0 強制走 keyword）

Supabase 需要的資料表（手動 apply）：

    create table if not exists diet_nutrient_cache (
        foods_key   text primary key,
        items       jsonb not null,
        total_protein_g  numeric not null default 0,
        total_water_ml   numeric not null default 0,
        total_fiber_g    numeric not null default 0,
        created_at  timestamptz not null default now()
    );
    create index if not exists diet_nutrient_cache_created_idx
        on diet_nutrient_cache (created_at desc);
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_LLM_ENABLED = os.getenv("DIET_NUTRIENT_LLM", "1") not in ("0", "false", "False", "")
_LLM_MAX_ITEMS = 12  # 每筆 record 最多解析這麼多項，防止 prompt 爆量

NUTRIENT_LLM_SYSTEM_PROMPT = (
    "你是台灣飲食營養分析助手。輸入是一段使用者口語化的食物清單，"
    "可能含份量修飾（半個、一顆、兩碗、×2、半塊…）與多種食物。\n"
    "請逐項解析，每項估算「一份常見份量」的蛋白質/水分/纖維，並抓出份量倍數。\n\n"
    "輸出純 JSON（**不要** markdown code block、**不要**前後綴文字）：\n"
    "{\n"
    '  "items": [\n'
    '    {"name": "<標準化食物名>", "count": <number>, '
    '"protein_g": <number>, "water_ml": <number>, "fiber_g": <number>}\n'
    "  ]\n"
    "}\n\n"
    "規則：\n"
    "1. 繁體中文、台灣食品慣用名（柳橙＝柳丁、番茄＝蕃茄都可）\n"
    "2. 「一份」採國健署常見份量：白飯 1 碗、雞胸 100g、蛋 1 顆、青菜 100g、飲料 1 杯\n"
    "3. count 倍數：半個/半塊=0.5、一/一顆/一碗=1、兩/雙=2、×N=N；抓不到填 1\n"
    "4. 飲料的 water_ml 取整杯（手搖/茶飲 350-500、運動飲料 500、湯品 250）\n"
    "5. 含糖飲料（舒跑、可樂、奶茶…）的 protein/fiber 保守填 0\n"
    "6. 完全看不懂的食物：name 保留原字串、三項營養素全填 0\n"
    "7. 寧可保守低估，不要瞎掰數值\n"
    "8. items 至多 12 項；超過請挑前 12 項\n"
)


# ──────────────────────────────────────────────────────────────────────
# Normalization & in-memory cache
# ──────────────────────────────────────────────────────────────────────

def _normalize_foods_key(foods: str) -> str:
    """正規化作為 cache key：trim、合併空白、去重複標點。"""
    s = foods.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[，,；;、]+", ",", s)
    return s


# 行程內 cache（單 process 共用），上限 1024 條
@lru_cache(maxsize=1024)
def _llm_classify_cached(foods_key: str) -> Optional[tuple]:
    """純呼 LLM + 解 JSON，回 (protein_g, water_ml, fiber_g, items_json)。

    任何錯誤都回 None，由呼叫端決定 fallback。lru_cache 不快取 None
    （Python lru_cache 會快取 None；這裡用 sentinel 規避）。
    """
    result = _llm_classify_raw(foods_key)
    if result is None:
        # 用一個明顯的 sentinel，這樣 lru_cache 也會「記得」失敗過、
        # 同一段文字下次直接走 fallback 而不再燒 token
        return ("__LLM_FAILED__", 0.0, 0.0, 0.0, [])
    return result


def _llm_classify_raw(foods_key: str) -> Optional[tuple]:
    """實際呼叫 LLM、parse JSON、加總。"""
    try:
        from backend.services.llm_service import call_claude
    except Exception as e:
        logger.warning(f"diet_nutrient_llm: llm_service 載入失敗 {e}")
        return None

    try:
        raw = call_claude(NUTRIENT_LLM_SYSTEM_PROMPT, foods_key, max_tokens=512)
    except Exception as e:
        logger.warning(f"diet_nutrient_llm: call_claude 失敗 {e}")
        return None

    text = (raw or "").strip()
    # 容錯：把可能的 markdown code block 去掉
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"diet_nutrient_llm: JSON parse 失敗 raw={text[:200]!r}")
        return None

    items_raw = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items_raw, list):
        return None

    items: list[dict] = []
    p_sum = w_sum = f_sum = 0.0
    for it in items_raw[:_LLM_MAX_ITEMS]:
        if not isinstance(it, dict):
            continue
        try:
            count = float(it.get("count", 1) or 1)
            p = float(it.get("protein_g", 0) or 0)
            w = float(it.get("water_ml", 0) or 0)
            f = float(it.get("fiber_g", 0) or 0)
        except (TypeError, ValueError):
            continue
        name = str(it.get("name", "")).strip() or "未知"
        # 防呆：負數或荒謬大數直接 clamp
        count = max(0.0, min(count, 20.0))
        p = max(0.0, min(p, 200.0))
        w = max(0.0, min(w, 2000.0))
        f = max(0.0, min(f, 50.0))
        items.append({
            "name": name, "count": count,
            "protein_g": p, "water_ml": w, "fiber_g": f,
        })
        p_sum += count * p
        w_sum += count * w
        f_sum += count * f

    return ("ok", round(p_sum, 1), round(w_sum, 1), round(f_sum, 1), items)


# ──────────────────────────────────────────────────────────────────────
# Supabase persistent cache（graceful）
# ──────────────────────────────────────────────────────────────────────

def _read_persistent_cache(foods_key: str) -> Optional[tuple[float, float, float]]:
    try:
        from backend.db import get_supabase
        sb = get_supabase()
        rows = (sb.table("diet_nutrient_cache")
                  .select("total_protein_g,total_water_ml,total_fiber_g")
                  .eq("foods_key", foods_key)
                  .limit(1)
                  .execute())
        data = (rows.data or [])
        if not data:
            return None
        r = data[0]
        return (float(r.get("total_protein_g") or 0),
                float(r.get("total_water_ml")  or 0),
                float(r.get("total_fiber_g")   or 0))
    except Exception:
        # 表不存在、欄位不對、Supabase 不可用…全當沒 cache
        return None


def _write_persistent_cache(foods_key: str, items: list[dict],
                            p: float, w: float, f: float) -> None:
    try:
        from backend.db import get_supabase
        sb = get_supabase()
        sb.table("diet_nutrient_cache").upsert({
            "foods_key": foods_key,
            "items": items,
            "total_protein_g": p,
            "total_water_ml":  w,
            "total_fiber_g":   f,
        }).execute()
    except Exception:
        # 寫不進去就算了，行程內 cache 還是有效
        pass


# ──────────────────────────────────────────────────────────────────────
# Public entry
# ──────────────────────────────────────────────────────────────────────

def estimate_nutrients(
    foods: str,
    fallback: Callable[[str], tuple[float, float, float]],
) -> tuple[float, float, float]:
    """主入口：LLM 解析 → 失敗就 fallback 到 keyword 版。

    Args:
        foods: 原始食物字串
        fallback: 失敗時呼叫的 keyword 版 estimator，必須接 str 回 (p, w, f)

    Returns:
        (protein_g, water_ml, fiber_g)
    """
    if not foods:
        return 0.0, 0.0, 0.0
    if not _LLM_ENABLED:
        return fallback(foods)

    key = _normalize_foods_key(foods)
    if not key:
        return 0.0, 0.0, 0.0

    # L2: Supabase 持久 cache（行程重啟也保留）
    persistent = _read_persistent_cache(key)
    if persistent is not None:
        return persistent

    # L1: 行程內 LRU + LLM 呼叫
    result = _llm_classify_cached(key)
    if result is None or result[0] != "ok":
        return fallback(foods)

    _, p, w, f, items = result
    # 寫回持久 cache（best effort）
    _write_persistent_cache(key, items, p, w, f)
    return p, w, f


def reset_caches_for_test() -> None:
    """測試用：清空行程內 LRU。"""
    _llm_classify_cached.cache_clear()

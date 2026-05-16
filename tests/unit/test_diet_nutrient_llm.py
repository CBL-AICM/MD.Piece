"""diet_nutrient_llm 的單元測試。

覆蓋：
- LLM 成功回傳結構化 JSON → 加總正確
- count（份量倍數）有套用到加總
- LLM 例外 → 降回 keyword fallback
- LLM 回非 JSON → 降回 fallback 且失敗結果被快取（不會重複燒 token）
- DIET_NUTRIENT_LLM=0 → 直接走 fallback、完全不呼叫 LLM
- Supabase 持久 cache 命中時直接回傳，不呼 LLM
"""

from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_module(monkeypatch):
    """每個測試前重新載入模組，清空 LRU、讓 env 變更生效。"""
    monkeypatch.setenv("DIET_NUTRIENT_LLM", "1")
    import backend.utils.diet_nutrient_llm as mod
    importlib.reload(mod)
    yield mod
    mod.reset_caches_for_test()


def _fallback_zero(_foods: str) -> tuple[float, float, float]:
    return 99.0, 99.0, 99.0  # 用獨特值，方便驗證有沒有被走到


# ── LLM 成功 ────────────────────────────────────────────────────

def test_llm_happy_path(_reset_module):
    mod = _reset_module
    llm_json = json.dumps({
        "items": [
            {"name": "溫泉蛋", "count": 2, "protein_g": 6, "water_ml": 30, "fiber_g": 0},
            {"name": "雞胸肉", "count": 0.5, "protein_g": 25, "water_ml": 0, "fiber_g": 0},
        ]
    })
    with patch("backend.services.llm_service.call_claude", return_value=llm_json) as cc:
        p, w, f = mod.estimate_nutrients("一顆溫泉蛋×2, 半個雞胸肉", _fallback_zero)
    assert cc.called
    # 2*6 + 0.5*25 = 24.5
    assert p == pytest.approx(24.5, abs=0.1)
    # 2*30 + 0.5*0 = 60
    assert w == pytest.approx(60.0, abs=0.1)
    assert f == 0.0


def test_llm_strips_markdown_fence(_reset_module):
    mod = _reset_module
    raw = "```json\n" + json.dumps({
        "items": [{"name": "白飯", "count": 1, "protein_g": 4, "water_ml": 80, "fiber_g": 1}]
    }) + "\n```"
    with patch("backend.services.llm_service.call_claude", return_value=raw):
        p, w, f = mod.estimate_nutrients("一碗白飯", _fallback_zero)
    assert (p, w, f) == (4.0, 80.0, 1.0)


def test_llm_clamps_garbage_values(_reset_module):
    """LLM 回離譜大數要被 clamp，不會污染統計。"""
    mod = _reset_module
    llm_json = json.dumps({
        "items": [
            {"name": "??", "count": 99999, "protein_g": 99999,
             "water_ml": -100, "fiber_g": 99999},
        ]
    })
    with patch("backend.services.llm_service.call_claude", return_value=llm_json):
        p, w, f = mod.estimate_nutrients("亂打", _fallback_zero)
    # count clamp 20、p clamp 200 → 上限 4000；water 負值 clamp 0
    assert p <= 4000.0
    assert w == 0.0
    assert f <= 1000.0


# ── Fallback ────────────────────────────────────────────────────

def test_llm_exception_falls_back(_reset_module):
    mod = _reset_module
    with patch("backend.services.llm_service.call_claude",
               side_effect=RuntimeError("boom")):
        p, w, f = mod.estimate_nutrients("一顆蛋", _fallback_zero)
    assert (p, w, f) == (99.0, 99.0, 99.0)


def test_llm_non_json_falls_back(_reset_module):
    mod = _reset_module
    with patch("backend.services.llm_service.call_claude",
               return_value="這不是 JSON"):
        p, w, f = mod.estimate_nutrients("亂七八糟", _fallback_zero)
    assert (p, w, f) == (99.0, 99.0, 99.0)


def test_failure_is_cached_no_repeat_call(_reset_module):
    """LLM 失敗一次後，同段文字再來不應該再 call LLM（省 token）。"""
    mod = _reset_module
    with patch("backend.services.llm_service.call_claude",
               return_value="bad") as cc:
        mod.estimate_nutrients("某段文字", _fallback_zero)
        mod.estimate_nutrients("某段文字", _fallback_zero)
        mod.estimate_nutrients("某段文字  ", _fallback_zero)  # 正規化後同 key
    assert cc.call_count == 1


# ── Env toggle ──────────────────────────────────────────────────

def test_env_disables_llm(monkeypatch):
    monkeypatch.setenv("DIET_NUTRIENT_LLM", "0")
    import backend.utils.diet_nutrient_llm as mod
    importlib.reload(mod)
    with patch("backend.services.llm_service.call_claude") as cc:
        p, w, f = mod.estimate_nutrients("一顆蛋", _fallback_zero)
    assert not cc.called
    assert (p, w, f) == (99.0, 99.0, 99.0)


# ── 持久 cache 命中 ────────────────────────────────────────────

def test_persistent_cache_hit_skips_llm(_reset_module):
    mod = _reset_module
    fake_row = {"total_protein_g": 12.3, "total_water_ml": 45.6, "total_fiber_g": 7.8}
    fake_sb = MagicMock()
    (fake_sb.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value) = MagicMock(data=[fake_row])

    with patch("backend.db.get_supabase", return_value=fake_sb), \
         patch("backend.services.llm_service.call_claude") as cc:
        p, w, f = mod.estimate_nutrients("某餐", _fallback_zero)

    assert not cc.called
    assert (p, w, f) == (12.3, 45.6, 7.8)


def test_empty_string_returns_zeros(_reset_module):
    mod = _reset_module
    with patch("backend.services.llm_service.call_claude") as cc:
        assert mod.estimate_nutrients("", _fallback_zero) == (0.0, 0.0, 0.0)
        assert mod.estimate_nutrients("   ", _fallback_zero) == (0.0, 0.0, 0.0)
    assert not cc.called

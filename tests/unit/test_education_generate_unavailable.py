"""education /generate 失敗分流的單元測試。

重點在「為什麼」要分流，不只是「有沒有 raise」：

- LLM 整條 provider chain 死光（多半是 production 沒設 API key）是**永久性**失敗，
  再重試也不會好 → 必須回 503 + detail.error="llm_unavailable"，前端才會顯示
  「請管理者設定 API key」而不是無限「稍後再試」。
- rate-limit / 短暫錯誤是**暫時性**失敗 → 維持 500，前端的自動重試才有意義。
- 這個分流原本只有「模式 1（ICD-10+維度）」有，「模式 2（自由主題）」漏了；
  一般書本章節走的是模式 2，所以這支測試同時鎖住兩種模式都要正確分流。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.routers.education as edu

# call_claude 跑完整 chain 全失敗時真正會 raise 的字串（見 llm_service.call_claude）
_CHAIN_DEAD = RuntimeError("所有 LLM provider 都失敗，最後錯誤：[Errno 111] Connection refused")
# 暫時性錯誤：retry 用完仍 rate-limited，不該被當成 unavailable
_TRANSIENT = RuntimeError("Groq retry 全部用完仍 rate-limited")


@pytest.fixture(autouse=True)
def _no_supabase(monkeypatch):
    """避開 Supabase：cache 一律 miss、save/bump no-op，讓每次都實際走到 LLM 分支。"""
    monkeypatch.setattr(edu, "_edu_get_cache", lambda *a, **k: None)
    monkeypatch.setattr(edu, "_edu_save_cache", lambda *a, **k: None)
    monkeypatch.setattr(edu, "_edu_bump_count", lambda *a, **k: None)


def _patch_llm(monkeypatch, exc):
    def _boom(*_a, **_k):
        raise exc
    # education.py 是 `from ... import call_claude`，要 patch 它自己 namespace 裡的名字
    monkeypatch.setattr(edu, "call_claude", _boom)


def _call(body):
    with pytest.raises(HTTPException) as ei:
        edu.generate_education(body)
    return ei.value


def test_topic_chain_dead_returns_503_unavailable(monkeypatch):
    """模式 2（自由主題）全 provider 死光 → 503 llm_unavailable（本次修的 bug）。"""
    _patch_llm(monkeypatch, _CHAIN_DEAD)
    exc = _call(edu.EducationRequest(topic="紅斑性狼瘡：什麼是 SLE"))
    assert exc.status_code == 503
    assert isinstance(exc.detail, dict) and exc.detail.get("error") == "llm_unavailable"


def test_topic_transient_error_stays_500(monkeypatch):
    """模式 2 暫時性錯誤 → 仍 500，不可被誤判為 unavailable（否則前端自動重試形同失效）。"""
    _patch_llm(monkeypatch, _TRANSIENT)
    exc = _call(edu.EducationRequest(topic="紅斑性狼瘡：什麼是 SLE"))
    assert exc.status_code == 500
    # 確認不是 llm_unavailable 的 dict detail
    assert not (isinstance(exc.detail, dict) and exc.detail.get("error") == "llm_unavailable")


def test_icd10_dimension_chain_dead_returns_503_unavailable(monkeypatch):
    """模式 1（ICD-10+維度）全死光 → 503，確保本次改動沒有讓既有分流回歸。"""
    _patch_llm(monkeypatch, _CHAIN_DEAD)
    icd_prefix = next(iter(edu.ICD10_MAP.keys()))
    dimension = next(iter(edu.DIMENSION_PROMPTS.keys()))
    exc = _call(edu.EducationRequest(icd10_code=icd_prefix + ".0", dimension=dimension))
    assert exc.status_code == 503
    assert isinstance(exc.detail, dict) and exc.detail.get("error") == "llm_unavailable"

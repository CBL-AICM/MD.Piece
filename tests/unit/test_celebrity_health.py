"""celebrity_health 服務的單元測試。

涵蓋：
- 預過濾：黑名單來源 / 缺健康關鍵字 / 揣測詞一律不送 LLM
- LLM 回 is_celebrity_health=true → 帶出 person/disease/icd10/related_articles
- LLM 回 is_celebrity_health=false → 過濾掉，且結果寫入負快取
- LLM 例外 / 非 JSON → 對該則回 None，不擋其他則
- 24h 快取命中 → 不重複呼叫 LLM
- CELEBRITY_HEALTH_ENABLED=0 → 直接回 []，完全不呼叫 LLM
- LLM 呼叫上限：超過 MAX_LLM_CALLS_PER_REQUEST 就停止
- 反查表：常見別名（中風、肺腺癌、SLE…）都能命中
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.services import celebrity_health


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setenv("CELEBRITY_HEALTH_ENABLED", "true")
    celebrity_health.reset_cache()
    yield
    celebrity_health.reset_cache()


def _item(title="", summary="", link="https://example.com/1", source=""):
    return {"title": title, "summary": summary, "link": link, "source": source}


# ── 預過濾 ────────────────────────────────────────────────


def test_skip_official_source_by_link():
    """衛福部官方公告 (link 含 mohw.gov.tw)：不送 LLM，回 0。"""
    items = [_item(
        title="衛福部公告：林志玲確診糖尿病",  # 帶名人 + 疾病也不放行
        summary="新聞稿",
        link="https://www.mohw.gov.tw/news/123",
    )]
    with patch("backend.services.celebrity_health.call_claude") as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []
    assert not cc.called


def test_skip_official_source_by_feed():
    """來源欄位含 cdc.gov.tw 也黑名單。"""
    items = [_item(
        title="名人確診糖尿病分享心路歷程",
        summary="...",
        link="https://example.com/1",
        source="https://www.cdc.gov.tw/rss/health.xml",
    )]
    with patch("backend.services.celebrity_health.call_claude") as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []
    assert not cc.called


def test_skip_no_health_keyword():
    """沒提到健康關鍵字 → 不送 LLM。"""
    items = [_item(
        title="某藝人公布新專輯",
        summary="演唱會宣傳",
        link="https://example.com/2",
    )]
    with patch("backend.services.celebrity_health.call_claude") as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []
    assert not cc.called


def test_skip_rumor_keywords():
    """含揣測詞「疑似」「驚傳」「傳出」→ 不送 LLM。"""
    items = [
        _item(title="驚傳某天王罹癌住院", summary="...", link="https://e.com/a"),
        _item(title="某影后疑似確診失智症", summary="...", link="https://e.com/b"),
        _item(title="傳出某政要中風", summary="...", link="https://e.com/c"),
    ]
    with patch("backend.services.celebrity_health.call_claude") as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []
    assert not cc.called


# ── LLM happy path ────────────────────────────────────────


def test_extracts_celebrity_story():
    items = [_item(
        title="余苑綺證實大腸癌復發，分享治療歷程",
        summary="余苑綺在臉書親自證實大腸癌再度復發，目前持續化療中",
        link="https://news.example.com/yuyuanqi",
    )]
    llm_json = json.dumps({
        "is_celebrity_health": True,
        "person": "余苑綺",
        "disease_keyword": "大腸癌",
        "event_type": "治療中",
        "soft_framing": "余苑綺分享治療歷程，提醒我們 50 歲後定期篩檢的重要性",
    })
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json) as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert cc.called
    assert len(out) == 1
    s = out[0]
    assert s["person"] == "余苑綺"
    assert s["disease_keyword"] == "大腸癌"
    assert s["icd10_prefix"] == "C18"
    assert s["disease_name"] == "大腸癌"
    assert s["event_type"] == "治療中"
    assert "篩檢" in s["soft_framing"]
    assert s["source_link"] == "https://news.example.com/yuyuanqi"


def test_extracts_with_alias_mapping():
    """LLM 抽出『肺腺癌』 → 應反查到 C34 肺癌。"""
    items = [_item(
        title="某資深藝人罹肺腺癌，呼籲戒菸",
        summary="他表示確診後積極治療中",
        link="https://news.example.com/x",
    )]
    llm_json = json.dumps({
        "is_celebrity_health": True,
        "person": "某藝人",
        "disease_keyword": "肺腺癌",
        "event_type": "倡議推廣",
        "soft_framing": "他用親身經驗呼籲戒菸與定期低劑量電腦斷層篩檢",
    })
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json):
        out = celebrity_health.extract_celebrity_stories(items)
    assert out[0]["icd10_prefix"] == "C34"
    assert out[0]["disease_name"] == "肺癌"


def test_unknown_disease_keeps_story_but_no_icd10():
    """LLM 抽出系統沒收錄的疾病 → 仍然回故事，但 icd10_prefix=None。"""
    items = [_item(
        title="某名人確診罕見疾病",
        summary="確診後分享心路歷程",
        link="https://news.example.com/rare",
    )]
    llm_json = json.dumps({
        "is_celebrity_health": True,
        "person": "某名人",
        "disease_keyword": "罕見病 XYZ",
        "event_type": "確診",
        "soft_framing": "他的勇敢分享讓更多人關注罕病議題",
    })
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json):
        out = celebrity_health.extract_celebrity_stories(items)
    assert len(out) == 1
    assert out[0]["icd10_prefix"] is None
    assert out[0]["disease_name"] is None
    assert out[0]["related_articles"] == []


# ── LLM 過濾 / 錯誤 ────────────────────────────────────────


def test_llm_says_not_celebrity_health_filtered():
    items = [_item(
        title="新型癌症治療藥獲核准",
        summary="衛福部宣布新藥納入健保",
        link="https://news.example.com/drug",
    )]
    llm_json = json.dumps({"is_celebrity_health": False})
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json):
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []


def test_llm_exception_skips_item():
    items = [
        _item(title="某藝人確診糖尿病分享病情", summary="...", link="https://e.com/a"),
        _item(title="某球員手術康復回歸", summary="...", link="https://e.com/b"),
    ]

    def flaky(*args, **kwargs):
        if "糖尿病" in args[1]:
            raise RuntimeError("LLM 掛了")
        return json.dumps({
            "is_celebrity_health": True,
            "person": "某球員",
            "disease_keyword": "其他",
            "event_type": "康復",
            "soft_framing": "他的康復故事鼓勵了許多病友",
        })

    with patch("backend.services.celebrity_health.call_claude", side_effect=flaky):
        out = celebrity_health.extract_celebrity_stories(items)
    assert len(out) == 1
    assert out[0]["person"] == "某球員"


def test_llm_returns_non_json_skipped():
    items = [_item(
        title="某藝人確診癌症",
        summary="確診後分享",
        link="https://e.com/x",
    )]
    with patch("backend.services.celebrity_health.call_claude", return_value="這不是 JSON"):
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []


def test_llm_returns_partial_json_skipped():
    """LLM 回 true 但缺欄位 → 不算合格。"""
    items = [_item(
        title="某藝人確診糖尿病",
        summary="分享病情",
        link="https://e.com/x",
    )]
    llm_json = json.dumps({"is_celebrity_health": True, "person": "某人"})  # 缺 disease/framing
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json):
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []


# ── 快取 ────────────────────────────────────────────────


def test_cache_hits_skip_llm_on_second_call():
    items = [_item(
        title="某藝人確診糖尿病分享心路",
        summary="...",
        link="https://news.example.com/cache",
    )]
    llm_json = json.dumps({
        "is_celebrity_health": True,
        "person": "某藝人",
        "disease_keyword": "糖尿病",
        "event_type": "治療中",
        "soft_framing": "他的經驗提醒我們血糖控制的重要",
    })
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json) as cc:
        first = celebrity_health.extract_celebrity_stories(items)
        second = celebrity_health.extract_celebrity_stories(items)
    assert cc.call_count == 1
    assert first == second
    assert len(first) == 1


def test_negative_cache_skips_llm_on_second_call():
    items = [_item(
        title="新型癌症治療藥",
        summary="非名人新聞",
        link="https://news.example.com/neg",
    )]
    llm_json = json.dumps({"is_celebrity_health": False})
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json) as cc:
        celebrity_health.extract_celebrity_stories(items)
        celebrity_health.extract_celebrity_stories(items)
    assert cc.call_count == 1


# ── 上限 / 開關 ────────────────────────────────────────


def test_disabled_by_env(monkeypatch):
    monkeypatch.setenv("CELEBRITY_HEALTH_ENABLED", "false")
    items = [_item(
        title="某藝人確診糖尿病",
        summary="...",
        link="https://e.com/x",
    )]
    with patch("backend.services.celebrity_health.call_claude") as cc:
        out = celebrity_health.extract_celebrity_stories(items)
    assert out == []
    assert not cc.called


def test_stops_at_limit():
    items = [
        _item(
            title=f"某藝人{i}確診糖尿病分享心路歷程",
            summary="...",
            link=f"https://e.com/{i}",
        )
        for i in range(10)
    ]
    llm_json = json.dumps({
        "is_celebrity_health": True,
        "person": "某藝人",
        "disease_keyword": "糖尿病",
        "event_type": "治療中",
        "soft_framing": "他的經驗提醒我們血糖控制的重要",
    })
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json) as cc:
        out = celebrity_health.extract_celebrity_stories(items, limit=3)
    assert len(out) == 3
    assert cc.call_count == 3  # 命中 limit 就停


def test_llm_call_budget_bounds_latency():
    """全部都通過預過濾但 LLM 全回 false → 最多跑 MAX_LLM_CALLS_PER_REQUEST 次。"""
    items = [
        _item(
            title=f"新癌症研究 {i} 治療突破",
            summary="...",
            link=f"https://e.com/study{i}",
        )
        for i in range(20)
    ]
    llm_json = json.dumps({"is_celebrity_health": False})
    with patch("backend.services.celebrity_health.call_claude", return_value=llm_json) as cc:
        celebrity_health.extract_celebrity_stories(items)
    assert cc.call_count == celebrity_health.MAX_LLM_CALLS_PER_REQUEST


# ── 反查表 ────────────────────────────────────────────────


@pytest.mark.parametrize("keyword,expected_prefix", [
    ("糖尿病", "E11"),
    ("高血壓", "I10"),
    ("中風", "I63"),
    ("腦中風", "I63"),
    ("失智症", "G30"),
    ("阿茲海默", "G30"),
    ("巴金森氏症", "G20"),
    ("漸凍症", "G12"),
    ("乳癌", "C50"),
    ("肺癌", "C34"),
    ("肺腺癌", "C34"),
    ("大腸癌", "C18"),
    ("結腸癌", "C18"),
    ("洗腎", "N18"),
    ("狼瘡", "M32"),
    ("SLE", "M32"),
    ("類風濕性關節炎", "M06"),
    ("痛風", "M10"),
    ("骨質疏鬆", "M81"),
    ("憂鬱症", "F32"),
])
def test_reverse_icd10_aliases(keyword, expected_prefix):
    assert celebrity_health._map_disease_to_icd10(keyword) == expected_prefix


def test_reverse_icd10_unknown_returns_none():
    assert celebrity_health._map_disease_to_icd10("某種完全不存在的疾病 ABCXYZ") is None
    assert celebrity_health._map_disease_to_icd10("") is None

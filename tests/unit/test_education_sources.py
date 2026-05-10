"""education_content 模組的單元測試。

涵蓋：
- _parse_source 從來源字串抽 IF / 年份 / DOI / PMID / journal
- has_high_if_sources 評估是否符合 IF>5 規範
- _load_article 解析新格式的 frontmatter（含引號字串、特殊字元）
"""

from pathlib import Path

import pytest

from backend.services.education_content import (
    Article,
    HIGH_IF_JOURNALS,
    _parse_source,
    _load_article,
)


# ── _parse_source ──────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected_if,expected_year,expected_doi",
    [
        (
            "Whelton PK, et al. (2018). 2017 ACC/AHA Hypertension Guideline. Hypertension (IF=7.7). doi:10.1161/HYP.0000000000000065",
            7.7,
            "2018",
            "10.1161/HYP.0000000000000065",
        ),
        (
            "SPRINT Research Group (2015). NEJM (IF=158.5). doi:10.1056/NEJMoa1511939",
            158.5,
            "2015",
            "10.1056/NEJMoa1511939",
        ),
        (
            "Cipriani A, et al. (2018). Lancet (IF=98.4). doi:10.1016/S0140-6736(17)32802-7",
            98.4,
            "2018",
            "10.1016/S0140-6736(17)32802-7",
        ),
    ],
)
def test_parse_source_extracts_metadata(text, expected_if, expected_year, expected_doi):
    parsed = _parse_source(text)
    assert parsed["impact_factor"] == expected_if
    assert parsed["year"] == expected_year
    assert parsed["doi"] == expected_doi
    assert parsed["is_peer_reviewed"] is True


def test_parse_source_pmid():
    parsed = _parse_source("Some Author (2020). Title. Journal. PMID:12345678")
    assert parsed["pmid"] == "12345678"
    assert parsed["is_peer_reviewed"] is True


def test_parse_source_url():
    parsed = _parse_source("WHO Guidelines 2023. https://www.who.int/publications/x")
    assert parsed["url"] == "https://www.who.int/publications/x"


def test_parse_source_journal_lookup_fills_if():
    """期刊名能在 HIGH_IF_JOURNALS 找到時，自動補 IF。"""
    parsed = _parse_source("Some Author (2024). New England Journal of Medicine.")
    assert parsed["journal"] == "New England Journal of Medicine"
    assert parsed["impact_factor"] == HIGH_IF_JOURNALS["New England Journal of Medicine"]


def test_parse_source_guideline_no_if():
    parsed = _parse_source("中華民國心臟學會：2022 台灣高血壓治療指引")
    assert parsed["impact_factor"] is None
    assert parsed["doi"] is None
    assert parsed["is_peer_reviewed"] is False


def test_parse_source_empty():
    parsed = _parse_source("")
    assert parsed["text"] == ""
    assert parsed["impact_factor"] is None


# ── Article.has_high_if_sources ──────────────────────────────


def test_has_high_if_sources_meets_threshold():
    art = Article(
        slug="test",
        title="Test",
        sources=[
            "A et al. (2020). NEJM (IF=158.5). doi:10.1/x",
            "B et al. (2021). Lancet (IF=98.4). doi:10.2/y",
            "中華民國學會：指引（補充）",
        ],
    )
    assert art.has_high_if_sources(min_count=2, min_if=5.0) is True


def test_has_high_if_sources_below_threshold():
    art = Article(
        slug="test",
        title="Test",
        sources=[
            "A et al. (2020). NEJM (IF=158.5). doi:10.1/x",
            "中華民國學會：指引",
        ],
    )
    assert art.has_high_if_sources(min_count=2, min_if=5.0) is False


def test_has_high_if_sources_low_if_excluded():
    art = Article(
        slug="test",
        title="Test",
        sources=[
            "A et al. (2020). Some Journal (IF=2.5).",
            "B et al. (2021). Other Journal (IF=4.9).",
        ],
    )
    assert art.has_high_if_sources(min_count=2, min_if=5.0) is False


# ── to_card / to_full include parsed_sources + meets_evidence_standard ─


def test_to_card_includes_parsed_sources_and_evidence_flag():
    art = Article(
        slug="test",
        title="Test",
        sources=[
            "A et al. (2020). NEJM (IF=158.5). doi:10.1/x",
            "B et al. (2021). Lancet (IF=98.4). doi:10.2/y",
        ],
    )
    card = art.to_card()
    assert "parsed_sources" in card
    assert len(card["parsed_sources"]) == 2
    assert card["parsed_sources"][0]["impact_factor"] == 158.5
    assert card["meets_evidence_standard"] is True
    assert "body" not in card


def test_to_full_includes_body():
    art = Article(slug="t", title="T", body="hello", sources=[])
    full = art.to_full()
    assert full["body"] == "hello"
    assert full["meets_evidence_standard"] is False


# ── _load_article 解析新格式 frontmatter ────────────────────


def test_load_article_with_quoted_sources(tmp_path: Path):
    md = tmp_path / "test-article.md"
    md.write_text(
        """---
title: 測試文章
slug: test-article
icd10: I10
featured: true
category: disease
sources:
  - "Whelton PK, et al. (2018). 2017 ACC/AHA Hypertension Guideline. Hypertension (IF=7.7). doi:10.1161/HYP.0000000000000065"
  - "Williams B, et al. (2018). 2018 ESC/ESH Guidelines. European Heart Journal (IF=37.6). doi:10.1093/eurheartj/ehy339"
  - "中華民國心臟學會：2022 治療指引（補充指引）"
reviewed_at: 2026-05-10
---

# 測試文章

內容
""",
        encoding="utf-8",
    )
    art = _load_article(md)
    assert art is not None
    assert art.title == "測試文章"
    assert art.featured is True
    assert art.category == "disease"
    assert len(art.sources) == 3
    parsed = art.parsed_sources()
    assert parsed[0]["impact_factor"] == 7.7
    assert parsed[1]["impact_factor"] == 37.6
    assert parsed[2]["impact_factor"] is None
    assert art.has_high_if_sources(min_count=2, min_if=5.0) is True

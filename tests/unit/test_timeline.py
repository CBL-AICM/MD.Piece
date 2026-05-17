"""timeline 路由的純函式單元測試（不打 DB）。"""

from backend.routers.timeline import (
    _classify_importance,
    _normalize_date,
    _TYPE_TO_SEVERITY,
)


def test_admission_is_high_importance():
    assert _classify_importance("admission", None) == "high"


def test_cancer_icd10_is_high_importance():
    # C00–C97 都是 neoplasm
    assert _classify_importance("visit", "C50") == "high"


def test_cardiovascular_icd10_is_high_importance():
    # I00–I99 是循環系統
    assert _classify_importance("lab", "I21") == "high"


def test_general_visit_without_icd_is_normal():
    assert _classify_importance("visit", None) == "normal"
    assert _classify_importance("medication", None) == "normal"


def test_normalize_date_truncates_to_yyyy_mm_dd():
    assert _normalize_date("2026-05-17T08:23:00Z") == "2026-05-17"
    assert _normalize_date("2026-05-17") == "2026-05-17"
    assert _normalize_date(None) == ""
    assert _normalize_date("") == ""


def test_severity_token_names_match_css():
    valid = {"self", "clinic", "regional", "medical", "er"}
    for color in _TYPE_TO_SEVERITY.values():
        assert color in valid

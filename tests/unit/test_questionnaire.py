"""五層症狀問卷單元測試"""
from backend.utils.symptom_questionnaire import (
    BODY_PARTS,
    OVERALL_OPTIONS,
    calculate_severity_index,
    get_questionnaire_schema,
    to_structured_summary,
)


def test_questionnaire_schema_has_5_layers():
    schema = get_questionnaire_schema()
    assert len(schema["layers"]) == 5
    assert [l["step"] for l in schema["layers"]] == [1, 2, 3, 4, 5]


def test_questionnaire_skip_logic_for_good():
    schema = get_questionnaire_schema()
    layer1 = schema["layers"][0]
    assert "good" in layer1["skip_to_done_if"]
    assert "ok" in layer1["skip_to_done_if"]


def test_body_parts_have_front_and_back():
    assert "front" in BODY_PARTS
    assert "back" in BODY_PARTS
    # 確認座標都有
    for side in BODY_PARTS.values():
        for part in side:
            assert "x" in part and "y" in part and "label" in part


def test_severity_index_zero_for_good():
    assert calculate_severity_index({"overall_feeling": "good"}) == 0


def test_severity_index_amplified_by_pattern_and_locations():
    sub = {
        "overall_feeling": "bad",
        "severity": 8,
        "change_pattern": "sudden",  # weight 2
        "body_locations": ["chest", "left_arm", "head_front"],
    }
    # 8 * 2 * (1 + 0.2) / 2 = 9.6
    idx = calculate_severity_index(sub)
    assert 9.0 <= idx <= 10


def test_to_structured_summary_includes_all_dimensions():
    sub = {
        "overall_feeling": "bad",
        "body_locations": ["chest"],
        "symptom_types": ["pain"],
        "free_text": "走路就喘",
        "severity": 6,
        "change_pattern": "gradual_worse",
    }
    summary = to_structured_summary(sub)
    assert "整體感覺" in summary
    assert "胸部" in summary
    assert "痛" in summary
    assert "走路就喘" in summary
    assert "6" in summary

"""severity_color 對應規則的單元測試。

驗證 backend/routers/triage.py 的 severity_color_for() 把 triage 結果
正確對應到 docs/research/ui_color_research.md §4 的 5 級分級醫療 token。
"""

from backend.routers.triage import SEVERITY_COLOR_MAP, severity_color_for


def test_emergency_maps_to_er():
    assert severity_color_for("emergency") == "er"


def test_follow_up_maps_to_regional():
    assert severity_color_for("follow_up") == "regional"


def test_stable_maps_to_self_care():
    assert severity_color_for("stable") == "self"


def test_unknown_result_defaults_to_self():
    # 未知結果回 self（自我照護）— 不要把使用者誤導去急診
    assert severity_color_for("unknown") == "self"
    assert severity_color_for("") == "self"


def test_severity_token_names_are_valid_css_suffixes():
    # 確保所有 severity token 名稱都對應到 :root 裡的 --sev-* 變數
    valid_suffixes = {"self", "clinic", "regional", "medical", "er"}
    for color in SEVERITY_COLOR_MAP.values():
        assert color in valid_suffixes, f"{color} 不是合法的 --sev-* token"

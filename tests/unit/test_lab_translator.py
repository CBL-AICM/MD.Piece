"""檢驗數值白話翻譯單元測試"""
from backend.utils.lab_translator import LAB_REFERENCE, translate_value


def test_normal_crp_returns_normal_level():
    r = translate_value("CRP", 3)
    assert r["level"] == "normal"
    assert "穩定" in r["message"] or "正常" in r["message"]
    # 不能洩漏原始數字
    assert "3" not in r["message"]


def test_high_crp_does_not_alarm():
    r = translate_value("CRP", 7)
    assert r["level"] == "slightly_high"
    # 強調醫師已注意
    assert "醫師" in r["message"]


def test_trend_improvement_for_crp():
    r = translate_value("CRP", 4, previous=10)
    assert r["trend"] == "improved"


def test_unknown_code_falls_back_safely():
    r = translate_value("UNKNOWN_CODE", 99)
    assert r["level"] == "unknown"
    assert "醫師" in r["message"]


def test_hdl_inverted_logic():
    # HDL 越高越好；高於 nmin 是正常
    r = translate_value("HDL", 50)
    assert r["level"] == "normal"
    # HDL 偏低
    r2 = translate_value("HDL", 30)
    assert r2["level"] in ("slightly_low", "low")


def test_blood_pressure_known():
    assert "BP_systolic" in LAB_REFERENCE
    r = translate_value("BP_systolic", 120)
    assert r["level"] == "normal"

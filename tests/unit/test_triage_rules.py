"""第一層分流規則引擎（確定性急診紅旗閘）的單元測試。

驗證「為什麼」（鐵則 9）：這層是不走 LLM 的安全閘，必須能從病人自填的自由文字
口語中抓出致命紅旗。若有人把它退回「字串完全相等」比對，下列同義詞/子字串案例
就會失敗——而那正是把生命攸關的判斷悄悄丟給機率性 LLM 的退化。
"""

from backend.utils.triage_rules import (
    check_emergency,
    matched_emergency_symptoms,
)


def test_exact_canonical_still_triggers():
    assert check_emergency(["胸痛"]) is True
    assert check_emergency(["呼吸困難"]) is True


def test_colloquial_synonyms_trigger():
    # 病人不會剛好填 canonical；口語也必須觸發
    assert check_emergency(["胸悶"]) is True
    assert check_emergency(["喘不過氣"]) is True
    assert check_emergency(["突然講不出話"]) is True
    assert check_emergency(["心悸"]) is True
    assert check_emergency(["昏倒"]) is True


def test_substring_within_freetext_sentence_triggers():
    # 自由文字句子裡含紅旗詞也要抓到（子字串比對）
    assert check_emergency(["今天早上突然覺得胸口悶痛"]) is True
    assert check_emergency(["走幾步路就喘不過氣"]) is True


def test_case_and_space_insensitive():
    assert check_emergency(["Chest Pain"]) is True
    assert check_emergency(["  胸　痛  "]) is True


def test_non_emergency_does_not_trigger():
    # 一般症狀不可誤升級（否則安全閘失去意義、整天叫人去急診）
    assert check_emergency(["流鼻水"]) is False
    assert check_emergency(["輕微頭痛", "喉嚨癢"]) is False
    assert check_emergency([]) is False
    assert check_emergency(["", "  "]) is False


def test_immunosuppressed_fever_rule():
    # 免疫抑制 + 發燒 ≥38 → 紅旗；缺任一條件則否
    assert check_emergency([], is_immunosuppressed=True, temperature=38.5) is True
    assert check_emergency([], is_immunosuppressed=True, temperature=37.5) is False
    assert check_emergency([], is_immunosuppressed=False, temperature=39.0) is False


def test_matched_returns_original_input_strings():
    # 回傳病人實際填的原字串（供前端顯示），且只挑中紅旗那幾筆
    got = matched_emergency_symptoms(["流鼻水", "胸口悶痛", "喉嚨癢"])
    assert got == ["胸口悶痛"]

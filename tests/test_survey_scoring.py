"""
研究問卷計分引擎單元測試（純函式，不碰 DB）。

規則 9：每個測試都驗「為什麼這個行為重要」，而非只跑得過。
量表計分若寫錯（反向題沒反、N/A 沒排除、缺漏門檻沒擋、top-score 判錯），
會讓研究數據失真——這些測試正是用來在計分邏輯漂移時亮紅燈。

執行：
    pytest tests/test_survey_scoring.py        # 或
    python tests/test_survey_scoring.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers.surveys import (  # noqa: E402
    _score_response, _cronbach_alpha, _rank_biserial, _describe,
)
from backend.seed_study_surveys import STUDY_SURVEYS  # noqa: E402

S = {s["key"]: s for s in STUDY_SURVEYS}


def test_secd6_mean_and_missing_rule():
    # 為什麼：SECD-6 是「平均」計分，且文件規定「缺 > 2 題不計分」。
    full = _score_response(S["mdpiece-b1-secd6"], {1: 8, 2: 7, 3: 9, 4: 6, 5: 8, 6: 7})
    assert full["mean"] == 7.5 and full["valid"] is True
    miss3 = _score_response(S["mdpiece-b1-secd6"], {1: 8, 2: 7, 3: 9})
    assert miss3["valid"] is False and miss3["mean"] is None  # 缺 3 題 → 不計分


def test_eheals_sum_with_mean_imputation():
    # 為什麼：eHEALS 是加總（8–40），文件規定「缺 1 題以平均補」維持滿分可比。
    assert _score_response(S["mdpiece-b2-eheals"], {i: 5 for i in range(1, 9)})["total"] == 40
    miss1 = _score_response(S["mdpiece-b2-eheals"], {i: 5 for i in range(1, 8)})  # 缺 1
    assert miss1["valid"] is True and miss1["total"] == 40  # 7×5 平均補成 8×5


def test_wfpts_reverse_item_changes_total():
    # 為什麼：Wake Forest 第 1 題是反向題；沒做反向會把「最不信任」算成「最信任」。
    rev = _score_response(S["mdpiece-d2-trust"], {1: 1, 2: 5, 3: 5, 4: 5, 5: 5})
    assert rev["total"] == 25  # q1=1 反向→5，全分
    noflip = _score_response(S["mdpiece-d2-trust"], {1: 5, 2: 5, 3: 5, 4: 5, 5: 5})
    assert noflip["total"] == 21  # q1=5 反向→1
    assert rev["total"] != noflip["total"]  # 反向確實改變結果
    miss = _score_response(S["mdpiece-d2-trust"], {1: 1, 2: 5, 3: 5, 4: 5})  # 缺 1（max_missing 0）
    assert miss["valid"] is False


def test_mauq_subscales_and_na_excluded():
    # 為什麼：MAUQ 是三分量表平均，且 N/A 必須排除、不可當 0 計入。
    ans = {f"s{i}": 6 for i in range(1, 19)}
    r = _score_response(S["mdpiece-c5-mauq"], ans)
    assert r["subscales"]["ease"]["mean"] == 6.0 and r["subscales"]["ease"]["n"] == 5
    assert r["subscales"]["useful"]["n"] == 6
    ans["s1"] = "NA"
    r2 = _score_response(S["mdpiece-c5-mauq"], ans)
    assert r2["subscales"]["ease"]["n"] == 4 and r2["subscales"]["ease"]["mean"] == 6.0  # NA 不拉低平均


def test_collaborate_top_score():
    # 為什麼：collaboRATE 採 top-score（三題皆 9 才記 1），是文件指定的主要計分。
    assert _score_response(S["mdpiece-d3-collaborate"], {1: 9, 2: 9, 3: 9})["top_score"] == 1
    assert _score_response(S["mdpiece-d3-collaborate"], {1: 9, 2: 8, 3: 9})["top_score"] == 0


def test_c3_excludes_critical_trust_item():
    # 為什麼：C3 第 5 題測「批判性信任」，文件明令不納 C3 平均、需獨立報告。
    r = _score_response(S["mdpiece-c3-shap"], {1: 7, 2: 7, 3: 7, 4: 7, 5: 2})
    assert r["mean"] == 7.0  # 只平均 1–4
    assert r.get("extra", {}).get("5") == 2  # q5 獨立保留


def test_e_nps_classification_and_e1_mean():
    # 為什麼：E1 取平均、NPS（e2_1，0–10）需獨立分類，且不可混入 E1 平均。
    r = _score_response(S["mdpiece-e-intent"],
                        {"e1_1": 6, "e1_2": 6, "e1_3": 6, "e1_4": 6, "e2_1": 10, "e2_2": "很可能"})
    assert r["mean"] == 6.0  # e2_1 已排除
    assert r["nps"]["class"] == "promoter" and r["nps"]["score"] == 10
    detr = _score_response(S["mdpiece-e-intent"], {"e1_1": 5, "e1_2": 5, "e1_3": 5, "e1_4": 5, "e2_1": 6})
    assert detr["nps"]["class"] == "detractor"


def test_background_part_is_unscored():
    # 為什麼：背景資料不該被算成分數。
    r = _score_response(S["mdpiece-a-background"], {"a1": "男", "a4": ["高血壓", "第二型糖尿病"]})
    assert r["method"] == "none" and r["valid"] is True


def test_cronbach_alpha_perfect_and_insufficient():
    # 為什麼：α 是自編量表信度依據（目標 ≥ .7）；資料不足要安全回 None 而非報錯。
    assert _cronbach_alpha([[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6]]) == 1.0  # 完全相關 → 1
    assert _cronbach_alpha([[1, 2, 3]]) is None  # 只有 1 人 → 無法估


def test_rank_biserial_effect_size_direction():
    # 為什麼：n 小不依賴 p 值，效應量 r（rank-biserial）方向必須正確（post>pre 為正）。
    inc = _rank_biserial([5, 5, 5, 5], [7, 8, 6, 9])
    assert inc["r"] == 1.0 and inc["direction"] == "increase"
    dec = _rank_biserial([7, 8, 9], [5, 6, 7])
    assert dec["r"] == -1.0 and dec["direction"] == "decrease"
    assert _rank_biserial([5, 5], [5, 5]) is None  # 全無變化 → 無效應量


def test_describe_basic_stats():
    d = _describe([1, 2, 3, 4, 5])
    assert d["n"] == 5 and d["mean"] == 3.0 and d["median"] == 3.0 and d["min"] == 1.0 and d["max"] == 5.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", fn.__name__, "-", e)
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

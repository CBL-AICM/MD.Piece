"""
健康積分規則引擎單元測試（純函式，不碰 DB）。

規則 9：每個測試都驗「為什麼這條規則重要」，而非只跑得過。
積分若算錯（問卷沒給分、連續中斷把分數收回、兌換沒檢查餘額、等級門檻錯置），
會直接影響使用者信任與院方發放——這些測試就是用來在規則漂移時亮紅燈。

執行：
    pytest tests/test_rewards_rules.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import rewards_rules as R  # noqa: E402


def test_survey_and_active_day_points():
    # 為什麼：填問卷 +20/份、每日打卡 +10/天 是最核心的兩條規則，算錯整套就崩。
    a = {"survey_count": 2, "active_day_count": 5, "longest_streak": 0, "eheals_done": False}
    p = R.compute_points(a)
    assert p["breakdown"]["survey"] == 40
    assert p["breakdown"]["active_days"] == 50
    assert p["earned"] == 90  # 40 + 50，無連續/識能加分


def test_streak_bonus_is_cumulative_and_monotonic():
    # 為什麼：里程碑依「最長連續」累計，連續中斷不收回，使用者分數才不會倒退。
    assert R.streak_bonus(2) == (0, [])
    assert R.streak_bonus(7) == (55, [3, 7])          # 15 + 40
    assert R.streak_bonus(30) == (345, [3, 7, 14, 30])  # 15+40+90+200
    # 即使目前連續只剩 1 天，最長曾達 7 仍保留 55 分。
    a = {"survey_count": 0, "active_day_count": 0, "longest_streak": 7, "current_streak": 1}
    assert R.compute_points(a)["breakdown"]["streak"] == 55


def test_eheals_bonus_only_when_done():
    # 為什麼：eHEALS 完成才給 +30，沒完成不能給，否則獎勵失去意義。
    assert R.compute_points({"eheals_done": True})["breakdown"]["eheals"] == 30
    assert R.compute_points({"eheals_done": False})["breakdown"]["eheals"] == 0


def test_compute_streaks_current_is_trailing_run():
    # 為什麼：current 必須是「結尾那段」連續天數，而非整體最長，否則顯示會誤導。
    days = ["2026-06-01", "2026-06-02", "2026-06-03",  # 一段 3 連
            "2026-06-10", "2026-06-11"]                 # 結尾 2 連
    longest, current = R.compute_streaks(days)
    assert longest == 3 and current == 2
    # 重複日期不應灌水
    assert R.compute_streaks(["2026-06-01", "2026-06-01"]) == (1, 1)
    assert R.compute_streaks([]) == (0, 0)


def test_level_thresholds_and_progress():
    # 為什麼：等級門檻與「距離下一級」是使用者最常看的數字，錯置會直接被發現。
    assert R.level_for(0)["name"] == "萌芽"
    assert R.level_for(99)["index"] == 1
    lv2 = R.level_for(100)
    assert lv2["name"] == "穩定" and lv2["index"] == 2
    # 100→300 區間的中點 200，進度應為 0.5、距離下一級 100。
    mid = R.level_for(200)
    assert mid["progress"] == 0.5 and mid["to_next"] == 100
    top = R.level_for(5000)
    assert top["name"] == "達人" and top["progress"] == 1.0 and top["to_next"] == 0


def test_badges_unlock_on_exact_conditions():
    # 為什麼：徽章解鎖條件若鬆動（例如 6 天就給「規律一週」），徽章就名不符實。
    none = {b["id"]: b for b in R.evaluate_badges({})}
    assert none["week-regular"]["earned"] is False
    assert none["first-feedback"]["earned"] is False

    rich = {b["id"]: b for b in R.evaluate_badges({
        "survey_count": 1, "longest_streak": 30, "emotion_days": 14,
        "medication_log_count": 30, "eheals_done": True, "triple_day": True,
    })}
    assert all(rich[k]["earned"] for k in
               ["first-feedback", "week-regular", "month-regular",
                "mood-aware", "med-buddy", "eheals-done", "all-round"])
    # 邊界：連續 6 天還不該拿「規律一週」
    six = {b["id"]: b for b in R.evaluate_badges({"longest_streak": 6})}
    assert six["week-regular"]["earned"] is False


def test_catalog_affordability_reflects_balance():
    # 為什麼：買不起卻標成可兌換，會讓 redeem 後才失敗，體驗與信任雙輸。
    cat = {r["id"]: r for r in R.catalog_with_affordability(120)}
    assert cat["edu-booklet"]["affordable"] is True    # 50
    assert cat["priority-slot"]["affordable"] is True   # 120 剛好
    assert cat["health-kit"]["affordable"] is False     # 200 > 120
    assert R.get_reward("health-kit")["cost"] == 200
    assert R.get_reward("does-not-exist") is None

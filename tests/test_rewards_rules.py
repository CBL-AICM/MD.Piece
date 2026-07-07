"""
健康積分規則引擎單元測試（純函式，不碰 DB）。

規則 9：每個測試都驗「為什麼這條規則重要」，而非只跑得過。
積分若算錯（打卡沒給分、連續中斷把分數收回、兌換沒檢查餘額、等級門檻錯置），
會直接影響使用者信任與院方發放——這些測試就是用來在規則漂移時亮紅燈。

執行：
    pytest tests/test_rewards_rules.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import rewards_rules as R  # noqa: E402


def test_active_day_points():
    # 為什麼：每日打卡 +10/天 是核心計分規則，算錯整套就崩。
    a = {"active_day_count": 5, "longest_streak": 0}
    p = R.compute_points(a)
    assert p["breakdown"]["active_days"] == 50
    assert p["earned"] == 50  # 只有打卡分，無連續加分


def test_streak_bonus_is_cumulative_and_monotonic():
    # 為什麼：里程碑依「最長連續」累計，連續中斷不收回，使用者分數才不會倒退。
    assert R.streak_bonus(2) == (0, [])
    assert R.streak_bonus(7) == (55, [3, 7])          # 15 + 40
    assert R.streak_bonus(30) == (345, [3, 7, 14, 30])  # 15+40+90+200
    # 即使目前連續只剩 1 天，最長曾達 7 仍保留 55 分。
    a = {"active_day_count": 0, "longest_streak": 7, "current_streak": 1}
    assert R.compute_points(a)["breakdown"]["streak"] == 55


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

    rich = {b["id"]: b for b in R.evaluate_badges({
        "longest_streak": 30, "emotion_days": 14,
        "medication_log_count": 30, "triple_day": True,
    })}
    assert all(rich[k]["earned"] for k in
               ["week-regular", "month-regular",
                "mood-aware", "med-buddy", "all-round"])
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


def test_spent_excludes_cancelled_so_cancel_refunds():
    # 為什麼：後台「退回」一筆兌換＝退點。若 cancelled 仍計入已花點數，
    # 病患會被白白扣點，發放流程就失去可逆性——這條保證 cancel 真的退點。
    rows = [
        {"cost": 50, "status": "requested"},   # 已扣
        {"cost": 120, "status": "fulfilled"},  # 已扣（已發放仍算花掉）
        {"cost": 200, "status": "cancelled"},  # 退回，不計
    ]
    assert R.spent_from_rows(rows) == 170      # 50 + 120，不含被退回的 200
    # status 缺漏視為 requested（仍計入），避免舊資料被當成免費
    assert R.spent_from_rows([{"cost": 30}]) == 30
    # 全部退回 → 已花 0
    assert R.spent_from_rows([{"cost": 80, "status": "cancelled"}]) == 0


# ── 療程拼圖（每月主題收藏 metagame）──────────────────────────

def test_puzzle_theme_rotates_by_month_and_is_year_stable():
    # 為什麼：月主題必須只由「月份」決定、跨年穩定，否則同一月在不同年顯示不同
    # 主題，收藏冊就對不上。1 月跟 13（=明年 1 月語意）應拿到同一主題。
    jan = R.theme_for_month("2026-01")
    jul = R.theme_for_month("2026-07")
    assert jan["key"] != jul["key"]                 # 不同月不同主題
    assert R.theme_for_month("2027-01")["key"] == jan["key"]  # 跨年同月同主題
    # 壞格式不應丟例外，退回第一個主題（UI 永遠有東西可顯示）
    assert R.theme_for_month("garbage")["key"] == R.PUZZLE_THEMES[0]["key"]


def test_puzzle_pieces_unlock_on_exact_thresholds():
    # 為什麼：拼片解鎖門檻是這套 metagame 的核心。若門檻鬆動（例如 2 個活躍日就
    # 給第 1 片），整個「靠紀錄換收藏」的承諾就失真。逐片驗門檻邊界。
    empty = R.puzzle_board("2026-06", {})
    assert empty["total_pieces"] == 9
    assert empty["unlocked_count"] == 0
    assert empty["complete"] is False
    # 全 0 時第一片（3 活躍日）距門檻 3
    assert empty["to_next"] == 3
    assert empty["pieces"][0]["unlocked"] is False
    assert empty["pieces"][0]["remaining"] == 3

    # 剛好 3 活躍日 → 只解第 1 片，第 2 片（need 6）還差 3
    a3 = R.puzzle_board("2026-06", {"active_days": 3})
    assert a3["pieces"][0]["unlocked"] is True
    assert a3["pieces"][1]["unlocked"] is False
    assert a3["unlocked_count"] == 1
    assert a3["to_next"] == 3   # 6 - 3

    # 邊界：2 活躍日還不該解第 1 片
    assert R.puzzle_board("2026-06", {"active_days": 2})["unlocked_count"] == 0


def test_puzzle_each_unlocked_piece_carries_a_reason_and_locked_a_hint():
    # 為什麼：憲法 2「每片可解釋」。解鎖的片必須帶 reason（為什麼拿到），
    # 未解鎖的片必須帶 hint（還差什麼）——少了任何一邊，可解釋承諾就破。
    board = R.puzzle_board("2026-06", {"active_days": 3})
    p0, p1 = board["pieces"][0], board["pieces"][1]
    assert p0["unlocked"] and p0["reason_zh"] and p0["hint_zh"] is None
    assert (not p1["unlocked"]) and p1["hint_zh"] and p1["reason_zh"] is None
    assert p1["hint_en"]  # 雙語都要有


def test_puzzle_triple_day_piece_needs_all_three_in_one_day():
    # 為什麼：第 8 片代表「同一天記齊 症狀＋生理＋情緒」這個全面紀錄行為。
    # 若 triple_day=False 也給片，這片就名不副實。
    no_triple = R.puzzle_board("2026-06", {"triple_day": False})
    assert no_triple["pieces"][7]["unlocked"] is False
    yes_triple = R.puzzle_board("2026-06", {"triple_day": True})
    assert yes_triple["pieces"][7]["unlocked"] is True


def test_puzzle_complete_unlocks_a_redeemable_reward():
    # 為什麼：集滿 9 片才算 complete，且必須指向一個既有可兌換品項，
    # 否則「集滿有獎」的承諾落空。湊齊所有門檻 → complete + complete_reward。
    full = {
        "active_days": 15, "emotion_days": 3,
        "longest_streak": 7, "triple_day": True,
    }
    board = R.puzzle_board("2026-06", full)
    assert board["unlocked_count"] == 9
    assert board["complete"] is True
    assert board["to_next"] == 0
    # 兌換品項必須真的存在於既有 CATALOG，不能指向不存在的 id
    assert board["complete_reward"] == R.PUZZLE_COMPLETE_REWARD
    assert R.get_reward(board["complete_reward"]) is not None
    # 未完成時不可外洩兌換資格
    assert R.puzzle_board("2026-06", {"active_days": 12})["complete_reward"] is None


# ── 健康小夥伴（companion metagame）──────────────────────────

def test_companion_stage_thresholds_and_progress():
    # 為什麼：成長階段是夥伴的核心回饋。門檻錯置或進度算錯，使用者看到的
    # 「還差多少破殼／升級」就會誤導，破壞養成動機。
    assert R.companion_stage(0)["key"] == "egg"
    assert R.companion_stage(29)["key"] == "egg"
    assert R.companion_stage(30)["key"] == "hatch"      # 剛好破殼門檻
    # 30→150 區間中點 90：進度應 0.5、距下一階段 60。
    mid = R.companion_stage(90)
    assert mid["progress"] == 0.5 and mid["to_next"] == 60
    top = R.companion_stage(99999)
    assert top["key"] == "shine" and top["progress"] == 1.0 and top["to_next"] == 0


def test_companion_xp_equals_earned_and_is_monotonic():
    # 為什麼：夥伴 XP 必須＝earned（只增不減），兌換扣點不能讓夥伴「退化」，
    # 否則花點數兌換反而懲罰使用者、與鼓勵初衷相反。
    a = {"active_day_count": 10, "longest_streak": 7}
    xp = R.compute_points(a)["earned"]
    # earned 只由 active/streak 決定，與兌換無關 → 用同一 activity 兩次結果一致。
    assert R.compute_points(a)["earned"] == xp
    assert R.companion_stage(xp)["key"] in {s[1] for s in R.COMPANION_STAGES}


def test_companion_mood_is_gentle_and_never_punishing():
    # 為什麼：慢性病照護鐵則——久沒紀錄最差只能是「睡著了」，不可出現生病／死亡
    # 等懲罰性狀態。同時今天有紀錄要能被認出（sparkle），給即時正回饋。
    assert R.companion_mood("2026-07-08", "2026-07-08")["key"] == "sparkle"
    assert R.companion_mood("2026-07-07", "2026-07-08")["key"] == "happy"
    assert R.companion_mood("2026-07-05", "2026-07-08")["key"] == "miss"      # 3 天
    assert R.companion_mood("2026-06-01", "2026-07-08")["key"] == "sleepy"    # 很久
    assert R.companion_mood(None, "2026-07-08")["key"] == "sleepy"            # 從未紀錄
    # 每個 mood 都要有中英文，UI 不會顯示空字串
    for key in R.COMPANION_MOODS:
        m = R.companion_mood(None, "2026-07-08") if key == "sleepy" else None
    assert set(R.COMPANION_MOODS) == {"sparkle", "happy", "miss", "sleepy"}


def test_companion_message_is_deterministic_and_always_returns_one():
    # 為什麼：鼓勵語選取是純算術（規則 5），同一天同輸入必須固定（可重現、可測），
    # 且任何 pool_key 都要回得出一句（含壞 key 退回 sleepy 池），UI 永不空白。
    m1 = R.companion_message("sparkle", "2026-07-08", 120)
    m2 = R.companion_message("sparkle", "2026-07-08", 120)
    assert m1 == m2 and m1["zh"] and m1["en"]              # 確定性 + 雙語非空
    # 壞 pool_key 不丟例外，退回 sleepy 池
    assert R.companion_message("nonexistent", "2026-07-08", 0) in R.COMPANION_MESSAGES["sleepy"]
    # 壞日期字串不丟例外
    assert R.companion_message("egg", "garbage", 0)["zh"]


def test_companion_name_is_sanitized_and_falls_back_to_default():
    # 為什麼：名字會被顯示，長度／空白／不可列印字元若不整理，會撐爆 UI 或顯示亂碼；
    # 空名要退回物種預設名，卡片永遠有稱呼。
    sp = R.get_species("sprout")
    assert R.normalize_companion_name("  芽芽  ", sp) == "芽芽"           # 去頭尾空白
    assert R.normalize_companion_name("", sp) == sp["default_name"]       # 空 → 預設
    assert R.normalize_companion_name(None, sp) == sp["default_name"]     # 非字串 → 預設
    assert len(R.normalize_companion_name("超長名字" * 10, sp)) == R.COMPANION_NAME_MAX  # 截長
    assert R.get_species("does-not-exist") is None

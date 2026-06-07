"""
健康積分／獎勵中心 — 純規則引擎（不碰 DB）。

定位：把使用者「已經在做的事」（填問卷、打卡、連續紀錄、完成 eHEALS）
換算成積分、等級、徽章與可兌換獎勵。所有換算都是確定性算術，跟 surveys.py
的計分一樣抽成純函式，方便單元測試與後台對帳。

設計鐵則：
  - 規則 5：得分／等級／徽章／可否兌換都是 if-else 算術 → 純程式碼，零 LLM。
  - 規則 2/3：不新增使用者必做的操作，積分只是對既有紀錄行為的唯讀換算。
  - 規則 9：每條規則都能被 tests/test_rewards_rules.py 在邏輯漂移時打回。

router（rewards.py）負責從各資料表撈出 activity dict，本檔只負責換算；
DB 讀取與換算分離（比照 surveys.py：計分純函式、DB 在 endpoint）。

activity dict（由 router 組好後傳入）欄位：
  survey_count          已提交的問卷作答份數
  active_day_count      有任一健康紀錄的不重複日數
  longest_streak        最長連續打卡天數
  current_streak        目前（截至最近一次紀錄）連續打卡天數
  eheals_done           是否完成 eHEALS 健康識能量表
  emotion_days          有情緒紀錄的不重複日數
  medication_log_count  服藥打卡次數
  triple_day            是否曾在同一天集滿 症狀＋生理＋情緒
"""

# ── 積分規則（純資料，院方可調）──────────────────────────────
PER_SURVEY = 20          # 每提交一份問卷
PER_ACTIVE_DAY = 10      # 每有一天任一健康紀錄（一天封頂一次，避免刷分）
EHEALS_BONUS = 30        # 完成 eHEALS 一次性獎勵

# 連續打卡里程碑：達到門檻一次性給分，依「最長連續天數」累計，
# 故連續中斷也不會把已得分數收回（分數對使用者單調不減，較不挫折）。
STREAK_MILESTONES = [(3, 15), (7, 40), (14, 90), (30, 200)]

# ── 等級（earned 累積分數決定；不受兌換扣點影響）────────────
# (門檻下限, key, 顯示名)。語氣溫和但不幼稚，貼合醫療場景與長者模式。
LEVELS = [
    (0, "sprout", "萌芽"),
    (100, "steady", "穩定"),
    (300, "regular", "規律"),
    (700, "disciplined", "自律"),
    (1500, "master", "達人"),
]

# ── 徽章（確定性解鎖；icon 用前端既有的 lucide 名）──────────
BADGES = [
    {"id": "first-feedback", "name": "初次回饋", "desc": "完成第一份健康回饋問卷", "icon": "message-square-heart"},
    {"id": "week-regular", "name": "規律一週", "desc": "連續打卡達 7 天", "icon": "calendar-check"},
    {"id": "month-regular", "name": "規律一月", "desc": "連續打卡達 30 天", "icon": "calendar-heart"},
    {"id": "mood-aware", "name": "情緒覺察", "desc": "累積 14 天情緒紀錄", "icon": "battery-charging"},
    {"id": "med-buddy", "name": "用藥好夥伴", "desc": "累積 30 次服藥打卡", "icon": "pill"},
    {"id": "eheals-done", "name": "健康識能達成", "desc": "完成 eHEALS 健康識能量表", "icon": "graduation-cap"},
    {"id": "all-round", "name": "全面紀錄", "desc": "曾在同一天完成 症狀＋生理＋情緒", "icon": "sparkles"},
]

# ── 兌換清單（示意品項，實際由院方在此調整；對應「後續會發放獎勵」）──
# redeem 只記一筆兌換意願（status='requested'），實品由院方線下發放。
CATALOG = [
    {"id": "edu-booklet", "name": "衛教小手冊", "desc": "院方提供的疾病／用藥衛教手冊", "cost": 50, "icon": "book-heart"},
    {"id": "priority-slot", "name": "回診優先時段", "desc": "下次回診優先安排時段（依院方排程）", "cost": 120, "icon": "calendar-clock"},
    {"id": "health-kit", "name": "健康小禮包", "desc": "血壓記錄本／分藥盒等照護小物", "cost": 200, "icon": "gift"},
]

_CATALOG_BY_ID = {r["id"]: r for r in CATALOG}


def get_reward(reward_id):
    """取兌換品項定義；不存在回 None。"""
    return _CATALOG_BY_ID.get(reward_id)


# ── 連續天數 ─────────────────────────────────────────────
def compute_streaks(days):
    """給一組日期字串（YYYY-MM-DD，可含重複、未排序），算出
    (longest, current)。current＝以「最近一天」結尾的那段連續天數，
    不要求最近一天就是今天（避開時區誤差，也較鼓勵）。純日期運算。
    """
    uniq = sorted({str(d)[:10] for d in days if d})
    if not uniq:
        return 0, 0
    from datetime import date

    def _parse(s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    parsed = [p for p in (_parse(d) for d in uniq) if p]
    if not parsed:
        return 0, 0

    longest = run = 1
    for prev, cur in zip(parsed, parsed[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    # run 此時正是「結尾那段」的長度，即 current。
    return longest, run


def streak_bonus(longest_streak):
    """依最長連續天數累計里程碑獎勵。回 (總分, 已達成門檻清單)。"""
    total = 0
    reached = []
    for threshold, pts in STREAK_MILESTONES:
        if longest_streak >= threshold:
            total += pts
            reached.append(threshold)
    return total, reached


# ── 得分 ─────────────────────────────────────────────────
def compute_points(activity):
    """把 activity 換算成 earned 總分與各來源明細（純算術）。"""
    survey_pts = int(activity.get("survey_count", 0)) * PER_SURVEY
    active_pts = int(activity.get("active_day_count", 0)) * PER_ACTIVE_DAY
    streak_pts, reached = streak_bonus(int(activity.get("longest_streak", 0)))
    eheals_pts = EHEALS_BONUS if activity.get("eheals_done") else 0
    earned = survey_pts + active_pts + streak_pts + eheals_pts
    return {
        "earned": earned,
        "breakdown": {
            "survey": survey_pts,
            "active_days": active_pts,
            "streak": streak_pts,
            "eheals": eheals_pts,
        },
        "streak_milestones_reached": reached,
    }


# ── 等級 ─────────────────────────────────────────────────
def level_for(earned):
    """由 earned 總分換算等級與「距離下一級」進度。"""
    idx = 0
    for i, (floor, _key, _name) in enumerate(LEVELS):
        if earned >= floor:
            idx = i
    floor, key, name = LEVELS[idx]
    out = {
        "index": idx + 1,           # 1-based，給前端顯示 Lv.N
        "key": key,
        "name": name,
        "current_floor": floor,
        "max_level": len(LEVELS),
    }
    if idx + 1 < len(LEVELS):
        next_floor, _nk, next_name = LEVELS[idx + 1]
        span = next_floor - floor
        out.update({
            "next_name": next_name,
            "next_floor": next_floor,
            "to_next": next_floor - earned,
            "progress": round((earned - floor) / span, 2) if span else 1.0,
        })
    else:
        out.update({
            "next_name": None,
            "next_floor": None,
            "to_next": 0,
            "progress": 1.0,        # 已滿級
        })
    return out


# ── 徽章 ─────────────────────────────────────────────────
def _badge_earned(badge_id, a):
    """單一徽章的解鎖條件（確定性）。"""
    return {
        "first-feedback": int(a.get("survey_count", 0)) >= 1,
        "week-regular": int(a.get("longest_streak", 0)) >= 7,
        "month-regular": int(a.get("longest_streak", 0)) >= 30,
        "mood-aware": int(a.get("emotion_days", 0)) >= 14,
        "med-buddy": int(a.get("medication_log_count", 0)) >= 30,
        "eheals-done": bool(a.get("eheals_done")),
        "all-round": bool(a.get("triple_day")),
    }.get(badge_id, False)


def evaluate_badges(activity):
    """回傳所有徽章的解鎖狀態（earned True/False），維持 BADGES 順序。"""
    return [dict(b, earned=_badge_earned(b["id"], activity)) for b in BADGES]


# ── 兌換 ─────────────────────────────────────────────────
def catalog_with_affordability(available):
    """在兌換清單上標出每項以目前 available 點數是否買得起。"""
    return [dict(r, affordable=available >= r["cost"]) for r in CATALOG]

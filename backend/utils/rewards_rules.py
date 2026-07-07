"""
健康積分／獎勵中心 — 純規則引擎（不碰 DB）。

定位：把使用者「已經在做的事」（每日打卡、連續紀錄、情緒/服藥紀錄）
換算成積分、等級、徽章與可兌換獎勵。所有換算都是確定性算術，抽成純函式，
方便單元測試與後台對帳。

設計鐵則：
  - 規則 5：得分／等級／徽章／可否兌換都是 if-else 算術 → 純程式碼，零 LLM。
  - 規則 2/3：不新增使用者必做的操作，積分只是對既有紀錄行為的唯讀換算。
  - 規則 9：每條規則都能被 tests/test_rewards_rules.py 在邏輯漂移時打回。

router（rewards.py）負責從各資料表撈出 activity dict，本檔只負責換算；
DB 讀取與換算分離：計分為純函式，DB 讀取集中在 endpoint。

activity dict（由 router 組好後傳入）欄位：
  active_day_count      有任一健康紀錄的不重複日數
  longest_streak        最長連續打卡天數
  current_streak        目前（截至最近一次紀錄）連續打卡天數
  emotion_days          有情緒紀錄的不重複日數
  medication_log_count  服藥打卡次數
  triple_day            是否曾在同一天集滿 症狀＋生理＋情緒
"""

# ── 積分規則（純資料，院方可調）──────────────────────────────
PER_ACTIVE_DAY = 10      # 每有一天任一健康紀錄（一天封頂一次，避免刷分）

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
    {"id": "week-regular", "name": "規律一週", "desc": "連續打卡達 7 天", "icon": "calendar-check"},
    {"id": "month-regular", "name": "規律一月", "desc": "連續打卡達 30 天", "icon": "calendar-heart"},
    {"id": "mood-aware", "name": "情緒覺察", "desc": "累積 14 天情緒紀錄", "icon": "battery-charging"},
    {"id": "med-buddy", "name": "用藥好夥伴", "desc": "累積 30 次服藥打卡", "icon": "pill"},
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
    active_pts = int(activity.get("active_day_count", 0)) * PER_ACTIVE_DAY
    streak_pts, reached = streak_bonus(int(activity.get("longest_streak", 0)))
    earned = active_pts + streak_pts
    return {
        "earned": earned,
        "breakdown": {
            "active_days": active_pts,
            "streak": streak_pts,
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
        "week-regular": int(a.get("longest_streak", 0)) >= 7,
        "month-regular": int(a.get("longest_streak", 0)) >= 30,
        "mood-aware": int(a.get("emotion_days", 0)) >= 14,
        "med-buddy": int(a.get("medication_log_count", 0)) >= 30,
        "all-round": bool(a.get("triple_day")),
    }.get(badge_id, False)


def evaluate_badges(activity):
    """回傳所有徽章的解鎖狀態（earned True/False），維持 BADGES 順序。"""
    return [dict(b, earned=_badge_earned(b["id"], activity)) for b in BADGES]


# ── 兌換 ─────────────────────────────────────────────────
# 兌換狀態：requested（待發放）/ fulfilled（已發放）都已扣點；
# cancelled（院方退回）視為退點，不計入已花點數。


def spent_from_rows(rows):
    """已花點數＝未取消的兌換 cost 加總。cancelled 退回不計；status 缺漏視為 requested。"""
    return sum(
        int(r.get("cost") or 0)
        for r in rows
        if (r.get("status") or "requested") != "cancelled"
    )


def catalog_with_affordability(available):
    """在兌換清單上標出每項以目前 available 點數是否買得起。"""
    return [dict(r, affordable=available >= r["cost"]) for r in CATALOG]


# ── 療程拼圖（每月主題收藏 metagame）──────────────────────────
# 概念：每月一張 9 片（3x3）療程主題拼圖，靠使用者「平常的健康紀錄」自動解鎖，
# 不花積分買、不抽卡。全部用確定性規則，跟上面的積分一樣是純算術、可單元測試。
#
# 設計鐵則（對照產品憲法 / 12 鐵則）：
#   - 單調不減：解鎖門檻只看「當月累積量」，量只增不減 → 已解鎖的片永不收回。
#   - 零付費：解鎖完全來自既有紀錄行為，不需新操作、不需花點數。
#   - 每片可解釋（憲法 2）：每片都附「為什麼解鎖 / 還差什麼」。
#   - 不製造焦慮：文案溫和，未解鎖只說「再 N 就好」，不倒數施壓。
#
# 月主題用 year_month 決定（12 主題輪替，跨年仍穩定）。集滿 9 片 → complete，
# 解鎖一個既有兌換品項（PUZZLE_COMPLETE_REWARD），由使用者自行到獎勵中心兌換
# （不自動寫入 reward_redemptions，避免動到既有兌換流程與帳本；router 只回報
# 「已可兌換」狀態）。

# 月主題輪替（用 month 1-12 取，跨年穩定）。flat 可愛風，貼合療程/照護語境。
PUZZLE_THEMES = [
    {"key": "spring-garden", "name": "療癒花園", "en": "Healing Garden"},
    {"key": "warm-tea", "name": "暖心茶時光", "en": "Warm Tea Time"},
    {"key": "morning-walk", "name": "晨間散步", "en": "Morning Walk"},
    {"key": "blossom", "name": "盛開時節", "en": "In Full Bloom"},
    {"key": "sunny-window", "name": "灑進陽光的窗", "en": "Sunny Window"},
    {"key": "rainy-day", "name": "聽雨的午後", "en": "Rainy Afternoon"},
    {"key": "summer-fruit", "name": "夏日鮮果", "en": "Summer Fruit"},
    {"key": "starry-night", "name": "好眠星空", "en": "Starry Night"},
    {"key": "autumn-leaf", "name": "微涼秋葉", "en": "Autumn Leaves"},
    {"key": "harvest", "name": "豐收餐桌", "en": "Harvest Table"},
    {"key": "cozy-home", "name": "溫暖的家", "en": "Cozy Home"},
    {"key": "snow-rest", "name": "冬日歇息", "en": "Winter Rest"},
]

# 集滿 9 片可兌換的品項（沿用既有 CATALOG 的 id；不另設新獎品池）。
PUZZLE_COMPLETE_REWARD = "edu-booklet"

# 9 片的解鎖條件（確定性、可解釋、單調不減）。每片一條 rule：
#   field   ＝ 用 month-scoped activity 的哪個累積量判斷
#   need    ＝ 達標門檻（>= 即解鎖）
#   piece_zh/piece_en ＝ 解鎖後可說「靠什麼拿到的」
# 第 1~5 片走「活躍日階梯」（3/6/9/12/15 天），新手最快看到進度；
# 第 6~9 片串起情緒、連續、全面紀錄、月里程碑，剛好把 App 的紀錄行為都帶到。
PUZZLE_PIECE_RULES = [
    {"field": "active_days", "need": 3,  "piece_zh": "本月累積 3 個有紀錄的日子", "piece_en": "3 active days this month"},
    {"field": "active_days", "need": 6,  "piece_zh": "本月累積 6 個有紀錄的日子", "piece_en": "6 active days this month"},
    {"field": "active_days", "need": 9,  "piece_zh": "本月累積 9 個有紀錄的日子", "piece_en": "9 active days this month"},
    {"field": "active_days", "need": 12, "piece_zh": "本月累積 12 個有紀錄的日子", "piece_en": "12 active days this month"},
    {"field": "active_days", "need": 15, "piece_zh": "本月累積 15 個有紀錄的日子", "piece_en": "15 active days this month"},
    {"field": "emotion_days", "need": 3, "piece_zh": "本月有 3 天記錄了心情", "piece_en": "Logged mood on 3 days this month"},
    {"field": "longest_streak", "need": 3, "piece_zh": "本月達成連續 3 天打卡", "piece_en": "Reached a 3-day streak this month"},
    {"field": "triple_day", "need": 1, "piece_zh": "本月曾在同一天記齊 症狀＋生理＋情緒", "piece_en": "Logged symptom + vital + mood in one day"},
    {"field": "longest_streak", "need": 7, "piece_zh": "本月達成連續 7 天打卡", "piece_en": "Reached a 7-day streak this month"},
]

PUZZLE_TOTAL_PIECES = len(PUZZLE_PIECE_RULES)  # = 9


def theme_for_month(year_month):
    """由 'YYYY-MM' 取當月主題（12 主題輪替）。格式不對時退回第一個主題（不丟例外，
    讓 UI 永遠有東西可顯示——規則 12 寧可降級也不靜默壞掉）。"""
    month = 1
    try:
        month = int(str(year_month).split("-")[1])
    except (IndexError, ValueError):
        month = 1
    if not 1 <= month <= 12:
        month = 1
    return PUZZLE_THEMES[(month - 1) % len(PUZZLE_THEMES)]


def _piece_value(activity, field):
    """取 month-scoped activity 在某 field 的數值；triple_day 這種布林換成 0/1。"""
    v = activity.get(field, 0)
    if isinstance(v, bool):
        return 1 if v else 0
    return int(v or 0)


# ── 健康小夥伴（companion metagame）──────────────────────────
# 概念：一隻皮克敏／寶可夢式的小生物，靠使用者「平常的健康紀錄」餵養長大。
# XP＝earned 積分（唯讀換算、只增不減；兌換扣點不影響夥伴成長），
# 心情＝距離最近一次紀錄的天數（永遠溫和：最差只是「睡著了」，不會生病或死掉——
# 慢性病照護不製造罪惡感）。全部確定性算術（規則 5），可單元測試。

COMPANION_SPECIES = [
    {"key": "sprout", "name_zh": "小芽", "name_en": "Sprout", "default_name": "芽芽",
     "personality_zh": "安靜溫柔，會跟著你的紀錄慢慢發芽、長出新葉。",
     "personality_en": "Gentle and quiet — sprouts new leaves as you keep logging."},
    {"key": "droplet", "name_zh": "小露", "name_en": "Droplet", "default_name": "露露",
     "personality_zh": "活潑愛乾淨，最喜歡看你按時照顧自己。",
     "personality_en": "Playful and tidy — loves seeing you care for yourself on time."},
    {"key": "sunny", "name_zh": "小暖", "name_en": "Sunny", "default_name": "暖暖",
     "personality_zh": "熱情開朗，你的每一筆紀錄都讓牠更閃亮。",
     "personality_en": "Warm and cheerful — every entry makes it glow a little brighter."},
]

_SPECIES_BY_KEY = {s["key"]: s for s in COMPANION_SPECIES}


def get_species(key):
    """取夥伴物種定義；不存在回 None。"""
    return _SPECIES_BY_KEY.get(key)


COMPANION_NAME_MAX = 12


def normalize_companion_name(name, species):
    """整理使用者取的名字：去頭尾空白、移除不可列印字元、截到 12 字；
    空值或全被清掉時退回該物種的預設名。顯示端仍需 escapeHtml（信任邊界在前端）。"""
    default = (species or {}).get("default_name") or "小夥伴"
    if not isinstance(name, str):
        return default
    cleaned = "".join(ch for ch in name if ch.isprintable()).strip()
    return cleaned[:COMPANION_NAME_MAX] or default


# 成長階段：(XP 門檻下限, key, 中文名, 英文名)。
# 第一階段門檻刻意低（30 XP ≈ 認真記錄 2~3 天）讓「破殼」很快發生——
# 新手最快嘗到甜頭；後段拉長，給長期慢病管理一條可走一年的成長曲線。
COMPANION_STAGES = [
    (0, "egg", "孵蛋期", "Egg"),
    (30, "hatch", "破殼期", "Hatchling"),
    (150, "kid", "幼年期", "Child"),
    (400, "grown", "茁壯期", "Grown-up"),
    (1000, "shine", "閃耀期", "Radiant"),
]


def companion_stage(xp):
    """由 XP（=earned 積分）換算成長階段與「距離下一階段」進度（同 level_for 形狀）。"""
    xp = int(xp or 0)
    idx = 0
    for i, (floor, _k, _zh, _en) in enumerate(COMPANION_STAGES):
        if xp >= floor:
            idx = i
    floor, key, zh, en = COMPANION_STAGES[idx]
    out = {
        "index": idx,                    # 0-based
        "key": key,
        "name_zh": zh,
        "name_en": en,
        "count": len(COMPANION_STAGES),
        "floor": floor,
    }
    if idx + 1 < len(COMPANION_STAGES):
        next_floor, _nk, nzh, nen = COMPANION_STAGES[idx + 1]
        span = next_floor - floor
        out.update({
            "next_floor": next_floor,
            "next_name_zh": nzh,
            "next_name_en": nen,
            "to_next": next_floor - xp,
            "progress": round((xp - floor) / span, 2) if span else 1.0,
        })
    else:
        out.update({
            "next_floor": None, "next_name_zh": None, "next_name_en": None,
            "to_next": 0, "progress": 1.0,
        })
    return out


# 心情：只看「距離最近一次紀錄幾天」。語氣鐵則：永遠不指責、不倒數施壓；
# 最差狀態只是打盹，隨時回來記一筆就會醒。
COMPANION_MOODS = {
    "sparkle": {"zh": "精神奕奕", "en": "Full of energy"},
    "happy": {"zh": "心情很好", "en": "Happy"},
    "miss": {"zh": "想你了", "en": "Missing you"},
    "sleepy": {"zh": "睡著了", "en": "Napping"},
}


def companion_mood(last_active_day, today):
    """由最近一次紀錄日（台灣日 'YYYY-MM-DD'）與今天算心情。
    今天有紀錄→sparkle；昨天→happy；2~3 天→miss；更久或從未→sleepy。"""
    from datetime import date

    def _parse(s):
        try:
            return date.fromisoformat(str(s)[:10])
        except (TypeError, ValueError):
            return None

    t = _parse(today)
    last = _parse(last_active_day)
    gap = (t - last).days if (t and last) else None
    if gap is not None and gap <= 0:
        key = "sparkle"
    elif gap == 1:
        key = "happy"
    elif gap is not None and gap <= 3:
        key = "miss"
    else:
        key = "sleepy"
    return dict(COMPANION_MOODS[key], key=key)


# 鼓勵語庫：依（蛋期／心情）分池。寫給慢性病患者：肯定小步前進、允許休息、
# 永不愧疚式催促。挑選為確定性輪替（同一天固定、跨天輪換），零 LLM（規則 5）。
COMPANION_MESSAGES = {
    "egg": [
        {"zh": "我在蛋裡聽得到你的心跳……每記錄一筆，蛋就更暖一點。", "en": "I can hear your heartbeat from inside the egg… every entry keeps it warm."},
        {"zh": "再累積一點點紀錄，我就要破殼囉！", "en": "Just a little more logging and I'll hatch!"},
        {"zh": "謝謝你把我帶回家。慢慢來，我等得起。", "en": "Thank you for adopting me. Take your time — I can wait."},
    ],
    "sparkle": [
        {"zh": "今天也有好好照顧自己，我超驕傲的！", "en": "You took care of yourself today — I'm so proud!"},
        {"zh": "每一筆紀錄，都是你溫柔對待身體的證明。", "en": "Every entry is proof you're being kind to your body."},
        {"zh": "慢性病照護是場馬拉松，今天你又穩穩跑了一段！", "en": "Chronic care is a marathon — you ran another steady stretch today!"},
        {"zh": "有你在，我每天都在長大。謝謝你！", "en": "I grow a little every day because of you. Thank you!"},
        {"zh": "今天的你，比昨天更懂自己的身體了。", "en": "You understand your body a little better than yesterday."},
        {"zh": "紀錄完成！小小的一步，大大的累積。", "en": "Logged! Small steps add up to something big."},
    ],
    "happy": [
        {"zh": "昨天有記錄，今天也想聽聽你的狀況～", "en": "You logged yesterday — I'd love to hear how today feels too."},
        {"zh": "我吃飽睡好，等你回來記一筆！", "en": "I'm well fed and rested, ready whenever you are!"},
        {"zh": "不急，照自己的步調就好。我都在。", "en": "No rush — go at your own pace. I'm right here."},
    ],
    "miss": [
        {"zh": "想你了～最近身體還好嗎？", "en": "I missed you! How have you been feeling?"},
        {"zh": "好幾天沒見了，回來記一筆讓我安心好嗎？", "en": "It's been a few days — a quick entry would put my mind at ease."},
        {"zh": "休息也是照顧的一部分。準備好了再回來就好。", "en": "Rest is part of self-care too. Come back when you're ready."},
    ],
    "sleepy": [
        {"zh": "Zzz……（輕輕記一筆，我就會醒來喔）", "en": "Zzz… (log one entry and I'll wake right up)"},
        {"zh": "我先瞇一下。你回來記錄，我馬上起床！", "en": "Just napping — I'll be up the moment you log something!"},
        {"zh": "不管隔多久回來，我都會在這裡等你。", "en": "However long it's been, I'll always be here waiting for you."},
    ],
}


def companion_message(pool_key, today, xp):
    """從語庫挑一句：同一天固定、跨天輪替（day ordinal + xp 取模，確定性、零隨機）。
    pool_key 不存在時退到 sleepy 池（永遠有話可說，UI 不會空白）。"""
    from datetime import date

    pool = COMPANION_MESSAGES.get(pool_key) or COMPANION_MESSAGES["sleepy"]
    try:
        ordinal = date.fromisoformat(str(today)[:10]).toordinal()
    except (TypeError, ValueError):
        ordinal = 0
    return pool[(ordinal + int(xp or 0)) % len(pool)]


def puzzle_board(year_month, activity):
    """算某月的拼圖狀態（純函式，零 DB / 零 LLM）。

    activity 是「該月」的累積量 dict（由 router 把全量紀錄過濾到當月後組好）：
      active_days     當月有任一紀錄的不重複日數
      emotion_days    當月有情緒紀錄的不重複日數
      longest_streak  當月最長連續打卡天數
      triple_day      當月是否曾在同一天集滿 症狀＋生理＋情緒（bool）

    回傳：theme、total_pieces=9、pieces[]（每片 index/unlocked/reason 或 hint）、
    unlocked_count、complete、to_next（距離下一片還差多少，已滿則 0）、
    complete_reward（集滿可兌換的品項 id）。
    """
    theme = theme_for_month(year_month)
    pieces = []
    unlocked_count = 0
    to_next = None  # 第一個還沒解鎖的片，距離門檻還差多少
    for i, rule in enumerate(PUZZLE_PIECE_RULES):
        have = _piece_value(activity, rule["field"])
        unlocked = have >= rule["need"]
        gap = max(0, rule["need"] - have)
        piece = {
            "index": i,                       # 0-based，對應 3x3 grid 位置
            "unlocked": unlocked,
            "field": rule["field"],
            "need": rule["need"],
            "have": have,
            # reason：解鎖了就說「靠什麼拿到的」；hint：還沒解鎖就說「還差什麼」
            "reason_zh": rule["piece_zh"] if unlocked else None,
            "reason_en": rule["piece_en"] if unlocked else None,
            "hint_zh": None if unlocked else f"再 {gap} 就能解鎖（{rule['piece_zh']}）",
            "hint_en": None if unlocked else f"{gap} more to go ({rule['piece_en']})",
            "remaining": 0 if unlocked else gap,
        }
        pieces.append(piece)
        if unlocked:
            unlocked_count += 1
        elif to_next is None:
            to_next = gap
    complete = unlocked_count >= PUZZLE_TOTAL_PIECES
    return {
        "year_month": str(year_month),
        "theme": theme,
        "total_pieces": PUZZLE_TOTAL_PIECES,
        "unlocked_count": unlocked_count,
        "pieces": pieces,
        "complete": complete,
        "to_next": 0 if complete else (to_next or 0),
        "complete_reward": PUZZLE_COMPLETE_REWARD if complete else None,
    }

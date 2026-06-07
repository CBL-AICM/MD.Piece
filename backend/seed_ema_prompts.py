"""
Seed：EMA casual 短打卡「完整框架」—— 題庫 + 註冊後旅程（不定時推送，非固定研究問卷）。

設計理念（對齊使用者方向）：
  不把問卷當「固定畫面叫人填的研究問卷」，而是註冊後以「偶爾、不定時」自然推送的
  10 秒短打卡。一套完整框架包含三層：
    1) 題庫（PROMPTS）：多種 casual 微問卷，輪流出現才不重複、不煩。
    2) 註冊後旅程（JOURNEY_RULES）：以入組天數 elapsed 觸發，刻意用「不規則、漸寬」的
       間隔（D1,2,4,7,10,14,21,28），每天至多 1 則、時點 10:00–21:00 內隨機 → 不定時感。
    3) 事件觸發（EVENT_RULES）：剛記錄完偶爾追一則（cooldown 1 天）。
  刻意「不放每日填充」，維持「偶爾」而非天天問。與正式研究量表 seed_study_surveys.py 分開。
  冪等，可安全重跑。

執行：python -m backend.seed_ema_prompts
"""

import logging

from backend.db import get_supabase

logger = logging.getLogger(__name__)
STUDY = "mdpiece_feasibility_v2"
OWNER = "system:ema-prompt"


def _likert(text, lo, hi, lo_label, hi_label):
    return {"items": [{"id": "v", "type": "likert", "text": text}],
            "scoring": {"method": "none", "kind": "ema_prompt",
                        "scale": {"min": lo, "max": hi, "min_label": lo_label, "max_label": hi_label}}}


# ── 1) 題庫：6 種 casual 短打卡（皆無 timepoints → 隨時可填）──
PROMPTS = [
    {"key": "ema-mood",  "title": "快速打卡", "description": "花 10 秒，現在的感覺",
     **_likert("現在心情如何？", 1, 5, "很差", "很好")},
    {"key": "ema-body",  "title": "隨手打卡", "description": "花 10 秒就好",
     **_likert("今天整體身體狀態還好嗎？", 0, 10, "很不好", "很好")},
    {"key": "ema-app",   "title": "用得還順嗎", "description": "想聽聽你的感覺",
     **_likert("App 用起來順手嗎？", 1, 5, "很不順", "很順手")},
    {"key": "ema-value", "title": "有幫到你嗎", "description": "一題就好",
     **_likert("這幾天 App 有幫到你嗎？", 1, 5, "沒幫助", "很有幫助")},
    {"key": "ema-med",   "title": "今天吃藥了嗎", "description": "輕鬆回一下",
     "items": [{"id": "med", "type": "single", "text": "今天有按時吃藥嗎？",
                "options": ["有按時", "忘了一些", "今天沒有藥"]}],
     "scoring": {"method": "none", "kind": "ema_prompt"}},
    {"key": "ema-open",  "title": "想說點什麼嗎", "description": "選填，沒有也沒關係",
     "items": [{"id": "note", "type": "text", "text": "這陣子用下來，想跟我們說什麼嗎？（選填）"}],
     "scoring": {"method": "none", "kind": "ema_prompt"}},
]

# ── 2) 註冊後旅程：不規則、漸寬間隔，每則換不同打卡 ──
#    （入組天數 elapsed；每天 ≤1、時點隨機；像認識一個新朋友，不是發問卷）
JOURNEY = [
    (1,  "ema-mood",  "剛註冊歡迎打卡"),
    (2,  "ema-app",   "第二天 · 用得順嗎"),
    (4,  "ema-body",  "第四天 · 身體狀態"),
    (7,  "ema-value", "第七天 · 有幫到嗎"),
    (10, "ema-med",   "第十天 · 吃藥情況"),
    (14, "ema-mood",  "兩週 · 心情打卡"),
    (21, "ema-value", "三週 · 還有幫助嗎"),
    (28, "ema-open",  "四週 · 想說的話"),
]
JOURNEY_RULES = [
    {"name": name, "survey_key": key,
     "trigger_config": {"type": "elapsed", "on": "enrollment_day", "day": day,
                        "deliver_window": {"start": "10:00", "end": "21:00"}}}
    for day, key, name in JOURNEY
]

# ── 3) 事件觸發：剛記錄完偶爾追一則 ──
EVENT_RULES = [
    {"name": "記錄後偶爾打卡", "survey_key": "ema-mood",
     "trigger_config": {"type": "event", "match": {"event_type": "data", "event_name": "submit"},
                        "cooldown_min": 1440, "deliver_window": {"start": "10:00", "end": "21:00"}}},
]

RULES = JOURNEY_RULES + EVENT_RULES


def seed() -> dict:
    sb = get_supabase()
    for p in PROMPTS:                                  # 題庫：依 key upsert
        row = {**p, "created_by": OWNER, "active": 1}
        existing = sb.table("surveys").select("id").eq("key", p["key"]).limit(1).execute().data or []
        if existing:
            sb.table("surveys").update({k: row[k] for k in ("title", "description", "items", "scoring", "active")}
                                       ).eq("key", p["key"]).execute()
        else:
            sb.table("surveys").insert(row).execute()
    try:                                               # 規則：依 name 去重
        existing_names = {r.get("name") for r in (sb.table("ema_rules").select("*").execute().data or [])}
    except Exception:
        existing_names = set()
    inserted = 0
    for r in RULES:
        if r["name"] in existing_names:
            continue
        sb.table("ema_rules").insert({**r, "study": STUDY, "expires_after_min": 1440,
                                      "active": 1, "created_by": OWNER}).execute()
        inserted += 1
    result = {"prompts": len(PROMPTS), "journey_days": [d for d, _, _ in JOURNEY], "rules_inserted": inserted}
    logger.info("seed_ema_prompts: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(seed())

"""
Seed：EMA casual 短打卡 + 生命週期觸發規則。

定位（對齊使用者方向）：不要把問卷當成「固定畫面叫人填的研究問卷」，而是用
「不定時發送」自然推送的 casual 微問卷——剛註冊、記錄後、時不時、事件觸發時偶爾跳一下。
與正式研究量表（seed_study_surveys.py）分開：研究量表走排程時點（D0/D14/D28/FU48），
本檔的短打卡走 EMA 觸發引擎（backend/routers/ema.py）。冪等，可安全重跑。

執行：python -m backend.seed_ema_prompts
"""

import logging

from backend.db import get_supabase

logger = logging.getLogger(__name__)
STUDY = "mdpiece_feasibility_v2"
OWNER = "system:ema-prompt"

# ── casual 短打卡（非研究量表；無 timepoints → 隨時可填、submit 不要求時點）──
PROMPTS = [
    {
        "key": "ema-mood",
        "title": "快速打卡",
        "description": "花 10 秒，現在的感覺如何？",
        "items": [{"id": "mood", "type": "likert", "text": "現在心情如何？"}],
        "scoring": {"method": "none", "kind": "ema_prompt",
                    "scale": {"min": 1, "max": 5, "min_label": "很差", "max_label": "很好"}},
    },
]

# ── 生命週期 / 不定時觸發規則（都推 casual 打卡；每人每日 ≤1 份、時點隨機）──
RULES = [
    {"name": "剛註冊歡迎打卡", "survey_key": "ema-mood",
     "trigger_config": {"type": "elapsed", "on": "enrollment_day", "day": 1,
                        "deliver_window": {"start": "10:00", "end": "21:00"}}},
    {"name": "記錄後偶爾打卡", "survey_key": "ema-mood",
     "trigger_config": {"type": "event", "match": {"event_type": "data", "event_name": "submit"},
                        "cooldown_min": 1440, "deliver_window": {"start": "10:00", "end": "21:00"}}},
    {"name": "日常時不時打卡", "survey_key": "ema-mood",
     "trigger_config": {"type": "time", "windows": [{"start": "10:00", "end": "21:00"}],
                        "per_window": 1, "respect_daily_cap": True}},
]


def seed() -> dict:
    sb = get_supabase()
    # 短打卡（依 key upsert）
    for p in PROMPTS:
        row = {**p, "created_by": OWNER, "active": 1}
        existing = sb.table("surveys").select("id").eq("key", p["key"]).limit(1).execute().data or []
        if existing:
            sb.table("surveys").update({k: row[k] for k in ("title", "description", "items", "scoring", "active")}
                                       ).eq("key", p["key"]).execute()
        else:
            sb.table("surveys").insert(row).execute()
    # 規則（依 name 去重，避免重跑灌爆）
    try:
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
    result = {"prompts": len(PROMPTS), "rules_inserted": inserted}
    logger.info("seed_ema_prompts: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(seed())

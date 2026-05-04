"""藥物服用時段與安全間隔解析。

把藥袋常見的「一天三次／早晚／睡前／每 8 小時／PRN」等寫法
轉成標準的時段標籤（早 / 中 / 晚 / 其他），
並提供「是否可立即服用」的安全檢查（預設最少間隔 4 小時）。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

# 對外公開的時段 key
SLOT_MORNING = "morning"
SLOT_NOON = "noon"
SLOT_EVENING = "evening"
SLOT_OTHER = "other"

ALL_SLOTS = (SLOT_MORNING, SLOT_NOON, SLOT_EVENING, SLOT_OTHER)

SLOT_LABELS_ZH = {
    SLOT_MORNING: "早",
    SLOT_NOON: "中午",
    SLOT_EVENING: "晚",
    SLOT_OTHER: "其他",
}

# 預設「每 X 小時」型藥物的最少安全間隔（小時）
DEFAULT_MIN_INTERVAL_HOURS = 4

_ORDER = {SLOT_MORNING: 0, SLOT_NOON: 1, SLOT_EVENING: 2, SLOT_OTHER: 3}


def _norm(text: str | None) -> str:
    if not text:
        return ""
    s = str(text).lower()
    # 把全形數字轉半形，方便正則
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(table)
    # 中文數字 → 阿拉伯（只處理常見的 1~6）
    cn_num = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6"}
    for cn, ar in cn_num.items():
        s = s.replace(cn, ar)
    return s


def _is_prn(text: str) -> bool:
    return bool(re.search(r"prn|p\.r\.n|必要時|需要時|有狀況時|不舒服時|疼痛時|疼時", text))


def _interval_hours(text: str) -> int | None:
    """抓「每 X 小時」、「每隔 X 小時」、「qXh」型的間隔。

    Note: 「小時」是中文，後面不需要 \\b（中文字會被 \\w 視為 word char，
    \\b 在中→中／中→英／中→數字之間不成立，所以直接以單位字結尾就好）。
    """
    candidates = [
        r"每\s*(?:隔)?\s*(\d{1,2})\s*小時",
        r"每\s*(?:隔)?\s*(\d{1,2})\s*hrs?\b",
        r"每\s*(?:隔)?\s*(\d{1,2})\s*h\b",
        r"q\s*(\d{1,2})\s*h\b",
    ]
    for pat in candidates:
        m = re.search(pat, text)
        if m:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if 1 <= n <= 24:
                return n
    return None


def parse_time_slots(frequency: str | None, usage: str | None = None) -> dict:
    """
    解析服藥頻率與用法字串。

    回傳 dict：
      - slots:          ["morning"|"noon"|"evening"] 的子集合，按時間順序
      - interval_hours: int | None，「每 X 小時」型的間隔
      - is_prn:         bool，是否屬於「需要時服用」
      - bucket:         "morning" / "noon" / "evening" / "other" 中的最高優先時段
                        （供前端決定預設展開哪一格）
      - is_other:       bool，slots 為空 → True，前端要顯示在「其他」分類

    判斷規則：
      - 抓得到「每 X 小時」或 PRN → slots 為空，丟到「其他」
      - 抓得到「三餐 / TID / 一天3次」→ 早 + 中 + 晚
      - 抓得到「早晚 / BID / 一天2次」→ 早 + 晚
      - 抓得到「睡前 / HS」→ 晚
      - 文字裡只出現「中午」→ 中
      - 完全判斷不出來 → 早（多數醫囑預設）
    """
    text = _norm((frequency or "") + " " + (usage or ""))

    is_prn = _is_prn(text)
    interval = _interval_hours(text)

    if is_prn or interval:
        return {
            "slots": [],
            "interval_hours": interval,
            "is_prn": is_prn,
            "bucket": SLOT_OTHER,
            "is_other": True,
        }

    slots: set[str] = set()

    # 注意：text 已經過 _norm()，中文數字（一/兩/三/四…）與全形數字都被轉成
    # 半形阿拉伯數字。因此正則用 1/2/3/4 而不是 一/兩/三/四。
    # `[每1]\s*[天日]` 同時涵蓋「每天」「每日」「1天」「1日」。

    # ── 三餐 / 三餐飯後 / TID / 1 天 3 次 / QID（一天四次）──
    if re.search(r"3\s*餐|\btid\b|[每1]\s*[天日]\s*3\s*次|3\s*times", text):
        slots.update([SLOT_MORNING, SLOT_NOON, SLOT_EVENING])
    if re.search(r"\bqid\b|[每1]\s*[天日]\s*4\s*次|4\s*times", text):
        slots.update([SLOT_MORNING, SLOT_NOON, SLOT_EVENING])
    # ── 早晚 / BID / 1 天 2 次 ──
    if re.search(r"早晚|\bbid\b|[每1]\s*[天日]\s*2\s*次|2\s*times", text):
        slots.update([SLOT_MORNING, SLOT_EVENING])
    # ── 1 天 1 次 / QD ──
    one_per_day = re.search(r"\bqd\b|[每1]\s*[天日]\s*1\s*次|1\s*time(?!s)", text)

    # ── 個別時段 ──
    if re.search(r"早上|早晨|清晨|晨間|起床後|\bam\b", text):
        slots.add(SLOT_MORNING)
    if re.search(r"中午|午餐|午間|\bnoon\b|lunch", text):
        slots.add(SLOT_NOON)
    if re.search(r"晚上|晚餐|晚飯|睡前|\bhs\b|qhs|\bpm\b|bedtime|夜間", text):
        slots.add(SLOT_EVENING)
    # 「早」「晚」單字補抓（已被「早晚／晚上／早上…」處理過的不會重複算）
    if re.search(r"(?<![早晚])早(?![上晨晚])", text):
        slots.add(SLOT_MORNING)
    if re.search(r"(?<![早])晚(?![上餐間飯])", text):
        slots.add(SLOT_EVENING)

    if one_per_day and not slots:
        slots.add(SLOT_MORNING)

    if not slots:
        # 解析不出來，預設早上提醒
        slots.add(SLOT_MORNING)

    sorted_slots = sorted(slots, key=lambda s: _ORDER[s])
    return {
        "slots": sorted_slots,
        "interval_hours": None,
        "is_prn": False,
        "bucket": sorted_slots[0],
        "is_other": False,
    }


def annotate_medication(med: dict) -> dict:
    """在 medication dict 上掛載 schedule 欄位（不修改原本 row）。

    使用方式：
        med = dict(row)
        med.update(annotate_medication(med))
    """
    info = parse_time_slots(med.get("frequency"), med.get("instructions"))
    return {
        "slots": info["slots"],
        "interval_hours": info["interval_hours"],
        "is_prn": info["is_prn"],
        "bucket": info["bucket"],
        "is_other": info["is_other"],
    }


# ---------------------------------------------------------------------------
# 服藥安全檢查
# ---------------------------------------------------------------------------

def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    # ISO 8601；接受結尾 Z
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def check_dose_safety(
    logs: Iterable[dict],
    *,
    interval_hours: int | None,
    now: datetime | None = None,
    min_hours: int = DEFAULT_MIN_INTERVAL_HOURS,
) -> dict:
    """
    判斷此刻是否可以再服一次藥。

    參數：
      logs:           最近的服藥紀錄（要包含 taken_at；taken=False 的會自動忽略）
      interval_hours: 藥物本身的間隔小時數（從 parse_time_slots 得到）
      min_hours:      最少安全間隔（預設 4 小時）

    回傳：
      - allowed:           是否建議現在服用
      - last_taken_at:     上次有效服用時間（ISO，沒有就 None）
      - hours_since_last:  距離上次幾小時（float，沒有上次就 None）
      - required_hours:    本次該等多久（取 interval_hours 與 min_hours 較大者）
      - hours_remaining:   還差多久才安全（>0 代表太早；None 代表沒上一筆）
      - level:             "safe" | "warn" | "block"
                           safe = 可以服用
                           warn = 只到 min_hours 但還沒到藥物本身的 interval（少見）
                           block = 連最低 4 小時都還沒到
      - message:           給患者看的中文訊息
    """
    now = now or datetime.now(timezone.utc)
    required = max(min_hours, interval_hours or 0)

    # 找最近一筆有效服藥
    last_dt: datetime | None = None
    for log in logs:
        if not log.get("taken"):
            continue
        dt = _parse_dt(log.get("taken_at"))
        if dt and (last_dt is None or dt > last_dt):
            last_dt = dt

    if last_dt is None:
        return {
            "allowed": True,
            "last_taken_at": None,
            "hours_since_last": None,
            "required_hours": required,
            "hours_remaining": None,
            "level": "safe",
            "message": "目前沒有近期服藥紀錄，可以服用。",
        }

    delta_hours = (now - last_dt).total_seconds() / 3600.0
    hours_remaining = max(0.0, required - delta_hours)
    last_iso = last_dt.astimezone(timezone.utc).isoformat()

    if delta_hours >= required:
        return {
            "allowed": True,
            "last_taken_at": last_iso,
            "hours_since_last": round(delta_hours, 2),
            "required_hours": required,
            "hours_remaining": 0.0,
            "level": "safe",
            "message": f"距離上次服藥已 {delta_hours:.1f} 小時，可以服用。",
        }

    # 還沒滿安全間隔
    if delta_hours < min_hours:
        msg = (
            f"距離上次服藥只有 {delta_hours:.1f} 小時，"
            f"短時間內重複服藥可能造成肝腎負擔、藥效過量、低血壓或腸胃出血等風險。"
            f"建議再等 {hours_remaining:.1f} 小時再服用，"
            "若症狀無法忍受請聯繫醫師或藥師，不要自行加量。"
        )
        level = "block"
    else:
        msg = (
            f"距離上次服藥 {delta_hours:.1f} 小時，"
            f"此藥建議間隔 {required} 小時，再等 {hours_remaining:.1f} 小時較安全。"
        )
        level = "warn"

    return {
        "allowed": False,
        "last_taken_at": last_iso,
        "hours_since_last": round(delta_hours, 2),
        "required_hours": required,
        "hours_remaining": round(hours_remaining, 2),
        "level": level,
        "message": msg,
    }

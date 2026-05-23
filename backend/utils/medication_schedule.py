"""藥物服用時段與安全間隔解析。

把藥袋常見的「一天三次／早晚／睡前／每 8 小時／PRN」等寫法
轉成標準的時段標籤（早 / 中 / 晚 / 其他），
並提供「是否可立即服用」的安全檢查：預設最少間隔 6 小時，硬底線 4 小時，
PRN 且醫師有明確指示的可低於 4 小時。
"""

from __future__ import annotations

import json
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

# 一般情況的預設最少安全間隔（小時）。沒有特別指定 interval 的藥（如早/中/晚、
# 或單純 PRN 沒指定間隔）都用這個值。
DEFAULT_MIN_INTERVAL_HOURS = 6

# 絕對底線：任何狀況都不能低於這個時數，**除非** 是 PRN 且醫師有明確指示 interval。
# 例：interval_hours=3 的「每 3 小時」非 PRN 藥，仍會以 4 小時為底線。
ABSOLUTE_FLOOR_HOURS = 4

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


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_custom_schedule(raw) -> dict | None:
    """
    把使用者自訂的非統一排程正規化成 {"entries": [{"weekdays": [...], "time": "HH:MM"}]}。

    輸入可以是 dict / JSON 字串 / None；不合法的 entry 會被丟掉。
    weekdays 用 0=Mon..6=Sun（與 datetime.weekday() / reminders.days_of_week 一致）。
    回傳 None 代表「沒有有效的自訂排程」，呼叫端應 fallback 到 frequency 文字解析。

    為什麼集中在這裡：藥物表的 custom_schedule 欄位無論存到 Supabase（jsonb）或
    SQLite（TEXT 存 JSON），讀回來後都用這個函式做一次「修整 + 去蕪存菁」，
    避免 router、annotate、UI 各自重複驗證導致格式漂移。
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None
    if not isinstance(raw, dict):
        return None
    entries_in = raw.get("entries")
    if not isinstance(entries_in, list) or not entries_in:
        return None
    valid: list[dict] = []
    seen: set[tuple] = set()
    for e in entries_in:
        if not isinstance(e, dict):
            continue
        wd_raw = e.get("weekdays")
        t_raw = e.get("time")
        if not isinstance(wd_raw, list) or not isinstance(t_raw, str):
            continue
        wd_norm: list[int] = []
        for d in wd_raw:
            try:
                di = int(d)
            except (TypeError, ValueError):
                continue
            if 0 <= di <= 6 and di not in wd_norm:
                wd_norm.append(di)
        if not wd_norm:
            continue
        wd_norm.sort()
        m = _TIME_RE.match(t_raw.strip())
        if not m:
            continue
        h, mi = int(m.group(1)), int(m.group(2))
        if not (0 <= h <= 23 and 0 <= mi <= 59):
            continue
        time_str = f"{h:02d}:{mi:02d}"
        key = (tuple(wd_norm), time_str)
        if key in seen:
            continue
        seen.add(key)
        valid.append({"weekdays": wd_norm, "time": time_str})
    if not valid:
        return None
    valid.sort(key=lambda e: (e["time"], e["weekdays"]))
    return {"entries": valid}


def custom_schedule_times_for_weekday(custom_schedule: dict | None, weekday: int) -> list[str]:
    """從 normalized custom_schedule 取出今天該排程的所有時刻（HH:MM 字串、排序、去重）。"""
    if not custom_schedule:
        return []
    times: set[str] = set()
    for e in custom_schedule.get("entries", []):
        if weekday in e.get("weekdays", []):
            times.add(e["time"])
    return sorted(times)


def annotate_medication(med: dict) -> dict:
    """在 medication dict 上掛載 schedule 欄位（不修改原本 row）。

    使用方式：
        med = dict(row)
        med.update(annotate_medication(med))

    custom_schedule（若存在且合法）會 override frequency 文字解析的 slots：
      - 把 custom 時刻轉成早/中/晚 bucket（≤10:30 → morning、10:30–15:30 → noon、
        15:30–20:30 → evening、否則 evening）以維持舊版分桶 UI 相容
      - 把原本的 slots / bucket / is_other 覆寫成 custom 推得的值
    """
    info = parse_time_slots(med.get("frequency"), med.get("instructions"))
    custom = parse_custom_schedule(med.get("custom_schedule"))
    out = {
        "slots": info["slots"],
        "interval_hours": info["interval_hours"],
        "is_prn": info["is_prn"],
        "bucket": info["bucket"],
        "is_other": info["is_other"],
        "custom_schedule": custom,
    }
    if custom:
        # 自訂排程優先：把所有 entries 涵蓋到的時刻分桶，覆寫 slots/bucket。
        slots_set: set[str] = set()
        for e in custom["entries"]:
            slots_set.add(_time_to_bucket(e["time"]))
        ordered = sorted(slots_set, key=lambda s: _ORDER.get(s, 99))
        if ordered:
            out["slots"] = ordered
            out["bucket"] = ordered[0]
            out["is_other"] = False
    return out


def _time_to_bucket(hhmm: str) -> str:
    """HH:MM → 早/中/晚 bucket，用於把自訂時刻 fallback 對應到舊版分桶 UI。"""
    m = _TIME_RE.match(hhmm)
    if not m:
        return SLOT_OTHER
    minutes = int(m.group(1)) * 60 + int(m.group(2))
    if minutes < 10 * 60 + 30:
        return SLOT_MORNING
    if minutes < 15 * 60 + 30:
        return SLOT_NOON
    return SLOT_EVENING


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
    is_prn: bool = False,
    now: datetime | None = None,
    min_hours: int = DEFAULT_MIN_INTERVAL_HOURS,
    floor_hours: int = ABSOLUTE_FLOOR_HOURS,
) -> dict:
    """
    判斷此刻是否可以再服一次藥。

    規則（從寬到緊）：
      1. PRN + 醫師明確指示 interval_hours → 用醫師指示（可低於 floor_hours，
         例：止痛藥 q2h prn）
      2. 非 PRN 但有明確 interval_hours → max(floor_hours, interval_hours)，
         即使醫師寫每 3 小時也要守住 4 小時底線
      3. 沒指定 interval_hours（早/中/晚、單純 PRN 沒間隔）→ min_hours（預設 6）

    參數：
      logs:           最近的服藥紀錄（要包含 taken_at；taken=False 的會自動忽略）
      interval_hours: 藥物本身的間隔小時數（從 parse_time_slots 得到）
      is_prn:         是否為「需要時服用」(PRN)；PRN + interval_hours 可低於 floor
      min_hours:      一般情況的預設間隔（小時，預設 6）
      floor_hours:    絕對底線（小時，預設 4）；非 PRN 不會低於它

    回傳：
      - allowed:           是否建議現在服用
      - last_taken_at:     上次有效服用時間（ISO，沒有就 None）
      - hours_since_last:  距離上次幾小時（float，沒有上次就 None）
      - required_hours:    本次該等多久
      - hours_remaining:   還差多久才安全（>0 代表太早；None 代表沒上一筆）
      - level:             "safe" | "warn" | "block"
                           safe = 可以服用
                           warn = 過了 floor 但還沒到 required（介於 4~6 間的灰區）
                           block = 連 floor 都還沒到（或 PRN 沒到醫師指定的 interval）
      - message:           給患者看的中文訊息
    """
    now = now or datetime.now(timezone.utc)
    if is_prn and interval_hours:
        # PRN + 醫師指示 → 完全信醫師
        required = interval_hours
    elif interval_hours:
        # 非 PRN 有 interval → 用 interval 但守 floor
        required = max(floor_hours, interval_hours)
    else:
        # 沒 interval → 用一般預設
        required = min_hours

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

    # 還沒滿安全間隔。決定 block vs warn：
    #   - PRN + 醫師指示：required 就是底線，沒到就 block（沒 warn 區）
    #   - 其他：< floor_hours 是硬 block 區；floor ~ required 之間是 warn 區
    #     例：required=6, floor=4，delta=5 → 過 floor 但沒到 6 → warn
    block_threshold = required if (is_prn and interval_hours) else floor_hours
    if delta_hours < block_threshold:
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

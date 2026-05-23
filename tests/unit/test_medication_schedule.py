"""parse_time_slots / check_dose_safety 的單元測試。

涵蓋台灣藥袋常見的服藥時段寫法，
以及「每 X 小時」型藥物的 4 小時安全間隔檢查。
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.utils.medication_schedule import (
    DEFAULT_MIN_INTERVAL_HOURS,
    SLOT_EVENING,
    SLOT_MORNING,
    SLOT_NOON,
    SLOT_OTHER,
    annotate_medication,
    check_dose_safety,
    custom_schedule_times_for_weekday,
    parse_custom_schedule,
    parse_time_slots,
)


# ── parse_time_slots ──────────────────────────────────────────


def _slots(freq, usage=None):
    return parse_time_slots(freq, usage)


@pytest.mark.parametrize(
    "freq,usage,expected",
    [
        # 三餐 / TID 一律 早 + 中 + 晚
        ("一天三次", "飯後", [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]),
        ("TID", "PC", [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]),
        ("三餐飯後", None, [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]),
        ("每日三次", "飯前", [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]),
        # 早晚 / BID
        ("一天兩次", "飯後", [SLOT_MORNING, SLOT_EVENING]),
        ("BID", "", [SLOT_MORNING, SLOT_EVENING]),
        ("早晚各一", None, [SLOT_MORNING, SLOT_EVENING]),
        # 一天一次（預設早上）
        ("一天一次", "早餐後", [SLOT_MORNING]),
        ("QD", "", [SLOT_MORNING]),
        # 中午
        ("一天一次", "中午飯後", [SLOT_NOON]),
        # 睡前
        ("睡前", "", [SLOT_EVENING]),
        ("HS", "", [SLOT_EVENING]),
        # 純文字找不到 → 預設早
        ("", "", [SLOT_MORNING]),
        ("醫師指示", "", [SLOT_MORNING]),
    ],
)
def test_named_slots(freq, usage, expected):
    info = _slots(freq, usage)
    assert info["slots"] == expected
    assert info["is_other"] is False
    assert info["interval_hours"] is None


@pytest.mark.parametrize(
    "freq",
    [
        "每 8 小時一次",
        "每8小時",
        "每 6 hr 一顆",
        "Q6H",
        "q12h",
        "每隔 4 小時服用",
    ],
)
def test_interval_meds_go_to_other(freq):
    info = _slots(freq)
    assert info["is_other"] is True
    assert info["bucket"] == SLOT_OTHER
    assert info["slots"] == []
    assert isinstance(info["interval_hours"], int)
    assert 1 <= info["interval_hours"] <= 24


@pytest.mark.parametrize(
    "freq",
    ["PRN", "需要時服用", "必要時 1 顆", "疼痛時"],
)
def test_prn_meds_go_to_other(freq):
    info = _slots(freq)
    assert info["is_other"] is True
    assert info["is_prn"] is True
    assert info["interval_hours"] is None


def test_annotate_medication_returns_extra_fields():
    med = {"name": "X", "frequency": "一天三次", "instructions": "飯後"}
    extra = annotate_medication(med)
    assert extra["slots"] == [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]
    assert extra["bucket"] == SLOT_MORNING
    assert extra["is_other"] is False
    assert extra["custom_schedule"] is None


# ── parse_custom_schedule（非統一時刻自訂排程） ──────────────


def test_parse_custom_schedule_none_and_empty():
    assert parse_custom_schedule(None) is None
    assert parse_custom_schedule("") is None
    assert parse_custom_schedule({}) is None
    assert parse_custom_schedule({"entries": []}) is None


def test_parse_custom_schedule_normalizes_time_and_dedups_weekdays():
    raw = {"entries": [{"weekdays": [1, 3, 5, 1, 3], "time": "8:00"}]}
    out = parse_custom_schedule(raw)
    assert out == {"entries": [{"weekdays": [1, 3, 5], "time": "08:00"}]}


def test_parse_custom_schedule_accepts_json_string():
    raw = '{"entries":[{"weekdays":[0],"time":"22:30"}]}'
    out = parse_custom_schedule(raw)
    assert out == {"entries": [{"weekdays": [0], "time": "22:30"}]}


def test_parse_custom_schedule_drops_invalid_entries():
    raw = {"entries": [
        {"weekdays": [9], "time": "12:00"},  # weekday 超範圍 → 整筆丟掉
        {"weekdays": [], "time": "12:00"},   # 空 weekdays → 丟掉
        {"weekdays": [0], "time": "25:99"},  # 時間不合法 → 丟掉
        {"weekdays": [0], "time": "noon"},   # 非 HH:MM → 丟掉
        {"weekdays": [0], "time": "09:15"},  # ✓ 保留
    ]}
    out = parse_custom_schedule(raw)
    assert out == {"entries": [{"weekdays": [0], "time": "09:15"}]}


def test_parse_custom_schedule_dedups_identical_entries_and_sorts():
    raw = {"entries": [
        {"weekdays": [2], "time": "14:00"},
        {"weekdays": [2], "time": "14:00"},  # 完全重複 → 去重
        {"weekdays": [1], "time": "08:00"},
    ]}
    out = parse_custom_schedule(raw)
    assert out == {"entries": [
        {"weekdays": [1], "time": "08:00"},
        {"weekdays": [2], "time": "14:00"},
    ]}


def test_custom_schedule_times_for_weekday():
    sched = {"entries": [
        {"weekdays": [0, 2, 4], "time": "08:00"},
        {"weekdays": [1], "time": "14:00"},
        {"weekdays": [0], "time": "20:00"},
    ]}
    assert custom_schedule_times_for_weekday(sched, 0) == ["08:00", "20:00"]
    assert custom_schedule_times_for_weekday(sched, 1) == ["14:00"]
    assert custom_schedule_times_for_weekday(sched, 3) == []
    assert custom_schedule_times_for_weekday(None, 0) == []


def test_annotate_medication_custom_schedule_overrides_slots():
    # frequency 文字寫「一天一次」（會解析成 morning），但自訂排程是「週二 14:00 + 週四 20:00」
    # → slots 應該以自訂排程的時刻分桶為主（noon + evening），不再用 frequency 推算。
    med = {
        "frequency": "一天一次",
        "custom_schedule": {"entries": [
            {"weekdays": [1], "time": "14:00"},
            {"weekdays": [3], "time": "20:00"},
        ]},
    }
    extra = annotate_medication(med)
    assert SLOT_NOON in extra["slots"]
    assert SLOT_EVENING in extra["slots"]
    assert SLOT_MORNING not in extra["slots"]
    assert extra["bucket"] == SLOT_NOON
    assert extra["is_other"] is False
    assert extra["custom_schedule"] is not None


def test_annotate_medication_invalid_custom_schedule_falls_back():
    # 自訂排程全部不合法 → 退回 frequency 文字解析。
    med = {"frequency": "一天三次", "custom_schedule": {"entries": [{"weekdays": [9], "time": "bad"}]}}
    extra = annotate_medication(med)
    assert extra["slots"] == [SLOT_MORNING, SLOT_NOON, SLOT_EVENING]
    assert extra["custom_schedule"] is None


# ── check_dose_safety ────────────────────────────────────────


def _now() -> datetime:
    return datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc)


def _log_taken(hours_ago: float):
    return {"taken": True, "taken_at": (_now() - timedelta(hours=hours_ago)).isoformat()}


def test_no_logs_returns_safe():
    res = check_dose_safety([], interval_hours=6, now=_now())
    assert res["allowed"] is True
    assert res["level"] == "safe"
    assert res["last_taken_at"] is None


def test_within_floor_blocks():
    # interval=6, 上次 1.5 小時前 → 連 4 小時 floor 都沒到 → block
    logs = [_log_taken(1.5)]
    res = check_dose_safety(logs, interval_hours=6, now=_now())
    assert res["allowed"] is False
    assert res["level"] == "block"
    assert res["hours_remaining"] > 0
    assert "風險" in res["message"]


def test_between_floor_and_default_warns():
    # interval=6, 上次 5 小時前 → 過 4 小時 floor 但沒到 6 → warn（灰區）
    logs = [_log_taken(5)]
    res = check_dose_safety(logs, interval_hours=6, now=_now())
    assert res["allowed"] is False
    assert res["level"] == "warn"
    assert res["required_hours"] == 6


def test_after_interval_allows():
    logs = [_log_taken(7)]
    res = check_dose_safety(logs, interval_hours=6, now=_now())
    assert res["allowed"] is True
    assert res["level"] == "safe"


def test_no_interval_uses_6_hour_default():
    # 早/中/晚（沒填 interval_hours）→ 一般預設 6 小時
    # 5 小時前 → 過 floor 但沒到 6 → warn
    res_warn = check_dose_safety([_log_taken(5)], interval_hours=None, now=_now())
    assert res_warn["allowed"] is False
    assert res_warn["level"] == "warn"
    assert res_warn["required_hours"] == DEFAULT_MIN_INTERVAL_HOURS  # 6

    # 2 小時前 → 連 4 小時 floor 都沒到 → block
    res_block = check_dose_safety([_log_taken(2)], interval_hours=None, now=_now())
    assert res_block["allowed"] is False
    assert res_block["level"] == "block"


def test_non_prn_interval_below_floor_uses_floor():
    # 非 PRN 但 interval=3（罕見）→ 不能低於 4 小時底線
    res = check_dose_safety(
        [_log_taken(3.5)], interval_hours=3, is_prn=False, now=_now()
    )
    # required = max(4, 3) = 4；delta=3.5 < 4 → block
    assert res["required_hours"] == 4
    assert res["level"] == "block"


def test_prn_with_short_interval_uses_doctor_setting():
    # PRN q2h（止痛藥常見指示）：required 用 2 小時，連 4 小時 floor 都可破
    res_block = check_dose_safety(
        [_log_taken(1.5)], interval_hours=2, is_prn=True, now=_now()
    )
    assert res_block["allowed"] is False
    assert res_block["level"] == "block"
    assert res_block["required_hours"] == 2

    # 過了 PRN 的 2 小時 → 放行（即使還沒到 4 小時 floor）
    res_safe = check_dose_safety(
        [_log_taken(2.5)], interval_hours=2, is_prn=True, now=_now()
    )
    assert res_safe["allowed"] is True
    assert res_safe["level"] == "safe"


def test_prn_without_interval_uses_default():
    # PRN 但沒明確 interval（醫師只寫「需要時」）→ 走一般預設 6
    res = check_dose_safety(
        [_log_taken(3)], interval_hours=None, is_prn=True, now=_now()
    )
    assert res["allowed"] is False
    assert res["required_hours"] == DEFAULT_MIN_INTERVAL_HOURS


def test_skipped_logs_are_ignored():
    logs = [
        {"taken": False, "taken_at": (_now() - timedelta(hours=0.5)).isoformat()},
        _log_taken(8),
    ]
    res = check_dose_safety(logs, interval_hours=6, now=_now())
    assert res["allowed"] is True
    assert res["hours_since_last"] == pytest.approx(8.0, abs=0.01)

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


def test_within_4_hours_blocks():
    logs = [_log_taken(1.5)]
    res = check_dose_safety(logs, interval_hours=6, now=_now())
    assert res["allowed"] is False
    assert res["level"] == "block"
    assert res["hours_remaining"] > 0
    assert "風險" in res["message"]


def test_after_min_but_before_interval_warns():
    # min=4, interval=6, 上次 5 小時前 → 過了 4 小時但沒到 6 → warn
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


def test_default_min_interval_when_no_interval_hours():
    # 沒填 interval_hours → 用 4 小時當門檻
    logs = [_log_taken(3)]
    res = check_dose_safety(logs, interval_hours=None, now=_now())
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

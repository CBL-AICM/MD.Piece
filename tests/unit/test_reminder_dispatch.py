"""復發提醒排程 _compute_next_fire 的回歸測試。

鎖住「為什麼重要」（規則 9）：提醒必須在使用者『設定的時刻』重複觸發，
而不是漂移到「剛好被派發到的那個時間」。

之前的 bug：daily/weekly 以 now 為基準 + 1 天，導致每天的觸發時刻會隨著
dispatch 命中的時間一路往前漂（設 08:00 結果隔天變 03:51…）。本測試用一個
「已到期、設定在 08:00」的 reminder，驗證下一次仍落在 08:00（同一時刻），
而非 now 之後 24 小時。若有人改回 base=now，這裡會立刻變紅。
"""

from datetime import datetime, timedelta, timezone

from backend.routers.reminders import _compute_next_fire


def _fixed_8am_yesterday():
    """昨天 08:00 UTC（已到期，模擬剛被 dispatch 的 daily reminder 的 next_fire_at）。"""
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)


def test_once_never_repeats():
    assert _compute_next_fire("once", _fixed_8am_yesterday(), "08:00", None) is None


def test_daily_keeps_clock_time_not_drift():
    """daily：下一次必須仍是 08:00（保留時刻），且嚴格落在未來。"""
    fired_at = _fixed_8am_yesterday()
    nxt = _compute_next_fire("daily", fired_at, "08:00", None)
    now = datetime.now(timezone.utc)
    assert nxt > now
    assert (nxt.hour, nxt.minute, nxt.second) == (8, 0, 0), "daily 觸發時刻漂移了，沒保留 08:00"
    # 應是「今天或明天的 08:00」，與被派發的當下時間無關（不是 now+24h）
    assert nxt.date() in (now.date(), (now + timedelta(days=1)).date())


def test_daily_catches_up_after_long_offline():
    """app 長時間沒開、錯過很多天 → 補到未來最近一次，仍保留 08:00。"""
    fired_at = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=10)
    nxt = _compute_next_fire("daily", fired_at, "08:00", None)
    now = datetime.now(timezone.utc)
    assert nxt > now
    assert (nxt.hour, nxt.minute) == (8, 0)
    assert nxt <= now + timedelta(days=1)


def test_weekly_picks_next_allowed_weekday_keeping_time():
    """weekly：下一次必須是未來、落在指定星期，且保留原本時刻。"""
    anchor = _fixed_8am_yesterday()
    # 只允許週一(0) 與 週四(3)
    nxt = _compute_next_fire("weekly", anchor, "08:00", [0, 3])
    now = datetime.now(timezone.utc)
    assert nxt > now
    assert nxt.weekday() in (0, 3)
    assert (nxt.hour, nxt.minute) == (8, 0)


def test_weekly_without_days_advances_one_week():
    anchor = _fixed_8am_yesterday()
    nxt = _compute_next_fire("weekly", anchor, "08:00", None)
    now = datetime.now(timezone.utc)
    assert nxt > now
    assert (nxt.hour, nxt.minute) == (8, 0)

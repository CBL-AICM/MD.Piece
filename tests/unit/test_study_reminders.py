"""問卷到期提醒「排程時點」單元測試（純函式，不碰 DB / 不需 Supabase）。

規則 9：驗的是「為什麼這個排程是對的」，不是只跑得過。
- 起算日（帳號建立日）+ N 天的日期算錯，使用者就會在錯的日子被提醒。
- D0 不該排（註冊當天不需提醒）、FU48 不該排（回診事件型，不是日數窗格）——
  若有人把它們加進 STUDY_REMINDER_OFFSETS，這些測試要亮紅燈。
- 天數必須與前端 STUDY_WINDOWS（app.js）一致：D14=14、D28=28。

執行：pytest tests/unit/test_study_reminders.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.routers.surveys import STUDY_REMINDER_OFFSETS, _study_due_at  # noqa: E402


def test_offsets_match_frontend_windows():
    # 與 app.js 的 STUDY_WINDOWS 對齊；漂移會讓前後端「該填哪份」不一致。
    assert STUDY_REMINDER_OFFSETS == {"D14": 14, "D28": 28}


def test_d0_and_fu48_are_not_scheduled():
    # D0 = 註冊當天（不需提醒）、FU48 = 回診事件型（非日數）——都不該被排程。
    assert "D0" not in STUDY_REMINDER_OFFSETS
    assert "FU48" not in STUDY_REMINDER_OFFSETS


def test_due_at_adds_days_and_pins_9am_utc():
    start = datetime(2026, 1, 1, 13, 45, tzinfo=timezone.utc)
    d14 = _study_due_at(start, 14)
    assert d14 == datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    d28 = _study_due_at(start, 28)
    assert d28 == datetime(2026, 1, 29, 9, 0, tzinfo=timezone.utc)


def test_due_at_treats_naive_start_as_utc():
    # Supabase created_at 偶爾沒帶時區；不能當成 local 否則跨時區會差一天。
    naive = datetime(2026, 1, 1, 0, 0)
    out = _study_due_at(naive, 14)
    assert out.tzinfo == timezone.utc
    assert out == datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)


def test_due_at_crosses_month_boundary():
    # 月底起算要正確進位，不能用「同月加日」的錯誤寫法。
    start = datetime(2026, 1, 20, 8, 0, tzinfo=timezone.utc)
    assert _study_due_at(start, 28) == datetime(2026, 2, 17, 9, 0, tzinfo=timezone.utc)

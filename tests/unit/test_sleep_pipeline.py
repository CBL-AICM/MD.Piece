"""睡眠判睡 pipeline 單元測試（規格 §7 驗收 #1, #2）。

驗證「為什麼」而非只是「有沒有」（鐵則 9）：
  - 安靜整夜 → 高睡眠效率、低 WASO；中間插一段動作 → WASO 與清醒次數正確反映。
  - 分類器是可替換 interface（Cole-Kripke / Sadeh 皆可跑）。
  - 夜間時段限制：白天靜止不被算成睡眠。
  - 指標算術正確（efficiency = total_sleep / time_in_bed，介於 0–1）。
"""

from datetime import datetime, timedelta

import pytest

from backend.utils.sleep_pipeline import (
    Epoch,
    SleepConfig,
    compute_metrics_from_times,
    get_classifier,
    run_pipeline,
)


def _epochs(start: datetime, activity_per_min: list[float]) -> list[Epoch]:
    return [
        Epoch(timestamp=start + timedelta(minutes=i), activity_count=a)
        for i, a in enumerate(activity_per_min)
    ]


def test_classifier_interface_is_swappable():
    """兩種分類器都實作同一介面、都能跑（規格 §3.1 可替換擴充點）。"""
    start = datetime(2026, 5, 1, 23, 0)
    eps = _epochs(start, [0.0] * 30)
    for name in ("cole_kripke", "sadeh"):
        clf = get_classifier(name)
        states = clf.classify(eps)
        assert len(states) == len(eps)
        assert set(states) <= {"sleep", "wake"}
        assert clf.name == name
    with pytest.raises(ValueError):
        get_classifier("nonexistent-model")


def test_quiet_night_is_mostly_sleep_high_efficiency():
    """整夜安靜（低 activity）→ 判為睡眠、效率高、WASO 低。"""
    start = datetime(2026, 5, 1, 23, 0)  # 夜間時段內
    eps = _epochs(start, [0.0] * 480)    # 8 小時幾乎不動
    session = run_pipeline(eps, "u1", cfg=SleepConfig(classifier="cole_kripke"))
    assert session is not None
    assert session["source"] == "auto"
    assert session["total_sleep_minutes"] > 400          # 大部分判為睡眠
    assert session["sleep_efficiency"] > 0.9
    assert 0.0 <= session["sleep_efficiency"] <= 1.0
    assert session["waso_minutes"] < 20


def test_midnight_awakening_counts_waso_and_awakenings():
    """睡到一半有一段明顯動作 → 該段計入 WASO 與清醒次數，但不切斷整段睡眠。"""
    start = datetime(2026, 5, 1, 23, 0)
    # 100 分鐘睡 + 15 分鐘大動作（清醒）+ 100 分鐘睡
    activity = [0.0] * 100 + [800.0] * 15 + [0.0] * 100
    session = run_pipeline(eps := _epochs(start, activity), "u1",
                           cfg=SleepConfig(classifier="cole_kripke"))
    assert session is not None
    assert session["awakenings_count"] >= 1               # 至少一次夜醒
    assert session["waso_minutes"] >= 10                  # 中間清醒被計入 WASO
    # onset 在最終 wake 之前，整段沒被切成兩筆（pipeline 只輸出一筆）
    assert session["sleep_onset"] < session["wake_time"]
    assert session["total_sleep_minutes"] > 150           # 兩段睡眠仍合計入睡眠


def test_daytime_stillness_not_counted_as_sleep():
    """白天（夜間時段外）的靜止不應被判成睡眠（規格 §3.2）。"""
    start = datetime(2026, 5, 1, 13, 0)  # 下午 1 點，不在 22:00–10:00
    eps = _epochs(start, [0.0] * 120)
    session = run_pipeline(eps, "u1", cfg=SleepConfig())
    assert session is None


def test_efficiency_formula_matches_definition():
    """睡眠效率 = total_sleep / time_in_bed（規格 §2.1），手動算術版。"""
    bed = datetime(2026, 5, 1, 23, 0)
    onset = datetime(2026, 5, 1, 23, 30)   # 30 分鐘才入睡
    wake = datetime(2026, 5, 2, 7, 30)     # 睡到 7:30 → onset..wake = 480 分
    m = compute_metrics_from_times(bed, onset, wake, waso_minutes=30)
    # time_in_bed = 23:00..07:30 = 510 分；total_sleep = 480 - 30(waso) = 450
    assert m["time_in_bed_minutes"] == 510
    assert m["total_sleep_minutes"] == 450
    assert m["sleep_efficiency"] == round(450 / 510, 4)
    assert 0.0 <= m["sleep_efficiency"] <= 1.0


def test_empty_signal_returns_none():
    assert run_pipeline([], "u1") is None

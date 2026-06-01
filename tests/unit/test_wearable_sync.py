"""穿戴裝置同步 — 純映射 / state 簽章單元測試（規則 9：驗為什麼）。

map_fitbit_sleep_to_session 是 source=imported 的核心：把 Fitbit 的欄位語意
正確轉成本專案 schema。若有人把 efficiency 當成已是 0–1、或忘了加入睡潛伏期
（minutesToFallAsleep）、或把夜醒次數抓錯欄位，這些測試都會變紅。
"""

import pytest

from backend.services import wearable_sync


# 取自 Fitbit Sleep API v1.2 「stages」型回應的代表性一筆。
_FITBIT_STAGES_LOG = {
    "dateOfSleep": "2026-05-21",
    "startTime": "2026-05-20T23:08:00.000",
    "endTime": "2026-05-21T06:43:00.000",
    "minutesToFallAsleep": 12,
    "minutesAsleep": 395,
    "minutesAwake": 59,
    "timeInBed": 455,
    "efficiency": 92,
    "isMainSleep": True,
    "type": "stages",
    "levels": {"summary": {
        "deep": {"count": 5, "minutes": 104},
        "light": {"count": 30, "minutes": 200},
        "rem": {"count": 8, "minutes": 91},
        "wake": {"count": 28, "minutes": 59},
    }},
}


def test_efficiency_is_converted_from_percent_to_fraction():
    """Fitbit efficiency 是百分比（92），本專案存 0–1（0.92）。"""
    row = wearable_sync.map_fitbit_sleep_to_session(_FITBIT_STAGES_LOG, "u1")
    assert row["sleep_efficiency"] == 0.92
    assert 0.0 <= row["sleep_efficiency"] <= 1.0


def test_onset_includes_minutes_to_fall_asleep():
    """入睡時間 = 上床時間 + 睡潛伏期；不是直接等於 startTime。"""
    row = wearable_sync.map_fitbit_sleep_to_session(_FITBIT_STAGES_LOG, "u1")
    assert row["bed_time"] == "2026-05-20T23:08:00"
    assert row["sleep_onset"] == "2026-05-20T23:20:00"   # +12 分
    assert row["wake_time"] == "2026-05-21T06:43:00"


def test_core_metrics_map_one_to_one():
    row = wearable_sync.map_fitbit_sleep_to_session(_FITBIT_STAGES_LOG, "u1")
    assert row["total_sleep_minutes"] == 395
    assert row["time_in_bed_minutes"] == 455
    assert row["waso_minutes"] == 59
    assert row["awakenings_count"] == 28          # 來自 levels.summary.wake.count
    assert row["source"] == "imported"
    assert row["is_edited"] is False
    assert row["user_id"] == "u1"


def test_classic_log_uses_awake_count_for_awakenings():
    """classic（非 stages）型沒有 wake，用 awake.count；缺則 0。"""
    classic = {**_FITBIT_STAGES_LOG, "type": "classic",
               "levels": {"summary": {"awake": {"count": 4, "minutes": 30},
                                      "restless": {"count": 9, "minutes": 20},
                                      "asleep": {"count": 1, "minutes": 405}}}}
    row = wearable_sync.map_fitbit_sleep_to_session(classic, "u1")
    assert row["awakenings_count"] == 4

    no_levels = {**_FITBIT_STAGES_LOG, "levels": {}}
    assert wearable_sync.map_fitbit_sleep_to_session(no_levels, "u1")["awakenings_count"] == 0


def test_missing_efficiency_is_none_not_zero():
    """缺 efficiency 應為 None（資料不存在），而非誤填 0（看起來像效率超差）。"""
    no_eff = {k: v for k, v in _FITBIT_STAGES_LOG.items() if k != "efficiency"}
    assert wearable_sync.map_fitbit_sleep_to_session(no_eff, "u1")["sleep_efficiency"] is None


def test_state_signature_roundtrip_and_tamper(monkeypatch):
    """state 帶 user_id 並用 client_secret 簽章：正常可解、被竄改則拒（防 CSRF）。"""
    monkeypatch.setattr(wearable_sync, "FITBIT_CLIENT_SECRET", "test-secret-123")
    state = wearable_sync.make_state("patient-42")
    assert wearable_sync.parse_state(state) == "patient-42"
    # 竄改 user_id 但沿用舊簽章 → 驗章失敗
    bad = "attacker-id." + state.rpartition(".")[2]
    assert wearable_sync.parse_state(bad) is None
    assert wearable_sync.parse_state("garbage") is None

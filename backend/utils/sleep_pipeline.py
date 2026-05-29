"""
判睡 pipeline — 睡眠紀錄模組核心邏輯（與 UI 解耦，可獨立單元測試）。

依《睡眠紀錄模組 開發規格》§3：
  原始訊號 → 切 epoch → 算 activity_count → 逐 epoch 分類 sleep/wake
           → 合併連續 sleep 區段 → 計算指標 → 輸出一筆 SleepSession dict

設計邊界（務必遵守）：純記錄與計算，不下診斷、不給建議、不做風險警示。

擴充點（專案主軸延伸）：分類器抽象成 SleepClassifier interface，
日後可替換為個人化模型，pipeline 其餘不動。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Protocol


# ── Epoch 輸入 ────────────────────────────────────────────

@dataclass
class Epoch:
    """1 分鐘為一段的判睡中間產物（規格 §2.2）。"""
    timestamp: datetime
    activity_count: float
    heart_rate: Optional[float] = None
    state: Optional[str] = None  # 'sleep' | 'wake'，分類後回填


# ── 分類器 interface（可替換擴充點，規格 §3.1）────────────

class SleepClassifier(Protocol):
    """逐 epoch 分類成 sleep/wake。日後可替換為個人化模型。"""
    name: str

    def classify(self, epochs: List[Epoch]) -> List[str]:
        """回傳與 epochs 等長的 ['sleep'|'wake', ...]。"""
        ...


class ColeKripkeClassifier:
    """經典 actigraphy 演算法 Cole-Kripke（規格 §3.1 預設之一）。

    以加權移動窗計算每個 epoch 的活動分數 D；D < 1 判為 sleep。
    權重為文獻經典值（1-min epoch 版本）；activity_count 先做尺度縮放。
    這是「確定性演算法」，不是 ML 黑箱——可重現、可測試。
    """
    name = "cole_kripke"

    # 經典 Cole-Kripke 權重與比例常數（Cole 1992，1-min epoch 版）。
    # 期望 activity_count 為未縮放的 actigraph 動作量：睡眠時通常 <50、
    # 清醒時數百~上千。D = P·Σ(W_i·A_i)；D < 1 判 sleep。
    _P = 0.00001
    _W = [106, 54, 58, 76, 230, 74, 67]  # [-4,-3,-2,-1,0,+1,+2]
    _SCALE = 1.0

    def classify(self, epochs: List[Epoch]) -> List[str]:
        n = len(epochs)
        counts = [max(0.0, e.activity_count) / self._SCALE for e in epochs]
        states: List[str] = []
        for i in range(n):
            # window offsets -4..+2 對應權重
            acc = 0.0
            for k, off in enumerate(range(-4, 3)):
                j = i + off
                if 0 <= j < n:
                    acc += self._W[k] * counts[j]
            d = self._P * acc
            states.append("sleep" if d < 1.0 else "wake")
        return states


class SadehClassifier:
    """經典 actigraphy 演算法 Sadeh（規格 §3.1 預設之一，可切換）。

    用 5 分鐘窗的平均、標準差與 NAT（落在 50–100 區間的 epoch 數）判睡。
    同樣是確定性演算法。
    """
    name = "sadeh"

    def classify(self, epochs: List[Epoch]) -> List[str]:
        n = len(epochs)
        counts = [max(0.0, e.activity_count) for e in epochs]
        states: List[str] = []
        for i in range(n):
            lo = max(0, i - 5)
            hi = min(n, i + 6)  # 含 i 前後共 ~11 分鐘窗
            window = counts[lo:hi]
            mean = sum(window) / len(window)
            # 標準差
            var = sum((x - mean) ** 2 for x in window) / len(window)
            sd = math.sqrt(var)
            # NAT：window 內 activity 介於 50–100 的 epoch 數
            nat = sum(1 for x in window if 50 <= x < 100)
            # 當前 epoch 的 log 活動量
            log_act = math.log(counts[i] + 1.0)
            psa = 7.601 - 0.065 * mean - 1.08 * nat - 0.056 * sd - 0.703 * log_act
            states.append("sleep" if psa >= 0 else "wake")
        return states


_CLASSIFIERS = {
    ColeKripkeClassifier.name: ColeKripkeClassifier,
    SadehClassifier.name: SadehClassifier,
}


def get_classifier(name: str = "cole_kripke") -> SleepClassifier:
    cls = _CLASSIFIERS.get(name)
    if cls is None:
        raise ValueError(f"未知的分類器：{name}，可用：{sorted(_CLASSIFIERS)}")
    return cls()


# ── 夜間時段（規格 §3.2，可設定）─────────────────────────

@dataclass
class SleepConfig:
    night_start_hour: int = 22       # 夜間時段起（含）
    night_end_hour: int = 10         # 夜間時段迄（不含），跨午夜
    epoch_minutes: int = 1
    short_wake_threshold_min: int = 5  # 短暫清醒門檻（規格 §3.3，不切斷睡眠）
    classifier: str = "cole_kripke"


def _in_night_window(ts: datetime, cfg: SleepConfig) -> bool:
    """是否落在夜間時段內（跨午夜：22:00–翌日 10:00）。"""
    h = ts.hour
    start, end = cfg.night_start_hour, cfg.night_end_hour
    if start <= end:
        return start <= h < end
    # 跨午夜：h >= start（晚上）或 h < end（凌晨）
    return h >= start or h < end


# ── pipeline 主流程（規格 §3）────────────────────────────

def run_pipeline(
    epochs: List[Epoch],
    user_id: str,
    cfg: Optional[SleepConfig] = None,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """輸入原始 epoch 序列，輸出一筆 SleepSession dict（或 None 表這段沒有睡眠）。

    步驟對應規格 §3 的 1–6。epoch 已切好（呼叫端負責切 + 算 activity_count，
    或直接餵入帶 activity_count 的 epoch）。
    """
    cfg = cfg or SleepConfig()
    if not epochs:
        return None

    # 2+3. 夜間時段過濾 + 逐 epoch 分類
    night = [e for e in sorted(epochs, key=lambda x: x.timestamp) if _in_night_window(e.timestamp, cfg)]
    if not night:
        return None

    classifier = get_classifier(cfg.classifier)
    states = classifier.classify(night)
    for e, s in zip(night, states):
        e.state = s

    # 4. 找第一個與最後一個 sleep epoch（睡眠主區段範圍）
    sleep_idx = [i for i, e in enumerate(night) if e.state == "sleep"]
    if not sleep_idx:
        return None
    first_sleep = sleep_idx[0]
    last_sleep = sleep_idx[-1]

    ep = cfg.epoch_minutes
    bed_time = night[0].timestamp
    sleep_onset = night[first_sleep].timestamp
    # 最終醒來 = 最後一個 sleep epoch 結束時刻
    wake_time = night[last_sleep].timestamp + timedelta(minutes=ep)

    # 5. 指標：在 onset..last_sleep 範圍內計 WASO 與清醒次數（規格 §3.3）
    waso_minutes = 0
    awakenings_count = 0
    total_sleep_minutes = 0
    in_wake_run = False
    cur_wake_run = 0

    span = night[first_sleep:last_sleep + 1]
    for e in span:
        if e.state == "sleep":
            total_sleep_minutes += ep
            if in_wake_run:
                # 一段清醒結束
                if cur_wake_run > 0:
                    waso_minutes += cur_wake_run
                    awakenings_count += 1
                in_wake_run = False
                cur_wake_run = 0
        else:  # wake（夾在睡眠中間）
            in_wake_run = True
            cur_wake_run += ep

    time_in_bed_minutes = int(round((wake_time - bed_time).total_seconds() / 60))
    # 躺床時間至少涵蓋睡眠主區段
    if time_in_bed_minutes <= 0:
        time_in_bed_minutes = total_sleep_minutes + waso_minutes
    sleep_efficiency = round(total_sleep_minutes / time_in_bed_minutes, 4) if time_in_bed_minutes else 0.0
    sleep_efficiency = max(0.0, min(1.0, sleep_efficiency))

    return {
        "user_id": user_id,
        "bed_time": bed_time.isoformat(),
        "sleep_onset": sleep_onset.isoformat(),
        "wake_time": wake_time.isoformat(),
        "out_of_bed_time": None,
        "total_sleep_minutes": total_sleep_minutes,
        "time_in_bed_minutes": time_in_bed_minutes,
        "sleep_efficiency": sleep_efficiency,
        "waso_minutes": waso_minutes,
        "awakenings_count": awakenings_count,
        "source": "auto",
        "is_edited": False,
        "classifier": classifier.name,
    }


def compute_metrics_from_times(
    bed_time: datetime,
    sleep_onset: datetime,
    wake_time: datetime,
    waso_minutes: int = 0,
    awakenings_count: int = 0,
    out_of_bed_time: Optional[datetime] = None,
) -> dict:
    """手動補登/修正用：使用者直接給時間點，純算術算出衍生指標（規格 §4 manual）。

    不碰判睡演算法（使用者已直接指定 onset/wake），只做確定性計算。
    """
    end = out_of_bed_time or wake_time
    time_in_bed_minutes = max(0, int(round((end - bed_time).total_seconds() / 60)))
    asleep_span = max(0, int(round((wake_time - sleep_onset).total_seconds() / 60)))
    total_sleep_minutes = max(0, asleep_span - max(0, waso_minutes))
    sleep_efficiency = round(total_sleep_minutes / time_in_bed_minutes, 4) if time_in_bed_minutes else 0.0
    sleep_efficiency = max(0.0, min(1.0, sleep_efficiency))
    return {
        "total_sleep_minutes": total_sleep_minutes,
        "time_in_bed_minutes": time_in_bed_minutes,
        "sleep_efficiency": sleep_efficiency,
        "waso_minutes": max(0, waso_minutes),
        "awakenings_count": max(0, awakenings_count),
    }

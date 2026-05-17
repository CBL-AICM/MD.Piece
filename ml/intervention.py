"""MD.Piece App intervention model (counterfactual / what-if simulation).

每位虛擬患者跑兩次：
  - Control arm: 沒用 App（intervention=None）
  - Treatment arm: 用 MD.Piece App（intervention=AppIntervention(...)）

App 介入機制（基於系統實際功能）：
  1. 智慧提醒 → 降低 daily_miss_prob（透過 adherence_multiplier）
  2. AI 早期預警 → 接近 flare threshold 時減弱 trigger 強度
  3. 行為可避免觸發警示 → 減少可避免類 trigger 的 prob_per_day
  4. 衛教 + 醫病共決 → 提升 trust_in_medicine、placebo amplification
  5. 不是所有人都會「真的用」→ engagement 由 health literacy + 年齡決定
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from md_piece.social_profile import FullPersonProfile


# ============================================================================
# Trigger / life-event 行為可避免性分類
# ============================================================================
# 這些 trigger 是「使用者行為可調整 + App 可發提醒」的：
#   抽菸、飲酒、飲食、運動過度、姿勢、環境暴露、睡眠/壓力
AVOIDABLE_TRIGGERS: frozenset[str] = frozenset({
    # 飲食/物質
    "alcohol", "alcohol_binge", "purine", "purine_meal",
    "dietary_indiscretion", "nsaid_use", "food_allergen", "trigger_food",
    "smoking", "smoke_exposure",
    # 物理過度
    "physical_overuse", "overuse", "prolonged_sitting", "physical_strain",
    "tight_clothing", "trauma_minor", "injury_minor", "oral_trauma",
    "trauma_koebner",
    # 環境暴露（App 推播提醒避免）
    "heat_exposure", "cold_winter", "cold_weather", "cold_stress",
    "cold", "heat", "uv_exposure", "uv_sun",
    "dry_environment", "dry_air",
    # 睡眠 / 心理壓力（App 可以做正念引導、睡眠衛教）
    "poor_sleep", "stress", "emotional_stress", "stress_major",
    "emotional_stress_major",
    # 脫水（提醒喝水）
    "dehydration",
    # 旅行污染（App 可預警）
    "travel_pollution",
})


# 不可避免（不論用不用 App 都會發生）：感染、生理週期、急性疾病、手術、社會事件
UNAVOIDABLE_TRIGGERS: frozenset[str] = frozenset({
    "viral_infection", "infection", "gi_infection", "viral_uri",
    "acute_exacerbation",
    "menstruation", "pregnancy", "postpartum", "menopause",
    "surgery", "bereavement", "job_loss",
    "seasonal_change", "imaging_finding", "hospitalization",
    "cancer_screening_positive",
    "medication_change", "skin_flare",
})


@dataclass
class AppIntervention:
    """MD.Piece App 介入效果參數。

    全部都是「相對於對照組（無 App）」的乘數或加法。
    """
    # ─── 1. 智慧提醒：直接降低 adherence_multiplier
    # 因為 adherence_multiplier ↓ → daily_miss_prob ↓ → 漏藥 ↓
    adherence_boost: float = 0.55
    """對 social_profile.adherence_multiplier 的乘數。0.55 = 漏藥機率變成原本 55%。"""

    # ─── 2. 行為可避免觸發降低
    avoidable_trigger_reduction: float = 0.55
    """AVOIDABLE_TRIGGERS 中每個 trigger 的 prob_per_day amplification 乘以此值。"""

    # ─── 3. AI 早期預警
    early_warning_threshold_ratio: float = 0.85
    """當 activity > flare_threshold × ratio 時，啟動預警模式。"""
    early_warning_trigger_dampening: float = 0.5
    """預警模式下，新 trigger 的 magnitude 衰減此倍率（患者主動減少行為觸發）。"""

    # ─── 4. 衛教 + 醫病共決 → 提升 placebo（信任治療）
    placebo_boost: float = 1.20

    # ─── 5. Engagement model（不是所有人都會持續用 App）
    base_engagement: float = 0.80
    """基準 engagement，會再依社經/人格調整。"""

    # ─── 6. 治療可近性（衛教讓患者願意接受更貴/複雜療法）
    treatment_access_boost: float = 1.15
    """提升難取得療法的 access multiplier 上限。"""


# ============================================================================
# Engagement model: 多少 % 的介入效應「真的傳到」患者身上
# ============================================================================

def compute_engagement(
    profile: FullPersonProfile,
    age: int,
    base: float = 0.80,
) -> float:
    """根據社經/人格估計 App engagement 率（0~1）。

    Engagement 反映：患者真的會用 App、看通知、跟著建議調整行為的比例。
    高健康識讀、高盡責性、有家人代理（老年） → engagement↑
    低識讀、極高齡獨居、低信任 → engagement↓
    """
    e = base
    hb = profile.health_behavior
    p = profile.personality
    s = profile.social

    if hb.health_literacy == "高":
        e *= 1.15
    elif hb.health_literacy == "低":
        e *= 0.65

    e *= (0.7 + p.conscientiousness * 0.6)
    e *= (0.7 + hb.trust_in_medicine * 0.6)

    # 老年獨居：自己用 App 困難，但 App 有家屬模式可救回來
    if age >= 70:
        if s.living_arrangement == "alone" and s.family_support == "低":
            e *= 0.50
        elif s.family_support == "高":
            e *= 1.10

    return float(max(0.0, min(1.0, e)))


# ============================================================================
# 把介入效果「注入」到 social_profile（不破壞原物件，回傳新副本）
# ============================================================================

def apply_intervention(
    profile: FullPersonProfile,
    age: int,
    intervention: AppIntervention,
) -> tuple[FullPersonProfile, float]:
    """把 App 介入效果套到一份 social profile 上。

    回傳：(modified_profile, engagement)
    """
    new = deepcopy(profile)
    eng = compute_engagement(new, age, base=intervention.base_engagement)

    # 1. Adherence boost（attenuated by engagement）
    #    new_mult = old_mult × (1 - eng) + (old_mult × boost) × eng
    new.adherence_multiplier = (
        new.adherence_multiplier * (1.0 - eng)
        + new.adherence_multiplier * intervention.adherence_boost * eng
    )

    # 2. 行為可避免 triggers：降低 prob amplification
    #    對於 profile 中已被放大的 trigger（trigger_amplification），App 把它拉回來
    #    對於沒在 amp 中、但屬於 AVOIDABLE 的 trigger，App 在每日採樣時會減低（見 patient.py 那層）
    amp = dict(new.trigger_amplification)
    for tid in AVOIDABLE_TRIGGERS:
        old = amp.get(tid, 1.0)
        reduction = intervention.avoidable_trigger_reduction
        new_amp = old * (1.0 - eng) + old * reduction * eng
        amp[tid] = new_amp
    new.trigger_amplification = amp

    # 3. 衛教 → 信任治療 → placebo amplification
    delta = (intervention.placebo_boost - 1.0) * eng
    new.placebo_amplification = float(min(2.0, new.placebo_amplification * (1.0 + delta)))

    # 4. Treatment access boost：難取得療法稍微容易些
    delta_acc = (intervention.treatment_access_boost - 1.0) * eng
    new_access = dict(new.treatment_access_multiplier)
    for k in list(new_access.keys()):
        new_access[k] = min(1.0, new_access[k] * (1.0 + delta_acc))
    new.treatment_access_multiplier = new_access

    # 5. mental health 邊際提升（衛教 + 同儕支持降低憂鬱 / 焦慮）
    #    這直接影響 subjective amplification（透過 _compute_modifiers 的公式）
    #    這裡不重算公式，直接微調 subjective_amplification
    sub_reduction = 0.10 * eng        # 10% 主觀疼痛降低（最大值）
    new.subjective_amplification = max(
        0.5, new.subjective_amplification * (1.0 - sub_reduction)
    )

    return new, eng


# ============================================================================
# 早期預警 trigger dampening — 在 patient.py 整合迴圈中呼叫
# ============================================================================

def early_warning_active(
    activity: float, flare_threshold: float,
    intervention: AppIntervention,
) -> bool:
    """是否進入早期預警狀態（activity 接近 flare 閾值）。"""
    return activity > flare_threshold * intervention.early_warning_threshold_ratio


def dampen_trigger_magnitude(
    triggers: list[tuple[str, float, float]],
    intervention: AppIntervention,
    engagement: float,
) -> list[tuple[str, float, float]]:
    """在早期預警狀態下，新發生的可避免 trigger 強度被衰減。

    患者收到「即將 flare」警報後主動降低暴露（吃清淡、休息、避免運動）。
    """
    out = []
    base_dampen = intervention.early_warning_trigger_dampening
    # 效應 = 1.0 - (1 - dampen) * engagement
    # 例：dampen=0.5, eng=1.0 → 強度 ×0.5；eng=0 → 強度 ×1.0
    multiplier = 1.0 - (1.0 - base_dampen) * engagement
    for (tid, dur, mag) in triggers:
        if tid in AVOIDABLE_TRIGGERS:
            out.append((tid, dur, mag * multiplier))
        else:
            out.append((tid, dur, mag))
    return out

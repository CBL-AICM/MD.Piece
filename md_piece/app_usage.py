"""MD.Piece App 使用模擬 — 把虛擬患者變成「真的會用 App 的人」。

給定每位患者的疾病軌跡(activity/flare) + 社經/人格 profile，本模組模擬
他們註冊 MD.Piece 後 12 個月的真實使用行為：

  1. 註冊傾向(registration propensity) — 不是每個人都會註冊。
  2. 使用者原型(engagement archetype) — 重度/穩定/反應型/隨意/早退/幽靈。
  3. 留存曲線(retention) — 隨時間流失，符合數位健康的「流失定律」。
     Reference (PubMed): Eysenbach G. The law of attrition. J Med Internet Res
     2005;7(1):e11. doi:10.2196/jmir.7.1.e11 (見 disease_evidence.ATTRITION_REF)
  4. 逐功能記錄 — 哪些功能會用、每天記不記、會不會忘。
  5. 缺漏情境 — 忘記吃藥/忘記紀錄、整段沒在用、註冊了卻幾乎不用(幽靈)。

設計原則(對應 CLAUDE.md 規則 5)：使用模型只負責「人會怎麼用 App」這種
主觀行為的隨機抽樣；確定性的對應(例如女性才有月經紀錄)一律寫死。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from md_piece.social_profile import FullPersonProfile


# ============================================================================
# MD.Piece 功能清單（對應 backend/routers/*）
# ============================================================================
# daily   : 每日型功能，活躍日有機率記錄
# episodic: 回診型功能，繞著回診日產生（labs/報告/回診）
# setup   : 一次性設定型（提醒），多在前期設定

@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    kind: str               # daily / episodic / setup
    base_adoption: float    # 註冊者「曾經用過」此功能的基準機率
    daily_rate: float       # daily 型：活躍日記錄機率（episodic/setup 忽略）
    activity_driven: bool   # 症狀高時記錄機率上升


FEATURES: list[Feature] = [
    Feature("symptoms",    "症狀紀錄",   "daily",    0.92, 0.55, True),
    Feature("medications", "用藥紀錄",   "daily",    0.80, 0.65, False),
    Feature("emotions",    "情緒追蹤",   "daily",    0.55, 0.30, True),
    Feature("diet",        "飲食/拍照",  "daily",    0.45, 0.35, False),
    Feature("vitals",      "生理量測",   "daily",    0.50, 0.25, False),
    Feature("sleep",       "睡眠紀錄",   "daily",    0.40, 0.30, False),
    Feature("menstrual",   "月經週期",   "daily",    0.50, 0.18, False),
    Feature("memos",       "健康memo",   "daily",    0.35, 0.15, False),
    Feature("education",   "衛教閱讀",   "daily",    0.60, 0.20, False),
    Feature("labs",        "檢驗上傳",   "episodic", 0.45, 0.0,  False),
    Feature("follow_ups",  "回診追蹤",   "episodic", 0.55, 0.0,  False),
    Feature("reports",     "就診前報告", "episodic", 0.40, 0.0,  False),
    Feature("reminders",   "智慧提醒",   "setup",    0.65, 0.0,  False),
]
FEATURE_KEYS = [f.key for f in FEATURES]


# ============================================================================
# 使用者原型 + 留存參數（流失定律：多數人會在前幾週流失）
# ============================================================================
# share        : 在「會註冊者」中的目標占比
# base         : 平均每日開 App 的基準機率
# floor        : 留存曲線長期底線（穩定核心使用者的殘留率）
# tau          : 指數衰減時間常數（天），越大越不流失
# churn        : (lo, hi) 之間隨機一個「徹底不用」日；None = 不硬性流失
# n_feat       : 功能採用度乘數（重度使用者採用更多功能）
# reactive_gain: 症狀/flare 日提升開 App 機率的倍率

@dataclass(frozen=True)
class Archetype:
    name: str
    share: float
    base: float
    floor: float
    tau: float
    churn: tuple[int, int] | None
    n_feat: float
    reactive_gain: float


# floor 校準目標：12 個月留存約 30–40%（符合自助型數位健康 app 的流失定律）。
# 只有 power_user 與部分 steady 有明顯長期殘留率，其餘長尾逐步趨近於零。
ARCHETYPES: list[Archetype] = [
    Archetype("power_user",    0.10, 0.82, 0.42, 400.0, None,      1.30, 0.6),
    Archetype("steady",        0.18, 0.50, 0.10, 150.0, None,      1.10, 0.7),
    Archetype("reactive",      0.22, 0.22, 0.04, 300.0, None,      0.85, 2.5),
    Archetype("casual",        0.20, 0.30, 0.00,  70.0, None,      0.80, 0.8),
    Archetype("early_churner", 0.22, 0.45, 0.00,  18.0, (14, 45),  0.70, 0.5),
    Archetype("ghost",         0.08, 0.15, 0.00,   6.0, (1, 7),    0.30, 0.2),
]
ARCHETYPE_BY_NAME = {a.name: a for a in ARCHETYPES}


# ============================================================================
# 註冊傾向
# ============================================================================

def registration_propensity(
    profile: FullPersonProfile, age: int, disease_id: str = "",
) -> float:
    """估計一位患者會註冊並嘗試使用 MD.Piece 的傾向分數(~0..1)。

    驅動因子：智慧型手機可近性(年齡/收入/都市化)、健康識讀、盡責性、
    對醫療的信任、開放性。高齡可由家屬代理救回一部分。
    """
    p = profile.personality
    hb = profile.health_behavior
    se = profile.socioeconomic
    s = profile.social

    score = 0.45
    score += (p.conscientiousness - 0.5) * 0.30
    score += (p.openness - 0.5) * 0.15
    score += (hb.trust_in_medicine - 0.5) * 0.20

    if hb.health_literacy == "高":
        score += 0.15
    elif hb.health_literacy == "低":
        score -= 0.18

    if se.education in ("大專", "研究所以上"):
        score += 0.08
    elif se.education == "國中以下":
        score -= 0.10

    if se.income_tier in ("低收", "中下"):
        score -= 0.08        # 智慧型手機/網路可近性較低
    if se.urban_rural == "鄉村":
        score -= 0.05

    # 年齡：智慧型手機採用隨年齡下降，但中壯年最積極追蹤健康
    if age < 30:
        score += 0.05
    elif age >= 70:
        score -= 0.22
        if s.family_support == "高":
            score += 0.14   # 家屬模式代理操作救回
    elif age >= 60:
        score -= 0.08

    return float(np.clip(score, 0.02, 0.98))


def select_registered(
    propensities: dict[str, float], n_register: int, seed: int,
) -> set[str]:
    """從所有患者中選出剛好 n_register 位註冊者。

    依傾向分數排序，但加入帶種子的抖動，使得高傾向者較常被選中、
    低傾向者偶爾也會註冊（保留真實世界的異質性），結果可重現。
    """
    rng = np.random.default_rng(seed)
    ranked = []
    for pid, prop in propensities.items():
        jitter = float(rng.normal(0.0, 0.12))
        ranked.append((prop + jitter, pid))
    ranked.sort(reverse=True)
    return {pid for _, pid in ranked[:n_register]}


# ============================================================================
# 使用者原型指派
# ============================================================================

def assign_archetype(
    profile: FullPersonProfile, age: int, rng: np.random.Generator,
) -> str:
    """依 profile 把患者歸到一個使用者原型（帶機率，非寫死）。

    高盡責+高識讀 → 偏 power/steady；低識讀/低信任 → 偏 casual/churner/ghost；
    高神經質/憂鬱 → 偏 reactive(症狀焦慮型監測)；高齡獨居低支持 → 偏 churner/ghost。
    """
    p = profile.personality
    hb = profile.health_behavior
    mh = profile.mental_health
    s = profile.social

    w = {a.name: a.share for a in ARCHETYPES}

    # 盡責 + 識讀 → 重度/穩定
    diligence = p.conscientiousness + (0.3 if hb.health_literacy == "高" else
                                       -0.3 if hb.health_literacy == "低" else 0.0)
    if diligence > 0.7:
        w["power_user"] *= 2.0
        w["steady"] *= 1.5
        w["ghost"] *= 0.4
        w["early_churner"] *= 0.6
    elif diligence < 0.3:
        w["casual"] *= 1.4
        w["early_churner"] *= 1.5
        w["ghost"] *= 1.8
        w["power_user"] *= 0.3

    # 神經質/憂鬱/焦慮 → 反應型（症狀一上來就猛記）
    if p.neuroticism > 0.6 or mh.phq9_score >= 10 or mh.gad7_score >= 10:
        w["reactive"] *= 2.0

    # 低信任 → 早退/幽靈
    if hb.trust_in_medicine < 0.4:
        w["early_churner"] *= 1.4
        w["ghost"] *= 1.5

    # 高齡獨居低支持 → 難持續
    if age >= 70 and s.living_arrangement == "alone" and s.family_support == "低":
        w["ghost"] *= 2.0
        w["early_churner"] *= 1.5
        w["power_user"] *= 0.2
    # 高齡但家屬支持高 → 代理操作，偏穩定
    elif age >= 70 and s.family_support == "高":
        w["steady"] *= 1.5
        w["ghost"] *= 0.5

    names = list(w.keys())
    weights = np.array([w[n] for n in names], dtype=float)
    weights = weights / weights.sum()
    return str(rng.choice(names, p=weights))


# ============================================================================
# 功能採用度（哪些功能「這個人會用」）+ 關聯性
# ============================================================================

def _feature_relevance(
    feat: Feature, profile: FullPersonProfile, age: int, sex: str,
    comorbidities: list[str],
) -> float:
    """回傳 0 表示完全不適用（如男性的月經紀錄），其餘為採用/頻率乘數。"""
    hb = profile.health_behavior
    mh = profile.mental_health
    b = profile.behavioral

    if feat.key == "menstrual":
        return 1.0 if (sex == "F" and 13 <= age <= 52) else 0.0
    if feat.key == "emotions":
        return 1.6 if (mh.phq9_score >= 10 or mh.gad7_score >= 10) else 1.0
    if feat.key == "vitals":
        r = 1.0
        if age >= 60:
            r *= 1.5
        if "cardiovascular" in comorbidities:
            r *= 1.6
        return r
    if feat.key == "sleep":
        return 1.7 if (b.sleep_quality == "差" or b.sleep_hours_avg < 6.0) else 0.9
    if feat.key == "diet":
        return 1.4 if age < 45 else 0.8
    if feat.key == "education":
        return 1.5 if hb.health_literacy == "高" else (0.6 if hb.health_literacy == "低" else 1.0)
    if feat.key == "memos":
        return 0.6 + profile.personality.openness * 0.8
    if feat.key == "reminders":
        return 1.4 if profile.personality.conscientiousness > 0.6 else 0.8
    if feat.key == "follow_ups" or feat.key == "reports":
        return 1.3 if hb.appointment_adherence > 0.7 else 0.8
    return 1.0


def _adopted_features(
    arche: Archetype, profile: FullPersonProfile, age: int, sex: str,
    comorbidities: list[str], has_treatments: bool, rng: np.random.Generator,
) -> set[str]:
    adopted = set()
    for feat in FEATURES:
        rel = _feature_relevance(feat, profile, age, sex, comorbidities)
        if rel <= 0.0:
            continue
        if feat.key == "medications" and not has_treatments:
            continue
        prob = float(np.clip(feat.base_adoption * arche.n_feat * (0.6 + 0.4 * rel),
                             0.0, 0.98))
        if rng.random() < prob:
            adopted.add(feat.key)
    # 症狀紀錄是核心：只要不是幽靈，幾乎一定採用
    if arche.name != "ghost" and rng.random() < 0.9:
        adopted.add("symptoms")
    return adopted


# ============================================================================
# 留存曲線
# ============================================================================

def retention_multiplier(arche: Archetype, day_since_join: int) -> float:
    """回傳第 d 天的留存乘數(0..~1.2)，含前期新鮮感、指數衰減。"""
    d = day_since_join
    decay = arche.floor + (1.0 - arche.floor) * np.exp(-d / arche.tau)
    # 前 14 天新鮮感加成（線性退去）
    novelty = 1.0 + 0.20 * max(0.0, (14 - d) / 14.0)
    return float(decay * novelty)


# ============================================================================
# 使用紀錄輸出
# ============================================================================

@dataclass
class UsageRecord:
    patient_id: str
    disease_id: str
    age: int
    sex: str
    region: str
    region_macro: str
    income_tier: str
    education: str
    urban_rural: str
    family_support: str
    living_arrangement: str
    comorbidity_count: int
    registered: bool
    # --- 以下僅註冊者有意義 ---
    archetype: str = ""
    join_day: int = -1
    observation_days: int = 0
    active_days: int = 0
    total_records: int = 0
    features: dict = field(default_factory=dict)     # key -> {adopted,n_records,last_day}
    med_log_adherence: float = 0.0                   # 該記藥日中實際有記的比例
    data_completeness: float = 0.0                   # active_days / observation_days
    months_active: int = 0
    retained: dict = field(default_factory=dict)     # D1/D7/D30/D90/D180/D365 -> bool
    churn_day: int = -1                              # 最後一個活躍日（相對 join）
    engaged_at_12m: bool = False
    non_registration_reason: str = ""

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def _non_registration_reason(profile: FullPersonProfile, age: int) -> str:
    hb = profile.health_behavior
    se = profile.socioeconomic
    s = profile.social
    if age >= 70 and s.family_support != "高":
        return "高齡且缺家屬協助"
    if hb.health_literacy == "低":
        return "健康識讀低"
    if hb.trust_in_medicine < 0.4:
        return "對醫療/數位工具信任低"
    if se.income_tier in ("低收", "中下") and se.urban_rural == "鄉村":
        return "鄉村且數位可近性低"
    if profile.personality.conscientiousness < 0.35:
        return "自我管理動機低"
    return "未被觸及/暫無使用動機"


def simulate_patient_usage(
    *,
    patient_id: str,
    disease_id: str,
    age: int,
    sex: str,
    profile: FullPersonProfile,
    comorbidities: list[str],
    has_treatments: bool,
    activity: np.ndarray,
    in_flare: np.ndarray,
    registered: bool,
    join_day: int,
    sim_days: int,
    seed: int,
) -> UsageRecord:
    """模擬單一患者 12 個月(sim_days)的 MD.Piece 使用行為。"""
    se = profile.socioeconomic
    rec = UsageRecord(
        patient_id=patient_id, disease_id=disease_id, age=age, sex=sex,
        region=se.region, region_macro=se.region_macro,
        income_tier=se.income_tier, education=se.education,
        urban_rural=se.urban_rural,
        family_support=profile.social.family_support,
        living_arrangement=profile.social.living_arrangement,
        comorbidity_count=len(comorbidities),
        registered=registered,
    )
    if not registered:
        rec.non_registration_reason = _non_registration_reason(profile, age)
        return rec

    rng = np.random.default_rng(seed)
    arche = ARCHETYPE_BY_NAME[assign_archetype(profile, age, rng)]
    rec.archetype = arche.name
    rec.join_day = join_day

    obs_days = max(1, sim_days - join_day)
    rec.observation_days = obs_days

    # 硬性流失日（相對 join）
    churn_at = None
    if arche.churn is not None:
        lo, hi = arche.churn
        churn_at = int(rng.integers(lo, hi + 1))

    # 症狀日：flare 或活動度高於個人均值 → 較想開 App
    mean_act = float(np.mean(activity[join_day:])) if obs_days > 0 else 0.0
    symptomatic = (in_flare.astype(bool)) | (activity > mean_act * 1.2)

    adopted = _adopted_features(arche, profile, age, sex, comorbidities,
                                has_treatments, rng)
    feat_state = {k: {"adopted": (k in adopted), "n_records": 0, "last_day": -1}
                  for k in FEATURE_KEYS}

    # 回診排程：疾病活動度高→回診較密；可近性低→可能漏診
    visit_interval = 60 if mean_act >= 4.0 else 90
    next_visit = join_day + visit_interval
    appt_adh = profile.health_behavior.appointment_adherence

    # 用藥記錄受既有 adherence_multiplier 影響（高=依從差=常忘記/沒記）。
    # 藥每天都該記；med_log_adherence 以「整段觀察期」為分母，
    # 同時涵蓋『沒開 App』與『開了卻忘記記』兩種缺漏 → 反映真實的低完成率。
    adh_mult = profile.adherence_multiplier
    med_log_base = float(np.clip(0.85 / (0.5 + 0.5 * adh_mult), 0.1, 0.95))
    med_due_days = obs_days if feat_state["medications"]["adopted"] else 0
    med_logged_days = 0

    active_days = 0
    active_month = set()
    active_rel_days: list[int] = []      # 活躍日（相對 join），供留存里程碑判斷
    last_active = -1

    for d in range(join_day, sim_days):
        ds = d - join_day
        if churn_at is not None and ds > churn_at:
            # 已流失：僅在嚴重 flare 時偶爾回來看一下
            p_active = 0.04 if symptomatic[d] else 0.005
        else:
            ret = retention_multiplier(arche, ds)
            p_active = arche.base * ret
            if symptomatic[d]:
                p_active *= (1.0 + arche.reactive_gain)
        p_active = min(0.98, p_active)

        is_active = rng.random() < p_active

        # 回診日（不一定活躍才回診，但會依 appointment adherence 出席）
        if d >= next_visit:
            if rng.random() < appt_adh:
                for fk in ("follow_ups", "reports", "labs"):
                    if feat_state[fk]["adopted"]:
                        feat_state[fk]["n_records"] += 1
                        feat_state[fk]["last_day"] = d
                is_active = True       # 回診當天通常也會開 App
            next_visit += visit_interval

        if not is_active:
            continue

        active_days += 1
        active_month.add(ds // 30)
        active_rel_days.append(ds)
        last_active = ds

        # 提醒：多在前 30 天設定一次
        if feat_state["reminders"]["adopted"] and ds < 30 and feat_state["reminders"]["n_records"] == 0:
            if rng.random() < 0.5:
                feat_state["reminders"]["n_records"] += 1
                feat_state["reminders"]["last_day"] = d

        # 每日型功能
        for feat in FEATURES:
            if feat.kind != "daily" or not feat_state[feat.key]["adopted"]:
                continue
            if feat.key == "medications":
                if rng.random() < med_log_base:        # 開了 App 仍可能忘記記錄
                    feat_state[feat.key]["n_records"] += 1
                    feat_state[feat.key]["last_day"] = d
                    med_logged_days += 1
                continue
            rate = feat.daily_rate
            if feat.activity_driven and symptomatic[d]:
                rate = min(0.95, rate * 1.6)
            if rng.random() < rate:
                feat_state[feat.key]["n_records"] += 1
                feat_state[feat.key]["last_day"] = d

    # ---- 彙整 ----
    rec.features = feat_state
    rec.active_days = active_days
    rec.total_records = int(sum(v["n_records"] for v in feat_state.values()))
    rec.med_log_adherence = float(med_logged_days / med_due_days) if med_due_days else 0.0
    rec.data_completeness = float(active_days / obs_days)
    rec.months_active = len(active_month)
    rec.churn_day = last_active

    # 留存里程碑：第 N 天前後 30 天視窗內「實質活躍」(≥2 個活躍日)。
    # 用 ≥2 而非 ≥1，避免半年後因 flare 偶爾開一次 App 就被當成仍留存——
    # 那種一次性回訪不是真的還在用。早期(D7)視窗短，用 ≥1。
    active_set = set(active_rel_days)

    def win_count(lo: int, hi: int) -> int:
        return sum(1 for x in active_set if lo <= x <= hi)

    last30_lo = max(0, obs_days - 30)
    rec.retained = {
        "D1": (0 in active_set) or (1 in active_set),
        "D7": win_count(0, 7) >= 1,
        "D30": (win_count(1, 30) >= 2) if obs_days >= 20 else False,
        "D90": (win_count(61, 90) >= 2) if obs_days >= 90 else False,
        "D180": (win_count(151, 180) >= 2) if obs_days >= 180 else False,
        "D365": (win_count(last30_lo, obs_days) >= 2),
    }
    rec.engaged_at_12m = rec.retained["D365"]
    return rec

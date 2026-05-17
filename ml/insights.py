"""Rule-based insight generator — turns model predictions + patient state into
natural-language 心得 (commentary) shown in the PWA.

Why rule-based?
  - Deterministic and reproducible (no LLM API calls).
  - Explainable — every sentence comes from an inspectable rule.
  - Cheap — runs offline alongside the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


SEX_NAME = {"F": "女性", "M": "男性"}
DISEASE_NAME = {
    "rheumatoid_arthritis": "類風濕關節炎",
    "asthma": "氣喘",
    "systemic_sclerosis": "全身性硬化症",
}
RESPONDER_NAME = {
    "typical": "典型反應者",
    "super": "超級反應者",
    "partial": "部分反應者",
    "non_responder": "無反應者",
}


@dataclass
class PatientInsight:
    """Bundle of model output + commentary for one patient."""
    patient_id: str
    predictions: list[dict]                   # [{day, activity_pred, flare_prob}]
    mae: float
    flare_recall: float | None
    flare_precision: float | None
    insight_zh: str
    insight_lines: list[str]


def _flare_metrics(flare_true: np.ndarray, flare_prob: np.ndarray) -> tuple[float | None, float | None]:
    """Recall + precision at 0.5 threshold; returns None if class missing."""
    pred = (flare_prob >= 0.5).astype(int)
    n_true_pos = int(((flare_true == 1) & (pred == 1)).sum())
    n_pos = int((flare_true == 1).sum())
    n_pred_pos = int((pred == 1).sum())
    recall = n_true_pos / n_pos if n_pos > 0 else None
    precision = n_true_pos / n_pred_pos if n_pred_pos > 0 else None
    return recall, precision


def _life_event_near_flare(patient, flare_days_truth: list[int]) -> list[tuple[str, int]]:
    """Find life events whose duration overlaps a truth flare day (±5 days)."""
    matches = []
    for e in patient.life_events:
        win_lo = e.onset_day - 5
        win_hi = e.onset_day + e.duration_days + 5
        for d in flare_days_truth:
            if win_lo <= d <= win_hi:
                matches.append((e.id, int(e.onset_day)))
                break
    return matches


def generate_insight(
    patient,
    predict_result: dict,
) -> PatientInsight:
    """Build a 心得 from one Patient + the dict returned by predict_from_patient.

    predict_result keys: day, activity_pred, activity_true, flare_prob, flare_true.
    """
    days = predict_result["day"]
    act_pred = predict_result["activity_pred"]
    act_true = predict_result["activity_true"]
    flare_prob = predict_result["flare_prob"]
    flare_true = predict_result["flare_true"]

    mae = float(np.mean(np.abs(act_pred - act_true)))
    recall, precision = _flare_metrics(flare_true, flare_prob)

    predictions = [
        {
            "day": int(d),
            "activity_pred": round(float(ap), 3),
            "activity_true": round(float(at), 3),
            "flare_prob": round(float(fp), 3),
            "flare_true": int(ft),
        }
        for d, ap, at, fp, ft in zip(days, act_pred, act_true, flare_prob, flare_true)
    ]

    lines: list[str] = []

    # 1) patient profile
    sex_zh = SEX_NAME.get(patient.sex, patient.sex)
    disease_zh = DISEASE_NAME.get(patient.disease_id, patient.disease_id)
    lines.append(
        f"📋 患者畫像：{patient.age} 歲 {sex_zh}，診斷為 {disease_zh}"
        f"（{patient.subtype} 亞型）"
        f"，被分類為 {RESPONDER_NAME.get(patient.responder_class, patient.responder_class)}。"
    )

    # 2) age / elderly
    if patient.age_profile and patient.age_profile.is_elderly:
        comorb = ", ".join(patient.age_profile.elderly_comorbidities) or "無自動加註的共病"
        lines.append(
            f"👴 老年機制觸發：CRP 反應遲鈍至 {patient.age_profile.crp_dampening:.1f}×、"
            f"治療反應修正 {patient.age_profile.treatment_response_modifier:.1f}×、"
            f"伴隨用藥 {patient.age_profile.polypharmacy_count} 項，"
            f"自動疊加共病：{comorb}。"
        )

    # 3) treatments + adherence
    if patient.treatments:
        tx_lines = []
        for tx in patient.treatments:
            tx_lines.append(f"{tx['id']}（強度 {tx['effect_magnitude']:.2f}）")
        skips_total = sum(len(s.daily_skips) for s in patient.adherence_states.values())
        disc = [s for s in patient.adherence_states.values() if s.discontinuation_day is not None]
        adh_note = ""
        if disc:
            disc_day = int(min(s.discontinuation_day for s in disc))
            adh_note = f"，並在第 {disc_day} 天停藥"
        elif skips_total > 0:
            adh_note = f"，共漏吃 {skips_total} 天"
        lines.append(f"💊 治療：{', '.join(tx_lines)}{adh_note}。")
    else:
        lines.append("💊 治療：未接受任何處方治療。")

    # 4) life events
    if patient.life_events:
        ev_names = [e.id for e in patient.life_events[:5]]
        more = "" if len(patient.life_events) <= 5 else f" 等共 {len(patient.life_events)} 件"
        lines.append(f"🎲 生活事件：{', '.join(ev_names)}{more}。")

    # 5) long-tail event
    if patient.long_tail_event is not None:
        onset, dur, mag = patient.long_tail_event
        lines.append(
            f"⚠️ 此患者出現罕見「long-tail」事件："
            f"第 {int(onset)} 天起 {int(dur)} 天內疾病活動度暴增 +{mag:.1f}。"
        )

    # 6) model performance on this patient
    cohort_avg_mae = 0.26  # from v2 model card
    quality_word = (
        "顯著優於" if mae < cohort_avg_mae * 0.7
        else "接近" if mae < cohort_avg_mae * 1.3
        else "遜於"
    )
    lines.append(
        f"🤖 AI 預測表現：活動度 MAE = {mae:.2f}，{quality_word} cohort 平均（0.26）。"
    )

    # 7) flare prediction
    n_truth_flare = int(flare_true.sum())
    n_pred_flare = int((flare_prob >= 0.5).sum())
    if n_truth_flare == 0 and n_pred_flare == 0:
        lines.append("🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。")
    elif n_truth_flare > 0 and n_pred_flare > 0:
        r_str = f"{recall*100:.0f}%" if recall is not None else "—"
        p_str = f"{precision*100:.0f}%" if precision is not None else "—"
        lines.append(
            f"🔍 Flare 預測：實際 {n_truth_flare} 個 flare 窗口，"
            f"模型預警 {n_pred_flare} 個，召回率 {r_str}、準確率 {p_str}。"
        )
    elif n_truth_flare > 0 and n_pred_flare == 0:
        lines.append(
            f"🔍 Flare 預測：實際有 {n_truth_flare} 個 flare 但模型未預警 — "
            "可能因為亞型/反應者組合在此 cohort 中較罕見。"
        )
    else:
        lines.append(
            f"🔍 Flare 預測：模型發出 {n_pred_flare} 個誤警，實際未發生 flare — "
            "可能受到夜間活動度高峰或 life event 訊號干擾。"
        )

    # 8) factor attribution near flares
    flare_days_truth = [int(d) for d, ft in zip(days, flare_true) if ft == 1]
    if flare_days_truth:
        matches = _life_event_near_flare(patient, flare_days_truth)
        if matches:
            sample = ", ".join(f"{eid}(d{onset})" for eid, onset in matches[:3])
            lines.append(f"📌 可能觸發因子：實際 flare 附近出現 {sample}。")

    # 9) closing note
    if patient.responder_class == "non_responder":
        lines.append("📝 結論：作為 non-responder，建議考慮替代治療策略。")
    elif patient.responder_class == "super":
        lines.append("📝 結論：超級反應者，當前治療可維持。")
    elif patient.age_profile and patient.age_profile.is_elderly:
        lines.append("📝 結論：老年患者，建議監測共病與藥物交互作用。")
    else:
        lines.append("📝 結論：典型病程，持續追蹤即可。")

    insight_zh = "\n".join(lines)

    return PatientInsight(
        patient_id=patient.patient_id,
        predictions=predictions,
        mae=mae,
        flare_recall=recall,
        flare_precision=precision,
        insight_zh=insight_zh,
        insight_lines=lines,
    )

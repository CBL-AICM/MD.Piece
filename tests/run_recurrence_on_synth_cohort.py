"""把「過去合成過的 3200 位假患者」餵進產品線復發引擎（backend/utils/recurrence.py）跑預測。

資料來源：md_piece 模擬器（sim 分支）以 base_seed=2024 決定性重生的 16 疾病 × 200 患者 × 180 天，
         與當初「過去合成過的」那一批逐一相同（seed 固定 → 完全可重現）。

橋接：模擬器每位患者的逐日時序（activity / in_flare / dose_any_skipped / 觸發因子 / 生物標記）
     → 轉成 recurrence 引擎吃的 Supabase 表列（情緒 / 用藥 / 症狀 / 睡眠 / 飲食 / 就診 / 檢驗）。
     轉接是「同一個底層惡化狀態，多訊號同時變差」的忠實展開，每條對應在下方明列（規則 12：透明）。

驗證設計（這才是重點）：把 as_of 釘在第 165 天，引擎只看前 60 天去預測「未來 14 天復發風險」，
     再拿模擬器真實的第 166–179 天 flare 當 ground truth → 量「產品引擎的風險分數有沒有對到真的復發」
     （band × 實際復發交叉表 + AUROC + 平均風險對比）。

跑法：
    PYTHONPATH=. python tests/run_recurrence_on_synth_cohort.py            # 200/疾病 = 3200
    PYTHONPATH=. python tests/run_recurrence_on_synth_cohort.py 5          # 5/疾病 = 80（煙霧測試）
"""
from __future__ import annotations

import os
import sys
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows cp950 → 繁中/emoji 不亂碼
except Exception:
    pass

from backend.utils import recurrence
from md_piece.disease_loader import list_diseases, load_disease
from md_piece.cohort_generator import generate_cohort

# ── 重現「過去合成過的」那批的參數（取自 ml/config.yaml）──────────────
N_PER = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SIM_DAYS = 180
BASE_SEED = 2024
HORIZON = recurrence.HORIZON_DAYS            # 引擎預測未來 14 天
DAY_AS_OF = SIM_DAYS - 1 - HORIZON           # 165：留 14 天未來當 ground truth
EMIT_FROM = DAY_AS_OF - recurrence.BASELINE_WINDOW - 1   # 只需展開引擎會看的那 ~60 天
NOW = datetime(2026, 6, 8, 9, 0, 0)          # date(DAY_AS_OF) := NOW


def dt(day, hour=9):
    """模擬日 index → 日曆字串；day=DAY_AS_OF 對齊 NOW，越早的 day 越久以前。"""
    d = (NOW - timedelta(days=(DAY_AS_OF - day))).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    return d.strftime("%Y-%m-%d %H:%M:%S")


# ── 記憶體 Supabase 替身（只實作 recurrence.py 用到的查詢子集；每人各一個）──
class _Result:
    def __init__(self, data): self.data = data


class _Query:
    def __init__(self, rows): self._rows, self._f = rows, []
    def select(self, *a, **k): return self
    def eq(self, c, v): self._f.append((c, v)); return self
    def execute(self):
        rows = self._rows
        for c, v in self._f:
            rows = [r for r in rows if r.get(c) == v]
        return _Result(rows)


class MemSB:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return _Query(self.tables.get(name, []))


# ── 16 疾病 → 復發 band + 中文名（band 為臨床分級啟發式，非逐病文獻；已標明）──
ZH = {
    "rheumatoid_arthritis": "類風濕性關節炎", "asthma": "氣喘",
    "systemic_sclerosis": "全身性硬化症", "systemic_lupus_erythematosus": "系統性紅斑性狼瘡",
    "inflammatory_bowel_disease": "發炎性腸道疾病", "multiple_sclerosis": "多發性硬化症",
    "gout": "痛風", "ankylosing_spondylitis": "僵直性脊椎炎",
    "psoriatic_arthritis": "乾癬性關節炎", "sjogren_syndrome": "乾燥症",
    "behcet_disease": "貝賽特氏病", "anca_vasculitis": "ANCA 血管炎",
    "igg4_related_disease": "IgG4 相關疾病", "chronic_urticaria": "慢性蕁麻疹",
    "osteoarthritis": "退化性關節炎", "idiopathic_pulmonary_fibrosis": "特發性肺纖維化",
}
BAND = {
    "rheumatoid_arthritis": "high", "systemic_lupus_erythematosus": "high",
    "systemic_sclerosis": "high", "inflammatory_bowel_disease": "high",
    "multiple_sclerosis": "high", "anca_vasculitis": "high",
    "igg4_related_disease": "high", "behcet_disease": "high",
    "idiopathic_pulmonary_fibrosis": "high",
    "psoriatic_arthritis": "medium", "ankylosing_spondylitis": "medium",
    "sjogren_syndrome": "medium", "gout": "medium", "asthma": "medium",
    "chronic_urticaria": "medium", "osteoarthritis": "low",
}
DRIVERS = [
    {"maps_to": "adherence", "weight": "high", "evidence": "停藥／漏服與復發相關（橋接：dose_any_skipped）。"},
    {"maps_to": "symptoms", "weight": "high", "evidence": "症狀活動度升高常為復發前兆（橋接：活動度／in_flare）。"},
    {"maps_to": "stress", "weight": "medium", "evidence": "壓力／情緒與疾病活動度相關（橋接：活動度→情緒分數）。"},
    {"maps_to": "sleep", "weight": "medium", "evidence": "睡眠惡化與發炎指標相關（橋接：惡化日睡眠變差）。"},
    {"maps_to": "labs", "weight": "medium", "evidence": "檢驗異常與活動度相關（橋接：惡化日異常值）。"},
]


def disease_ref_row(did):
    return {
        "id": did, "name_zh": ZH[did], "name_en": did,
        "aliases": [did, ZH[did]],
        "recurrence_data": {
            "matched": True,
            "recurrence_rate": {
                "band": BAND[did], "range_text": "（模擬世代；band 為疾病分級啟發式）",
                "horizon": "12 個月", "summary": f"{ZH[did]} 復發與用藥順從性、活動度、壓力相關。"},
            "drivers": DRIVERS,
            "watch_signs": ["症狀活動度上升", "新發或加劇的不適"],
            "disclaimer": "band 為疾病分級啟發式，非逐病文獻；個別情況以主治醫師為準。",
        },
        "references_data": [{"pmid": "00000000", "title": f"{did} flare predictors", "year": 2020, "source": "sim"}],
    }


# ── 橋接：一位模擬患者的時序 → 引擎吃的表列 + ground-truth flare ──────────
def adapt(patient, base_act, flare_thr):
    """回傳 (tables, truth)。tables 只展開引擎會看的 ~60 天（as_of 之前）。

    活動度以「疾病別絕對刻度」base_act→flare_thr 轉成主觀訊號（同病所有人共用同一把尺，
    不做 per-patient 正規化）——這樣慢性高活動但穩定的人不會被誤判成『正常』，
    引擎的情緒 level / 睡眠 / 檢驗等『絕對值』因子才讀得到真正的嚴重度（忠實展開）。
    """
    rows = patient.timeseries.to_dict("records")
    rows.sort(key=lambda r: r["day"])
    window = [r for r in rows if EMIT_FROM <= r["day"] <= DAY_AS_OF]
    span = (flare_thr - base_act) or 1.0

    def severity(act):                      # 0 = 基線, 1 = 達發作閾值（可 >1）
        return max(0.0, (act - base_act) / span)

    emo, meds, symp, bed, diet, visits, labs = [], [], [], [], [], [], []
    prev_flare = 0
    lab_phase = DAY_AS_OF % 7
    for r in window:
        day, act, flare = r["day"], r["activity"], int(r["in_flare"])
        sev = severity(act)
        bad = flare or sev >= 0.6
        when = dt(day)
        # 情緒 1(差)~5(好)：嚴重度越高 → 分數越低（基線≈5，達閾值≈1.3；絕對刻度）
        emo.append({"patient_id": patient.patient_id,
                    "score": int(min(5, max(1, round(5 - 3.5 * min(sev, 1.2))))), "created_at": when})
        # 用藥：直接取模擬器的漏服旗標
        meds.append({"patient_id": patient.patient_id, "taken": 0 if r["dose_any_skipped"] else 1, "taken_at": when})
        # 症狀紀錄頻率：壞日才記 → 近期變頻繁＝活動度上升
        if bad:
            symp.append({"patient_id": patient.patient_id, "symptoms": "症狀加劇", "created_at": when})
        # 睡眠：壞日睡不好
        bed.append({"patient_id": patient.patient_id, "sleep": "失眠、睡不好" if bad else "正常", "created_at": when})
        # 飲食：發作日自我管理鬆懈（略過記錄）→ 近期記錄變少
        if not flare:
            diet.append({"patient_id": patient.patient_id, "meal_type": "lunch", "foods": "均衡", "eaten_at": when})
        # 檢驗：每 7 天一次，嚴重日異常
        if day % 7 == lab_phase:
            labs.append({"patient_id": patient.patient_id,
                         "status": "high" if (flare or sev >= 0.75) else "normal", "created_at": when})
        # 就診：flare 起始邊緣 → 一次回診（同時是 trend 的 flare 標記）
        if flare and not prev_flare:
            visits.append({"patient_id": patient.patient_id, "visit_date": when,
                           "diagnosis": f"{ZH[patient.disease_id]}發作", "symptoms": ""})
        prev_flare = flare

    tables = {
        "emotions": emo, "medication_logs": meds, "symptoms_log": symp,
        "bedside_logs": bed, "diet_records": diet, "medical_records": visits,
        "labs": labs, "sleep_sessions": [], "menstrual_cycles": [],
        "patient_profiles": [], "disease_reference": [disease_ref_row(patient.disease_id)],
    }

    # ground truth：未來 14 天（166..179）真的有沒有 flare / 新發作
    future = [r for r in rows if DAY_AS_OF < r["day"] <= DAY_AS_OF + HORIZON]
    at_asof = next((int(r["in_flare"]) for r in window if r["day"] == DAY_AS_OF), 0)
    anyflare = any(int(r["in_flare"]) for r in future)
    onset, prev = False, at_asof
    for r in future:
        f = int(r["in_flare"])
        if f and not prev:
            onset = True
        prev = f
    truth = {"anyflare": anyflare, "onset": onset, "in_flare_at_asof": bool(at_asof)}
    return tables, truth


def auroc(scores, labels):
    """Mann–Whitney AUROC（含 tie 平均秩）；無正或無負樣本回 None。"""
    n = len(scores)
    pos = sum(1 for l in labels if l)
    neg = n - pos
    if pos == 0 or neg == 0:
        return None
    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and scores[order[j]] == scores[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    sum_pos = sum(ranks[i] for i in range(n) if labels[i])
    return (sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)


def run():
    diseases = list_diseases()
    N = len(diseases) * N_PER

    bands = Counter(); trends = Counter(); confidence = Counter()
    top_features = Counter(); cold = 0; bound = 0
    risk_all, lab_any, lab_onset = [], [], []
    band_flare = defaultdict(lambda: [0, 0])     # band → [n, n_anyflare]
    per_disease = defaultdict(lambda: {"n": 0, "anyflare": 0, "onset": 0, "risk": []})
    samples = {}

    print("=" * 72)
    print(f"產品復發引擎 × 過去合成 {N} 位假患者（{len(diseases)}疾病×{N_PER}, seed={BASE_SEED}, "
          f"as_of=第{DAY_AS_OF}天, 預測未來{HORIZON}天）")
    print("=" * 72)
    print(f"重生 + 橋接 + 預測中 …（{len(diseases)} 疾病）")

    for di, did in enumerate(diseases, 1):
        cfg = load_disease(did)
        base_act = float(cfg.baseline["activity"])
        flare_thr = float(cfg.flare["threshold"])
        cohort = generate_cohort(cfg, N_PER, SIM_DAYS, base_seed=BASE_SEED)
        for p in cohort.patients:
            tables, truth = adapt(p, base_act, flare_thr)
            pred = recurrence.predict(MemSB(tables), p.patient_id, as_of=NOW, disease_hint=did)
            pd_ = per_disease[did]
            pd_["n"] += 1
            pd_["anyflare"] += int(truth["anyflare"])
            pd_["onset"] += int(truth["onset"])
            if pred.get("cold_start"):
                cold += 1
                continue
            rp = pred["risk_percent"]
            bands[pred["risk_band"]] += 1
            trends[pred["trend"]] += 1
            confidence[pred["confidence"]] += 1
            if pred["disease"]["bound"]:
                bound += 1
            td = pred.get("top_driver")
            top_features[td["feature"] if td else "（無推升因子）"] += 1
            risk_all.append(rp); pd_["risk"].append(rp)
            lab_any.append(int(truth["anyflare"])); lab_onset.append(int(truth["onset"]))
            band_flare[pred["risk_band"]][0] += 1
            band_flare[pred["risk_band"]][1] += int(truth["anyflare"])
            if truth["anyflare"] and "flare_high" not in samples and pred["risk_band"] == "high":
                samples["flare_high"] = {"pred": pred, "truth": truth}
            if not truth["anyflare"] and "stable_low" not in samples and pred["risk_band"] == "low":
                samples["stable_low"] = {"pred": pred, "truth": truth}
        print(f"  [{di:2d}/{len(diseases)}] {did:32s} band={BAND[did]:<6} "
              f"n={per_disease[did]['n']} anyflare={per_disease[did]['anyflare']}")

    predicted = len(risk_all)

    def pc(c, t): return f"{c} ({c/t*100:.1f}%)" if t else f"{c} (—)"
    def mean(xs): return sum(xs)/len(xs) if xs else 0.0

    print(f"\n世代覆蓋")
    print(f"  總人數 {N} | 可預測 {pc(predicted, N)} | 冷啟動 {pc(cold, N)} | 綁定疾病 {pc(bound, predicted)}")

    print(f"\n引擎風險 band 分布（可預測 n={predicted}）")
    for b in ("low", "medium", "high"):
        print(f"  {b:<8} {pc(bands.get(b,0), predicted)}")
    print(f"  平均風險 % {mean(risk_all):.1f}")

    print(f"\n趨勢 / 信心 / top driver")
    print("  趨勢   " + " | ".join(f"{t}={trends.get(t,0)}" for t in ("up","flat","down")))
    print("  信心   " + " | ".join(f"{c}={confidence.get(c,0)}" for c in ("high","medium","low")))
    for feat, c in top_features.most_common():
        print(f"  driver {recurrence.FEATURE_LABEL.get(feat, feat):<12} {pc(c, predicted)}")

    # ── 驗證：引擎風險 vs 模擬器真實 flare（這是「有沒有對到」）────────────
    print(f"\n{'='*72}\n預測 vs 真實復發（未來 {HORIZON} 天，模擬器 in_flare 為 ground truth）\n{'='*72}")
    base_any = mean(lab_any); base_onset = mean(lab_onset)
    print(f"  實際復發基率：任一日復發 {base_any*100:.1f}% | 新發作 {base_onset*100:.1f}%")
    au_any = auroc(risk_all, lab_any); au_onset = auroc(risk_all, lab_onset)
    print(f"  AUROC（風險% 判別）：任一日復發 {au_any:.3f} | 新發作 {au_onset:.3f}" if au_any else "  AUROC：N/A")
    rf = mean([r for r, l in zip(risk_all, lab_any) if l])
    rn = mean([r for r, l in zip(risk_all, lab_any) if not l])
    print(f"  平均風險%：實際會復發者 {rf:.1f}  vs  不復發者 {rn:.1f}")

    print(f"\n  風險 band × 實際復發率（理想：band 越高、實際復發率越高）")
    band_rate = {}
    for b in ("low", "medium", "high"):
        n, k = band_flare[b]
        band_rate[b] = (k / n) if n else 0.0
        print(f"    {b:<8} n={n:<6} 實際復發 {pc(k, n)}")

    print(f"\n  各疾病 實際復發基率 + 平均引擎風險%")
    for did in diseases:
        d = per_disease[did]
        if not d["n"]:
            continue
        ar = d["anyflare"]/d["n"]*100
        print(f"    {ZH[did]:<12}({BAND[did]:<6}) n={d['n']:<5} 實際復發 {ar:4.0f}% | 平均風險 {mean(d['risk']):4.1f}")

    # ── 管線正確性 gate（這些『應該』通過；沒過＝我的橋接有 bug，不是引擎表現）──
    print(f"\n{'='*72}\n管線正確性 gate（失敗＝橋接 bug）\n{'='*72}")
    failures = []
    def gate(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{('  '+detail) if detail else ''}")
        if not ok: failures.append(name)

    gate("全員越過冷啟動門檻（~60 天展開）", cold == 0, f"cold_start={cold}")
    gate("三個 band 皆有樣本", all(bands.get(b, 0) > 0 for b in ("low", "medium", "high")),
         f"low={bands.get('low',0)} med={bands.get('medium',0)} high={bands.get('high',0)}")
    gate("全員綁定到疾病文獻錨", bound == predicted, f"bound={bound}/{predicted}")

    # ── 引擎表現觀察（不是 gate；這是『產品引擎在這批資料表現如何』的發現，誠實呈現）──
    print(f"\n{'='*72}\n引擎表現觀察（findings，非 pass/fail）\n{'='*72}")
    mono = band_rate["high"] >= band_rate["medium"] >= band_rate["low"]
    print(f"  • AUROC（風險% → 未來{HORIZON}天復發）= {au_any:.3f}"
          + ("（>0.5：優於亂猜）" if au_any and au_any > 0.5 else "（≈0.5：接近亂猜）"))
    print(f"  • 會復發者平均風險 {rf:.1f} {'>' if rf > rn else '≤'} 不復發者 {rn:.1f}")
    print(f"  • band×實際復發率單調遞增（high≥med≥low）：{'是' if mono else '否'}"
          f"（{band_rate['low']*100:.0f}% / {band_rate['medium']*100:.0f}% / {band_rate['high']*100:.0f}%）")
    print(f"  • 註：asthma 等隨機觸發型疾病的 flare 本質上難由病程前兆預測（oracle AUROC≈0.5），")
    print(f"        會拉低整池判別力；慢性漸進型（RA/SLE）oracle 可達 0.68–0.75。")

    if failures:
        print(f"\n⚠️  管線 gate {len(failures)} 項未過：{failures}（橋接需修，非引擎問題）")
    else:
        print(f"\n[OK] 管線 gate 全過 — {N} 位『過去合成過的』患者已正確餵入產品引擎並完成預測。")

    summary = {
        "n": N, "n_per_disease": N_PER, "base_seed": BASE_SEED,
        "day_as_of": DAY_AS_OF, "horizon": HORIZON,
        "coverage": {"predicted": predicted, "cold_start": cold, "disease_bound": bound},
        "risk_band": dict(bands), "trend": dict(trends), "confidence": dict(confidence),
        "top_driver_feature": dict(top_features),
        "mean_risk_percent": round(mean(risk_all), 2),
        "actual_flare_base_rate": {"anyflare": round(base_any, 4), "onset": round(base_onset, 4)},
        "auroc": {"anyflare": au_any, "onset": au_onset},
        "mean_risk_flare_vs_nonflare": {"flare": round(rf, 2), "nonflare": round(rn, 2)},
        "band_vs_actual_flare_rate": {b: round(band_rate[b], 4) for b in ("low", "medium", "high")},
        "per_disease": {ZH[d]: {"n": per_disease[d]["n"],
                                 "anyflare_rate": round(per_disease[d]["anyflare"]/per_disease[d]["n"], 4),
                                 "mean_risk": round(mean(per_disease[d]["risk"]), 2)}
                        for d in diseases if per_disease[d]["n"]},
        "sanity_failures": failures,
        "samples": samples,
    }
    out = os.path.join(HERE, "_recurrence_synth_cohort_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n彙整已寫出：{out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())

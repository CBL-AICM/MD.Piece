"""把 3200 位虛擬患者「創建 MD.Piece 帳號並真實使用 12 個月」的端到端模擬。

流程：
  1. 重建 3200 位患者世代(16 疾病 × 200，seed=2024)，模擬天數 = 365。
     每位患者帶疾病軌跡 + 社經/家庭/地區/性別/共病/人格 profile。
  2. 計算每人的「註冊傾向」，選出剛好 1600 位註冊者。
  3. 為每位註冊者模擬 12 個月的 App 使用（含留存流失、逐功能記錄、
     忘記吃藥/沒紀錄/中途棄用等真實情境）。未註冊者記錄其未註冊原因。
  4. 彙整 + 輸出 JSON 與一份附 PubMed 引用的人類可讀報告。

執行：
  PYTHONPATH=. python -m ml.app_cohort
  PYTHONPATH=. python -m ml.app_cohort --n-register 1600 --sim-days 365 --quick
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np

from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_evidence import ATTRITION_REF, DISEASE_EVIDENCE, evidence_for
from md_piece.disease_loader import load_disease

DISEASES = [
    "rheumatoid_arthritis", "asthma", "systemic_sclerosis",
    "systemic_lupus_erythematosus", "inflammatory_bowel_disease",
    "multiple_sclerosis", "gout", "ankylosing_spondylitis",
    "psoriatic_arthritis", "sjogren_syndrome", "behcet_disease",
    "anca_vasculitis", "igg4_related_disease", "chronic_urticaria",
    "osteoarthritis", "idiopathic_pulmonary_fibrosis",
]

OUT_DIR = Path("output/mdpiece/app_cohort")
DOC_DIR = Path("docs/mdpiece/app_cohort")


def _age_band(age: int) -> str:
    if age < 40:
        return "年輕(<40)"
    if age < 60:
        return "中年(40-59)"
    return "老年(≥60)"


def build_candidates(diseases, n_per, sim_days, base_seed, n_workers):
    """生成所有患者並抽出使用模擬所需的輕量資料。"""
    cands = []
    for did in diseases:
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_per, sim_days, base_seed=base_seed,
                                 n_workers=n_workers)
        for p in cohort.patients:
            ts = p.timeseries.sort_values("day")
            act = ts["activity"].to_numpy(dtype=np.float32)
            fl = ts["in_flare"].to_numpy(dtype=np.int8)
            if len(act) < sim_days:                       # 保底補齊長度
                act = np.pad(act, (0, sim_days - len(act)), "edge")
                fl = np.pad(fl, (0, sim_days - len(fl)), "edge")
            cands.append({
                "pid": p.patient_id, "disease": p.disease_id,
                "age": p.age, "sex": p.sex, "profile": p.social_profile,
                "comorbidities": list(p.comorbidities),
                "has_treatments": bool(p.treatments),
                "act": act[:sim_days], "fl": fl[:sim_days], "seed": p.seed,
            })
    return cands


def run(n_per, sim_days, n_register, base_seed, n_workers):
    print(f"[1/4] 生成 {len(DISEASES)}×{n_per} = {len(DISEASES)*n_per} 位患者"
          f"（模擬 {sim_days} 天）…")
    cands = build_candidates(DISEASES, n_per, sim_days, base_seed, n_workers)
    total = len(cands)

    print(f"[2/4] 計算註冊傾向，選出 {n_register} 位註冊者…")
    props = {c["pid"]: au.registration_propensity(c["profile"], c["age"], c["disease"])
             for c in cands}
    registered = au.select_registered(props, n_register, seed=base_seed)

    print("[3/4] 模擬 12 個月 App 使用…")
    records = []
    for c in cands:
        join_rng = np.random.default_rng(c["seed"] ^ 0x5EED)
        join_day = int(join_rng.integers(0, 46))          # 0–45 天分批上線
        rec = au.simulate_patient_usage(
            patient_id=c["pid"], disease_id=c["disease"], age=c["age"], sex=c["sex"],
            profile=c["profile"], comorbidities=c["comorbidities"],
            has_treatments=c["has_treatments"], activity=c["act"], in_flare=c["fl"],
            registered=(c["pid"] in registered), join_day=join_day,
            sim_days=sim_days, seed=c["seed"] + 999983,
        )
        records.append(rec)

    print("[4/4] 彙整與輸出…")
    summary = aggregate(records, total, n_register, sim_days)
    write_outputs(records, summary, sim_days)
    _print_headline(summary)
    return records, summary


# ---------------------------------------------------------------------------
# 彙整
# ---------------------------------------------------------------------------

def aggregate(records, total, n_register, sim_days):
    reg = [r for r in records if r.registered]
    n_reg = len(reg)

    def pct(n, d):
        return round(100.0 * n / d, 1) if d else 0.0

    # 留存曲線
    retention = {k: pct(sum(r.retained[k] for r in reg), n_reg)
                 for k in ["D1", "D7", "D30", "D90", "D180", "D365"]}

    # 原型分布
    arche = Counter(r.archetype for r in reg)

    # 幽靈使用者：原型 ghost 或總紀錄 <3
    ghosts = sum(1 for r in reg if r.archetype == "ghost" or r.total_records < 3)

    # 功能採用率
    feat_adopt = {f.key: pct(sum(1 for r in reg if r.features.get(f.key, {}).get("adopted")), n_reg)
                  for f in au.FEATURES}

    # 用藥記錄完成率（有採用用藥紀錄者）
    med_users = [r for r in reg if r.features.get("medications", {}).get("adopted")]
    med_adh = round(mean(r.med_log_adherence for r in med_users), 3) if med_users else 0.0

    # 註冊率 by 各維度（分母=該層全部候選人）
    def reg_rate_by(keyfn):
        denom, numer = Counter(), Counter()
        for r in records:
            k = keyfn(r)
            denom[k] += 1
            if r.registered:
                numer[k] += 1
        return {k: {"candidates": denom[k], "registered": numer[k],
                    "rate_pct": pct(numer[k], denom[k])} for k in denom}

    by_disease = reg_rate_by(lambda r: r.disease_id)
    by_rarity = reg_rate_by(lambda r: (evidence_for(r.disease_id).rarity
                                       if evidence_for(r.disease_id) else "unknown"))
    by_onset = reg_rate_by(lambda r: (evidence_for(r.disease_id).onset_band
                                      if evidence_for(r.disease_id) else "unknown"))
    by_region = reg_rate_by(lambda r: r.region_macro or "未知")
    by_age = reg_rate_by(lambda r: _age_band(r.age))
    by_sex = reg_rate_by(lambda r: r.sex)
    by_income = reg_rate_by(lambda r: r.income_tier)
    by_urban = reg_rate_by(lambda r: r.urban_rural)

    # 縣市分布（所有候選人）
    region_county = Counter(r.region or "未知" for r in records)

    # 共病
    with_comorbid = sum(1 for r in records if r.comorbidity_count > 0)

    # 每疾病使用深度
    per_disease_usage = {}
    for did in DISEASES:
        dreg = [r for r in reg if r.disease_id == did]
        if not dreg:
            continue
        top_arche = Counter(r.archetype for r in dreg).most_common(1)[0][0]
        per_disease_usage[did] = {
            "registered": len(dreg),
            "engaged_at_12m": sum(r.engaged_at_12m for r in dreg),
            "engaged_at_12m_pct": pct(sum(r.engaged_at_12m for r in dreg), len(dreg)),
            "median_records": int(median([r.total_records for r in dreg])),
            "median_active_days": int(median([r.active_days for r in dreg])),
            "top_archetype": top_arche,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sim_days": sim_days,
        "totals": {
            "candidates": total,
            "registered": n_reg,
            "registration_rate_pct": pct(n_reg, total),
            "not_registered": total - n_reg,
            "with_comorbidity": with_comorbid,
            "with_comorbidity_pct": pct(with_comorbid, total),
        },
        "engagement": {
            "engaged_at_12m": sum(r.engaged_at_12m for r in reg),
            "engaged_at_12m_pct": pct(sum(r.engaged_at_12m for r in reg), n_reg),
            "ghost_users": ghosts,
            "ghost_users_pct": pct(ghosts, n_reg),
            "median_active_days": int(median([r.active_days for r in reg])) if reg else 0,
            "mean_active_days": round(mean([r.active_days for r in reg]), 1) if reg else 0,
            "median_total_records": int(median([r.total_records for r in reg])) if reg else 0,
            "mean_total_records": round(mean([r.total_records for r in reg]), 1) if reg else 0,
            "median_months_active": int(median([r.months_active for r in reg])) if reg else 0,
            "mean_data_completeness": round(mean([r.data_completeness for r in reg]), 3) if reg else 0,
            "mean_med_log_adherence": med_adh,
        },
        "retention_curve_pct": retention,
        "archetype_distribution": dict(arche),
        "feature_adoption_pct": feat_adopt,
        "registration_by": {
            "disease": by_disease, "rarity": by_rarity, "onset_band": by_onset,
            "region_macro": by_region, "age_band": by_age, "sex": by_sex,
            "income_tier": by_income, "urban_rural": by_urban,
        },
        "region_county_distribution": dict(region_county.most_common()),
        "per_disease_usage": per_disease_usage,
    }


# ---------------------------------------------------------------------------
# 輸出
# ---------------------------------------------------------------------------

def _slim_record(r: au.UsageRecord) -> dict:
    d = {
        "patient_id": r.patient_id, "disease_id": r.disease_id,
        "age": r.age, "sex": r.sex, "region": r.region, "region_macro": r.region_macro,
        "income_tier": r.income_tier, "education": r.education,
        "urban_rural": r.urban_rural, "family_support": r.family_support,
        "living_arrangement": r.living_arrangement,
        "comorbidity_count": r.comorbidity_count, "registered": r.registered,
    }
    if r.registered:
        d.update({
            "archetype": r.archetype, "join_day": r.join_day,
            "active_days": r.active_days, "total_records": r.total_records,
            "months_active": r.months_active,
            "med_log_adherence": round(r.med_log_adherence, 3),
            "data_completeness": round(r.data_completeness, 3),
            "engaged_at_12m": r.engaged_at_12m, "churn_day": r.churn_day,
            "retained": r.retained,
            "feature_records": {k: v["n_records"] for k, v in r.features.items()
                                if v["adopted"]},
        })
    else:
        d["non_registration_reason"] = r.non_registration_reason
    return d


def write_outputs(records, summary, sim_days):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "usage_records.json").write_text(
        json.dumps([_slim_record(r) for r in records], ensure_ascii=False),
        encoding="utf-8")
    (DOC_DIR / "README.md").write_text(render_report(summary), encoding="utf-8")
    print(f"  → {OUT_DIR/'summary.json'}")
    print(f"  → {OUT_DIR/'usage_records.json'}")
    print(f"  → {DOC_DIR/'README.md'}")


def render_report(s) -> str:
    t = s["totals"]
    e = s["engagement"]
    r = s["retention_curve_pct"]
    L = []
    L.append("# MD.Piece — 3200 虛擬患者註冊與 12 個月使用模擬")
    L.append("")
    L.append(f"*產生時間：{s['generated_at']}　模擬天數：{s['sim_days']} 天（12 個月）*")
    L.append("")
    L.append("本報告把先前的 3200 位虛擬患者（16 種疾病 × 200，seed=2024）放進虛擬世界，"
             "為每人建立社經/家庭/地區/性別/共病背景，讓其中 "
             f"**{t['registered']}** 位註冊 MD.Piece 並真實使用 12 個月，"
             "模擬包含留存流失、逐功能記錄、忘記吃藥/沒紀錄/中途棄用等真實情境。")
    L.append("")
    L.append("## 一、總覽")
    L.append("")
    L.append(f"- 候選患者：**{t['candidates']}** 位；註冊：**{t['registered']}** 位"
             f"（註冊率 {t['registration_rate_pct']}%）；未註冊：{t['not_registered']} 位")
    L.append(f"- 具至少一項共病：{t['with_comorbidity']} 位（{t['with_comorbidity_pct']}%）；"
             "其餘為單一慢性病")
    L.append(f"- 12 個月後仍活躍（engaged@12m）：**{e['engaged_at_12m']}** 位"
             f"（{e['engaged_at_12m_pct']}%）")
    L.append(f"- 幽靈使用者（註冊卻幾乎不用）：{e['ghost_users']} 位（{e['ghost_users_pct']}%）")
    L.append(f"- 每位註冊者：中位活躍天數 {e['median_active_days']} 天、"
             f"中位總紀錄 {e['median_total_records']} 筆、中位活躍月數 {e['median_months_active']} 個月")
    L.append(f"- 平均資料完整度（活躍天/觀察天）：{e['mean_data_completeness']}；"
             f"平均用藥記錄完成率：{e['mean_med_log_adherence']}")
    L.append("")
    L.append("## 二、留存曲線（流失定律）")
    L.append("")
    L.append("符合數位健康的『流失定律』：多數使用者在前幾週後逐漸流失，只剩穩定核心。")
    L.append("『實質活躍』定義為：該里程碑前後 30 天視窗內 **≥2 次**開啟 App"
             "（單次因 flare 偶爾回訪不算）。")
    L.append("")
    L.append(f"- 48 小時內首次開啟 App（onboarding 回訪）：**{r['D1']}%**")
    L.append("")
    L.append("| 里程碑 | D7 | D30 | D90 | D180 | D365(12個月) |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| 仍實質活躍 % | {r['D7']} | {r['D30']} | {r['D90']} | {r['D180']} | {r['D365']} |")
    L.append("")
    L.append("> 註：註冊者為傾向分數前 50% 的族群（自我選擇效應），故 12 個月留存"
             f"（{r['D365']}%）高於一般自助型 app；反應型使用者會因 flare 反覆回訪"
             "亦推升留存。")
    L.append("")
    L.append(f"> 依據(PubMed)：Eysenbach G. *{ATTRITION_REF.title}*. {ATTRITION_REF.journal} "
             f"{ATTRITION_REF.year}. [DOI](https://doi.org/{ATTRITION_REF.doi})")
    L.append("")
    L.append("## 三、使用者原型分布")
    L.append("")
    L.append("| 原型 | 人數 | 說明 |")
    L.append("|---|---|---|")
    desc = {
        "power_user": "重度使用者：幾乎每天記錄、流失極慢、功能採用廣",
        "steady": "穩定使用者：每週數次、緩慢衰退",
        "reactive": "反應型：平時少記，症狀/flare 一來才猛記",
        "casual": "隨意型：零星使用、衰退較快",
        "early_churner": "早退型：前幾週用一用就停（真實世界最大宗）",
        "ghost": "幽靈：註冊後幾乎不用",
    }
    for a in au.ARCHETYPES:
        n = s["archetype_distribution"].get(a.name, 0)
        L.append(f"| {a.name} | {n} | {desc[a.name]} |")
    L.append("")
    L.append("## 四、功能採用率（註冊者中曾用過該功能的比例）")
    L.append("")
    L.append("| 功能 | 採用率 % |")
    L.append("|---|---|")
    label = {f.key: f.label for f in au.FEATURES}
    for k, v in sorted(s["feature_adoption_pct"].items(), key=lambda x: -x[1]):
        L.append(f"| {label[k]} ({k}) | {v} |")
    L.append("")
    L.append("## 五、註冊率 × 族群（誰會註冊使用）")
    L.append("")
    L.append("**依疾病罕見度**（罕見病患者也照樣使用）：")
    L.append("")
    L.append("| 罕見度 | 候選 | 註冊 | 註冊率 % |")
    L.append("|---|---|---|---|")
    order = ["common", "uncommon", "rare"]
    zh = {"common": "常見", "uncommon": "較不常見", "rare": "罕見", "unknown": "未知"}
    by = s["registration_by"]["rarity"]
    for k in order:
        if k in by:
            L.append(f"| {zh[k]} | {by[k]['candidates']} | {by[k]['registered']} | {by[k]['rate_pct']} |")
    L.append("")
    L.append("**依好發年齡層**：")
    L.append("")
    L.append("| 好發層 | 候選 | 註冊 | 註冊率 % |")
    L.append("|---|---|---|---|")
    zhb = {"young": "年輕", "middle": "中年", "old": "老年", "unknown": "未知"}
    byo = s["registration_by"]["onset_band"]
    for k in ["young", "middle", "old"]:
        if k in byo:
            L.append(f"| {zhb[k]} | {byo[k]['candidates']} | {byo[k]['registered']} | {byo[k]['rate_pct']} |")
    L.append("")
    L.append("**依實際年齡層**（高齡註冊率較低，呼應數位落差；部分由家屬代理救回）：")
    L.append("")
    L.append("| 年齡層 | 候選 | 註冊 | 註冊率 % |")
    L.append("|---|---|---|---|")
    bya = s["registration_by"]["age_band"]
    for k in ["年輕(<40)", "中年(40-59)", "老年(≥60)"]:
        if k in bya:
            L.append(f"| {k} | {bya[k]['candidates']} | {bya[k]['registered']} | {bya[k]['rate_pct']} |")
    L.append("")
    L.append("**依地區（區域）**：")
    L.append("")
    L.append("| 區域 | 候選 | 註冊 | 註冊率 % |")
    L.append("|---|---|---|---|")
    byr = s["registration_by"]["region_macro"]
    for k in ["北部", "中部", "南部", "東部", "離島"]:
        if k in byr:
            L.append(f"| {k} | {byr[k]['candidates']} | {byr[k]['registered']} | {byr[k]['rate_pct']} |")
    L.append("")
    L.append("**依性別**：")
    L.append("")
    L.append("| 性別 | 候選 | 註冊 | 註冊率 % |")
    L.append("|---|---|---|---|")
    bysx = s["registration_by"]["sex"]
    for k in ["F", "M"]:
        if k in bysx:
            L.append(f"| {k} | {bysx[k]['candidates']} | {bysx[k]['registered']} | {bysx[k]['rate_pct']} |")
    L.append("")
    L.append("## 六、各疾病使用深度（連結 PubMed 實證）")
    L.append("")
    L.append("| 疾病 | 罕見度 | 好發層 | 註冊數 | @12m活躍 | 中位紀錄 | 主原型 | PubMed |")
    L.append("|---|---|---|---|---|---|---|---|")
    for did in DISEASES:
        u = s["per_disease_usage"].get(did)
        ev = DISEASE_EVIDENCE.get(did)
        if not u or not ev:
            continue
        L.append(f"| {ev.pubmed.title.split(':')[0][:28]} | {zh[ev.rarity]} | {zhb[ev.onset_band]} | "
                 f"{u['registered']} | {u['engaged_at_12m']}({u['engaged_at_12m_pct']}%) | "
                 f"{u['median_records']} | {u['top_archetype']} | "
                 f"[{ev.pubmed.pmid}](https://doi.org/{ev.pubmed.doi}) |")
    L.append("")
    L.append("## 七、疾病流行病學分類與 PubMed 來源")
    L.append("")
    L.append("依下列 PubMed 文獻把 16 種疾病分為罕見/常見、典型/不典型、好發年齡層"
             "（資料來源：PubMed）：")
    L.append("")
    for did in DISEASES:
        ev = DISEASE_EVIDENCE.get(did)
        if not ev:
            continue
        L.append(f"### {did}（{zh[ev.rarity]}・好發{zhb[ev.onset_band]}）")
        L.append(f"- 盛行率：{ev.prevalence_note}")
        L.append(f"- 典型：{ev.typical_note}")
        L.append(f"- 不典型：{ev.atypical_note}")
        L.append(f"- 來源(PubMed)：{ev.pubmed.title}. *{ev.pubmed.journal}* {ev.pubmed.year}. "
                 f"PMID {ev.pubmed.pmid}. [DOI](https://doi.org/{ev.pubmed.doi})")
        L.append("")
    L.append("---")
    L.append("")
    L.append("*所有疾病流行病學分類引用自 PubMed 檢索之文獻（PMID/DOI 如上）；"
             "本模擬為 in silico（虛擬）資料，未寫入任何正式環境或真實使用者資料。*")
    return "\n".join(L)


def _print_headline(s):
    t, e, r = s["totals"], s["engagement"], s["retention_curve_pct"]
    print("=" * 60)
    print(f"候選 {t['candidates']} / 註冊 {t['registered']} ({t['registration_rate_pct']}%)")
    print(f"留存 D7={r['D7']}% D30={r['D30']}% D90={r['D90']}% D180={r['D180']}% D365={r['D365']}%")
    print(f"@12m 仍活躍 {e['engaged_at_12m']} ({e['engaged_at_12m_pct']}%)；"
          f"幽靈 {e['ghost_users']} ({e['ghost_users_pct']}%)")
    print(f"中位紀錄 {e['median_total_records']} 筆/人；用藥記錄完成率 {e['mean_med_log_adherence']}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per", type=int, default=200)
    ap.add_argument("--sim-days", type=int, default=365)
    ap.add_argument("--n-register", type=int, default=1600)
    ap.add_argument("--base-seed", type=int, default=2024)
    ap.add_argument("--n-workers", type=int, default=4)
    ap.add_argument("--quick", action="store_true",
                    help="快速冒煙：每病 20 人、註冊 160、180 天")
    a = ap.parse_args()
    if a.quick:
        a.n_per, a.n_register, a.sim_days = 20, 160, 180
    run(a.n_per, a.sim_days, a.n_register, a.base_seed, a.n_workers)


if __name__ == "__main__":
    main()

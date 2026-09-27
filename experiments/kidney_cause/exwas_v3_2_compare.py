# -*- coding: utf-8 -*-
"""ExWAS v3 與 v3.2（資料修正後）之比較。  python exwas_v3_2_compare.py
（先跑 python run_exwas.py v3.2 與 python exwas_v3_checks.py v3.2；計畫 params/exwas_v3_2_plan.json）

1. 兩版暴露世代逐格比較：哪些欄位不同、不同是否只在 2017–2018 年（C3）或 C1 改名欄位
   → 若暴露、共變項欄位逐格相同，v3 結果即等同「2017–2018 年用原發布之肌酸酐」之敏感度分析
2. 結果標籤（kidney_damage）逐週期轉移
3. 逐暴露 M3 勝算比、q 值、顯著與否；對照檢查；血尿比較各格
輸出 results/exwas_v3_2_compare.json。
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                                   # noqa: E402
import pandas as pd                                                  # noqa: E402

from exposure_cohort import build                                    # noqa: E402
from nhanes_cohort import BRIDGE_J, BRIDGE_J_LOG10, V32_RENAMES      # noqa: E402

J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
C3_COLS = set(BRIDGE_J) | set(BRIDGE_J_LOG10) | {"LBXSGB", "LBXSOSSI", "eGFR", "kidney_damage"}
C1_COLS = set(V32_RENAMES) | set(V32_RENAMES.values())
LAB = {1.0: "異常", 0.0: "正常"}


def same(a, b):
    """逐格相同（兩邊皆缺視為相同）。"""
    if a.dtype == object or b.dtype == object:
        return (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())
    return (a == b) | (a.isna() & b.isna())


def cohort_diff(P):
    E3, E32 = build(P, verbose=False), build(P, verbose=False, fixes=True)
    a, b = E3["cohort"].set_index("SEQN"), E32["cohort"].set_index("SEQN")
    assert a.index.is_unique and b.index.is_unique and a.index.equals(b.index), "兩版世代的受試者不同"
    assert E3["exposures"] == E32["exposures"], "兩版暴露清單不同——依計畫停止"
    diff = {}
    for c in sorted(set(a.columns) | set(b.columns)):
        if c not in a.columns or c not in b.columns:
            diff[c] = dict(only_in="v3" if c in a.columns else "v3.2")
            continue
        bad = ~same(a[c], b[c])
        if bad.any():
            diff[c] = dict(n_rows=int(bad.sum()), cycles=sorted(a.loc[bad, "cycle"].unique().tolist()))
    used = set(E3["exposures"]) | set(E3["covariates"]) | {"cycle", "age", "sex"}
    unexpected = {c: v for c, v in diff.items() if c not in C3_COLS | C1_COLS}
    c3_outside = {c: v for c, v in diff.items() if c in C3_COLS - C1_COLS and v.get("cycles") != ["2017-2018"]}
    y3, y32 = a["kidney_damage"], b["kidney_damage"]
    lab = lambda s: s.map(LAB).fillna("未知")
    trans = pd.crosstab([a["cycle"], lab(y3)], lab(y32))
    changed = ~same(y3, y32)
    out = dict(
        n_rows=int(len(a)), columns_differing=diff,
        exposure_or_covariate_columns_differing=sorted(set(diff) & used),
        unexpected_columns=unexpected, c3_columns_outside_2017_2018=c3_outside,
        v3_equals_v32_with_original_2017_2018_creatinine=bool(not (set(diff) & used) and not unexpected and not c3_outside),
        label_changes=dict(
            n_changed=int(changed.sum()), by_cycle=a.loc[changed, "cycle"].value_counts().to_dict(),
            transitions=[dict(cycle=cy, v3=f, v3_2=t, n=int(n)) for (cy, f), row in trans.iterrows()
                         for t, n in row.items() if n and f != t]),
        counts=dict(v3={k: E3["counts"][k] for k in ("n_adults", "n_outcome_known", "n_kidney_damage", "n_exposures")},
                    v3_2={k: E32["counts"][k] for k in ("n_adults", "n_outcome_known", "n_kidney_damage", "n_exposures")}),
        n_by_exposure_identical=E3["counts"]["n_by_exposure"] == E32["counts"]["n_by_exposure"])
    return out


def results_diff():
    R3, R32 = J("results", "exwas_v3.json"), J("results", "exwas_v3_2.json")
    a = {r["exposure"]: r for r in R3["results"]}
    b = {r["exposure"]: r for r in R32["results"]}
    assert set(a) == set(b), "兩版掃描的暴露不同"
    per, changed = [], []
    for e in a:
        h3, h32 = a[e]["headline"], b[e]["headline"]
        rec = dict(exposure=e, scale=h3["scale"],
                   v3=dict(OR=h3["OR"], ci=h3["ci"], p=h3["p_two_sided"], q=a[e]["q_bh"], n=h3["n"], n_pos=h3["n_pos"],
                           sig=a[e]["significant_fdr05"], survives=a[e]["survives_full_adjustment"]),
                   v3_2=dict(OR=h32["OR"], ci=h32["ci"], p=h32["p_two_sided"], q=b[e]["q_bh"], n=h32["n"], n_pos=h32["n_pos"],
                             sig=b[e]["significant_fdr05"], survives=b[e]["survives_full_adjustment"]),
                   dlogOR=float(np.log(h32["OR"]) - np.log(h3["OR"])))
        per.append(rec)
        if (rec["v3"]["sig"], rec["v3"]["survives"]) != (rec["v3_2"]["sig"], rec["v3_2"]["survives"]):
            changed.append(e)
    per.sort(key=lambda r: r["v3_2"]["p"])
    big = max(per, key=lambda r: abs(r["dlogOR"]))
    sig3 = {e for e in a if a[e]["significant_fdr05"] and a[e]["survives_full_adjustment"]}
    sig32 = {e for e in b if b[e]["significant_fdr05"] and b[e]["survives_full_adjustment"]}
    inc = lambda R: sorted(x["exposure"] for x in R["urinary_correction_inconsistent"])
    return dict(
        v3_created=R3["created"], v3_2_created=R32["created"], v3_2_plan_sha256=R32.get("plan_sha256"),
        cohort=dict(
            v3={k: R3["cohort"][k] for k in ("n_adults", "n_outcome_known", "n_kidney_damage", "n_exposures")},
            v3_2={k: R32["cohort"][k] for k in ("n_adults", "n_outcome_known", "n_kidney_damage", "n_exposures")}),
        n_significant_fdr05=dict(v3=R3["n_significant_fdr05"], v3_2=R32["n_significant_fdr05"]),
        n_surviving_full_adjustment=dict(v3=R3["n_surviving_full_adjustment"], v3_2=R32["n_surviving_full_adjustment"]),
        significant_only_in_v3=sorted(sig3 - sig32), significant_only_in_v3_2=sorted(sig32 - sig3),
        status_changed=changed,
        max_abs_dlogOR=dict(exposure=big["exposure"], dlogOR=big["dlogOR"],
                            OR_v3=big["v3"]["OR"], OR_v3_2=big["v3_2"]["OR"]),
        control_check=dict(v3={k: R3["control_check"][k] for k in ("positive_hits", "negative_hits", "interpretation")},
                           v3_2={k: R32["control_check"][k] for k in ("positive_hits", "negative_hits", "interpretation")}),
        arsenic=dict(v3=R3["arsenic_builtin_control"]["interpretation"], v3_2=R32["arsenic_builtin_control"]["interpretation"]),
        urinary_inconsistent=dict(v3=inc(R3), v3_2=inc(R32)),
        per_exposure=per)


def checks_diff():
    C3, C32 = J("results", "exwas_v3_checks.json"), J("results", "exwas_v3_2_checks.json")
    out = {}
    for metal, m3 in C3["metals"].items():
        m32 = C32["metals"][metal]
        rows = []
        for oname, mm in m3["models"].items():
            for k, v in mm.items():
                w = m32["models"][oname][k]
                rows.append(dict(outcome=oname, measure=k,
                                 v3=dict(n=v["n"], n_pos=v["n_pos"], OR=v["OR_per_doubling"], ci=v["ci"], p=v["p"]),
                                 v3_2=dict(n=w["n"], n_pos=w["n_pos"], OR=w["OR_per_doubling"], ci=w["ci"], p=w["p"]),
                                 p_below_05=[v["p"] < 0.05, w["p"] < 0.05]))
        out[metal] = dict(n_both=[m3["n_both"], m32["n_both"]], cells=rows,
                          cells_changing_p_below_05=[f"{r['outcome']}｜{r['measure']}" for r in rows
                                                     if r["p_below_05"][0] != r["p_below_05"][1]])
    return out


def main():
    P = J("params", "design.json")
    plan = os.path.join(ROOT, "params", "exwas_v3_2_plan.json")
    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"),
               plan=os.path.relpath(plan, ROOT), plan_sha256=hashlib.sha256(open(plan, "rb").read()).hexdigest(),
               cohort_comparison=cohort_diff(P), results_comparison=results_diff(), checks_comparison=checks_diff())
    cc, rc = out["cohort_comparison"], out["results_comparison"]
    print(f"[世代] 標籤改變 {cc['label_changes']['n_changed']} 人 {cc['label_changes']['by_cycle']}；"
          f"暴露／共變項欄位不同：{cc['exposure_or_covariate_columns_differing']}；非預期欄位：{list(cc['unexpected_columns'])}")
    print(f"       v3＝v3.2 用原發布 2017–2018 肌酸酐：{cc['v3_equals_v32_with_original_2017_2018_creatinine']}")
    print(f"[結果] FDR<0.05：{rc['n_significant_fdr05']}；通過完整調整：{rc['n_surviving_full_adjustment']}；"
          f"狀態改變：{rc['status_changed']}；最大 |ΔlogOR|：{rc['max_abs_dlogOR']}")
    print(f"[對照] v3 {rc['control_check']['v3']['interpretation']}｜v3.2 {rc['control_check']['v3_2']['interpretation']}")
    for metal, m in out["checks_comparison"].items():
        print(f"[血尿 {metal}] n_both {m['n_both']}；p<0.05 改變之格：{m['cells_changing_p_below_05']}")
    json.dump(out, open(os.path.join(ROOT, "results", "exwas_v3_2_compare.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("[存檔] results/exwas_v3_2_compare.json")


if __name__ == "__main__":
    main()

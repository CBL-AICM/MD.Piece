# -*- coding: utf-8 -*-
"""UI 資料包匯出：讀 params／results（default.json、locked.json、grid.json 若存在）＋一個測試世代的代表序列，
嵌入 template.html 產生單一離線 index.html。前端不得硬寫係數／欄位／門檻——一律來自本 pack。
文案 lint：禁止 你的／您的／我的、燈號、等第、減藥建議、合成單一分數。
    python ui/export_ui_pack.py [--seed 20260818] [--n 1500]"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np                                        # noqa: E402
import m0_params as M0                                    # noqa: E402
from m0_params import value                               # noqa: E402
from m5_ews import rolling_indicators                     # noqa: E402
from figures import make_data, _representative, MECH_ORDER, MECH_ZH  # noqa: E402
from run import params_hash, ews_cfg                      # noqa: E402

FORBIDDEN = re.compile(r"你的|您的|我的|紅燈|綠燈|黃燈|警示燈|等第|甲上|評級|建議減藥|建議停藥|應減藥|應停藥|單一分數|綜合分數|風險燈")
MECH_DESC = {"bifurcation": "減藥途中緩慢跨越臨界點後翻轉——臨界減速理論上存在的正對照",
             "stochastic_escape": "未達臨界點，由隨機波動促成跳轉——前兆有限的翻轉",
             "continuous_deterioration": "平均水準線性上升、回復速度不變——檢驗去趨勢與特異性",
             "exogenous_shock": "外來事件（如感染）造成突發惡化——原理上無法預警的發作",
             "noise_amplification": "波動變大但穩定性不變——變異數假警報的來源",
             "stable": "全程平穩未發作——虛無序列，用來鎖定警報門檻"}


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def build_pack(seed, n):
    P = M0.load("thresholds.json"); Cj = M0.load("cohort.json")
    chk = M0.check(P, verbose=False)
    res_dir = os.path.join(ROOT, "results")
    default = json.load(open(os.path.join(res_dir, "default.json"), encoding="utf-8"))
    locked = json.load(open(os.path.join(res_dir, "locked.json"), encoding="utf-8"))
    grid_p = os.path.join(res_dir, "grid.json")
    grid = json.load(open(grid_p, encoding="utf-8")) if os.path.exists(grid_p) else None

    test, lk, t_alarm, cfg = make_data(P, Cj, seed, n)
    C, y = test["C"], test["y"]
    run_in, T = C["run_in"], C["T"]
    eval_times = np.arange(run_in, T, cfg["eval_every"])
    tgrid = np.arange(T)
    gallery = []
    for mech in MECH_ORDER:
        i = _representative(C, mech)
        ok = np.isfinite(y[i]); t_i, y_i = tgrid[ok], y[i][ok].astype(float)
        ar1, sd = rolling_indicators(t_i, y_i, eval_times, cfg["window_days"], cfg["min_obs"], cfg["detrend"], cfg["bw_frac"])
        gallery.append(dict(mech=mech, zh=MECH_ZH[mech], desc=MECH_DESC[mech],
                            rate=float(C["event_24m"][C["mech"] == mech].mean()), n=int((C["mech"] == mech).sum()),
                            t=(t_i - run_in).tolist(), y=np.round(y_i, 4).tolist(),
                            eval_t=(eval_times - run_in).tolist(), ar1=np.round(ar1, 4).tolist(), sd=np.round(sd, 4).tolist(),
                            t_event=int(C["t_event"][i] - run_in) if C["t_event"][i] >= 0 else None))
    # 效能層：MC 平均±SE（default.json）＋單一測試世代的提前期四分位
    summary = default["cell"]["summary"]
    leads = {}
    for mech in MECH_ORDER:
        sel = (C["mech"] == mech) & (C["t_event"] >= 0) & (t_alarm >= 0) & (t_alarm < C["t_event"])
        v = np.sort((C["t_event"] - t_alarm)[sel])
        if len(v) >= 3:
            leads[mech] = dict(n=int(len(v)), q=[float(np.percentile(v, p)) for p in (5, 25, 50, 75, 95)])
    ident = None
    if grid:
        ident = dict(cells=grid["identifiability"], n=grid["n"], mc=grid["mc"],
                     intervals={k: v for k, v in value(P, "sampling_intervals").items()},
                     errors={k: v for k, v in value(P, "meas_error_levels").items()},
                     biopsy_sens=locked["biopsy"]["sensitivity"] if locked.get("biopsy", {}).get("reachable") else None)
    prov_keys = ("mu_c", "tau_x", "tau_xi", "sigma_xi", "window_days", "min_obs_per_window", "eval_every_days", "joint_alarm",
                 "false_alarm_budget_per_py", "surrogates", "mechanisms", "hazard", "flare_rate_24m_range", "flare_rate_52w",
                 "biopsy_rule_counts", "taper_schedule", "g0", "pkpd_lag_days", "adherence", "N", "T", "run_in_days", "mc_datasets", "seed_families")
    provenance = [dict(key=k, status=P[k]["status"], source=P[k]["source"],
                       value=_clean(P[k]["value"] if P[k]["value"] is not None else P[k].get("placeholder")))
                  for k in prov_keys]
    return _clean(dict(
        meta=dict(title="狼瘡腎炎減藥翻轉預警——模型視覺化", date="2026-08-21", params_hash=params_hash(),
                  placeholders=[p["key"] for p in chk["placeholders"]],
                  scope=["全部為程式生成之合成序列，無任何真人資料", "使用佔位參數之產出不得對外引用",
                         "本頁不做診斷、不取代醫師判斷、不提供任何減藥時機或速度的判斷", "本頁不收集任何資料，離線可用"]),
        landscape=dict(mu_c=float(value(P, "mu_c")), g0=float(value(P, "g0"))),
        gallery=gallery,
        operating=dict(summary=summary, thresholds=default["cell"]["lock"]["thresholds"], achieved=default["cell"]["lock"]["achieved"],
                       budget=default["cell"]["lock"]["budget"], mc=default["cell"]["mc"], n=default["cell"]["n"],
                       leads=leads, leads_n=int(C["n"]), gates=[dict(gate=g["gate"], passed=g["passed"]) for g in default["gates"]]),
        identifiability=ident,
        provenance=provenance))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260818)
    ap.add_argument("--n", type=int, default=1500)
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "template.html"), encoding="utf-8").read()
    bad = FORBIDDEN.findall(re.sub(r"<script[\s\S]*?</script>", "", tpl))
    if bad:
        raise SystemExit(f"[lint] 模板含禁用語彙：{sorted(set(bad))}")
    pack = build_pack(a.seed, a.n)
    html = tpl.replace("__PACK_JSON__", json.dumps(pack, ensure_ascii=False, separators=(",", ":")))
    out = os.path.join(here, "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"[ui] index.html {os.path.getsize(out)/1024:.0f} KB；佔位 {pack['meta']['placeholders']}；圖D {'含' if pack['identifiability'] else '待補'}")


if __name__ == "__main__":
    main()

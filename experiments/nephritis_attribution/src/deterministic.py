# -*- coding: utf-8 -*-
"""L2 決定性標記硬分流。

本檔案刻意只 import numpy 與 json：沒有任何模型、沒有機率、沒有權重。
閘門 G2 會掃描原始碼確認這件事。理由是鐵則 5 —— 抗 GBM 抗體陽性這件事
本身就把答案講完了，再乘一個 0.87 的機率只是把確定的東西弄糊。

「標記沒回來」與「標記陰性」是兩種不同的狀態，程式裡分成兩個欄位
（xxx 與 xxx_available）。把未回覆當成陰性是這類系統最常見的靜默錯誤。
"""
import json
import os

import numpy as np

PARAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "params")

NO_ROUTE = -1


def rules():
    with open(os.path.join(PARAMS_DIR, "deterministic.json"), encoding="utf-8") as f:
        return json.load(f)


def active_sediment(raw, cfg):
    out = raw["rbc_cast"] > 0.5
    for c in cfg["any_of"]:
        if "urine_rbc_hpf_min" in c:
            out = out | ((raw["urine_rbc_hpf"] >= c["urine_rbc_hpf_min"]) &
                         (raw["dysmorphic_rbc_pct"] >= c["dysmorphic_rbc_pct_min"]))
    return out


def _marker_positive(markers, name):
    """只有「已回覆且為陽性」才算命中。"""
    return (markers[name + "_available"] > 0.5) & (markers[name] > 0.5)


def apply(raw, markers, R=None):
    """回傳 (route[n] 型態索引或 NO_ROUTE, rule_id[n])。第一條命中即定案。"""
    R = R or rules()
    n = len(raw["cr_now"])
    route = np.full(n, NO_ROUTE, dtype=object)
    rule_id = np.full(n, "", dtype=object)
    sed = active_sediment(raw, R["active_sediment"])

    for rule in R["rules"]:
        hit = np.ones(n, dtype=bool)
        for key, val in rule["when"].items():
            if key == "active_sediment":
                hit &= sed if val else ~sed
            elif key.endswith("_min"):
                f = key[:-4]
                hit &= np.nan_to_num(raw[f], nan=-np.inf) >= val
            else:
                hit &= _marker_positive(markers, key) if val else ~_marker_positive(markers, key)
        take = hit & (route == NO_ROUTE)
        route[take] = rule["route"]
        rule_id[take] = rule["id"]
    return route, rule_id


def pending_markers(markers):
    """哪些決定性標記還沒回來 —— 要顯示給使用者，不可靜默。"""
    names = [k for k in markers if not k.endswith("_available")]
    return {k: (markers[k + "_available"] < 0.5) for k in names}


def safety_override(raw, flags, R=None):
    """L3 之後的決定性否決：命中者一律不得被 rule out。

    這條只會把人從「可安全排除」拉回「不可排除」，永遠不會反過來。單向設計是刻意的
    —— 讓確定性規則去推翻機率是安全的，讓機率去推翻確定性規則不是。
    """
    R = R or rules()
    S = R["safety_override"]
    fast = np.nan_to_num(raw["cr_slope_per_week"], nan=0.0) >= S["cr_slope_per_week_min"]
    flagged = np.array([S["or_flag"] in f for f in flags])
    # ponytail: 曾試過把「活動性尿沉渣」也列入否決，否決率從 9% 衝到 54%，
    # 卻只少漏 1 位時效性個案 —— 代價與收益不成比例，改由下方的漏判率上限處理。
    return fast | flagged

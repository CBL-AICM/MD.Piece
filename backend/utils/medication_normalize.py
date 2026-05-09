"""把 LLM / OCR 回傳的劑量、頻率、用法字串正規化成統一中文格式。

目的：藥單上常混用 BID / TID / Q8H / 1# / 1tab / 5cc 等不一致寫法，
正規化後前端能一致顯示與排程。設計原則：
  - **保留原文**到 ``raw`` 欄位，只在 ``normalized`` 給整理過的版本，
    這樣使用者覺得我們翻錯也能看到原本是什麼。
  - 整理規則寫死、不打 LLM，因為這些縮寫醫療場域固定且我們要可預測。
"""
from __future__ import annotations

import re
from typing import Optional


# ── 頻率縮寫對照表 ─────────────────────────────────────────
# 拉丁縮寫（拉丁文 quaque die / bis in die / ter in die …）
_FREQ_MAP = {
    # 標準縮寫
    "QD": "一天一次",
    "QAM": "每天早上一次",
    "QPM": "每天下午一次",
    "QHS": "睡前一次",
    "HS": "睡前一次",
    "BID": "一天兩次",
    "BD": "一天兩次",
    "TID": "一天三次",
    "TDS": "一天三次",
    "TDD": "一天三次",
    "QID": "一天四次",
    "QDS": "一天四次",
    "Q4H": "每 4 小時一次",
    "Q6H": "每 6 小時一次",
    "Q8H": "每 8 小時一次",
    "Q12H": "每 12 小時一次",
    "Q24H": "每 24 小時一次",
    "QOD": "兩天一次",
    "QW": "一週一次",
    "PRN": "需要時服用",
    "STAT": "立即一次",
    # 中文常見口語
    "早晚": "一天兩次（早晚）",
    "三餐": "一天三次（三餐）",
    "三餐飯後": "一天三次（三餐飯後）",
    "三餐飯前": "一天三次（三餐飯前）",
    "睡前": "睡前一次",
    "需要時": "需要時服用",
}

# ── 用法縮寫（飯前飯後） ──────────────────────────────────
_USAGE_MAP = {
    "AC": "飯前",
    "PC": "飯後",
    "HS": "睡前",
    "QHS": "睡前",
    "PO": "口服",
    "IV": "靜脈注射",
    "IM": "肌肉注射",
    "SC": "皮下注射",
    "SL": "舌下含服",
    "TOP": "外用",
    "PR": "塞劑",
}

# ── 劑量單位：英文 / 縮寫對照 ───────────────────────────
_DOSAGE_UNIT_NORMALIZE = [
    (re.compile(r"(\d+(?:\.\d+)?)\s*tabs?\b", re.IGNORECASE), r"\1 錠"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*caps?\b", re.IGNORECASE), r"\1 顆"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*pills?\b", re.IGNORECASE), r"\1 顆"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*cc\b", re.IGNORECASE), r"\1 ml"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*ml\b", re.IGNORECASE), r"\1 ml"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.IGNORECASE), r"\1 mg"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE), r"\1 g"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*mcg\b", re.IGNORECASE), r"\1 μg"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*ug\b", re.IGNORECASE), r"\1 μg"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*iu\b", re.IGNORECASE), r"\1 IU"),
    # 1# / 1＃ → 1 顆（台灣藥單常見符號）
    (re.compile(r"(\d+(?:\.\d+)?)\s*[#＃]"), r"\1 顆"),
    # 1.0 → 1（去掉小數點為 0 的尾巴）
    (re.compile(r"(\d+)\.0+\b"), r"\1"),
]


def _strip_or_none(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def normalize_frequency(raw) -> Optional[str]:
    """把藥單上的頻率字串對應到統一中文表達。

    例：
      ``"BID"`` → ``"一天兩次"``
      ``"q8h"`` → ``"每 8 小時一次"``
      ``"一天三次"`` → ``"一天三次"`` （已是標準形不變）
      ``"PRN"`` → ``"需要時服用"``
    找不到對應就回原值（已 trim）。
    """
    text = _strip_or_none(raw)
    if text is None:
        return None
    upper = re.sub(r"\s+", "", text).upper()
    if upper in _FREQ_MAP:
        return _FREQ_MAP[upper]
    # 變體：每\d+小時 / Q\d+H 通用處理
    m = re.match(r"^Q(\d+)H$", upper)
    if m:
        return f"每 {m.group(1)} 小時一次"
    m = re.search(r"每\s*(\d+)\s*小時", text)
    if m:
        return f"每 {m.group(1)} 小時一次"
    # 「一日三次」等變體 → 「一天 N 次」
    text2 = text.replace("一日", "一天").replace("每天", "一天").replace("每日", "一天")
    return text2


def normalize_dosage(raw) -> Optional[str]:
    """單位寫法統一：5cc → 5 ml、500MG → 500 mg、1# → 1 顆。"""
    text = _strip_or_none(raw)
    if text is None:
        return None
    out = text
    for pat, repl in _DOSAGE_UNIT_NORMALIZE:
        out = pat.sub(repl, out)
    # 收掉多餘空白
    out = re.sub(r"\s+", " ", out).strip()
    return out


def normalize_usage(raw) -> Optional[str]:
    """飯前 / 飯後 / 睡前等用法縮寫換成中文。"""
    text = _strip_or_none(raw)
    if text is None:
        return None
    upper = re.sub(r"\s+", "", text).upper()
    if upper in _USAGE_MAP:
        return _USAGE_MAP[upper]
    # 拆組合：例如 "AC PO" → "飯前 口服"
    parts = re.split(r"[,，;；\s]+", text)
    pieces = []
    for p in parts:
        u = re.sub(r"\s+", "", p).upper()
        pieces.append(_USAGE_MAP.get(u, p))
    return " ".join([p for p in pieces if p])


def normalize_medication(med: dict) -> dict:
    """對單筆藥物的 frequency / dosage / usage 做正規化，原值另存到 ``*_raw``。

    其他欄位（name / category / instructions / hospital / prescribed_date）不動。
    """
    if not isinstance(med, dict):
        return med
    out = dict(med)
    if "frequency" in out and out["frequency"]:
        out["frequency_raw"] = out["frequency"]
        out["frequency"] = normalize_frequency(out["frequency"]) or out["frequency"]
    if "dosage" in out and out["dosage"]:
        out["dosage_raw"] = out["dosage"]
        out["dosage"] = normalize_dosage(out["dosage"]) or out["dosage"]
    if "usage" in out and out["usage"]:
        out["usage_raw"] = out["usage"]
        out["usage"] = normalize_usage(out["usage"]) or out["usage"]
    return out

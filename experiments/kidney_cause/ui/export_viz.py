# -*- coding: utf-8 -*-
"""打包 report.json ＋ 出處帳本 ＋ 文獻對照標籤 → 單一離線 ui/index.html。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KNOWN = {  # 「病因|特徵」→ 對照標籤（與 make_report.py 同步）
    "代謝性|LBXSTR": "已知重現（PMID 27537361、30300472）",
    "代謝性|LBXSUA": "已知重現（PMID 26342044、26935413；因果反例 32579811）",
    "代謝性|LBXSGTSI": "已知重現（PMID 27537361）",
    "代謝性|LBXSGL": "標籤鄰近（標籤含 HbA1c；敏感度已排除重跑）",
    "感染性|LBXSATSI": "標籤鄰近（標籤=肝炎血清，肝酶為其直接下游）",
    "感染性|LBXSASSI": "標籤鄰近（同上）",
    "感染性|LBXSGTSI": "標籤鄰近（同上）",
    "感染性|LBXSGB": "已知一致（慢性病毒性肝炎多株高球蛋白）",
    "免疫性|sex": "已知一致（自體免疫女性優勢）",
}

R = json.load(open(os.path.join(ROOT, "results", "report.json"), encoding="utf-8"))
prov = json.load(open(os.path.join(ROOT, "results", "provenance.json"), encoding="utf-8"))["files"]
lab_p = os.path.join(ROOT, "results", "lab_report.json")
lab = json.load(open(lab_p, encoding="utf-8")) if os.path.exists(lab_p) else None
hold_p = os.path.join(ROOT, "results", "holdout_eval.json")
hold = json.load(open(hold_p, encoding="utf-8")) if os.path.exists(hold_p) else None
pack = dict(report=R, provenance_files={k: dict(url=v["url"], sha256=v["sha256"][:16], bytes=v["bytes"]) for k, v in sorted(prov.items())},
            known_tags=KNOWN, lab=lab, holdout=hold)
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
out = tpl.replace("__PACK_JSON__", json.dumps(pack, ensure_ascii=False, separators=(",", ":")))
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(out)
print(f"[ui] index.html {os.path.getsize(os.path.join(HERE,'index.html'))/1024:.0f} KB")

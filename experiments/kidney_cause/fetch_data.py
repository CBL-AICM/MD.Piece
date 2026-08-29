# -*- coding: utf-8 -*-
"""下載 params/manifest.json 列出的真實公開檔案 → data/raw/，逐檔寫出處帳本（URL＋SHA256＋位元組數）。
    python fetch_data.py [--only key1,key2]
manifest 由資料查證工作流的結果產生（results/data_scout.json → make_manifest.py）；
本腳本**只下載、不生成**——任何本地創造的資料都進不了帳本，也就過不了 require_real()。"""
import argparse
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from provenance import record  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
UA = {"User-Agent": "Mozilla/5.0 (research; kidney-cause pipeline; contact: local)"}


def fetch(key, url, retries=3):
    os.makedirs(RAW, exist_ok=True)
    dest = os.path.join(RAW, key)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[fetch] 已存在 {key}（{os.path.getsize(dest)/1024:.0f} KB）——不重抓，帳本沿用")
        return dest
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(dest + ".part", dest)
            rec = record(dest, url)
            print(f"[fetch] {key}  {rec['bytes']/1024:.0f} KB  sha256 {rec['sha256'][:16]}…")
            return dest
        except Exception as e:
            print(f"[fetch] {key} 第 {k+1} 次失敗：{e}")
            time.sleep(2 * (k + 1))
    print(f"[fetch] ✗ {key} 放棄（{url}）——照實記錄，不以任何替代資料填補")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default=None)
    a = ap.parse_args()
    man_p = os.path.join(ROOT, "params", "manifest.json")
    if not os.path.exists(man_p):
        raise SystemExit("尚無 params/manifest.json——先由 results/data_scout.json 產生（make_manifest.py）")
    man = json.load(open(man_p, encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    ok, fail = [], []
    for key, row in man["files"].items():
        if only and key not in only:
            continue
        (ok if fetch(key, row["url"]) else fail).append(key)
    print(f"[fetch] 完成 {len(ok)}；失敗 {len(fail)}" + (f"：{fail}" if fail else ""))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()

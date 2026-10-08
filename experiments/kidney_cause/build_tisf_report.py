# -*- coding: utf-8 -*-
"""臺灣國際科學展覽研究報告——與研究計畫書 V3 同源（build_plan_v3.build），數字全由結果檔產生。
    python build_tisf_report.py [--force]
改動只有：附件三封面；壹之一、二換成研究者本人所寫之研究動機（docs/tisf_motivation.md，逐字照用，不代寫）；
計畫書原動機段之背景文字併入壹之三；刪去計畫書才有的「研究進度」「待研究者填寫」；「本計畫書」改「本報告」。
輸出：Obsidian 主稿 研究計畫書/臺灣國際科展研究報告.md（已修改時預設不覆蓋）與 repo 副本 experiments/docs/臺灣國際科展研究報告.md。"""
import os
import re
import sys

import build_fair_v3_2 as F
import build_plan_v3 as P
import nine_causes_section as N

NAME = "臺灣國際科展研究報告"
MOTIVATION = os.path.join(F.ROOT, "docs", "tisf_motivation.md")
KEYWORDS = "腎臟病因檢驗判斷、人工智慧醫療、反向因果"                      # 研究者原封面之關鍵詞


def build(fmt):
    t = P.build(fmt)
    head, body = t.split("\n## 摘要\n", 1)
    title = re.match(r"# (.+)\n", head).group(1)
    assert title == F.TITLE
    mot_old = P.cut(body, "### 一、研究動機\n", "### 二、研究背景與文獻回顧")
    bg = mot_old.split("\n> ⚠️ **待填寫**")[0].strip()
    assert "待填寫" not in bg and bg.startswith("腎臟病的病因評估")
    mine = open(MOTIVATION, encoding="utf-8").read().strip()
    body = body.replace(f"### 一、研究動機\n{mot_old}### 二、研究背景與文獻回顧\n",
                        f"{mine}\n\n### 三、研究背景與文獻回顧\n\n{bg}\n")
    prog = P.cut(body, "### 二、研究進度\n", "### 三、附錄")
    body = body.replace(f"### 二、研究進度\n{prog}### 三、附錄", "### 二、附錄")
    abs_old = body.split("## 壹、研究動機")[0].rstrip("\n")
    nine = ("另以事前提交之分析計畫檢驗九種病因中 NHANES 量得到的七項：調整年齡、性別、種族後，腎損傷成人較常見者依序為"
            + "、".join(f"{N.nm(d)}（{N.P[d]['contrasts']['腎損傷']['aPR']['est']:.2f}）" for d in N.HIGHER)
            + "，B 型肝炎無法區分，七項皆與文獻預期一致。")
    body = body.replace(abs_old, abs_old + nine, 1)
    body = body.replace("本計畫書", "本報告")
    for bad in ("待填寫", "待研究者填寫", "研究進度", "計畫書"):
        assert bad not in body, bad
    cover = f"""附件三

**研究報告封面**

**2027 年臺灣國際科學展覽**

**研究報告**

區別：

科別：生物及醫學科（動物與醫學組）

作品名稱：{title}

關鍵詞：{KEYWORDS}

編號：

（編號由國立臺灣科學教育館統一填列）

<!-- 分頁 -->
"""
    return f"{cover}\n# {title}\n\n## 摘要\n{body}"


def main():
    fm = ("---\ntitle: 臺灣國際科展研究報告\ntype: 研究報告\ncreated: 2026-10-08\nsource: 研究計劃書V_3（同源產生）\n"
          "tags: [腎病病因, 科展, 臺灣國際科展]\n---\n\n")
    note = ("> [!info] 由 `experiments/kidney_cause/build_tisf_report.py` 產生，與研究計畫書 V3 同源，數字全由結果檔產生。"
            "研究動機為研究者本人原文（docs/tisf_motivation.md）。Word 以 `md2docx.py <本檔> --fair` 轉出。\n\n")
    P.write(os.path.join(F.VAULT, f"{NAME}.md"), fm + note + build("vault"), guard=True)
    repo = ("> 臺灣國際科展研究報告（與 [科展計畫書_v3](科展計畫書_v3.md) 同源產生之副本）\n\n" + build("repo"))
    P.write(os.path.join(F.REPO_DOCS, f"{NAME}.md"), repo, guard=False)


if __name__ == "__main__":
    main()

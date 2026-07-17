#!/usr/bin/env python3
"""digest.py — 把 raw/<topic>/ 的零碎資料丟給 AI 整理，輸出到 knowledge/<topic>/

用法：
  python scripts/digest.py                    # 處理所有 topic
  python scripts/digest.py --topic mdpiece    # 只處理指定 topic
  python scripts/digest.py --topic personal --update  # 附上現有 wiki 做增量更新
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "raw"
KNOWLEDGE_DIR = ROOT / "knowledge"

sys.path.insert(0, str(ROOT))

_DIGEST_SYSTEM = """你是一個知識整理助手。使用者會丟給你一批零碎的筆記、文章、或資料，
請整理成結構清晰的 Markdown wiki 頁面。

輸出格式要求：
1. 用 ## 標題分區，每個核心概念一個區塊
2. 每個概念寫 2~4 句精簡摘要，說明「是什麼」和「為什麼重要」
3. 在文末加一個「## 概念關聯」區塊，說明這些概念之間的關係
4. 在文末加一個「## 知識缺口」區塊，列出目前資料裡還缺少的面向

語言：繁體中文（技術術語可保留英文）
風格：精簡、準確，不要廢話"""

_UPDATE_SYSTEM = """你是一個知識整理助手。使用者會提供：
1. 現有的 wiki（已整理好的知識庫）
2. 新的零碎資料

請把新資料整合進現有 wiki：
- 新概念：加入對應的 ## 區塊
- 補充現有概念：直接更新該區塊的內容
- 更新「## 概念關聯」和「## 知識缺口」

輸出整份更新後的 wiki（不是 diff，是完整的新版本）。
語言：繁體中文（技術術語可保留英文）"""


def read_raw_files(topic_dir: Path) -> str:
    """讀取 topic_dir 裡所有 .md .txt 文字檔，合併成一個字串。"""
    parts = []
    for ext in ("*.md", "*.txt"):
        for f in sorted(topic_dir.glob(ext)):
            text = f.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                parts.append(f"=== {f.name} ===\n{text}")
    return "\n\n".join(parts)


def read_existing_wiki(topic: str) -> str:
    wiki_path = KNOWLEDGE_DIR / topic / "wiki.md"
    if wiki_path.exists():
        return wiki_path.read_text(encoding="utf-8").strip()
    return ""


def save_wiki(topic: str, content: str):
    out_path = KNOWLEDGE_DIR / topic / "wiki.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"<!-- 最後更新：{ts} -->\n\n"
    out_path.write_text(header + content, encoding="utf-8")
    print(f"  → 已儲存：{out_path.relative_to(ROOT)}")


def digest_topic(topic: str, update: bool = False):
    topic_dir = RAW_DIR / topic
    if not topic_dir.exists():
        print(f"[跳過] raw/{topic}/ 不存在")
        return

    raw_text = read_raw_files(topic_dir)
    if not raw_text.strip():
        print(f"[跳過] raw/{topic}/ 裡沒有 .md 或 .txt 檔案")
        return

    print(f"[處理] {topic}（{len(raw_text)} 字元）")

    try:
        from backend.services.llm_service import call_claude
    except ImportError as e:
        print(f"  [錯誤] 無法 import llm_service：{e}")
        print("  請確認已安裝 backend 依賴，並在專案根目錄執行此腳本")
        return

    existing = read_existing_wiki(topic) if update else ""

    if update and existing:
        system = _UPDATE_SYSTEM
        user_msg = f"## 現有 wiki\n\n{existing}\n\n---\n\n## 新的零碎資料\n\n{raw_text}"
    else:
        system = _DIGEST_SYSTEM
        user_msg = raw_text

    try:
        result = call_claude(system, user_msg, max_tokens=4000)
    except Exception as e:
        print(f"  [錯誤] LLM 呼叫失敗：{e}")
        return

    save_wiki(topic, result)


def main():
    parser = argparse.ArgumentParser(description="raw/ → knowledge/ 知識整理腳本")
    parser.add_argument("--topic", help="指定 topic（預設處理所有 topic）")
    parser.add_argument("--update", action="store_true", help="增量更新模式（保留現有 wiki 並整合新資料）")
    args = parser.parse_args()

    if args.topic:
        digest_topic(args.topic, update=args.update)
    else:
        topics = [d.name for d in sorted(RAW_DIR.iterdir()) if d.is_dir()]
        if not topics:
            print("raw/ 下沒有任何 topic 資料夾")
            return
        for topic in topics:
            digest_topic(topic, update=args.update)


if __name__ == "__main__":
    main()

# 2026-10-18 全面審核（數據、文獻、圖表）

審核兩份 Word 文件（科展作品說明書含切片九種病因與英文摘要版、研究報告 V3 整合版含 GEO 去 AI 化版）。報告：`全面審核報告_20261018.md`。

腳本在副本目錄執行（`extract.py` 先抽出 docx → JSON）：
- `refcheck.py`：DOI → Crossref 書目比對、網址檢查、內文引用 ↔ 文獻清單
- `align.py`：重跑 build_fair_award／build_tisf_report，逐段比對數字序列
- `claims.py`：新寫段落（GEO、九種病因、檔案數）逐項由結果檔重算比對
- `recompute_c.py`：immune_geo 修正二獨立重算（不 import 主程式），輸出 `recompute_c_out.json`
- `cellpaths.py`、`numcheck.py`：數值索引（太寬鬆，只作輔助，未採為判定依據）

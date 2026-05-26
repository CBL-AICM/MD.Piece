import concurrent.futures
import json
import logging
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.db import get_supabase
from backend.services.llm_service import (
    build_patient_facing_system,
    call_claude,
    compute_patient_context,
    stream_claude,
)

# Vercel lambda 上限 60s — LLM provider 全卡死的最壞情況可能逼近這個額度，
# 一旦 lambda 被砍掉，前端 fetch 永遠不 resolve（HTTP 000 + 連線 hang），
# 使用者就看到「撰寫中…」轉圈圈沒下文。用 thread + 硬超時鎖在 45s 內，
# 超時就走 raw-data fallback，讓 HTTP 一定有回應。
_LLM_HARD_TIMEOUT_S = 45
_LLM_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _call_claude_bounded(system_prompt: str, user_message: str) -> str:
    """call_claude 加 45s 硬超時。超時 / 失敗都 raise，上層自行 fallback。"""
    fut = _LLM_EXECUTOR.submit(call_claude, system_prompt, user_message)
    return fut.result(timeout=_LLM_HARD_TIMEOUT_S)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 問診清單 prompt（病人會直接看到 → 套用風格層） ───────────

CHECKLIST_ROLE_PROMPT = (
    "【本次任務：問診清單】\n"
    "根據病人近期的症狀紀錄、情緒、用藥情形，列出這次回診時最需要跟醫師確認的三件事。\n\n"
    "情境專屬規則：\n"
    "1. 只列三件，依重要性排序\n"
    "2. 每件事用一句話描述，讓病人可以照著問醫師\n"
    "3. 用「想問醫師」的口吻，不要用「我覺得你應該…」這種命令句\n"
    "4. 不要塞百分比、不要丟風險分數（遵守風格層 [A.2]）\n"
    "5. 回覆格式：**純 JSON 陣列**，每個元素是一個字串，**不要 markdown、不要前後說明**\n"
    "   （這個輸出會被機器解析，所以這次例外：不需要在末尾加免責聲明文字 — 系統會另外處理）\n\n"
    "範例輸出：\n"
    '["最近頭痛比以前頻繁，想問醫師要不要調整止痛藥？",'
    '"情緒持續比較低落，想請醫師看要不要轉介心理支持？",'
    '"新藥吃完會胃不舒服，這是正常的嗎？要怎麼處理？"]'
)

# ── 整合摘要 prompt（v5：七條改善 — 資料一致性、PRN 分流、MOH 風險、三大重點、信心度、假設化、紀錄/AI 標示） ────
#
# 設計目標：一份「帶去診間用的整合摘要」同時服務醫師判讀與病人遞交，
# 風格類似住院醫師 / PA 的交班 + chief-complaint 呈報。
# 七段（§〇 + §一~§六）口吻分配：
#   §〇 三大重點：第三人稱，30 秒掃完
#   §一 主訴：第一人稱「我」（病人視角）
#   §二 資料整理：第三人稱（純事實）
#   §三、四、六：第三人稱（AI 摘要）
#   §五 想請醫師確認：條列，第一/第三人稱混用
#
# 紅線：
#   - 不替醫師下診斷、不點特定病名
#   - 不寫未來預測
#   - 不開藥、不寫劑量、不指示加減藥
#   - 病人主訴段不替自己歸因
#   - 跨指標關聯一律寫成「待驗證假設」，不可寫成因果結論
#
# 七條改善（規則 A–G）：
#   A 資料一致性 — 所有數字只能引用 user message【已計算統計】，禁止 LLM 自行重算
#   B PRN 分流 — 需要時藥（止痛藥）禁止寫服藥率，改寫使用天數/總劑量
#   C MOH 風險訊號 — 止痛藥月度 ≥15 天必出 MOH 風險訊號條
#   D 三大重點 — §〇 最多三行，依嚴重度排序，挑風險旗標
#   E 信心度 — confidence==low（涵蓋天數 < 30% 或 n ≤ 3）禁止寫趨勢
#   F 假設化措辭 — 跨指標共動寫成「待驗證假設」
#   G 紀錄/AI 標示 — 每段標題末加【紀錄】或【AI 摘要】

INTEGRATED_SUMMARY_PROMPT = (
    "【本次任務：診前整合摘要】\n"
    "把病人本期間的紀錄整合成一份「三大重點＋主訴＋資料整理＋觀察＋風險＋建議＋綜合判斷」的文件。\n"
    "這份摘要會由病人帶進診間遞給醫師，也可能由病人念給醫師聽 — 所以同時要醫師讀得懂、"
    "病人也唸得出口。風格：像住院醫師／PA 向主治交班，先講三大重點、再 chief complaint、再做資料整理。\n\n"
    "報告期間會在 user message 開頭以「報告期間：XXX」給出，請依該期間描述，不要假定 30 天。\n"
    "user message **第一個區塊**會是「## 已計算統計（請只使用以下數字，不要自行重算）」，\n"
    "後面才是「症狀／情緒／用藥／飲食…」等 raw 資料區塊。\n\n"
    "═══ 七條必守規則（違反任一條視為輸出失敗）═══\n\n"
    "【規則 A — 數據一致性】\n"
    "所有統計數值（次數、平均、比率、走向方向、天數、劑量）**只能引用 user message 內**\n"
    "「## 已計算統計」區塊提供的數字，**禁止自行重新推導、估算或從其他段落反推**。\n"
    "產出後逐項自我檢查：文字段提到的每個數字，必須與【已計算統計】完全一致。\n"
    "若發現任一不一致，停止並回報「數據不一致：__」，不要輸出報告。\n\n"
    "【規則 B — 藥物類型分流】\n"
    "依藥物類型分開呈現：\n"
    "- **scheduled（固定每日服用）**：使用「服藥率 = 實際/應服次數」\n"
    "- **prn（需要時服用，as-needed）**：**禁止計算或寫出服藥率**（無分母）。\n"
    "  改為呈現：本期使用天數、每週使用天數、總劑量、單日最高劑量\n"
    "【已計算統計】已按 type 標註，請依該分類撰寫，不要把 prn 藥當 scheduled。\n\n"
    "【規則 C — 止痛藥過度使用風險訊號】\n"
    "若 user message 的【已計算統計】中標記為「analgesic: true」的藥物，\n"
    "其「本期月度推算使用天數」≥ 15 天，**必須**在「四、風險訊號」段列出一條：\n"
    "  「__藥本期月度推算使用 __ 天（累計 __ mg），建議醫師評估是否有藥物過度使用性頭痛之可能」\n"
    "措辭只能用上面這句的變體，**不得直接下任何診斷**。\n\n"
    "【規則 D — §〇 本次三大重點】\n"
    "報告開頭產生「## 〇、本次三大重點【AI 摘要】」方塊，**最多三行，每行一句**。\n"
    "依嚴重度排序（從【已計算統計】的「風險旗標」由上往下挑），\n"
    "挑選本期最需要醫師注意的變化。語氣為**中性事實陳述**，不含建議或診斷。\n"
    "若【已計算統計】的「風險旗標」少於 3 條，三大重點段就少於 3 條。\n\n"
    "【規則 E — 資料信心度】\n"
    "每個指標在【已計算統計】中會給出 confidence 標籤（\"ok\" 或 \"low\"）。\n"
    "若 confidence == \"low\"（涵蓋天數 < 30%，或筆數 ≤ 3）：\n"
    "- 描述該指標時必須加註「（資料不足，僅供參考）」\n"
    "- **不寫趨勢方向**（連「走向：上行/下行」都不能寫，因為資料不足以判讀）\n"
    "- §三 觀察變化段對 low confidence 指標只能寫「資料量不足，未列入本期變化判讀」\n\n"
    "【規則 F — 跨指標關聯是假設不是結論】\n"
    "跨指標的關聯性（如頭痛、情緒、血壓共動）一律定位為「**待驗證的假設**」，\n"
    "不可表述為已成立的結論或因果關係。\n"
    "固定措辭範例：「本期此三項指標方向一致，**但尚無法判斷因果**，\n"
    "建議醫師評估是否需進一步同步監測以驗證。」\n"
    "禁用：「因為 A 所以 B」「A 造成 B」「A 與 B 相關」（後者隱含已驗證）。\n\n"
    "【規則 G — 紀錄 vs AI 摘要 標示】\n"
    "每段標題**必須**在最末加上以下其中一個標籤：\n"
    "- 直接來自病人自填資料的事實 → 加「【紀錄】」\n"
    "- 演算法的整理、推論、判斷 → 加「【AI 摘要】」\n"
    "標籤對應（**完全照抄，不要改字也不要改順序**）：\n"
    "  §〇 三大重點 →【AI 摘要】\n"
    "  §一 主訴 →【紀錄】\n"
    "  §二 資料整理 →【紀錄】\n"
    "  §三 本期觀察到的變化 →【AI 摘要】\n"
    "  §四 風險訊號 →【AI 摘要】\n"
    "  §五 想請醫師確認與建議追蹤 →【紀錄】\n"
    "  §六 綜合判斷 →【AI 摘要】\n"
    "  §七 可參考方向 →【AI 摘要】\n\n"
    "【規則 H — §七 可參考方向（輔助診斷，但非診斷）】\n"
    "在【已計算統計】最末會給出「可考慮的鑑別方向」表，由 backend 規則觸發。\n"
    "§七 只能引用該表內容，**不得自行加方向、不得自行新增疾病名**。\n"
    "規則：\n"
    "- 若 backend 沒列出方向（無明顯模式）→ §七 寫一句：\n"
    "    「依本期資料尚未識別出特定鑑別重點，建議醫師於回診時做整體評估」\n"
    "- 若 backend 列出 ≥ 1 個方向 hint：每個 hint 列「資料模式 + 可考慮方向（複數）」\n"
    "- **§〇 三大重點完全禁止點名任何疾病或方向**（§〇 只能講數字事實）\n"
    "- §七 末尾必須加一句：\n"
    "    「以上僅供醫師問診切入參考，**不代表診斷**，最終判斷以醫師親自評估為準」\n"
    "- 措辭限定（**完全照抄**）：「可考慮的方向：A、B、C」、「（尚未排除）」\n"
    "- **嚴格禁止**：「病人是 X」「應該是 X」「特徵符合 X」「典型 X 表現」\n"
    "- **嚴格禁止**：只列單一方向（看起來像下單一診斷）\n\n"
    "═══ 段落輸出規格 ═══\n\n"
    "輸出格式：繁體中文 Markdown，嚴格使用以下七段、順序固定、不新增段落、結尾不加免責聲明。\n"
    "**段落標題只能用下方提供的格式**，標題後**只能**加上【規則 G】指定的標籤，"
    "不要再加任何括號註記（『（病人視角）』『（給醫師交班用）』等都是內部提示，禁止寫進輸出）。\n\n"
    "## 〇、本次三大重點【AI 摘要】\n"
    "最多 3 條條列，每條一句、依嚴重度排序（從【已計算統計】風險旗標由上往下挑）。\n"
    "語氣**純數字 + 走向 + 事實**，**完全禁止**點名任何疾病或鑑別方向\n"
    "（鑑別方向只能寫進 §七，§〇 不出現任何病名／方向關鍵字）。範例：\n"
    "- 止痛藥療效評分由 3.5 降到 2.1，同期本期使用 14 天（月度推算 14 天）\n"
    "- 情緒評分連續 4 次低於 2\n"
    "- 血壓家庭量測本期間 3 次達 ≥140/90\n\n"
    "## 一、主訴【紀錄】\n"
    "用 2–4 句、第一人稱「我」書寫，像病人開口跟醫師講最困擾的事。\n"
    "只寫病人主觀感受到的核心問題（最不舒服的症狀、頻率、對生活的影響），\n"
    "不放數值、不放百分比、不下臨床判斷。**絕對不要替病人歸因**\n"
    "（不要寫「我覺得應該是壓力大造成的」「應該是因為 X」這種因果推論句；\n"
    "只描述感受，原因留給醫師判斷）。範例語氣：\n"
    "「醫師我這個月最困擾的是反覆頭痛，幾乎每週都來個兩三天，痛起來連工作都做不下去。」\n\n"
    "## 二、資料整理【紀錄】\n"
    "切換成第三人稱，像在跟主治交班，把本期間散落的資料串起來看 — 純資料彙整，**不下判讀**。\n"
    "用 4–10 個條列，每點一句話，涵蓋（有資料才寫）：\n"
    "- 症狀模式：高頻症狀、新增、已改善（low confidence 套規則 E）\n"
    "- 情緒走向：平均、是否連續低落（low confidence 不寫方向、套規則 E）\n"
    "- 用藥（依 type 分流寫，套規則 B）：\n"
    "    · scheduled 藥：藥名 + 服藥率 + 療效評分\n"
    "    · prn 藥：藥名 + 本期使用天數 + 月度推算 + 累計劑量（**不寫服藥率**）\n"
    "- **用藥變更**：本期間有沒有停藥/加藥/劑量調整/換藥\n"
    "- **住院/長期療程**：本期間有沒有急性住院或長期療程施打紀錄\n"
    "- 飲食規律度，以及與【慢性病登記】之飲食禁忌是否相符（low confidence 套規則 E）\n"
    "- 慢性病登記 + 過敏史 與本期紀錄的交集點\n"
    "- 即將回診排程銜接\n"
    "**只整理事實，不下推論**（不要寫「此型態與 X 一致」「呈現典型 Y」這種暗示性結論）。\n\n"
    "## 三、本期觀察到的變化【AI 摘要】\n"
    "用 2–4 個條列，把資料的「方向」說清楚 — **只描述本期內已發生的走向**，不做未來預測：\n"
    "- 整體狀態：穩定/需留意/需盡快與醫師討論（用分級詞，不用 % 數字）\n"
    "- 各指標的方向：「症狀頻率從前 14 天的 X 次上升到後 14 天的 Y 次」、\n"
    "  「療效評分由 4 降到 2」這種**已觀察到**的變化\n"
    "- **low confidence 指標不寫方向**（套規則 E），可寫「資料量不足，未列入本期變化判讀」\n"
    "- 點出「目前資料還不足以判斷」的部分，明說需要哪類資料才能下一步\n"
    "**嚴格禁止**：「預期會」「可能演變為」「若維持此模式，會 ...」「預後不佳」「復發機率 X%」"
    "等任何未來推論/預測診斷的措辭。\n\n"
    "## 四、風險訊號【AI 摘要】\n"
    "這段主動點出病人可能還沒意識到的客觀訊號 — **只列事實型紅旗**，不點病名、不暗示診斷。\n"
    "用 2–5 個條列：\n"
    "- 服藥率 < 70%、療效評分多次 ≤ 2、情緒連續 3 次以上 ≤ 2、副作用回報、\n"
    "  飲食與慢性病禁忌衝突、過敏史與本期用藥/飲食衝突、生理指標（血壓/血糖）異常\n"
    "- **規則 C 觸發時必出 MOH 條**（止痛藥月度使用 ≥ 15 天，措辭限定）\n"
    "- 寫法限於「事實 + 為何值得醫師關注」，例如：\n"
    "    ✓「止痛藥本期使用 18 天、月度推算 18 天，建議醫師評估是否有藥物過度使用性頭痛之可能」\n"
    "    ✓「血壓家庭量測本期間 3 次偏高，建議醫師於回診時複查」\n"
    "    ✗「特徵與偏頭痛慢性化一致」「符合憂鬱症篩檢條件」「應該是 X」\n"
    "- 若本期間真的無顯著訊號，寫「本期間無顯著風險訊號，整體呈穩定」一句，不要敷衍\n\n"
    "## 五、想請醫師確認與建議追蹤【紀錄】\n"
    "輸出兩個小段，子標題請**只用以下文字**，不要加任何括號註記：\n"
    "**想請醫師確認的事** — 條列 2–4 點，第一人稱「我想請教醫師…」、「我想知道…」口吻：\n"
    "  「我想請教醫師 ___ 是不是需要調整？」「我想知道 ___ 算不算正常？」這種口吻。\n"
    "**建議追蹤項目** — 條列 2–4 點，具體可量化的追蹤項目：\n"
    "  例如「建議追蹤血壓家庭量測連續 2 週、每日早晚」、\n"
    "  「建議下次回診重新評估藥物 X 的療效（病人★評分偏低）」。\n"
    "  **不寫**：開藥建議、劑量調整、停藥/加藥指示。\n\n"
    "## 六、綜合判斷【AI 摘要】\n"
    "**這段是給醫師看的整體性回顧**，把前面散落的資料串成一個視角：目前的治療策略，"
    "從病人這 N 天的資料看下來，**有哪些方向值得醫師回診時重新評估**。\n"
    "用 4–6 個條列，每點 1–2 句，需涵蓋（有資料才寫）：\n"
    "- **藥物治療的成效訊號**：各主要藥物的療效評分走向、服藥率/使用天數、副作用回報\n"
    "- **跨指標互動（規則 F：定位為待驗證假設）**：症狀/情緒/飲食/生理指標之間有沒有共動關係\n"
    "    措辭限定：「本期此 N 項指標方向一致，**但尚無法判斷因果**，建議醫師評估是否需進一步同步監測以驗證」\n"
    "    禁用：「相關」「造成」「因為 A 所以 B」等已驗證關係的措辭\n"
    "- **資料缺口與下一步建議**：明說缺哪類資料、需要病人補記什麼\n"
    "- **整體生活負擔**：以病人主觀生活品質角度，本期間整體負擔的方向感（仍可工作/影響日常/已嚴重干擾）\n"
    "**語氣分寸**（重要）：\n"
    "  ✓「目前的治療策略需要醫師於回診時重新評估」\n"
    "  ✓「現有資料尚不足以支持後續決策，建議醫師判斷是否需要追加 ___ 檢查」\n"
    "  ✓「跨指標訊號方向一致，但尚無法判斷因果，建議醫師整體評估」\n"
    "  ✗「治療失敗」「應加藥」「應換藥」「明顯失效」「應立即停藥」\n"
    "  ✗ §六**不點特定病名**（病名／鑑別方向只能寫進 §七）、不下診斷、不給未來預測\n\n"
    "## 七、可參考方向【AI 摘要】\n"
    "**這段是「輔助診斷」性質的方向 hint — 給醫師問診切入用，非診斷**。\n"
    "依【規則 H】產出（措辭限定、必須複數方向、結尾必有 disclaimer 一句）。\n"
    "格式範本：\n"
    "  「**資料模式**：__（從 backend hint 抄）\n"
    "   **可考慮的方向**：__、__、__（從 backend hint 抄）」\n"
    "（每個 backend hint 各列一組「資料模式 + 可考慮的方向」）\n"
    "段末必加一句免責：\n"
    "  「以上僅供醫師問診切入參考，**不代表診斷**，最終判斷以醫師親自評估為準」\n"
    "若 backend 沒列方向：只寫一句\n"
    "  「依本期資料尚未識別出特定鑑別重點，建議醫師於回診時做整體評估」\n"
    "（搭配規則 H 的禁用列表）\n\n"
    "═══ 全文規則 ═══\n"
    "- 繁體中文 + Markdown 二級標題（##）+ 條列\n"
    "- 八段（§〇 + §一 ~ §七）都要寫；有資料就寫得詳細、沒資料就誠實註明「本期間無相關紀錄」\n"
    "- 不要在結尾加 AI 免責聲明（§七 disclaimer 除外，那是規則 H 內建），系統會另外渲染\n"
    "- 不要在開頭加前言或標題，第一行直接是「## 〇、本次三大重點【AI 摘要】」\n"
    "- 全文字數約 1100–1700 字\n"
    "- **全文禁止**：自行重算【已計算統計】內的數字、§〇 ~ §六 任何特定病名、未來預測句、開藥/停藥/改劑量指示、"
    "病人替自己歸因的因果推論、把跨指標關聯講成已驗證的因果"
)


# ── 藥物分類 + 預計算助手 ────────────────────────────────────
#
# 規則 5（從 CLAUDE.md）：能用程式碼確定性決定的，就不要交給 LLM。
# 所有「資料一致性、PRN/scheduled 分流、信心度、MOH 觸發」等判斷一律 backend 算好，
# 包成「## 已計算統計」區塊塞進 user message 第一段；LLM 只負責挑、寫、組織語氣。

ANALGESIC_KEYWORDS = (
    "acetaminophen", "paracetamol", "普拿疼", "tylenol", "panadol",
    "ibuprofen", "advil", "motrin",
    "naproxen", "aleve",
    "aspirin", "diclofenac", "voltaren",
    "mefenamic", "ponstan",
    "止痛",
)

PRN_KEYWORDS = (
    "需要時", "prn", "as needed", "as-needed",
    "視需要", "依需要", "視情況", "頭痛時", "疼痛時",
)


def _classify_medication(med: dict) -> str:
    """從 frequency 字串判斷 PRN vs scheduled。
    PRN keywords 命中 → "prn"；否則 → "scheduled"（包含沒填 frequency 的情況）。
    """
    freq = (med.get("frequency") or "").lower()
    if any(k in freq for k in PRN_KEYWORDS):
        return "prn"
    return "scheduled"


def _is_analgesic(med: dict) -> bool:
    """從藥名判斷是否為止痛類（規則 C MOH 風險訊號用）。"""
    name = (med.get("name") or "").lower()
    return any(k in name for k in ANALGESIC_KEYWORDS)


_DOSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|μg)", re.IGNORECASE)


def _extract_dose_mg(dosage: str | None) -> float | None:
    """從 dosage 字串解析 mg 值。'500mg' → 500.0、'1g' → 1000.0、'250 mcg' → 0.25。"""
    if not dosage:
        return None
    m = _DOSE_RE.search(str(dosage))
    if not m:
        return None
    try:
        n = float(m.group(1))
    except (TypeError, ValueError):
        return None
    unit = m.group(2).lower()
    if unit == "mg":
        return n
    if unit == "g":
        return n * 1000.0
    if unit in ("mcg", "μg"):
        return n / 1000.0
    return n


def _indicator_confidence(n: int, covered_days: int, period_days: int) -> tuple[str, str]:
    """信心度規則（規則 E）：n ≤ 3 或 涵蓋天數 < 30% → low；其餘 ok。
    回傳 (label, note_string) — label is "ok" or "low".
    """
    if not period_days:
        return ("low", "資料不足")
    coverage_pct = covered_days / period_days * 100
    if n <= 3 or coverage_pct < 30:
        return ("low", f"資料不足（{n} 筆, 涵蓋 {covered_days}/{period_days} 天 {coverage_pct:.0f}%）")
    return ("ok", f"{n} 筆, 涵蓋 {covered_days}/{period_days} 天 {coverage_pct:.0f}%")


def _parse_iso_safe(s: str | None) -> datetime | None:
    """從 ISO datetime 字串解析，失敗回 None。"""
    if not s:
        return None
    try:
        # Supabase 回的可能是 'YYYY-MM-DDTHH:MM:SS+00:00' 或 'YYYY-MM-DDTHH:MM:SS.fffZ'
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _build_precomputed_stats(
    *,
    days: int,
    period_label: str,
    symptoms_data: list,
    emotions_data: list,
    active_meds: list,
    med_logs_data: list,
    effects_data: list,
    diet_data: list,
    admissions_data: list,
    med_changes_data: list,
) -> tuple[str, list[str]]:
    """產出「## 已計算統計」block 字串 + 排序好的風險旗標 list。

    所有統計都在這裡算好，LLM 不重算（規則 A 的程式碼保證）。
    回傳 (precomputed_text, risk_flags) — risk_flags 按嚴重度排序，
    最嚴重的（含 MOH）放最前，§〇 三大重點請從上往下挑。
    """
    parts = ["## 已計算統計（請只使用以下數字，不要自行重算）"]
    parts.append(f"報告期間：{period_label}（共 {days} 天）")
    parts.append("")
    risk_flags: list[str] = []

    # ── 症狀 ──
    if symptoms_data:
        sym_days = {(s.get("created_at") or "")[:10] for s in symptoms_data if s.get("created_at")}
        sym_days.discard("")
        conf_label, conf_note = _indicator_confidence(len(symptoms_data), len(sym_days), days)
        parts.append(f"### 症狀（confidence: {conf_label}）")
        parts.append(f"- {conf_note}")
        freq = Counter()
        for s in symptoms_data:
            syms = s.get("symptoms", [])
            if isinstance(syms, list):
                freq.update(syms)
            elif isinstance(syms, str):
                freq[syms] += 1
        top = freq.most_common(3)
        if top:
            parts.append(f"- 高頻症狀：{'、'.join(f'{n}({c})' for n, c in top)}")
        if conf_label == "ok" and days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days // 2)
            first = sum(1 for s in symptoms_data
                        if (_parse_iso_safe(s.get("created_at")) or datetime.now(timezone.utc)) < cutoff)
            second = len(symptoms_data) - first
            if first or second:
                trend = "上行" if second > first * 1.2 else ("下行" if first > second * 1.2 else "平穩")
                parts.append(f"- 前半 {first} 次 → 後半 {second} 次（走向：{trend}）")
                if second >= 5 and second >= first * 1.5:
                    risk_flags.append(f"症狀頻率上升（前半 {first} 次 → 後半 {second} 次）")
        else:
            parts.append("- ⚠ confidence: low，不寫走向")
        parts.append("")

    # ── 情緒 ──
    if emotions_data:
        emo_days = {(e.get("created_at") or "")[:10] for e in emotions_data if e.get("created_at")}
        emo_days.discard("")
        conf_label, conf_note = _indicator_confidence(len(emotions_data), len(emo_days), days)
        scores = [e.get("score") for e in emotions_data if e.get("score") is not None]
        parts.append(f"### 情緒（confidence: {conf_label}）")
        parts.append(f"- {conf_note}")
        if scores:
            avg = statistics.mean(scores)
            parts.append(f"- 平均：{avg:.1f} / 5、最低 {min(scores)}、最高 {max(scores)}")
            consec = 0
            max_consec = 0
            for s in scores:
                if s <= 2:
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0
            if max_consec >= 2:
                parts.append(f"- 連續 ≤ 2：{max_consec} 次")
                if max_consec >= 3:
                    risk_flags.append(f"情緒連續 {max_consec} 次低於 2")
            if conf_label == "ok" and len(scores) >= 4:
                mid_i = len(scores) // 2
                first_avg = statistics.mean(scores[:mid_i])
                second_avg = statistics.mean(scores[mid_i:])
                trend = "下行" if first_avg - second_avg > 0.5 else ("上行" if second_avg - first_avg > 0.5 else "平穩")
                parts.append(f"- 前半平均 {first_avg:.1f} → 後半平均 {second_avg:.1f}（走向：{trend}）")
                if avg < 2.5:
                    risk_flags.append(f"情緒整體偏低（平均 {avg:.1f}）")
        parts.append("")

    # ── 用藥（依 type 分流；規則 B、規則 C） ──
    if active_meds:
        parts.append("### 用藥（依類型分流，規則 B）")
        # logs 按 medication_id 聚合
        log_stats = {}
        for l in med_logs_data:
            mid = l.get("medication_id")
            if not mid:
                continue
            log_stats.setdefault(mid, {"total": 0, "taken": 0, "by_day": defaultdict(int)})
            log_stats[mid]["total"] += 1
            if l.get("taken"):
                log_stats[mid]["taken"] += 1
                d = (l.get("taken_at") or "")[:10]
                if d:
                    log_stats[mid]["by_day"][d] += 1
        for m in active_meds:
            mtype = _classify_medication(m)
            analgesic = _is_analgesic(m)
            tags = f"[type: {mtype}"
            if analgesic:
                tags += ", analgesic: true"
            tags += "]"
            dosage = m.get("dosage", "") or ""
            parts.append(f"- {m.get('name', '?')} {dosage} {tags}".strip())
            s = log_stats.get(m.get("id"), {"total": 0, "taken": 0, "by_day": {}})
            if mtype == "scheduled":
                if s["total"]:
                    rate = s["taken"] / s["total"] * 100
                    parts.append(f"    服藥率：{rate:.0f}%（{s['taken']}/{s['total']}）")
                    if rate < 70:
                        risk_flags.append(f"{m.get('name', '?')} 服藥率 {rate:.0f}% < 70%")
                else:
                    parts.append(f"    服藥率：本期間無服藥日誌")
            else:  # prn
                use_days = len(s["by_day"])
                monthly = round(use_days / days * 30, 1) if days else float(use_days)
                mg_per_dose = _extract_dose_mg(dosage)
                total_mg = mg_per_dose * s["taken"] if mg_per_dose else None
                max_daily_doses = max(s["by_day"].values()) if s["by_day"] else 0
                max_daily_mg = max_daily_doses * mg_per_dose if mg_per_dose else None
                parts.append(f"    本期使用 {use_days} 天（月度推算 {monthly:.0f} 天）")
                if total_mg is not None:
                    if max_daily_mg is not None:
                        parts.append(f"    累計 {total_mg:.0f} mg、單日最高 {max_daily_mg:.0f} mg")
                    else:
                        parts.append(f"    累計 {total_mg:.0f} mg")
                # 規則 C：MOH 風險訊號
                if analgesic and monthly >= 15:
                    if total_mg is not None:
                        flag = (
                            f"{m.get('name', '?')}本期月度推算使用 {monthly:.0f} 天"
                            f"（累計 {total_mg:.0f} mg），建議醫師評估是否有藥物過度使用性頭痛之可能"
                        )
                    else:
                        flag = (
                            f"{m.get('name', '?')}本期月度推算使用 {monthly:.0f} 天，"
                            "建議醫師評估是否有藥物過度使用性頭痛之可能"
                        )
                    risk_flags.insert(0, flag)  # MOH 優先級高，放最前
        parts.append("")

    # ── 藥物療效評分 ──
    if effects_data:
        by_med = defaultdict(list)
        for e in effects_data:
            mid = e.get("medication_id")
            by_med[mid].append(e)
        med_name = {m.get("id"): m.get("name", "?") for m in active_meds}
        parts.append(f"### 藥物療效評分（{len(effects_data)} 筆，1=很差 5=很好）")
        for mid, evs in by_med.items():
            # 按 recorded_at 排序，最早 → 最近
            evs = sorted(evs, key=lambda x: (x.get("recorded_at") or ""))
            scores = [e.get("effectiveness") for e in evs if e.get("effectiveness") is not None]
            if not scores:
                continue
            name = med_name.get(mid, "未知藥物")
            n_eff = len(scores)
            conf = "low" if n_eff <= 3 else "ok"
            avg = sum(scores) / len(scores)
            line = f"- {name}：平均 {avg:.1f}（n={n_eff}, confidence: {conf}）"
            if conf == "ok" and len(scores) >= 2:
                trend = "下降" if scores[0] - scores[-1] >= 1 else ("上升" if scores[-1] - scores[0] >= 1 else "平穩")
                line += f"，{scores[0]:.1f} → {scores[-1]:.1f}（走向：{trend}）"
                if avg <= 2.5:
                    risk_flags.append(f"{name} 療效評分平均 {avg:.1f} ≤ 2.5")
                if trend == "下降" and scores[-1] <= 2:
                    risk_flags.append(f"{name} 療效評分下降至 {scores[-1]:.1f}")
            elif conf == "low":
                line += "（資料不足不寫走向）"
            parts.append(line)
            sides = [(e.get("side_effects") or "").strip() for e in evs if e.get("side_effects")]
            if sides:
                parts.append(f"    副作用回報：{'; '.join(sides[:3])}")
                risk_flags.append(f"{name} 有副作用回報")
        parts.append("")

    # ── 飲食 ──
    if diet_data:
        diet_days = {(r.get("eaten_at") or "")[:10] for r in diet_data if r.get("eaten_at")}
        diet_days.discard("")
        conf_label, conf_note = _indicator_confidence(len(diet_data), len(diet_days), days)
        parts.append(f"### 飲食（confidence: {conf_label}）")
        parts.append(f"- {conf_note}")
        if conf_label == "low":
            parts.append("- ⚠ confidence: low，不寫趨勢")
        else:
            # 三餐完整度（早午晚都有 = 完整日）
            by_day_meals: dict = defaultdict(set)
            for r in diet_data:
                d = (r.get("eaten_at") or "")[:10]
                if d:
                    by_day_meals[d].add(r.get("meal_type"))
            full_days = sum(1 for v in by_day_meals.values() if {"breakfast", "lunch", "dinner"}.issubset(v))
            parts.append(f"- 三餐齊全 {full_days}/{len(diet_days)} 天")
        parts.append("")

    # ── 住院 / 用藥變更（單純列數） ──
    if admissions_data:
        parts.append(f"### 住院／長期療程：{len(admissions_data)} 筆")
        parts.append("")
    if med_changes_data:
        parts.append(f"### 用藥變更：{len(med_changes_data)} 筆")
        parts.append("")

    # ── 風險旗標總列（依嚴重度，§〇 三大重點 picks from here） ──
    if risk_flags:
        parts.append("### 風險旗標（依嚴重度排序，§〇 三大重點請依序挑前 3 條）")
        for i, f in enumerate(risk_flags[:8], 1):
            parts.append(f"{i}. {f}")
    else:
        parts.append("### 風險旗標：本期間無顯著風險旗標")
    parts.append("")

    # ── 可考慮的鑑別方向（§七 用；保守規則表 gate，謹慎使用）──
    diff_hints = _compute_differential_hints(
        symptoms_data=symptoms_data,
        emotions_data=emotions_data,
        active_meds=active_meds,
        med_logs_data=med_logs_data,
        days=days,
    )
    if diff_hints:
        parts.append("### 可考慮的鑑別方向（§七 用 — 僅作問診切入參考，**非診斷**）")
        for i, h in enumerate(diff_hints, 1):
            parts.append(f"{i}. **資料模式**：{h['trigger']}")
            parts.append(f"   **可考慮的方向**：{'、'.join(h['directions'])}")
    else:
        parts.append("### 可考慮的鑑別方向：本期資料無明顯模式組合，§七 寫「依本期資料尚未識別出特定鑑別重點，建議醫師於回診時做整體評估」")
    parts.append("")

    return "\n".join(parts), risk_flags


# ── 鑑別方向規則表（規則 H：保守、複數方向、有閾值才觸發）──
#
# 設計原則（給未來修改者）：
#   1. 只在明確模式 + threshold 同時滿足才產出一條
#   2. 每條至少給 2 個方向，避免單一指向感（看起來像下診斷）
#   3. 方向措辭盡量寫「篩檢／鑑別／尚未排除」，不寫已成立的疾病名
#   4. 規則表變更需有臨床判斷依據；不要為了 LLM「看起來聰明」加規則

def _has_symptom(symptoms_data: list, keyword: str) -> bool:
    """檢查症狀紀錄是否含特定關鍵字。"""
    for s in symptoms_data:
        syms = s.get("symptoms") or []
        if isinstance(syms, str):
            if keyword in syms:
                return True
        elif isinstance(syms, list):
            for sym in syms:
                if isinstance(sym, str) and keyword in sym:
                    return True
    return False


def _compute_differential_hints(
    *, symptoms_data: list, emotions_data: list,
    active_meds: list, med_logs_data: list, days: int,
) -> list[dict]:
    """從資料模式組合產生鑑別方向 hint（§七 用）。

    回傳 list of {trigger: str, directions: list[str]}。
    保守規則表 — 只在明顯 pattern + threshold 同時滿足才返回 hint。
    """
    hints: list[dict] = []

    # 預先算每藥的「服藥日」set
    log_days_by_med: dict = {}
    for l in med_logs_data:
        if not l.get("taken"):
            continue
        mid = l.get("medication_id")
        d = (l.get("taken_at") or "")[:10]
        if mid and d:
            log_days_by_med.setdefault(mid, set()).add(d)

    # ── H1: 頭痛 + PRN 止痛藥月度 ≥ 15 天（MOH 高風險 + 慢性化）──
    if _has_symptom(symptoms_data, "頭痛"):
        for m in active_meds:
            if _classify_medication(m) != "prn" or not _is_analgesic(m):
                continue
            use_days = len(log_days_by_med.get(m.get("id"), set()))
            monthly = use_days / days * 30 if days else float(use_days)
            if monthly >= 15:
                hints.append({
                    "trigger": (
                        f"頭痛紀錄高頻 + {m.get('name', '?')}（PRN 止痛藥）"
                        f"月度推算使用 {monthly:.0f} 天"
                    ),
                    "directions": [
                        "藥物過度使用性頭痛（MOH，尚未排除）",
                        "慢性偏頭痛",
                        "緊張型頭痛",
                    ],
                })
                break  # 一藥觸發就夠了

    # ── H2: 情緒連續 ≥ 4 次 ≤ 2（情緒障礙篩檢需求）──
    if emotions_data:
        scores = [e.get("score") for e in emotions_data if e.get("score") is not None]
        consec = max_consec = 0
        for sc in scores:
            if sc is not None and sc <= 2:
                consec += 1
                max_consec = max(max_consec, consec)
            else:
                consec = 0
        if max_consec >= 4:
            hints.append({
                "trigger": f"情緒評分連續 {max_consec} 次 ≤ 2",
                "directions": [
                    "情緒障礙篩檢（建議使用 PHQ-9 / GAD-7 量表）",
                    "適應障礙",
                    "其他內科病因引發之情緒變化（例如甲狀腺、藥物副作用）",
                ],
            })

    # ── H3: scheduled 藥服藥率多項 < 70%（服藥順從性問題）──
    low_adh_meds = []
    for m in active_meds:
        if _classify_medication(m) != "scheduled":
            continue
        mid = m.get("id")
        total = sum(1 for l in med_logs_data if l.get("medication_id") == mid)
        taken = sum(1 for l in med_logs_data if l.get("medication_id") == mid and l.get("taken"))
        if total >= 10 and taken / total < 0.7:
            low_adh_meds.append(m.get("name", "?"))
    if len(low_adh_meds) >= 2:
        hints.append({
            "trigger": f"多項固定每日藥物服藥率 < 70%（{'、'.join(low_adh_meds[:3])}）",
            "directions": [
                "服藥順從性評估（建議了解漏藥原因：副作用、生活作息、認知、自費等）",
                "藥物副作用反應評估",
                "用藥指導／衛教需求評估",
            ],
        })

    return hints


# ── 共用：收集近 N 天資料 ────────────────────────────────────


def _empty_summary(period_label: str = "近 30 天"):
    """DB 整體無法連線時的預設回傳：空 summary、零計數、has_data=False、空 raw_records。"""
    empty_records = {
        "symptoms": [], "emotions": [], "medications": [], "medication_logs": [],
        "effects": [], "diet": [], "visits": [], "admissions": [],
        "medication_changes": [], "upcoming_follow_ups": [],
    }
    return (
        f"報告期間：{period_label}\n症狀記錄：無\n情緒記錄：無\n用藥紀錄：無\n就診紀錄：無\n飲食記錄：無",
        {"symptom_count": 0, "emotion_count": 0, "medication_count": 0,
         "visit_count": 0, "diet_count": 0, "admission_count": 0, "med_change_count": 0},
        False,
        empty_records,
    )


def _safe_query(fn, default):
    """執行 Supabase 查詢，失敗（憑證未設、表不存在、RLS 拒絕等）回傳預設值，
    避免單一資料源失效就讓整個報告 500。"""
    try:
        return fn()
    except Exception as e:
        logger.warning(f"Supabase query 失敗，使用空資料：{e}")
        return default


_FALLBACK_DAYS = 30


def _get_period(patient_id: str):
    """依「上次回診」決定報告期間。
    回傳 (days, period_label, last_visit_date)。
    - 有 medical_records.visit_date：days = 今天 - 上次 visit_date
    - 沒有 / 抓不到：fallback 為近 30 天
    任何 DB 例外都 swallow 成 fallback，不讓上層炸。
    """
    fallback = (_FALLBACK_DAYS, f"近 {_FALLBACK_DAYS} 天（無上次回診紀錄，使用預設區間）", None)

    try:
        sb = get_supabase()
    except Exception:
        return fallback

    try:
        rows = (
            sb.table("medical_records")
            .select("visit_date")
            .eq("patient_id", patient_id)
            .order("visit_date", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as e:
        logger.warning(f"_get_period: 抓上次回診失敗，使用 fallback：{e}")
        return fallback

    if not rows:
        return fallback

    visit_date_str = (rows[0].get("visit_date") or "")[:10]
    if not visit_date_str:
        return fallback

    try:
        visit_dt = datetime.strptime(visit_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return fallback

    days = max(1, (datetime.now(timezone.utc) - visit_dt).days)
    label = f"上次回診（{visit_date_str}）以來，共 {days} 天"
    return days, label, visit_date_str


def _collect_period_summary(patient_id: str, days: int | None = None, period_label: str | None = None):
    """收集本期間症狀／情緒／用藥／就診資料。
    回傳 (summary_text, raw_counts, has_data, days, period_label, raw_records)。

    `summary_text` 給 LLM 當 user message；`raw_records` 是每類完整 list 給前端
    PDF「本期間紀錄一覽」區塊用（不過 LLM）。

    `days` 沒帶（None）時會呼叫 `_get_period` 自動推算。
    任何 DB / 連線錯誤都會 swallow 成空資料，讓上層仍能產生「資料不足」版本的報告。
    """
    if days is None:
        days, auto_label, _ = _get_period(patient_id)
        if period_label is None:
            period_label = auto_label
    if period_label is None:
        period_label = f"近 {days} 天"

    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"無法連線資料庫，產生空摘要：{e}")
        text, counts, has_data, raw_records = _empty_summary(period_label)
        return text, counts, has_data, days, period_label, raw_records

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    symptoms_data = _safe_query(lambda: (
        sb.table("symptoms_log").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).order("created_at").execute().data or []
    ), [])
    emotions_data = _safe_query(lambda: (
        sb.table("emotions").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).order("created_at").execute().data or []
    ), [])
    meds_data = _safe_query(lambda: (
        sb.table("medications").select("*").eq("patient_id", patient_id)
        .execute().data or []
    ), [])
    med_logs_data = _safe_query(lambda: (
        sb.table("medication_logs").select("*").eq("patient_id", patient_id)
        .gte("taken_at", since).execute().data or []
    ), [])
    records_data = _safe_query(lambda: (
        sb.table("medical_records").select("*").eq("patient_id", patient_id)
        .gte("visit_date", since[:10]).order("visit_date").execute().data or []
    ), [])
    diet_data = _safe_query(lambda: (
        sb.table("diet_records").select("*").eq("patient_id", patient_id)
        .gte("eaten_at", since).order("eaten_at", desc=True).execute().data or []
    ), [])
    # 藥物療效評分 + 副作用（病人★評分，主觀但臨床很重要）
    effects_data = _safe_query(lambda: (
        sb.table("medication_effects").select("*").eq("patient_id", patient_id)
        .gte("recorded_at", since).order("recorded_at", desc=True).execute().data or []
    ), [])
    # 個人檔案 — 慢性病、過敏、基本資料；給 LLM 做風險偵測的 context（不算「期間紀錄」所以不影響 has_data）
    profile_data = _safe_query(lambda: (
        sb.table("patient_profiles").select("*").eq("user_id", patient_id).limit(1).execute().data or []
    ), [])
    profile = profile_data[0] if profile_data else None
    # 即將回診排程（upcoming follow-ups）— 讓 LLM 知道下次回診情境
    upcoming_fu = _safe_query(lambda: (
        sb.table("follow_ups").select("*").eq("patient_id", patient_id)
        .eq("status", "scheduled").gte("scheduled_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        .order("scheduled_date").limit(3).execute().data or []
    ), [])
    # 住院 / 長期療程紀錄（本期間有 admit_date 的）
    admissions_data = _safe_query(lambda: (
        sb.table("admissions").select("*").eq("patient_id", patient_id)
        .gte("admit_date", since[:10]).order("admit_date", desc=True).execute().data or []
    ), [])
    # 用藥變更紀錄（本期間 effective_date 的調藥）
    med_changes_data = _safe_query(lambda: (
        sb.table("medication_changes").select("*").eq("patient_id", patient_id)
        .gte("effective_date", since).order("effective_date", desc=True).execute().data or []
    ), [])

    has_data = bool(
        symptoms_data or emotions_data or med_logs_data or records_data
        or diet_data or effects_data or admissions_data or med_changes_data
    )
    parts = [f"報告期間：{period_label}\n"]

    # 個人背景 — 給 LLM 做風險偵測（慢性病 + 過敏 + 年齡 + 性別）
    if profile:
        bg = []
        # 年齡：從 birthday 算
        bday = profile.get("birthday")
        if bday:
            try:
                from datetime import date as _d
                y, m, d = bday[:10].split("-")
                today = datetime.now(timezone.utc).date()
                age = today.year - int(y) - ((today.month, today.day) < (int(m), int(d)))
                if 0 < age < 150:
                    bg.append(f"{age} 歲")
            except (ValueError, IndexError):
                pass
        if profile.get("gender"):
            gmap = {"male": "男", "female": "女", "other": "其他"}
            bg.append(gmap.get(profile["gender"], profile["gender"]))
        if bg:
            parts.append("患者背景：" + "、".join(bg))
        if profile.get("conditions"):
            parts.append(f"慢性病登記：{profile['conditions']}")
        if profile.get("current_disease"):
            parts.append(f"目前主要關注：{profile['current_disease']}")
        if profile.get("allergies"):
            parts.append(f"過敏史：{profile['allergies']}")
        parts.append("")  # 空行區隔

    if symptoms_data:
        all_symptoms = []
        for s in symptoms_data:
            syms = s.get("symptoms", [])
            if isinstance(syms, list):
                all_symptoms.extend(syms)
            elif isinstance(syms, str):
                all_symptoms.append(syms)
        freq = {}
        for sym in all_symptoms:
            freq[sym] = freq.get(sym, 0) + 1
        sorted_symptoms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        parts.append(f"症狀記錄（{len(symptoms_data)} 筆）：")
        for sym, count in sorted_symptoms[:10]:
            parts.append(f"  - {sym}：{count} 次")
    else:
        parts.append("症狀記錄：無")

    if emotions_data:
        scores = [e.get("score", 3) for e in emotions_data]
        import statistics
        avg_score = statistics.mean(scores)
        parts.append(f"\n情緒記錄（{len(emotions_data)} 筆）：")
        parts.append(f"  - 平均：{avg_score:.1f}/5  最低：{min(scores)}  最高：{max(scores)}")
        consecutive = 0
        max_consecutive = 0
        for s in scores:
            if s <= 2:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        if max_consecutive >= 3:
            parts.append(f"  - 曾連續 {max_consecutive} 次低落（<= 2 分）")
        notes = [e.get("note", "") for e in emotions_data if e.get("note")]
        if notes:
            parts.append(f"  - 備註摘要：{'; '.join(notes[:5])}")
    else:
        parts.append("\n情緒記錄：無")

    active_meds = [m for m in meds_data if m.get("active", 1)]
    if active_meds:
        parts.append(f"\n用藥（{len(active_meds)} 種）：")
        for m in active_meds:
            parts.append(f"  - {m['name']}" + (f"（{m.get('dosage', '')}）" if m.get("dosage") else ""))
    if med_logs_data:
        total_logs = len(med_logs_data)
        taken = sum(1 for l in med_logs_data if l.get("taken"))
        rate = taken / total_logs * 100 if total_logs else 0
        parts.append(f"  服藥率：{rate:.0f}%（{taken}/{total_logs}）")
    else:
        if not active_meds:
            parts.append("\n用藥紀錄：無")

    if records_data:
        parts.append(f"\n就診紀錄（{len(records_data)} 次）：")
        for r in records_data:
            date = r.get("visit_date", "?")[:10]
            diag = r.get("diagnosis", "未記錄")
            parts.append(f"  - {date}：{diag}")
    else:
        parts.append("\n就診紀錄：無")

    if diet_data:
        # 近 N 天飲食彙整：餐別分布 + 4 週完整度 + 常見食物 + 最近 raw 樣本
        meal_counts = {"breakfast": 0, "lunch": 0, "dinner": 0, "snack": 0}
        meal_label = {"breakfast": "早", "lunch": "午", "dinner": "晚", "snack": "點"}
        # 每日 meal set，用本地日期（台灣 +08:00）— 這裡簡化用 UTC date 即可，
        # 醫師看的是月度趨勢，不需要分鐘級的時區精度
        from datetime import date as _date_cls
        day_meals: dict = {}
        food_count: dict = {}
        for r in diet_data:
            mt = r.get("meal_type")
            if mt in meal_counts:
                meal_counts[mt] += 1
            eaten = r.get("eaten_at") or ""
            try:
                d_key = eaten[:10]  # YYYY-MM-DD
                day_meals.setdefault(d_key, set()).add(mt)
            except Exception:
                pass
            foods = (r.get("foods") or "").strip()
            if foods:
                # 簡單切詞 — 跟 diet.py 的 _FOOD_TOKEN_RE 邏輯一致
                import re as _re
                for tok in _re.split(r"[、,，;；]|\s+", foods):
                    tok = tok.strip()
                    if len(tok) >= 2 and tok not in {"和", "與", "或", "以及", "等"}:
                        food_count[tok] = food_count.get(tok, 0) + 1

        # 4 週完整度：以 7 天為 bucket
        from datetime import datetime as _dt
        try:
            today_utc = _dt.now(timezone.utc).date()
        except Exception:
            today_utc = _dt.utcnow().date()
        week_completeness = []
        for w in range(4):
            week_end = today_utc - timedelta(days=w * 7)
            week_start = week_end - timedelta(days=6)
            comp_sum = 0.0
            for i in range(7):
                d = (week_start + timedelta(days=i)).isoformat()
                meals = day_meals.get(d, set())
                comp_sum += (
                    (0.30 if "breakfast" in meals else 0)
                    + (0.30 if "lunch" in meals else 0)
                    + (0.30 if "dinner" in meals else 0)
                    + (0.10 if "snack" in meals else 0)
                )
            week_completeness.append(round(comp_sum / 7, 2))

        days_with_record = len(day_meals)
        parts.append(f"\n飲食記錄（{len(diet_data)} 筆，記了 {days_with_record} 天）：")
        parts.append(
            "  打卡分布：早 {b}、午 {l}、晚 {d}、點 {s}（本期間 {days} 天總次數）".format(
                b=meal_counts["breakfast"], l=meal_counts["lunch"],
                d=meal_counts["dinner"],   s=meal_counts["snack"],
                days=days,
            )
        )
        parts.append(
            "  4 週完整度：本週 {0}、上週 {1}、前週 {2}、再前 {3}（早午晚各權重 0.30、點心 0.10）".format(
                *week_completeness
            )
        )
        if food_count:
            top = sorted(food_count.items(), key=lambda x: (-x[1], x[0]))[:8]
            parts.append("  常見食物：" + "、".join(f"{name}({n})" for name, n in top))
        # 備註關鍵字頻次
        notes = [r.get("note") for r in diet_data if r.get("note")]
        if notes:
            note_count: dict = {}
            for n in notes:
                key = (n or "").strip()
                if key:
                    note_count[key] = note_count.get(key, 0) + 1
            top_notes = sorted(note_count.items(), key=lambda x: -x[1])[:5]
            parts.append("  備註頻次：" + "、".join(f"{k}({v})" for k, v in top_notes))
        # 最近 15 筆 raw 樣本（給 LLM 看具體吃了什麼）
        parts.append("  最近紀錄（最多 15 筆）：")
        for r in diet_data[:15]:
            mt = meal_label.get(r.get("meal_type"), "?")
            d = (r.get("eaten_at") or "")[:10]
            foods = (r.get("foods") or "").strip()
            note = (r.get("note") or "").strip()
            line = f"    - {d} {mt}：{foods}"
            if note:
                line += f"（{note}）"
            parts.append(line)
    else:
        parts.append("\n飲食記錄：無")

    # 藥物療效評分 + 副作用 — 病人主觀但臨床重要
    if effects_data:
        # 對齊 med 名稱（從 active_meds 抓）
        med_by_id = {m.get("id"): m.get("name") for m in active_meds}
        parts.append(f"\n藥物療效評分（{len(effects_data)} 筆，1=很差 5=很好）：")
        # 按藥分組
        by_med: dict = {}
        for e in effects_data:
            mid = e.get("medication_id")
            by_med.setdefault(mid, []).append(e)
        for mid, evs in list(by_med.items())[:8]:
            name = med_by_id.get(mid) or "未知藥物"
            scores = [e.get("effectiveness") for e in evs if e.get("effectiveness") is not None]
            if scores:
                avg = sum(scores) / len(scores)
                parts.append(f"  - {name}：平均 {avg:.1f} 分（{len(scores)} 次評分）")
            # 副作用聚合
            sides = [str(e.get("side_effects") or "").strip() for e in evs if e.get("side_effects")]
            if sides:
                parts.append(f"    副作用回報：{'; '.join(sides[:3])}")
            # 症狀變化聚合（最近一筆）
            changes = [str(e.get("symptom_changes") or "").strip() for e in evs if e.get("symptom_changes")]
            if changes:
                parts.append(f"    症狀變化：{changes[0]}")

    # 即將回診排程 — 給 LLM 知道病人下一步看哪一科
    if upcoming_fu:
        parts.append(f"\n即將回診（最近 {len(upcoming_fu)} 筆）：")
        for f in upcoming_fu:
            d = (f.get("scheduled_date") or "")[:10]
            dept = f.get("department") or ""
            hosp = f.get("hospital") or ""
            sess = {"am": "上午診", "pm": "下午診"}.get(f.get("session"), "")
            line = f"  - {d}"
            extras = [x for x in (sess, dept, hosp) if x]
            if extras:
                line += "：" + " · ".join(extras)
            parts.append(line)

    # 住院 / 長期療程 — 給 LLM 知道病人本期間有住院或長期療程
    if admissions_data:
        parts.append(f"\n住院／長期療程（{len(admissions_data)} 次）：")
        for a in admissions_data:
            ad = (a.get("admit_date") or "")[:10]
            dd = (a.get("discharge_date") or "")[:10]
            atype = {"acute": "急性住院", "chronic_infusion": "長期療程"}.get(a.get("type"), a.get("type") or "")
            diag = a.get("diagnosis") or "未記錄"
            ward = a.get("ward") or ""
            line = f"  - {ad}"
            if dd:
                line += f" → {dd}"
            line += f"｜{atype}｜{diag}"
            if ward:
                line += f"（{ward}）"
            parts.append(line)

    # 用藥變更（停藥／加藥／劑量調整）— 對醫師交班特別重要
    if med_changes_data:
        change_label = {
            "start": "新開始", "stop": "停藥", "dose_up": "加量",
            "dose_down": "減量", "switch": "換藥", "frequency": "改頻次", "other": "其他變更",
        }
        parts.append(f"\n用藥變更（{len(med_changes_data)} 次）：")
        for m in med_changes_data:
            ed = (m.get("effective_date") or "")[:10]
            ctype = change_label.get(m.get("change_type"), m.get("change_type") or "")
            reason = m.get("reason") or ""
            line = f"  - {ed}｜{ctype}"
            if reason:
                line += f"（原因：{reason}）"
            parts.append(line)

    counts = {
        "symptom_count": len(symptoms_data),
        "emotion_count": len(emotions_data),
        "medication_count": len(active_meds),
        "visit_count": len(records_data),
        "diet_count": len(diet_data),
        "effect_count": len(effects_data),
        "admission_count": len(admissions_data),
        "med_change_count": len(med_changes_data),
    }
    # raw_records — 全列給前端 PDF 渲染「本期間紀錄一覽」區塊（不過 LLM）
    raw_records = {
        "symptoms": symptoms_data,
        "emotions": emotions_data,
        "medications": active_meds,
        "medication_logs": med_logs_data,
        "effects": effects_data,
        "diet": diet_data,
        "visits": records_data,
        "admissions": admissions_data,
        "medication_changes": med_changes_data,
        "upcoming_follow_ups": upcoming_fu,
    }

    # 預計算統計區塊（規則 A、B、C、E）— 塞到 user message 最前面，
    # LLM 只能從這裡讀統計數字，不能自己重算。
    precomputed_text, risk_flags = _build_precomputed_stats(
        days=days,
        period_label=period_label,
        symptoms_data=symptoms_data,
        emotions_data=emotions_data,
        active_meds=active_meds,
        med_logs_data=med_logs_data,
        effects_data=effects_data,
        diet_data=diet_data,
        admissions_data=admissions_data,
        med_changes_data=med_changes_data,
    )
    full_text = precomputed_text + "\n\n" + "\n".join(parts)
    counts["risk_flag_count"] = len(risk_flags)
    raw_records["risk_flags"] = risk_flags
    return full_text, counts, has_data, days, period_label, raw_records


# ── 近 N 天月度報告（預設 30，前端可依回診日倒數覆寫） ─────────


# ── /monthly + /patient-summary 共用的 TTL cache ──
#
# 為什麼要 cache：兩個 endpoint 都會打 LLM 整合摘要，Groq free tier 在
# 高峰時 429。LLM call 失敗就 fallback 成「報告生成失敗，以下為原始數據摘要」，
# 病人帶去診間的 PDF 就是純 raw data dump、沒有 §〇 §七 跟 badge。
# 加 TTL cache 後：第一次 LLM 成功的結果被快取，後續同 patient+days 的請求
# （含 PDF 下載再打 endpoint）直接命中、避開 Groq 突發限流。
#
# 跟 /education/generate 的 cache 不同 — reports 內容會隨病人新紀錄改變，
# 所以用 TTL（預設 1 小時）而非永久 cache。資料量大時可能 1 小時內出現
# 新症狀 / 用藥變化，但這是「PDF 短時間內不刷新內容」的可接受取捨。

_REPORTS_CACHE_TTL_SECONDS = 3600  # 1 hour


def _reports_cache_key(patient_id: str, days: int, audience: str) -> str:
    return f"{audience}:{patient_id}:{days}"


def _reports_get_cache(cache_key: str) -> dict | None:
    """命中且未過期回 payload dict；miss / 過期 / DB 失敗 回 None。"""
    try:
        sb = get_supabase()
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = (
            sb.table("reports_cache").select("payload, expires_at")
            .eq("cache_key", cache_key).gt("expires_at", now_iso)
            .limit(1).execute().data or []
        )
        if rows:
            return rows[0].get("payload")
        return None
    except Exception as e:
        logger.warning(f"reports_cache lookup 失敗，視為 miss：{type(e).__name__}: {e}")
        return None


def _reports_save_cache(cache_key: str, patient_id: str, days: int,
                        audience: str, payload: dict) -> None:
    """寫 cache。失敗只 log，不影響回傳。
    報告內容明顯失敗（含 fallback 文字）不寫快取，下次仍會重試 LLM。"""
    report_text = payload.get("report") or payload.get("summary") or ""
    if "報告生成失敗" in report_text or "報告生成超時" in report_text:
        return
    if len(report_text.strip()) < 100:
        return
    try:
        sb = get_supabase()
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=_REPORTS_CACHE_TTL_SECONDS)).isoformat()
        sb.table("reports_cache").upsert({
            "cache_key": cache_key,
            "patient_id": patient_id,
            "days": days,
            "audience": audience,
            "payload": payload,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
        }, on_conflict="cache_key").execute()
    except Exception as e:
        logger.warning(f"reports_cache 寫入失敗（不阻塞回傳）：{type(e).__name__}: {e}")


@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str, days: int | None = Query(None, ge=1, le=365)):
    """回診間整合報告：症狀 + 情緒 + 用藥 + 就診 + 飲食。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。
    顯式帶 `days` 視為覆寫（測試／自訂區間用）。

    流程：
    1. 先查 reports_cache(audience='monthly')，TTL 內命中直接回
    2. 沒命中才 _collect_period_summary + 打 LLM
    3. LLM 成功 → 寫 cache + 回傳；LLM 失敗 → 回 fallback 文字但不寫 cache
    """
    # 先試 cache（用 effective days）— 還沒推算 days 時用提示性 key
    effective_days, _, _ = _get_period(patient_id) if days is None else (days, None, None)
    cache_key = _reports_cache_key(patient_id, effective_days or 30, "monthly")
    cached = _reports_get_cache(cache_key)
    if cached:
        cached["source"] = "cache"
        return cached

    data_summary, counts, has_data, days, period_label, raw_records = _collect_period_summary(
        patient_id, days=days
    )

    full_summary = data_summary

    if not has_data:
        payload = {
            "patient_id": patient_id,
            "report": f"此患者於「{period_label}」期間尚無足夠的健康數據可供產出報告。",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_data",
            "days": days,
            "period_label": period_label,
            "raw_data": counts,
            "raw_records": raw_records,
        }
        return payload

    try:
        report_text = _call_claude_bounded(INTEGRATED_SUMMARY_PROMPT, full_summary)
        source = "ai"
    except concurrent.futures.TimeoutError:
        logger.error(f"Monthly report timeout (>{_LLM_HARD_TIMEOUT_S}s)，回 raw fallback")
        report_text = (
            f"報告生成超時（AI 服務忙線中），以下為原始數據摘要：\n\n{full_summary}"
        )
        source = "timeout"
    except Exception as e:
        logger.error(f"Monthly report generation failed: {e}")
        report_text = f"報告生成失敗，以下為原始數據摘要：\n\n{full_summary}"
        source = "error"

    payload = {
        "patient_id": patient_id,
        "report": report_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        "period_label": period_label,
        "raw_data": counts,
        "raw_records": raw_records,
    }
    # 只有 ai 成功才寫 cache（timeout/error 不寫，下次重試）
    if source == "ai":
        _reports_save_cache(cache_key, patient_id, days, "monthly", payload)
    return payload


# ── 問診清單 ─────────────────────────────────────────────────


@router.get("/{patient_id}/checklist")
def get_consultation_checklist(patient_id: str, days: int | None = Query(None, ge=1, le=365)):
    """建議問診清單：根據本期間數據，生成這次最需要確認的三件事。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。
    """
    if days is None:
        days, period_label, _ = _get_period(patient_id)
    else:
        period_label = f"近 {days} 天"

    default_checklist = [
        "目前身體整體感覺如何？有沒有新的不舒服？",
        "目前的藥有沒有按時吃？有沒有什麼困難？",
        "生活和心情上有沒有需要醫師幫忙的地方？",
    ]

    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"checklist: 無法連線資料庫，回預設清單：{e}")
        return {
            "patient_id": patient_id,
            "checklist": default_checklist,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "db_offline",
            "days": days,
            "period_label": period_label,
        }

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # 本期間內的資料（任一失敗都當空陣列處理）
    symptoms_data = _safe_query(lambda: (
        sb.table("symptoms_log").select("*").eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at", desc=True).limit(10).execute().data or []
    ), [])
    emotions_data = _safe_query(lambda: (
        sb.table("emotions").select("*").eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at", desc=True).limit(10).execute().data or []
    ), [])
    medications_data = _safe_query(lambda: (
        sb.table("medications").select("*").eq("patient_id", patient_id)
        .eq("active", 1).execute().data or []
    ), [])

    if not symptoms_data and not emotions_data and not medications_data:
        return {
            "patient_id": patient_id,
            "checklist": default_checklist,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "default",
            "days": days,
            "period_label": period_label,
        }

    parts = [f"報告期間：{period_label}"]
    if symptoms_data:
        symptom_texts = []
        for s in symptoms_data:
            symptoms = s.get("symptoms", [])
            if isinstance(symptoms, list):
                symptom_texts.append("、".join(symptoms))
            elif isinstance(symptoms, str):
                symptom_texts.append(symptoms)
        if symptom_texts:
            parts.append(f"近期症狀記錄：{'; '.join(symptom_texts)}")

    if emotions_data:
        scores = [str(e.get("score", "?")) for e in emotions_data]
        notes = [e.get("note", "") for e in emotions_data if e.get("note")]
        parts.append(f"近期情緒評分（1-5）：{', '.join(scores)}")
        if notes:
            parts.append(f"情緒備註：{'; '.join(notes[:5])}")

    if medications_data:
        med_names = [m.get("name", "未知藥物") for m in medications_data]
        parts.append(f"目前用藥：{', '.join(med_names)}")

    user_message = "以下是這位患者的健康數據：\n" + "\n".join(parts)

    checklist_system = build_patient_facing_system(
        CHECKLIST_ROLE_PROMPT,
        patient_context=compute_patient_context(patient_id),
        include_examples=False,  # 純 JSON 陣列輸出，example 反而干擾結構
    )

    try:
        raw = _call_claude_bounded(checklist_system, user_message)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        checklist = json.loads(raw)
        if not isinstance(checklist, list):
            raise ValueError("Expected a JSON array")
    except concurrent.futures.TimeoutError:
        logger.warning(f"Checklist LLM timeout (>{_LLM_HARD_TIMEOUT_S}s)，回預設清單")
        checklist = default_checklist
    except Exception as e:
        logger.warning(f"Claude checklist parsing failed: {e}")
        checklist = [
            "請跟醫師討論近期的症狀變化",
            "確認目前的用藥是否需要調整",
            "聊聊最近的生活和心情狀況",
        ]

    return {
        "patient_id": patient_id,
        "checklist": checklist[:3],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai",
        "days": days,
        "period_label": period_label,
    }


# ── 帶去診間用的白話摘要（300–500 字） ───────────────────────


@router.get("/{patient_id}/patient-summary")
def get_patient_summary(patient_id: str, days: int | None = Query(None, ge=1, le=365)):
    """產出患者帶去診間用的白話摘要（PDF / Word 用）。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。

    流程同 /monthly：先試 reports_cache(audience='patient_summary')，TTL 內命中
    直接回；沒命中才打 LLM、成功才寫 cache。
    """
    # 先試 cache
    effective_days, _, _ = _get_period(patient_id) if days is None else (days, None, None)
    cache_key = _reports_cache_key(patient_id, effective_days or 30, "patient_summary")
    cached = _reports_get_cache(cache_key)
    if cached:
        cached["source"] = "cache"
        return cached

    data_summary, counts, has_data, days, period_label, raw_records = _collect_period_summary(
        patient_id, days=days
    )

    if not has_data:
        fallback = (
            f"醫師您好，這次回診前，我把{period_label}的紀錄整理了一下，但其實沒有特別記錄到什麼"
            "嚴重的症狀，整體狀況算是平穩。日常生活可以照常進行，吃飯、睡覺、心情都還算可以。\n\n"
            "想跟醫師確認的是：以我目前的狀況，下次回診大概多久後比較合適？平常有沒有什麼"
            "需要特別注意的地方，例如飲食、運動，或哪些症狀出現的時候應該趕快回診？\n\n"
            "另外，我會繼續用 MD.Piece 把症狀、心情、吃藥的情況記錄下來，下次回診再帶完整"
            "的紀錄給醫師看。謝謝醫師！"
        )
        return {
            "patient_id": patient_id,
            "summary": fallback,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_data",
            "days": days,
            "period_label": period_label,
            "raw_data": counts,
            "raw_records": raw_records,
        }

    # patient-summary 與 monthly 共用同一份整合摘要 — 風格憲法不適用（這是給醫師讀的交班，
    # 不是 AI 直接對病人講話），所以不過 build_patient_facing_system；
    # § 一段主訴的第一人稱口吻由 INTEGRATED_SUMMARY_PROMPT 內部規範。
    try:
        summary = _call_claude_bounded(INTEGRATED_SUMMARY_PROMPT, data_summary).strip()
        if summary.startswith("```"):
            summary = summary.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        source = "ai"
    except concurrent.futures.TimeoutError:
        logger.error(f"Patient summary timeout (>{_LLM_HARD_TIMEOUT_S}s)，回 fallback 文字")
        summary = (
            f"醫師您好，{period_label}我有持續記錄身體狀況，但這次 AI 摘要暫時忙線中沒辦法即時產生，"
            "我把原始紀錄帶來，麻煩醫師看一下。謝謝！"
        )
        source = "timeout"
    except Exception as e:
        logger.error(f"Patient summary generation failed: {e}")
        summary = (
            f"醫師您好，{period_label}我有持續記錄身體狀況，但這次摘要暫時沒辦法自動產生，"
            "我把原始紀錄帶來，麻煩醫師看一下。謝謝！"
        )
        source = "error"

    payload = {
        "patient_id": patient_id,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        "period_label": period_label,
        "raw_data": counts,
        "raw_records": raw_records,
    }
    if source == "ai":
        _reports_save_cache(cache_key, patient_id, days, "patient_summary", payload)
    return payload


# ── 整合摘要串流端點（SSE，給 in-page live preview） ──────────
#
# 跟 /monthly 與 /patient-summary 拿到的是「同一份」整合摘要（共用
# INTEGRATED_SUMMARY_PROMPT），差別只在這個端點是邊產邊送 token，前端可以
# 看著文字一個字一個字長出來，不用乾等 30–45 秒。
# PDF 下載仍走原本的非串流端點，這條只服務 in-page 即時預覽。


def _sse(payload: dict) -> str:
    """把 dict 包成 SSE event 一行。ensure_ascii=False 才能讓中文直接走在 wire 上。"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@router.get("/{patient_id}/integrated-summary/stream")
def stream_integrated_summary(
    patient_id: str,
    days: int | None = Query(None, ge=1, le=365),
):
    """整合摘要 SSE 串流。事件型別：
      - meta   ：第一個事件，含 raw_data / days / period_label
      - chunk  ：每個 LLM 文字片段（含 text 欄位）
      - done   ：最後一個事件（source: ai / no_data）
      - error  ：串流中失敗（含 detail）
    """
    data_summary, counts, has_data, days, period_label, raw_records = _collect_period_summary(
        patient_id, days=days
    )

    # 沒資料就直接送 meta + fallback chunk + done，不打 LLM
    if not has_data:
        fallback_text = (
            f"## 〇、本次三大重點【AI 摘要】\n\n"
            f"- 本期間紀錄不足以彙整三大重點，建議醫師於回診時親自詢問近期狀況\n\n"
            f"## 一、主訴【紀錄】\n\n"
            f"醫師您好，{period_label}我有開始用 MD.Piece 記錄，"
            f"但這段期間其實沒有特別嚴重的不舒服，整體還算平穩。\n\n"
            f"## 二、資料整理【紀錄】\n\n"
            f"- 本期間無顯著紀錄，可彙整的資料有限\n\n"
            f"## 三、本期觀察到的變化【AI 摘要】\n\n"
            f"- 目前資料還不足以判斷走向，需要更多每日紀錄\n\n"
            f"## 四、風險訊號【AI 摘要】\n\n"
            f"- 本期間無顯著風險訊號\n\n"
            f"## 五、想請醫師確認與建議追蹤【紀錄】\n\n"
            f"**想請醫師確認的事：**\n"
            f"- 我想請教醫師目前的狀況下，下次回診大概多久比較合適？\n"
            f"- 有沒有什麼日常需要特別注意的，例如哪些症狀出現要立刻就醫？\n\n"
            f"**建議追蹤項目：**\n"
            f"- 建議建立每日紀錄習慣（症狀、情緒、用藥），讓下次回診有更完整的資料\n\n"
            f"## 六、綜合判斷【AI 摘要】\n\n"
            f"- 本期間紀錄不足以做整體治療方向的綜合判斷，建議醫師於回診時詢問近期狀況，"
            f"並請病人開始每日記錄症狀、情緒、用藥，下次回診才有可決策的資料\n\n"
            f"## 七、可參考方向【AI 摘要】\n\n"
            f"依本期資料尚未識別出特定鑑別重點，建議醫師於回診時做整體評估。\n\n"
            f"以上僅供醫師問診切入參考，**不代表診斷**，最終判斷以醫師親自評估為準。\n"
        )

        def empty_gen():
            yield _sse({
                "type": "meta",
                "raw_data": counts,
                "raw_records": raw_records,
                "days": days,
                "period_label": period_label,
                "has_data": False,
            })
            yield _sse({"type": "chunk", "text": fallback_text})
            yield _sse({"type": "done", "source": "no_data"})

        return StreamingResponse(
            empty_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    # SSE 也共用 reports_cache（key 用 'monthly' — SSE 跟 PDF/monthly 是同一份摘要）
    # 命中時就不打 LLM，直接 stream cached 文字
    sse_cache_key = _reports_cache_key(patient_id, days, "monthly")
    cached_payload = _reports_get_cache(sse_cache_key)
    if cached_payload and cached_payload.get("report"):
        cached_text = cached_payload["report"]

        def cached_gen():
            yield _sse({
                "type": "meta",
                "raw_data": counts,
                "raw_records": raw_records,
                "days": days,
                "period_label": period_label,
                "has_data": True,
            })
            yield _sse({"type": "chunk", "text": cached_text})
            yield _sse({"type": "done", "source": "cache"})

        return StreamingResponse(
            cached_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    def event_gen():
        # 先把 meta 推出去（前端立刻可以顯示「症狀 N 筆、情緒 N 次…」骨架）
        # raw_records 包進 meta 給 PDF「本期間紀錄一覽」用，避免 PDF 下載再打一次後端
        yield _sse({
            "type": "meta",
            "raw_data": counts,
            "raw_records": raw_records,
            "days": days,
            "period_label": period_label,
            "has_data": True,
        })
        accumulated_chunks: list[str] = []
        try:
            for chunk in stream_claude(INTEGRATED_SUMMARY_PROMPT, data_summary):
                if chunk:
                    accumulated_chunks.append(chunk)
                    yield _sse({"type": "chunk", "text": chunk})
            yield _sse({"type": "done", "source": "ai"})
            # 串流完整段寫 cache，讓後續 /monthly + PDF 下載命中
            full_text = "".join(accumulated_chunks).strip()
            if full_text:
                _reports_save_cache(
                    sse_cache_key, patient_id, days, "monthly",
                    {
                        "patient_id": patient_id,
                        "report": full_text,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "source": "ai",
                        "days": days,
                        "period_label": period_label,
                        "raw_data": counts,
                        "raw_records": raw_records,
                    },
                )
        except Exception as e:
            logger.error(f"Integrated summary stream failed: {e}")
            yield _sse({"type": "error", "detail": str(e), "source": "error"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ── 心情 × 用藥改善 相關性 ──────────────────────────────────


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    denom = (dx2 * dy2) ** 0.5
    if denom == 0:
        return None
    return round(num / denom, 3)


@router.get("/{patient_id}/wellness-correlation")
def wellness_correlation(patient_id: str, days: int | None = None):
    """
    每日「心情」與「用藥改善程度」的相關性（Pearson）。
    回傳並排的每日序列與相關係數，前端可畫雙線圖。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。
    """
    if days is None:
        days, period_label, _ = _get_period(patient_id)
    else:
        period_label = f"近 {days} 天"
    if days < 2:
        raise HTTPException(status_code=400, detail="days 必須 >= 2")
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    emotions = _safe_query(lambda: (
        sb.table("emotions").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).execute().data or []
    ), [])
    logs = _safe_query(lambda: (
        sb.table("medication_logs").select("*").eq("patient_id", patient_id)
        .gte("taken_at", since).execute().data or []
    ), [])
    effects = _safe_query(lambda: (
        sb.table("medication_effects").select("*").eq("patient_id", patient_id)
        .gte("recorded_at", since).execute().data or []
    ), [])

    mood_by_day: dict[str, list[float]] = {}
    for e in emotions:
        day = (e.get("created_at") or "")[:10]
        s = e.get("score")
        if day and s is not None:
            mood_by_day.setdefault(day, []).append(s)

    med_by_day: dict[str, dict] = {}
    for log in logs:
        day = (log.get("taken_at") or "")[:10]
        if not day:
            continue
        d = med_by_day.setdefault(day, {"taken": 0, "total": 0, "effects": []})
        d["total"] += 1
        if log.get("taken"):
            d["taken"] += 1
    for ef in effects:
        day = (ef.get("recorded_at") or "")[:10]
        score = ef.get("effectiveness")
        if not day or score is None:
            continue
        d = med_by_day.setdefault(day, {"taken": 0, "total": 0, "effects": []})
        d["effects"].append(score)

    series = []
    paired_x, paired_y = [], []
    all_days = sorted(set(mood_by_day) | set(med_by_day))
    for day in all_days:
        moods = mood_by_day.get(day, [])
        mood_avg = round(sum(moods) / len(moods), 2) if moods else None

        d = med_by_day.get(day)
        if d:
            adherence = (d["taken"] / d["total"] * 100) if d["total"] else None
            eff = (sum(d["effects"]) / len(d["effects"]) / 5 * 100) if d["effects"] else None
            parts = [p for p in (adherence, eff) if p is not None]
            if not parts:
                improvement = None
            elif adherence is not None and eff is not None:
                improvement = round(adherence * 0.5 + eff * 0.5, 1)
            else:
                improvement = round(parts[0], 1)
        else:
            improvement = None

        series.append({"date": day, "mood": mood_avg, "improvement": improvement})
        if mood_avg is not None and improvement is not None:
            paired_x.append(mood_avg)
            paired_y.append(improvement)

    r = _pearson(paired_x, paired_y)
    if r is None:
        interpretation = "資料不足，至少需要 2 個同時有心情與用藥資料的日子"
    elif r >= 0.5:
        interpretation = "心情與用藥改善呈中至強正相關，服藥規律的日子心情較佳"
    elif r >= 0.2:
        interpretation = "弱正相關，存在一致趨勢但不顯著"
    elif r > -0.2:
        interpretation = "幾乎無相關"
    elif r > -0.5:
        interpretation = "弱負相關，需要更多資料釐清"
    else:
        interpretation = "中至強負相關，建議主動關心並檢視藥物副作用"

    return {
        "patient_id": patient_id,
        "days": days,
        "period_label": period_label,
        "series": series,
        "paired_days": len(paired_x),
        "pearson_r": r,
        "interpretation": interpretation,
    }


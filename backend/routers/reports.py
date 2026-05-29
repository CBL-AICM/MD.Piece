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

# ── 診前摘要 prompt（醫師版：一句話摘要 / 紅旗 / 關鍵指標趨勢 / 結構化摘要） ──────
#
# 設計目標：把病人「兩次門診之間」蒐集的縱向紀錄，整理成一份給醫師閱讀的診前摘要。
# 醫師閱讀時間以秒計算 — 目標不是完整呈現所有資料，而是讓醫師在 30 秒內抓到重點、
# 需要時再往下深入。這份摘要由病人帶進診間遞給醫師，也用於頁面即時預覽與醫師版 PDF。
#
# 不做診斷，只呈現現象與變化，臨床判斷留給醫師。
#
# 核心原則（出自診前摘要 spec）：
#   1. 只放有訊號的東西 — 維持穩定的項目一句話帶過，不要用正常數據淹沒醫師
#   2. 趨勢優先於單點 — 關鍵指標都相對於「上次回診」描述
#   3. 個人基線而非族群標準 — 判斷異常以這位病人自己過去的基線為比較對象，並在文字中點出
#   4. 可追溯 — 任何判讀產生的內容都附判斷依據
#   5. 避免診斷性語言 — 描述「現象」而非下「判斷」
#
# 紅線（沿用既有摘要的安全規範）：
#   - 不替醫師下診斷、不點特定病名
#   - 不寫未來預測
#   - 不開藥、不寫劑量、不指示加減藥
#   - 跨指標關聯一律寫成「待驗證假設」，不可寫成因果結論
#
# 資料一致性（規則 A）：所有統計數字只能引用 user message【已計算統計】，禁止 LLM 自行重算。
# 信心度（規則 E）：confidence==low（涵蓋天數 < 30% 或 n ≤ 3）禁止寫趨勢方向。
# 來源標示（規則 G）：每段標題末加【紀錄】或【AI 摘要】。
#
# 病人提問與原始數據附錄不在此 prompt 產出 — 由前端以結構化資料渲染（規則 5：確定性資料不過 LLM）。

INTEGRATED_SUMMARY_PROMPT = (
    "【本次任務：診前摘要（醫師版）】\n"
    "你是慢性病管理系統的臨床資料彙整助手。把病人「兩次門診之間」蒐集的縱向紀錄，"
    "整理成一份給醫師閱讀的診前摘要。醫師的閱讀時間以秒計算，目標是讓醫師在 30 秒內"
    "抓到重點、需要時再往下深入。\n"
    "你不是在做診斷 — 你的工作是呈現現象與變化，把臨床判斷留給醫師。\n\n"
    "報告期間會在 user message 開頭以「報告期間：XXX」給出，請依該期間描述，不要假定 30 天。\n"
    "user message **第一個區塊**是「## 已計算統計（請只使用以下數字，不要自行重算）」，"
    "後面才是症狀／情緒／用藥／飲食…等 raw 資料區塊。\n\n"
    "═══ 必守規則（違反任一條視為輸出失敗）═══\n\n"
    "【規則 A — 數據一致性】\n"
    "所有統計數值（次數、平均、比率、走向方向、天數、劑量）**只能引用**「## 已計算統計」"
    "區塊提供的數字，**禁止自行重新推導、估算或從其他段落反推**。\n"
    "若發現任一不一致，停止並回報「數據不一致：__」，不要輸出報告。\n\n"
    "【規則 B — 藥物類型分流】\n"
    "- scheduled（固定每日服用）：使用「服藥率 = 實際/應服次數」\n"
    "- prn（需要時服用）：**禁止計算服藥率**（無分母），改寫本期使用天數、月度推算、累計劑量。\n"
    "【已計算統計】已按 type 標註，依該分類撰寫。\n\n"
    "【規則 C — 止痛藥過度使用風險訊號】\n"
    "若【已計算統計】中標記「analgesic: true」的藥物，其「本期月度推算使用天數」≥ 15 天，"
    "**必須**在「需注意事項 / 紅旗」段列一條：「__藥本期月度推算使用 __ 天（累計 __ mg），"
    "建議醫師評估是否有藥物過度使用性頭痛之可能」。措辭只能用此句變體，**不得下任何診斷**。\n\n"
    "【規則 E — 資料信心度】\n"
    "每個指標在【已計算統計】中會給 confidence 標籤（\"ok\" 或 \"low\"）。\n"
    "若 confidence == \"low\"（涵蓋天數 < 30%，或筆數 ≤ 3）：描述時加註「（資料點有限，趨勢僅供參考）」，"
    "且**不寫趨勢方向**。\n\n"
    "【規則 F — 跨指標關聯是假設不是結論】\n"
    "跨指標關聯一律定位為「待驗證的假設」，不可表述為因果。\n"
    "固定措辭：「本期此 N 項指標方向一致，但尚無法判斷因果，建議醫師評估是否需進一步同步監測以驗證。」\n"
    "禁用：「因為 A 所以 B」「A 造成 B」「A 與 B 相關」。\n\n"
    "【規則 G — 來源標示】\n"
    "每段標題末**必須**加上以下其中一個標籤（完全照抄）：\n"
    "  一句話摘要 →【AI 摘要】\n"
    "  需注意事項 / 紅旗 →【AI 摘要】\n"
    "  關鍵指標趨勢 →【AI 摘要】\n"
    "  結構化摘要 →【紀錄】\n\n"
    "【規則 I — 個人基線優先】\n"
    "判斷異常時，以這位病人自己過去的基線（【已計算統計】中提供的個人基線/前期數值）為比較對象，"
    "**而非族群標準**，並在文字中明確點出（例如「相較其個人基線」「較上次回診」）。\n\n"
    "═══ 段落輸出規格（嚴格依此順序與分區，不新增段落）═══\n\n"
    "## 一句話摘要【AI 摘要】\n"
    "用**一句話**總結本期最重要的變化，引用【已計算統計】的具體數字。範例：\n"
    "「血壓較上次回診平均上升 12 mmHg，夜間數值尤其偏高。」\n\n"
    "## 需注意事項 / 紅旗【AI 摘要】\n"
    "條列本期需要醫師特別注意的項目（數值超標、新出現症狀、疑似藥物副作用），"
    "每一項都附**具體數據與判斷依據**，依嚴重程度排序。\n"
    "規則 C 觸發時必出 MOH 條。寫法限於「事實 + 為何值得醫師關注」，例如：\n"
    "  ✓「止痛藥本期使用 18 天、月度推算 18 天，建議醫師評估是否有藥物過度使用性頭痛之可能」\n"
    "  ✗「特徵與偏頭痛慢性化一致」「應該是 X」\n"
    "**若本期無異常，明確寫出「本期無明顯紅旗」一句**，不要敷衍。\n\n"
    "## 關鍵指標趨勢【AI 摘要】\n"
    "針對每個核心指標，以文字描述：(1) 趨勢方向、(2) 相較上次回診的變化幅度、"
    "(3) 相較個人基線的位置。每個指標 1–2 句。\n"
    "- low confidence 指標套規則 E（不寫方向、加註「資料點有限」）\n"
    "- 跨指標共動套規則 F（寫成待驗證假設）\n"
    "- **只描述本期已發生的走向，不做未來預測**\n\n"
    "## 結構化摘要【紀錄】\n"
    "精簡呈現以下面向的重點，各面向**只寫有訊號的部分**；無變化的面向統一以「其餘穩定」帶過：\n"
    "- **症狀**：本期變化、頻率、誘發因素\n"
    "- **用藥**：依 type 分流（規則 B）— 順從性／使用天數、療效評分、副作用回報；本期用藥變更\n"
    "- **生活型態**：有臨床意義的飲食／運動／睡眠變化（與慢性病禁忌是否相符）\n\n"
    "═══ 全文規則 ═══\n"
    "- 繁體中文 + Markdown 二級標題（##）+ 條列；語言精簡、臨床取向，使用醫療人員熟悉的詞彙與單位\n"
    "- 四段都要寫；有資料就寫，沒資料就誠實註明「本期間無相關紀錄」\n"
    "- 資料點不足以支持趨勢判斷時，明確標註「資料點有限，趨勢僅供參考」，不要過度詮釋\n"
    "- 不要在開頭加前言或標題，第一行直接是「## 一句話摘要【AI 摘要】」\n"
    "- 不要在結尾加 AI 免責聲明（系統會另外渲染）\n"
    "- 版面為列印優化：假設輸出會印成黑白 A4，全文約 500–900 字\n"
    "- **全文禁止**：自行重算【已計算統計】數字、點名任何特定病名、未來預測句、開藥/停藥/改劑量指示、"
    "把跨指標關聯講成已驗證的因果"
)


# ── 患者版精華 prompt（提示框彈出用，250–500 字白話） ──────────────
#
# 給病人自己看的口語精華 — 回診前在 App 提示框直接讀完，不下載 PDF。
# 跟醫師版用同一份 user message（含【已計算統計】），但口吻、長度、目的完全不同：
# 白話、安心、可唸給醫師聽；不丟百分比、不丟風險分數、不下診斷。

PATIENT_ESSENCE_PROMPT = (
    "【本次任務：患者版診前精華】\n"
    "把病人本期間的健康紀錄，整理成一段**給病人自己看的白話精華**，"
    "讓他回診前花 30 秒讀完就知道「這陣子我的狀況重點是什麼、等下要跟醫師說什麼」。\n\n"
    "user message 開頭是「## 已計算統計」與症狀／情緒／用藥／飲食等 raw 資料；"
    "報告期間以「報告期間：XXX」給出，請依該期間描述。\n\n"
    "撰寫規範：\n"
    "1. **250–500 字**，一到三段白話文，像在跟病人本人講話（用「你」或第一人稱「我」皆可，全文一致）。\n"
    "2. 只挑**最重要的 2–4 個重點**講：這陣子身體/心情/用藥最明顯的變化，以及最該跟醫師確認的事。\n"
    "3. **不要**丟百分比、不要丟風險分數、不要列一堆數字 — 用「比上次回診更頻繁」這種白話描述。\n"
    "4. **不下診斷、不點病名、不開藥、不寫劑量、不做未來預測**；不替自己歸因（原因留給醫師）。\n"
    "5. 數值只能引用【已計算統計】，不要自行重算。\n"
    "6. 結尾用一句話收：提醒帶健保卡/藥袋，或鼓勵把想問的事跟醫師說。\n\n"
    "輸出格式：純白話文字（可分段），**不要**用 Markdown 標題、不要條列符號、不要在結尾加免責聲明。"
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


@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str, days: int | None = Query(None, ge=1, le=365)):
    """回診間整合報告：症狀 + 情緒 + 用藥 + 就診 + 飲食。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。
    顯式帶 `days` 視為覆寫（測試／自訂區間用）。
    """
    data_summary, counts, has_data, days, period_label, raw_records = _collect_period_summary(
        patient_id, days=days
    )

    full_summary = data_summary

    if not has_data:
        return {
            "patient_id": patient_id,
            "report": f"此患者於「{period_label}」期間尚無足夠的健康數據可供產出報告。",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_data",
            "days": days,
            "period_label": period_label,
            "raw_data": counts,
            "raw_records": raw_records,
        }

    try:
        report_text = _call_claude_bounded(INTEGRATED_SUMMARY_PROMPT, full_summary)
    except concurrent.futures.TimeoutError:
        logger.error(f"Monthly report timeout (>{_LLM_HARD_TIMEOUT_S}s)，回 raw fallback")
        report_text = (
            f"報告生成超時（AI 服務忙線中），以下為原始數據摘要：\n\n{full_summary}"
        )
    except Exception as e:
        logger.error(f"Monthly report generation failed: {e}")
        report_text = f"報告生成失敗，以下為原始數據摘要：\n\n{full_summary}"

    return {
        "patient_id": patient_id,
        "report": report_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai",
        "days": days,
        "period_label": period_label,
        "raw_data": counts,
        "raw_records": raw_records,
    }


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
    """
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

    # patient-summary 走「患者版精華」prompt — 給病人在提示框直接讀的 250–500 字白話，
    # 不下載 PDF。醫師版（/monthly、stream）才用 INTEGRATED_SUMMARY_PROMPT。
    # 口吻已在 PATIENT_ESSENCE_PROMPT 內部規範，故不過 build_patient_facing_system。
    try:
        summary = _call_claude_bounded(PATIENT_ESSENCE_PROMPT, data_summary).strip()
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

    return {
        "patient_id": patient_id,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        "period_label": period_label,
        "raw_data": counts,
        "raw_records": raw_records,
    }


# ── 醫師版診前摘要串流端點（SSE，給 in-page live preview） ──────────
#
# 跟 /monthly 拿到的是「同一份」醫師版診前摘要（共用 INTEGRATED_SUMMARY_PROMPT），
# 差別只在這個端點是邊產邊送 token，前端可以看著文字一個字一個字長出來，不用乾等 30–45 秒。
# 醫師版 PDF 下載走非串流的 /monthly；患者版精華（提示框）走 /patient-summary，三者各自獨立。


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
            f"## 一句話摘要【AI 摘要】\n\n"
            f"{period_label}病人已開始使用 MD.Piece 記錄，但本期間紀錄量不足以彙整出明顯變化。\n\n"
            f"## 需注意事項 / 紅旗【AI 摘要】\n\n"
            f"本期無明顯紅旗（資料點有限）。\n\n"
            f"## 關鍵指標趨勢【AI 摘要】\n\n"
            f"- 目前資料點有限，尚不足以判斷各指標趨勢方向，建議病人開始每日記錄症狀、情緒、用藥\n\n"
            f"## 結構化摘要【紀錄】\n\n"
            f"- 本期間無顯著紀錄，可彙整的資料有限；建議醫師於回診時親自詢問近期狀況\n"
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
        try:
            for chunk in stream_claude(INTEGRATED_SUMMARY_PROMPT, data_summary):
                if chunk:
                    yield _sse({"type": "chunk", "text": chunk})
            yield _sse({"type": "done", "source": "ai"})
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


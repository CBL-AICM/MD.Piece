import concurrent.futures
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_supabase
from backend.services.llm_service import (
    build_patient_facing_system,
    call_claude,
    compute_patient_context,
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

# ── 整合摘要 prompt（取代舊的 monthly + patient-summary） ────
#
# 設計目標：一份「帶去診間用的整合摘要」同時服務醫師判讀與病人遞交，
# 風格類似住院醫師 / PA 的交班 + chief-complaint 呈報。
# 三種口吻分段使用：
#   §一 主訴：第一人稱「我」（病人視角，最困擾的事）
#   §二、三、四 整合判讀 / 趨勢預測 / 風險與鑑別：第三人稱（AI 整合員 + 交班）
#   §五 建議與想問醫師：條列，第一/第三人稱混用
#
# 比舊 MONTHLY 多了「趨勢預測」「鑑別參考」（使用者授權打破舊版「禁診斷推論」紅線），
# 但仍守住底線：不開藥、不寫劑量、鑑別措辭限於「特徵與 X 一致，建議醫師評估」，不下診斷。

INTEGRATED_SUMMARY_PROMPT = (
    "【本次任務：診前整合摘要】\n"
    "把病人本期間的紀錄整合成一份「主訴呈報＋整合判讀＋預測＋建議」的文件。\n"
    "這份摘要會由病人帶進診間遞給醫師，也可能由病人念給醫師聽 — 所以同時要醫師讀得懂、"
    "病人也唸得出口。風格：像住院醫師／PA 向主治交班，先講 chief complaint，再做整合判讀。\n\n"
    "報告期間會在 user message 開頭以「報告期間：XXX」給出，請依該期間描述，不要假定 30 天。\n"
    "user message 可能含「患者背景」「慢性病登記」「過敏史」「症狀」「情緒」「用藥」「服藥率」"
    "「藥物療效評分」「飲食」「就診」「即將回診」等區塊；有資料的全部納入，沒資料的跳過、不要編造。\n\n"
    "輸出格式：繁體中文 Markdown，嚴格使用以下五段、順序固定、不新增段落、結尾不加免責聲明：\n\n"
    "## 一、主訴（病人視角）\n"
    "用 2–4 句、第一人稱「我」書寫，像病人開口跟醫師講最困擾的事。\n"
    "只寫病人主觀感受到的核心問題（最不舒服的症狀、頻率、對生活的影響），\n"
    "不放數值、不放百分比、不下臨床判斷。範例語氣：\n"
    "「醫師我這個月最困擾的是反覆頭痛，幾乎每週都來個兩三天，痛起來連工作都做不下去。」\n\n"
    "## 二、整合判讀（資料彙整）\n"
    "切換成第三人稱，像在跟主治交班，把本期間散落的資料串起來看。\n"
    "用 4–8 個條列，每點一句話，涵蓋（有資料才寫）：\n"
    "- 症狀模式：高頻症狀、新增、已改善；併發或集中於特定時段／情境\n"
    "- 情緒走向：平均、趨勢方向、是否連續低落\n"
    "- 服藥狀況：服藥率區間、漏藥模式、療效評分與副作用回報（具體點出藥名 OK，但**不寫劑量**）\n"
    "- 飲食規律度，以及與【慢性病登記】之飲食禁忌是否相符\n"
    "- 慢性病登記 + 過敏史 與本期紀錄的交集點\n"
    "- 即將回診排程銜接\n"
    "用詞可以專業（醫師看的），但不要堆數字 — 同類數字最多保留一個關鍵值。\n\n"
    "## 三、趨勢與預測\n"
    "用 2–4 個條列，把資料的「走向」說清楚 — 純資料延伸的趨勢預測，不下診斷：\n"
    "- 整體狀態：穩定／需留意／需盡快與醫師討論（用分級詞，不用 % 數字）\n"
    "- 「若維持此模式，可能 ...」句型：例如「若服藥率持續低於本期間水準，療效評估會更難判讀」\n"
    "- 點出「目前資料還不足以判斷」的部分，明說需要哪類資料才能下一步\n"
    "措辭限制：可寫「趨勢」「走向」「可能演變」，**不寫**「復發機率 X%」「預後不佳」等\n"
    "病人不易懂的詞；不替醫師宣告診斷。\n\n"
    "## 四、風險訊號與鑑別參考\n"
    "這段是給醫師的提示 — 主動點出病人可能還沒意識到的訊號。用 2–5 個條列：\n"
    "- 紅旗訊號：服藥率 < 70%、療效評分多次 ≤ 2、情緒連續 3 次以上 ≤ 2、副作用回報、\n"
    "  飲食與慢性病禁忌衝突、過敏史與本期用藥／飲食衝突\n"
    "- 鑑別參考（**這是新功能**）：當症狀／情緒／服藥／飲食的組合呈現某種臨床上熟悉的模式時，\n"
    "  可以提出「此模式的特徵與 ___ 一致，建議醫師評估是否需要進一步檢查」。\n"
    "  **嚴格規則**：\n"
    "    ✓「症狀組合的呈現方式，特徵與偏頭痛慢性化的型態一致，建議醫師評估」\n"
    "    ✓「持續疲倦 + 情緒連續低落 + 食慾改變的組合，建議醫師評估是否符合憂鬱症的篩檢條件」\n"
    "    ✗「病人是偏頭痛慢性化」「病人罹患憂鬱症」「應該是 X」\n"
    "  鑑別只是「值得醫師考慮的方向」，不下結論、不替醫師排序機率。\n"
    "- 若本期間真的無顯著訊號，寫「本期間無顯著風險訊號，整體呈穩定」一句，不要敷衍\n\n"
    "## 五、想請醫師確認與建議追蹤\n"
    "兩個小段：\n"
    "**想請醫師確認的事（病人視角，第一人稱）** — 條列 2–4 點：\n"
    "  「我想請教醫師 ___ 是不是需要調整？」「我想知道 ___ 算不算正常？」這種口吻。\n"
    "**建議追蹤項目（給醫師參考）** — 條列 2–4 點：\n"
    "  具體可量化的追蹤項目，例如「建議追蹤血壓家庭量測連續 2 週、每日早晚」、\n"
    "  「建議下次回診重新評估藥物 X 的療效（病人★評分偏低）」。\n"
    "  **不寫**：開藥建議、劑量調整、停藥／加藥指示。\n\n"
    "全文規則：\n"
    "- 繁體中文 + Markdown 二級標題（##）+ 條列\n"
    "- 五段都要寫；有資料就寫得詳細、沒資料就誠實註明「本期間無相關紀錄」\n"
    "- 不要在結尾加 AI 免責聲明，系統會另外渲染\n"
    "- 不要在開頭加前言或標題，第一行直接是「## 一、主訴（病人視角）」\n"
    "- 全文字數約 700–1100 字，資料量大可延伸但避免冗餘"
)


# ── 共用：收集近 N 天資料 ────────────────────────────────────


def _empty_summary(period_label: str = "近 30 天"):
    """DB 整體無法連線時的預設回傳：空 summary、零計數、has_data=False。"""
    return (
        f"報告期間：{period_label}\n症狀記錄：無\n情緒記錄：無\n用藥紀錄：無\n就診紀錄：無\n飲食記錄：無",
        {"symptom_count": 0, "emotion_count": 0, "medication_count": 0,
         "visit_count": 0, "diet_count": 0},
        False,
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
    """收集本期間症狀／情緒／用藥／就診資料，回傳 (summary_text, raw_counts, has_data, days, period_label)。

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
        text, counts, has_data = _empty_summary(period_label)
        return text, counts, has_data, days, period_label

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

    has_data = bool(symptoms_data or emotions_data or med_logs_data or records_data or diet_data or effects_data)
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

    counts = {
        "symptom_count": len(symptoms_data),
        "emotion_count": len(emotions_data),
        "medication_count": len(active_meds),
        "visit_count": len(records_data),
        "diet_count": len(diet_data),
        "effect_count": len(effects_data),
    }
    return "\n".join(parts), counts, has_data, days, period_label


# ── 近 N 天月度報告（預設 30，前端可依回診日倒數覆寫） ─────────


@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str, days: int | None = Query(None, ge=1, le=365)):
    """回診間整合報告：症狀 + 情緒 + 用藥 + 就診 + 飲食。

    `days` 沒帶時 backend 自動依「上次回診到今天」推算；無回診紀錄則用預設 30。
    顯式帶 `days` 視為覆寫（測試／自訂區間用）。
    """
    data_summary, counts, has_data, days, period_label = _collect_period_summary(
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
    data_summary, counts, has_data, days, period_label = _collect_period_summary(
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

    return {
        "patient_id": patient_id,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        "period_label": period_label,
        "raw_data": counts,
    }


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


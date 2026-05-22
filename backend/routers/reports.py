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

# ── 月度報告 prompt ──────────────────────────────────────────

MONTHLY_SYSTEM_PROMPT = (
    "產出一份回診間整合報告供主治醫師閱讀。\n"
    "語氣：專業、清晰，像同行之間的交班。\n"
    "報告期間會在 user message 開頭以「報告期間：XXX」給出，請依該期間描述，不要假定 30 天。\n\n"
    "報告結構（嚴格使用以下三大段，順序固定，不要新增其他段落，不要在結尾加任何免責聲明）：\n\n"
    "## 1. 臨床觀察\n"
    "用 3–6 個短條列描述本期間患者發生了什麼。涵蓋（資料不足者跳過、不要杜撰）：\n"
    "- 整體狀態走向（穩定／惡化／改善）\n"
    "- 症狀模式：頻率最高的症狀、新出現的症狀、已改善的症狀\n"
    "- 情緒：平均分、趨勢方向、是否有連續低落\n"
    "- 用藥順從性：服藥率、漏藥模式、療效回饋\n"
    "- 飲食：規律度、與疾病飲食禁忌相關的訊號\n"
    "- 患者主動推送：把患者透過「診前報告」推送的事項整理出來，這是患者本人最在意的\n\n"
    "## 2. 追蹤建議\n"
    "提出下次門診值得特別問或量的項目。\n"
    "- 條列 2–4 點：哪些症狀／指標需要進一步追蹤、哪些主訴需要釐清\n"
    "- **嚴禁**寫出具體治療方案、開藥建議、劑量調整、診斷推論\n\n"
    "## 3. 風險提醒\n"
    "需要醫師留意的訊號（連續低落、漏藥模式、新症狀、症狀加劇等）。\n"
    "- 若無顯著風險訊號，請寫「本期間無顯著風險訊號」一句\n\n"
    "規則：\n"
    "- 使用繁體中文 + Markdown 標題與條列\n"
    "- 簡潔專業，不堆砌、不重複資料摘要\n"
    "- 資料不足的部分註明「資料不足」，不杜撰\n"
    "- **不要在結尾加免責聲明**，系統會自動附上固定免責聲明文字"
)

# ── 患者帶去診間用的白話摘要 prompt（病人會看 → 套用風格層） ──

PATIENT_SUMMARY_ROLE_PROMPT = (
    "【本次任務：帶去診間給醫師看的白話摘要（病人視角）】\n"
    "把病人本期間的紀錄整理成一段摘要 — 病人會帶著這份摘要去門診，也可能直接念給醫師聽。\n"
    "報告期間會在 user message 開頭以「報告期間：XXX」給出，請依該期間描述，不要假定 30 天或一個月。\n\n"
    "情境專屬規則：\n"
    "1. 字數以 300–500 字（含空白）為原則，不可少於 300；資料量大可彈性延伸但盡量不超出太多\n"
    "2. 用第一人稱「我」書寫，像病人自己在跟醫師描述\n"
    "3. 一定要涵蓋這幾塊（有資料才寫，沒資料就跳過、不要編造）：\n"
    "   - 最近身體上比較困擾的不舒服（什麼症狀、多常發生、有多嚴重）\n"
    "   - 心情狀態（最近覺得怎樣、有沒有特別低潮的日子）\n"
    "   - 目前在吃的藥、有沒有按時吃、有沒有副作用\n"
    "   - 飲食情況（這段期間吃得規律嗎？有沒有特別常吃或特別不吃的東西？\n"
    "     有沒有跟疾病飲食禁忌相關的訊號？吃完有特別不舒服的紀錄嗎？）\n"
    "   - 最想請醫師幫忙確認或調整的事\n"
    "4. 結構：用 2–4 個自然段落，不要用條列、不要用 markdown 標題\n"
    "5. 結尾用一句感謝或請醫師協助的話收尾\n"
    "6. 只輸出摘要本文，不要前言、不要說明、不要在開頭加標題\n"
    "7. 因為這份是「病人講給醫師聽的描述」、不是病人收到的 AI 回覆，所以**不要**\n"
    "   在結尾加風格層 [D] 的 AI 免責聲明文字（前端會另外渲染）"
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

    has_data = bool(symptoms_data or emotions_data or med_logs_data or records_data or diet_data)
    parts = [f"報告期間：{period_label}\n"]

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

    counts = {
        "symptom_count": len(symptoms_data),
        "emotion_count": len(emotions_data),
        "medication_count": len(active_meds),
        "visit_count": len(records_data),
        "diet_count": len(diet_data),
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
        report_text = call_claude(MONTHLY_SYSTEM_PROMPT, full_summary)
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
        raw = call_claude(checklist_system, user_message)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        checklist = json.loads(raw)
        if not isinstance(checklist, list):
            raise ValueError("Expected a JSON array")
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

    patient_summary_system = build_patient_facing_system(
        PATIENT_SUMMARY_ROLE_PROMPT,
        patient_context=compute_patient_context(patient_id),
        include_examples=True,  # 一整段散文，example 對穩定語氣有幫助
    )

    try:
        summary = call_claude(patient_summary_system, data_summary).strip()
        if summary.startswith("```"):
            summary = summary.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        source = "ai"
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


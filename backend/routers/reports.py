import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from backend.db import get_supabase
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 問診清單 prompt ──────────────────────────────────────────

CHECKLIST_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的問診準備助手。\n"
    "根據患者近期的症狀記錄、情緒狀態和用藥情形，\n"
    "列出這次回診時最需要跟醫師確認的三件事。\n\n"
    "規則：\n"
    "1. 只列三件，依重要性排序\n"
    "2. 每件事用一句話描述，讓患者可以直接照著問\n"
    "3. 語氣親切，像朋友提醒你看醫生前要問什麼\n"
    "4. 使用繁體中文\n"
    "5. 回覆格式：純 JSON 陣列，每個元素是一個字串，不要 markdown\n"
    '範例：["最近頭痛頻率增加，需要調整止痛藥嗎？",'
    '"情緒持續低落，是否需要心理支持？",'
    '"新藥的副作用（胃不舒服）正常嗎？"]'
)

# ── 月度報告 prompt ──────────────────────────────────────────

MONTHLY_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的臨床摘要助手，負責產出 30 天整合報告。\n"
    "報告對象是主治醫師，用專業但清楚的語言。\n\n"
    "報告結構：\n"
    "1. **整體概況** — 一段話總結患者近一個月的狀態變化\n"
    "2. **症狀趨勢** — 頻率最高的症狀、新出現的症狀、已改善的症狀\n"
    "3. **情緒追蹤** — 平均分、趨勢方向、是否有連續低落\n"
    "4. **用藥順從性** — 服藥率、漏藥模式、療效回饋\n"
    "5. **就診紀錄** — 期間內的就診次數與診斷摘要\n"
    "6. **患者主動推送** — 把患者透過「診前報告」推送給您的事項整理出來，這是患者本人最在意的，請特別重視\n"
    "7. **建議關注** — 需要醫師在下次門診特別留意的項目\n\n"
    "使用 Markdown 格式，簡潔專業。如果某類數據不足，註明「資料不足」而非杜撰。\n"
    "結尾務必加一行：「⚠ 本報告由 AI 整理，不可作為診斷或醫療依據。」"
)

# ── 患者帶去診間用的白話摘要 prompt ────────────────────────

PATIENT_SUMMARY_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的健康助理，幫患者把過去 30 天的紀錄整理成一段「帶去診間給醫師看的白話摘要」。\n\n"
    "讀者：患者本人會帶著這份摘要去門診，也可能直接念給醫師聽。\n\n"
    "規則：\n"
    "1. 字數控制在 300–500 字（含空白），不可少於 300、不可超過 500\n"
    "2. 用親切、好懂的口語，避免艱深醫學術語；必要時用括號簡單解釋\n"
    "3. 用第一人稱「我」的角度書寫，像患者自己在跟醫師描述\n"
    "4. 一定要涵蓋這幾塊（有資料才寫，沒資料就跳過、不要編造）：\n"
    "   - 最近身體上比較困擾的症狀（什麼症狀、多常發生、有多嚴重）\n"
    "   - 心情狀態（最近覺得怎樣、有沒有特別低潮的日子）\n"
    "   - 目前在吃的藥、有沒有按時吃、有沒有副作用\n"
    "   - 最想請醫師幫忙確認或調整的事\n"
    "5. 結構：用 2–4 個自然段落，不要用條列、不要用 markdown 標題\n"
    "6. 結尾用一句感謝或請醫師協助的話收尾\n"
    "7. 使用繁體中文\n"
    "8. 只輸出摘要本文，不要前言、不要說明、不要在開頭加標題"
)


# ── 共用：收集近 30 天資料 ───────────────────────────────────


def _empty_summary():
    """DB 整體無法連線時的預設回傳：空 summary、零計數、has_data=False。"""
    return (
        "報告期間：近 30 天\n症狀記錄：無\n情緒記錄：無\n用藥紀錄：無\n就診紀錄：無",
        {"symptom_count": 0, "emotion_count": 0, "medication_count": 0, "visit_count": 0},
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


def _collect_30d_summary(patient_id: str):
    """收集近 30 天症狀／情緒／用藥／就診資料，回傳 (summary_text, raw_counts, has_data)。
    任何 DB / 連線錯誤都會 swallow 成空資料，讓上層仍能產生「資料不足」版本的報告。"""
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"無法連線資料庫，產生空摘要：{e}")
        return _empty_summary()

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

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

    has_data = bool(symptoms_data or emotions_data or med_logs_data or records_data)
    parts = ["報告期間：近 30 天\n"]

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

    counts = {
        "symptom_count": len(symptoms_data),
        "emotion_count": len(emotions_data),
        "medication_count": len(active_meds),
        "visit_count": len(records_data),
    }
    return "\n".join(parts), counts, has_data


# ── 30 天月度報告 ────────────────────────────────────────────


@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str):
    """30 天整合月度報告：症狀 + 情緒 + 用藥 + 就診摘要"""
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"monthly: 無法連線資料庫：{e}")
        return {
            "patient_id": patient_id,
            "report": "目前資料庫尚未連線，無法產出 30 天健康摘要。請稍後再試。",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "db_offline",
            "raw_data": {"symptom_count": 0, "emotion_count": 0, "medication_count": 0, "visit_count": 0},
        }
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # 收集各面向資料（任一資料源失敗都不會炸整支 endpoint）
    symptoms_data = _safe_query(lambda: (
        sb.table("symptoms_log").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).order("created_at").execute().data or []
    ), [])
    emotions_data = _safe_query(lambda: (
        sb.table("emotions").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).order("created_at").execute().data or []
    ), [])
    meds_data = _safe_query(lambda: (
        sb.table("medications").select("*").eq("patient_id", patient_id).execute().data or []
    ), [])
    med_logs_data = _safe_query(lambda: (
        sb.table("medication_logs").select("*").eq("patient_id", patient_id)
        .gte("taken_at", since).execute().data or []
    ), [])
    records_data = _safe_query(lambda: (
        sb.table("medical_records").select("*").eq("patient_id", patient_id)
        .gte("visit_date", since[:10]).order("visit_date").execute().data or []
    ), [])
    # 患者主動推送（doctor_notes 中 tags 含 patient_push）
    pushes_raw = _safe_query(lambda: (
        sb.table("doctor_notes").select("*").eq("patient_id", patient_id)
        .gte("created_at", since).order("created_at", desc=True).execute().data or []
    ), [])
    pushes_data = [
        n for n in pushes_raw
        if isinstance(n.get("tags"), list) and "patient_push" in n["tags"]
    ]

    # 如果完全無資料
    has_data = symptoms_data or emotions_data or med_logs_data or records_data or pushes_data
    if not has_data:
        return {
            "patient_id": patient_id,
            "report": "此患者近 30 天尚無足夠的健康數據可供產出報告。",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_data",
        }

    # 組裝資料摘要
    parts = [f"報告期間：近 30 天\n"]

    # 症狀
    if symptoms_data:
        all_symptoms = []
        for s in symptoms_data:
            syms = s.get("symptoms", [])
            if isinstance(syms, list):
                all_symptoms.extend(syms)
            elif isinstance(syms, str):
                all_symptoms.append(syms)
        symptom_freq = {}
        for sym in all_symptoms:
            symptom_freq[sym] = symptom_freq.get(sym, 0) + 1
        sorted_symptoms = sorted(symptom_freq.items(), key=lambda x: x[1], reverse=True)
        parts.append(f"症狀記錄（{len(symptoms_data)} 筆）：")
        for sym, count in sorted_symptoms[:10]:
            parts.append(f"  - {sym}：{count} 次")
    else:
        parts.append("症狀記錄：無")

    # 情緒
    if emotions_data:
        scores = [e.get("score", 3) for e in emotions_data]
        import statistics
        avg_score = statistics.mean(scores)
        parts.append(f"\n情緒記錄（{len(emotions_data)} 筆）：")
        parts.append(f"  - 平均：{avg_score:.1f}/5")
        parts.append(f"  - 最低：{min(scores)}, 最高：{max(scores)}")
        # 連續低落檢查
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

    # 用藥
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

    # 就診
    if records_data:
        parts.append(f"\n就診紀錄（{len(records_data)} 次）：")
        for r in records_data:
            date = r.get("visit_date", "?")[:10]
            diag = r.get("diagnosis", "未記錄")
            parts.append(f"  - {date}：{diag}")
    else:
        parts.append("\n就診紀錄：無")

    # 患者主動推送（最重要，因為這是患者本人在乎的事）
    if pushes_data:
        parts.append(f"\n患者主動推送（{len(pushes_data)} 則）— **這是患者本人特別想讓您注意的事項**：")
        for p in pushes_data[:10]:
            d = (p.get("created_at") or "?")[:10]
            tags = p.get("tags", []) or []
            cat = next((t for t in tags if t != "patient_push"), "其他")
            content = (p.get("content") or "").strip()
            if len(content) > 200:
                content = content[:200] + "…"
            parts.append(f"  - [{d}][{cat}] {content}")
    else:
        parts.append("\n患者主動推送：無")

    data_summary = "\n".join(parts)

    try:
        report_text = call_claude(MONTHLY_SYSTEM_PROMPT, data_summary)
    except Exception as e:
        logger.error(f"Monthly report generation failed: {e}")
        report_text = f"報告生成失敗，以下為原始數據摘要：\n\n{data_summary}"

    return {
        "patient_id": patient_id,
        "report": report_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai",
        "raw_data": {
            "symptom_count": len(symptoms_data),
            "emotion_count": len(emotions_data),
            "medication_count": len(active_meds),
            "visit_count": len(records_data),
        },
    }


# ── 問診清單 ─────────────────────────────────────────────────


@router.get("/{patient_id}/checklist")
def get_consultation_checklist(patient_id: str):
    """建議問診清單：根據近期數據，生成這次最需要確認的三件事"""
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"checklist: 無法連線資料庫，回預設清單：{e}")
        return {
            "patient_id": patient_id,
            "checklist": [
                "目前身體整體感覺如何？有沒有新的不舒服？",
                "目前的藥有沒有按時吃？有沒有什麼困難？",
                "生活和心情上有沒有需要醫師幫忙的地方？",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "db_offline",
        }

    # 收集患者近期資料（任一失敗都當空陣列處理）
    symptoms_data = _safe_query(lambda: (
        sb.table("symptoms_log").select("*").eq("patient_id", patient_id)
        .order("created_at", desc=True).limit(10).execute().data or []
    ), [])
    emotions_data = _safe_query(lambda: (
        sb.table("emotions").select("*").eq("patient_id", patient_id)
        .order("created_at", desc=True).limit(10).execute().data or []
    ), [])
    medications_data = _safe_query(lambda: (
        sb.table("medications").select("*").eq("patient_id", patient_id)
        .eq("active", 1).execute().data or []
    ), [])

    # 如果完全沒有資料，回傳預設清單
    if not symptoms_data and not emotions_data and not medications_data:
        return {
            "patient_id": patient_id,
            "checklist": [
                "目前身體整體感覺如何？有沒有新的不舒服？",
                "目前的藥有沒有按時吃？有沒有什麼困難？",
                "生活和心情上有沒有需要醫師幫忙的地方？",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "default",
        }

    # 組裝 user prompt
    parts = []
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

    user_message = "以下是這位患者的近期健康數據：\n" + "\n".join(parts)

    try:
        raw = call_claude(CHECKLIST_SYSTEM_PROMPT, user_message)
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
    }


# ── 帶去診間用的白話摘要（300–500 字） ───────────────────────


@router.get("/{patient_id}/patient-summary")
def get_patient_summary(patient_id: str):
    """產出患者帶去診間用的 300–500 字白話摘要（PDF / Word 用）"""
    data_summary, counts, has_data = _collect_30d_summary(patient_id)

    if not has_data:
        fallback = (
            "醫師您好，這次回診前，我把過去一個月的紀錄整理了一下，但其實沒有特別記錄到什麼"
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
            "raw_data": counts,
        }

    try:
        summary = call_claude(PATIENT_SUMMARY_SYSTEM_PROMPT, data_summary).strip()
        if summary.startswith("```"):
            summary = summary.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        source = "ai"
    except Exception as e:
        logger.error(f"Patient summary generation failed: {e}")
        summary = (
            "醫師您好，過去一個月我有持續記錄身體狀況，但這次摘要暫時沒辦法自動產生，"
            "我把原始紀錄帶來，麻煩醫師看一下。謝謝！"
        )
        source = "error"

    return {
        "patient_id": patient_id,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
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
def wellness_correlation(patient_id: str, days: int = 30):
    """
    每日「心情」與「用藥改善程度」的相關性（Pearson）。
    回傳並排的每日序列與相關係數，前端可畫雙線圖。
    """
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
        "series": series,
        "paired_days": len(paired_x),
        "pearson_r": r,
        "interpretation": interpretation,
    }


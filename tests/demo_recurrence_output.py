"""一次性 demo：本地 SQLite 灌測試病患 → 跑復發風險預測引擎 → 印真實 JSON。

不連 production、不需任何憑證。隔離到臨時 DB，跑完自動清理。
跑法：python tests/demo_recurrence_output.py
"""
import os
import sys
import json
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import backend.db as db

# 隔離到臨時 DB，避免污染本地 dev DB（直接用 SQLite client，繞過 get_supabase 的 provider 選擇）
db.DB_PATH = os.path.join(HERE, "_demo_predict.db")
db._db_initialized = False
for ext in ("", "-wal", "-shm"):
    p = db.DB_PATH + ext
    if os.path.exists(p):
        os.remove(p)
db._init_db()

from backend.utils import recurrence

sb = db._SqliteSupabase()

PID = "demo-patient-001"
DISEASE = "類風濕性關節炎"
now = datetime.utcnow()


def ins(table, row):
    sb.table(table).insert(row).execute()


def dt(days_ago, hour=9):
    return (now - timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M:%S")


# ── 疾病文獻知識：給預測「疾病錨 + 文獻驅動因子加權 + 引用」──────────
recurrence_data = {
    "matched": True,
    "recurrence_rate": {
        "band": "high",
        "range_text": "控制不佳或停藥者一年內復發約 50–70%",
        "horizon": "12 個月",
        "summary": "類風濕性關節炎為慢性自體免疫疾病，規律用藥與壓力控制是復發的關鍵。",
    },
    "drivers": [
        {"maps_to": "adherence", "weight": "high",
         "evidence": "停用或漏服 DMARDs 顯著升高復發風險（多項世代研究）。"},
        {"maps_to": "stress", "weight": "medium",
         "evidence": "心理壓力與 RA 疾病活動度上升相關。"},
        {"maps_to": "sleep", "weight": "medium",
         "evidence": "睡眠不足與發炎指標及晨僵惡化相關。"},
        {"maps_to": "symptoms", "weight": "high",
         "evidence": "關節腫痛頻率增加常為復發前兆。"},
    ],
    "watch_signs": ["晨僵超過 30 分鐘", "新發關節腫脹", "對稱性關節疼痛加劇"],
    "disclaimer": "以上為族群層級文獻，個別情況請以主治醫師評估為準。",
}
references_data = [
    {"pmid": "29420902", "title": "Predictors of flare in rheumatoid arthritis", "year": 2018, "source": "PubMed"},
    {"pmid": "31278997", "title": "Medication adherence and disease flare in RA", "year": 2019, "source": "PubMed"},
]
ins("disease_reference", {
    "name_zh": DISEASE,
    "name_en": "Rheumatoid Arthritis",
    "aliases": ["RA", "類風濕關節炎"],
    "recurrence_data": recurrence_data,
    "references_data": references_data,
    "source": "demo",
})

# 病患本體（多張縱向表有 FOREIGN KEY → patients(id)，先建好以滿足約束）
ins("patients", {"id": PID, "name": "示範病患"})

# ── 縱向紀錄：基準窗(14–50天)穩定、近 14 天惡化、最近 7 天最糟 ──────
# 情緒 1(差)~5(好)
for d in range(0, 51):
    score = 2 if d <= 6 else (3 if d <= 13 else 4)
    ins("emotions", {"patient_id": PID, "score": score, "note": "", "created_at": dt(d)})

# 服藥：近 7 天常漏、8–14 天偶漏、基準規律
for d in range(0, 51):
    if d <= 6:
        taken = 0 if d % 2 == 0 else 1
    elif d <= 13:
        taken = 0 if d % 3 == 0 else 1
    else:
        taken = 1
    ins("medication_logs", {"patient_id": PID, "taken": taken, "taken_at": dt(d)})

# 症狀：近 14 天每天記錄（變頻繁）；基準每 4 天一筆
for d in range(0, 14):
    ins("symptoms_log", {"patient_id": PID, "symptoms": "關節腫痛", "created_at": dt(d)})
for d in range(14, 51, 4):
    ins("symptoms_log", {"patient_id": PID, "symptoms": "輕微僵硬", "created_at": dt(d)})

# 睡眠（床邊自由文字）：近 14 天差、基準正常
for d in range(0, 14):
    ins("bedside_logs", {"patient_id": PID, "sleep": "失眠、睡不好", "note": "", "created_at": dt(d)})
for d in range(14, 51, 2):
    ins("bedside_logs", {"patient_id": PID, "sleep": "正常", "note": "", "created_at": dt(d)})

# 飲食：基準每天記錄、近 14 天變少（自我管理鬆懈）
for d in range(14, 51):
    ins("diet_records", {"patient_id": PID, "meal_type": "lunch", "foods": "便當", "eaten_at": dt(d)})
for d in range(0, 14, 3):
    ins("diet_records", {"patient_id": PID, "meal_type": "lunch", "foods": "外食", "eaten_at": dt(d)})

# 就診：基準一次急性發作、近期一次回診（同時是 trend 的 flare 標記）
ins("medical_records", {"patient_id": PID, "visit_date": dt(40), "diagnosis": "類風濕性關節炎急性發作", "symptoms": "多關節腫痛"})
ins("medical_records", {"patient_id": PID, "visit_date": dt(5), "diagnosis": "關節腫痛回診", "symptoms": "晨僵"})


def show(title, obj):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


try:
    pred = recurrence.predict(sb, PID, disease_hint=DISEASE)
    exp = recurrence.explain(sb, PID, now, disease_hint=DISEASE)
    trend = recurrence.trend_series(sb, PID, 90, disease_hint=DISEASE)

    show("POST /predict/{id} — 風險卡 (畫面 A)", pred)
    show("GET /explain/{id} — 因子瀑布條 (畫面 C)", exp)

    trend_summary = {
        "window_days": trend["window_days"],
        "horizon_days": trend["horizon_days"],
        "bands": trend["bands"],
        "n_points": len(trend["points"]),
        "first_point": trend["points"][0] if trend["points"] else None,
        "last_point": trend["points"][-1] if trend["points"] else None,
        "flare_events": trend["flare_events"],
        "disease": {
            "disease_name": trend["disease"].get("disease_name"),
            "recurrence_band": trend["disease"].get("recurrence_band"),
            "has_literature": trend["disease"].get("has_literature"),
        },
    }
    show("GET /predict/{id}/trend — 趨勢圖 (畫面 B) [精簡]", trend_summary)
finally:
    for ext in ("", "-wal", "-shm"):
        p = db.DB_PATH + ext
        if os.path.exists(p):
            os.remove(p)

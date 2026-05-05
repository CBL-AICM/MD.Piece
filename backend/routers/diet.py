"""飲食模組

- GET  /diet/guide/{patient_id}    根據病史 AI 生成個人化飲食指南（3 段）
- POST /diet/records               紀錄一餐
- GET  /diet/records/{patient_id}  取得當日（或近 N 天）飲食紀錄

LLM 走 backend.services.llm_service.call_claude（預設 Ollama，雲端 fallback Anthropic/Groq）。

Supabase 需要的資料表（migration SQL）：

    create table if not exists diet_records (
        id          uuid primary key default gen_random_uuid(),
        patient_id  text not null,
        meal_type   text not null check (meal_type in ('breakfast','lunch','dinner','snack')),
        foods       text not null,
        note        text default '',
        eaten_at    timestamptz not null default now(),
        created_at  timestamptz not null default now()
    );
    create index if not exists diet_records_patient_eaten_idx
        on diet_records (patient_id, eaten_at desc);
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, date
import json
import logging

from backend.db import get_supabase
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()


DIET_SYSTEM_PROMPT = (
    "你是一位專業的臨床營養師。根據患者目前已知的診斷，給出『個人化』飲食建議。\n"
    "輸出必須是純 JSON（不要 markdown code block），結構如下：\n"
    "{\n"
    '  "daily_targets": {\n'
    '    "protein_g": <整數>,    // 每日蛋白質克數（成人約 0.8-1.2 g/kg；不知體重給 60）\n'
    '    "water_ml":  <整數>,    // 每日水分 ml（一般 1500-2500）\n'
    '    "fiber_g":   <整數>     // 每日膳食纖維克數（一般 20-30）\n'
    "  },\n"
    '  "general_tips": [<字串>], // 3-5 條通用飲食衛教\n'
    '  "warnings": [             // 依患者每個疾病分別列\n'
    '    {"disease": "<疾病名稱>", "avoid": [<食物>...], "reason": "<簡短說明>"}\n'
    "  ],\n"
    '  "meal_suggestions": {     // 三餐建議食物（已避開所有 warnings.avoid）\n'
    '    "breakfast": [<食物>...],   // 5-8 樣\n'
    '    "lunch":     [<食物>...],\n'
    '    "dinner":    [<食物>...]\n'
    "  }\n"
    "}\n"
    "規則：\n"
    "1. 一律繁體中文台灣用語\n"
    "2. warnings 只列患者『實際有的疾病』；無病史就回空陣列\n"
    "3. meal_suggestions 的食物必須完全避開 warnings 列出的禁忌\n"
    "4. 不下診斷、不開藥；若涉及警訊請在 reason 提醒就醫\n"
    "5. 寧可保守給日常常見食物，不要瞎掰罕見食材\n"
)


DIET_FALLBACK = {
    "daily_targets": {"protein_g": 60, "water_ml": 2000, "fiber_g": 25},
    "general_tips": [
        "三餐定時定量，避免暴飲暴食",
        "每餐都有蛋白質、蔬菜與全穀類",
        "減少油炸、加工食品與含糖飲料",
        "餐前 30 分鐘喝一杯水有助消化",
    ],
    "warnings": [],
    "meal_suggestions": {
        "breakfast": ["燕麥粥", "水煮蛋", "無糖豆漿", "新鮮水果", "全麥吐司"],
        "lunch":     ["糙米飯", "清蒸魚", "燙青菜", "豆腐湯", "蘋果"],
        "dinner":    ["蔬菜雞胸肉", "地瓜", "涼拌蔬菜", "番茄牛肉湯"],
    },
}


def _patient_diagnoses(patient_id: str) -> List[str]:
    """從 medical_records 撈該患者所有診斷字串（去重、保留順序）。"""
    sb = get_supabase()
    try:
        rows = (
            sb.table("medical_records")
              .select("diagnosis")
              .eq("patient_id", patient_id)
              .execute()
        )
        seen, result = set(), []
        for r in (rows.data or []):
            d = (r.get("diagnosis") or "").strip()
            if d and d not in seen:
                seen.add(d)
                result.append(d)
        return result
    except Exception as e:
        logger.warning(f"讀取病史失敗：{e}")
        return []


def _parse_diet_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{"):
        l, r = text.find("{"), text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l:r + 1]
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


@router.get("/guide/{patient_id}")
def get_diet_guide(patient_id: str):
    """根據患者病史 AI 生成個人化飲食指南。"""
    diagnoses = _patient_diagnoses(patient_id)
    user_msg = (
        f"患者已知診斷：{', '.join(diagnoses) if diagnoses else '（尚無病史紀錄）'}\n"
        "請依規格產出飲食建議 JSON。"
    )
    try:
        raw = call_claude(DIET_SYSTEM_PROMPT, user_msg)
        parsed = _parse_diet_json(raw)
    except Exception as e:
        logger.error(f"飲食指南 LLM 失敗：{e}")
        parsed = {}

    # 合併 fallback：缺欄補上、避免前端拿到 None
    if not parsed:
        parsed = dict(DIET_FALLBACK)
    else:
        for k, v in DIET_FALLBACK.items():
            parsed.setdefault(k, v)
        # daily_targets 內個別欄位也補
        dt = parsed.get("daily_targets") or {}
        for k, v in DIET_FALLBACK["daily_targets"].items():
            dt.setdefault(k, v)
        parsed["daily_targets"] = dt
    parsed["diagnoses"] = diagnoses
    return parsed


class DietRecordIn(BaseModel):
    patient_id: str
    meal_type: str  # breakfast | lunch | dinner | snack
    foods: str      # 文字描述：「白飯、滷雞腿、燙青菜」
    note: str = ""
    eaten_at: Optional[datetime] = None


VALID_MEALS = {"breakfast", "lunch", "dinner", "snack"}


@router.post("/records")
def log_diet_record(body: DietRecordIn):
    if body.meal_type not in VALID_MEALS:
        raise HTTPException(status_code=400, detail=f"meal_type 必須是 {sorted(VALID_MEALS)}")
    foods = body.foods.strip()
    if not foods:
        raise HTTPException(status_code=400, detail="foods 不能空白")

    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "meal_type":  body.meal_type,
        "foods":      foods,
        "note":       body.note.strip(),
        "eaten_at":   (body.eaten_at or datetime.utcnow()).isoformat(),
    }
    try:
        result = sb.table("diet_records").insert(data).execute()
        return {"ok": True, "record": (result.data or [None])[0]}
    except Exception as e:
        logger.error(f"飲食紀錄寫入失敗：{e}")
        raise HTTPException(status_code=500, detail="紀錄寫入失敗")


@router.get("/records/{patient_id}")
def get_diet_records(
    patient_id: str,
    date_str: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD；不填回近 N 天"),
    days: int = Query(7, ge=1, le=90),
):
    sb = get_supabase()
    q = sb.table("diet_records").select("*").eq("patient_id", patient_id)
    if date_str:
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式必須是 YYYY-MM-DD")
        start = datetime.combine(d, datetime.min.time()).isoformat()
        end   = datetime.combine(d + timedelta(days=1), datetime.min.time()).isoformat()
        q = q.gte("eaten_at", start).lt("eaten_at", end)
    else:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        q = q.gte("eaten_at", since)

    try:
        rows = q.order("eaten_at", desc=True).execute()
        return {"records": rows.data or []}
    except Exception as e:
        logger.error(f"讀取飲食紀錄失敗：{e}")
        return {"records": [], "error": str(e)}

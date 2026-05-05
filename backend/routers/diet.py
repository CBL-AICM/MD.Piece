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


# ─── 吃什麼神器 ───────────────────────────────────────────
# 給選擇障礙的患者用：依病史隨機推薦『一道具體菜色』，可以再 roll。

PICK_SYSTEM_PROMPT = (
    "你是台灣的飲食推薦達人。患者選擇障礙，需要你**只給一道**具體的菜色。\n"
    "輸出必須是純 JSON（不要 markdown），結構：\n"
    "{\n"
    '  "name":         "<菜色名，要具體：例「滷肉飯配燙青菜」「味噌鮭魚定食」「麻油雞麵線」>",\n'
    '  "components":   [<3-6 種主要食材或配菜>],\n'
    '  "cuisine":      "<台/日/中/西/泰/韓/早餐...>",\n'
    '  "reason":       "<為什麼適合這位患者，1-2 句口語>",\n'
    '  "where_to_get": "<可以去哪買：自助餐/便當店/超商/早餐店/自煮>"\n'
    "}\n"
    "規則：\n"
    "1. name 必須是具體可立刻買到/做到的菜色，不要寫『健康餐』『均衡飲食』這種模糊詞\n"
    "2. 完全避開患者疾病禁忌（痛風→無海鮮/啤酒/內臟；糖尿病→無含糖飲料/精緻糖；高血壓→低鈉；自體免疫→無花生/酒精）\n"
    "3. **必須符合指定餐別時段**：\n"
    "   - breakfast → 早餐性質：蛋餅/吐司/粥/三明治/豆漿米漿/燕麥/水煮蛋等，不要推中午便當\n"
    "   - lunch → 中餐：便當/飯類/麵類/定食等正餐，份量足\n"
    "   - dinner → 晚餐：清淡正餐為主，避免油炸大餐\n"
    "   - snack → 點心：水果/堅果/優格/小份量輕食，不是正餐\n"
    "4. 一律繁體中文台灣用語\n"
    "5. 不要給出 exclude 名單裡已經被丟掉的菜\n"
    "6. 寧可常見好取得，不要瞎掰罕見料理\n"
)


def _auto_meal_by_hour(now: Optional[datetime] = None) -> str:
    """依目前台灣時間自動決定餐別（'any' 時用）。"""
    h = (now or datetime.utcnow() + timedelta(hours=8)).hour  # UTC+8
    if 5 <= h < 10:    return "breakfast"
    if 10 <= h < 14:   return "lunch"
    if 14 <= h < 17:   return "snack"
    if 17 <= h < 21:   return "dinner"
    return "snack"


def _diagnosis_flags(diagnoses: List[str]) -> dict:
    """從診斷字串萃取常見疾病旗標，給 fallback pool 的安全過濾用。"""
    text = " ".join(diagnoses)
    return {
        "gout":         any(k in text for k in ["痛風", "Gout", "gout"]),
        "diabetes":     any(k in text for k in ["糖尿", "Diabetes", "diabetes", "DM"]),
        "hypertension": any(k in text for k in ["高血壓", "Hypertension", "hypertension", "HTN"]),
        "ckd":          any(k in text for k in ["腎", "Kidney", "kidney", "CKD"]),
        "autoimmune":   any(k in text for k in ["紅斑", "狼瘡", "Lupus", "lupus", "自體免疫", "類風濕", "RA"]),
        "ibs":          any(k in text for k in ["腸躁", "IBS", "胃潰瘍", "胃食道逆流", "GERD"]),
    }


# 每道菜標記：_unfit（不適合的疾病旗標）、_meals（適合的餐別）
# fallback 用；LLM 主路徑會自己處理疾病與餐別
PICK_FALLBACK_POOL = [
    # ── 早餐 ──
    {"name": "玉米蛋餅+無糖豆漿",  "components": ["蛋餅皮", "玉米", "蛋", "無糖豆漿"],       "cuisine": "台早", "where_to_get": "早餐店",   "reason": "早餐快速款、蛋白質有",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "鹹粥配蘿蔔糕",       "components": ["米", "瘦肉", "香菇", "蘿蔔糕"],           "cuisine": "台早", "where_to_get": "早餐店",   "reason": "溫熱好入口",
     "_unfit": ["hypertension"], "_meals": ["breakfast"]},
    {"name": "雞肉三明治+無糖紅茶", "components": ["全麥吐司", "雞胸肉", "生菜", "番茄"],     "cuisine": "西", "where_to_get": "早餐店",     "reason": "好攜帶、蛋白質充足",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "燕麥粥+水煮蛋+水果", "components": ["燕麥", "牛奶", "水煮蛋", "香蕉"],         "cuisine": "西", "where_to_get": "自煮",       "reason": "高纖好消化",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "饅頭夾蛋+無糖豆漿",  "components": ["饅頭", "蛋", "肉鬆", "無糖豆漿"],         "cuisine": "中", "where_to_get": "早餐店",     "reason": "經典中式早餐",
     "_unfit": [], "_meals": ["breakfast"]},

    # ── 午餐 ──
    {"name": "滷肉飯配燙青菜",     "components": ["滷肉", "白飯", "青菜", "滷蛋"],          "cuisine": "台", "where_to_get": "自助餐",     "reason": "便當店標配，澱粉蛋白蔬菜都有",
     "_unfit": ["hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "蒜泥白肉便當",       "components": ["白肉", "蒜泥醬", "白飯", "高麗菜"],       "cuisine": "台", "where_to_get": "便當店",     "reason": "蒸煮為主、油不重",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "雞肉飯便當",         "components": ["雞絲", "雞汁飯", "燙青菜", "蛋"],         "cuisine": "台", "where_to_get": "便當店",     "reason": "嘉義雞肉飯經典款",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "牛肉麵（清燉）",     "components": ["牛肉", "麵條", "青菜", "蘿蔔"],           "cuisine": "台", "where_to_get": "麵店",       "reason": "清燉湯頭比紅燒少油鈉",
     "_unfit": ["gout", "hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "雞絲涼麵（少醬）",   "components": ["雞絲", "麵條", "小黃瓜", "胡麻醬"],       "cuisine": "台", "where_to_get": "便利商店",   "reason": "夏天清爽選擇",
     "_unfit": ["diabetes"], "_meals": ["lunch"]},
    {"name": "豬肉水餃（10 顆）+ 燙青菜", "components": ["豬肉水餃", "燙青菜"],             "cuisine": "中", "where_to_get": "水餃店",     "reason": "簡單一餐解決",
     "_unfit": ["hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "雞胸肉沙拉碗",       "components": ["雞胸肉", "生菜", "番茄", "玉米", "藜麥"], "cuisine": "西", "where_to_get": "輕食店",     "reason": "高蛋白低油",
     "_unfit": [], "_meals": ["lunch"]},

    # ── 晚餐 ──
    {"name": "味噌鮭魚定食",       "components": ["鮭魚", "白飯", "味噌湯", "醃菜"],         "cuisine": "日", "where_to_get": "日式定食店", "reason": "鮭魚蛋白質好、好消化",
     "_unfit": ["gout", "hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "番茄炒蛋蓋飯",       "components": ["番茄", "蛋", "白飯", "蔥"],               "cuisine": "中", "where_to_get": "自煮",       "reason": "30 秒能想到的家常",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "蒸蛋豆腐+地瓜飯",    "components": ["蒸蛋", "豆腐", "地瓜", "白飯"],           "cuisine": "中", "where_to_get": "自煮",       "reason": "好消化、植物蛋白",
     "_unfit": ["ckd"], "_meals": ["dinner"]},
    {"name": "清蒸魚配糙米飯",     "components": ["白肉魚", "糙米飯", "燙青菜"],             "cuisine": "中", "where_to_get": "自煮",       "reason": "低油低鈉、高纖",
     "_unfit": ["gout"], "_meals": ["dinner"]},
    {"name": "蔬菜雞肉湯麵",       "components": ["雞胸肉", "麵", "高麗菜", "蘿蔔"],         "cuisine": "中", "where_to_get": "麵店",       "reason": "晚餐清淡好消化",
     "_unfit": [], "_meals": ["dinner"]},

    # ── 點心 ──
    {"name": "希臘優格+藍莓",      "components": ["無糖優格", "藍莓", "燕麥粒"],             "cuisine": "西", "where_to_get": "超商",       "reason": "蛋白質+抗氧化",
     "_unfit": [], "_meals": ["snack"]},
    {"name": "水煮蛋+小番茄",      "components": ["水煮蛋", "小番茄"],                       "cuisine": "—", "where_to_get": "超商",       "reason": "簡單高蛋白",
     "_unfit": [], "_meals": ["snack"]},
    {"name": "綜合堅果一小把",     "components": ["杏仁", "腰果", "核桃"],                   "cuisine": "—", "where_to_get": "超商",       "reason": "好油脂、有飽足感",
     "_unfit": ["autoimmune"], "_meals": ["snack"]},
    {"name": "香蕉+無糖豆漿",      "components": ["香蕉", "無糖豆漿"],                       "cuisine": "—", "where_to_get": "超商",       "reason": "下午低血糖救援",
     "_unfit": ["ckd"], "_meals": ["snack"]},
    {"name": "蘋果切片+花生醬",    "components": ["蘋果", "花生醬"],                         "cuisine": "西", "where_to_get": "超商",       "reason": "纖維+蛋白質",
     "_unfit": ["autoimmune"], "_meals": ["snack"]},
]


def _filter_pool_by_diagnoses(pool: list, flags: dict) -> list:
    """濾掉 _unfit 命中目前任一旗標的選項。"""
    active = {k for k, v in flags.items() if v}
    if not active:
        return pool
    return [m for m in pool if not (set(m.get("_unfit") or []) & active)]


def _filter_pool_by_meal(pool: list, meal: str) -> list:
    """只留下適合該餐別的菜（_meals 欄位包含 meal）。'any' 不過濾。"""
    if meal == "any" or not meal:
        return pool
    return [m for m in pool if meal in (m.get("_meals") or [])]


@router.get("/pick/{patient_id}")
def pick_meal(
    patient_id: str,
    meal_type: str = Query("any", description="breakfast/lunch/dinner/snack/any"),
    exclude: str = Query("", description="逗號分隔，已被丟掉的菜色，避免重複推薦"),
):
    """吃什麼神器：依病史 + 餐別時段隨機推薦一道具體菜色，避開禁忌與已丟掉的選項。"""
    diagnoses = _patient_diagnoses(patient_id)
    excluded = [x.strip() for x in exclude.split(",") if x.strip()]

    # any → 依現在台灣時間自動決定
    resolved_meal = _auto_meal_by_hour() if meal_type == "any" else meal_type
    if resolved_meal not in {"breakfast", "lunch", "dinner", "snack"}:
        resolved_meal = "lunch"

    meal_zh = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "點心"}[resolved_meal]
    user_msg = (
        f"患者已知診斷：{', '.join(diagnoses) if diagnoses else '（無紀錄）'}\n"
        f"想吃的餐別：{resolved_meal}（{meal_zh}）\n"
        f"已經被丟掉的菜（不要再推）：{', '.join(excluded) if excluded else '（無）'}\n"
        "請給一道**符合該餐別性質**且符合疾病禁忌的具體菜色 JSON。"
    )

    try:
        raw = call_claude(PICK_SYSTEM_PROMPT, user_msg)
        parsed = _parse_diet_json(raw)
    except Exception as e:
        logger.error(f"吃什麼神器 LLM 失敗：{e}")
        parsed = {}

    if not parsed or not parsed.get("name"):
        # Fallback：依餐別 + 疾病旗標過濾後隨機抽一個沒被排除的
        import random
        flags = _diagnosis_flags(diagnoses)
        meal_pool = _filter_pool_by_meal(PICK_FALLBACK_POOL, resolved_meal)
        safe_pool = _filter_pool_by_diagnoses(meal_pool, flags)
        pool = [m for m in safe_pool if m["name"] not in excluded]
        # 全濾光時的退讓順序：safe_pool → meal_pool → 全部
        if not pool:
            pool = safe_pool or meal_pool or PICK_FALLBACK_POOL
        choice = dict(random.choice(pool))
        choice.pop("_unfit", None)
        choice.pop("_meals", None)
        choice.setdefault("reason", "先給你一個常見的選擇")
        choice["fallback"] = True
        parsed = choice

    parsed["diagnoses"] = diagnoses
    parsed["meal_type"] = resolved_meal
    return parsed


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

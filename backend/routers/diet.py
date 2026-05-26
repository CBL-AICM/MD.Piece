"""飲食模組

- GET  /diet/guide/{patient_id}    根據病史 AI 生成個人化飲食指南（3 段）
- POST /diet/records               紀錄一餐
- GET  /diet/records/{patient_id}  取得當日（或近 N 天）飲食紀錄
- GET  /diet/weekly/{patient_id}   近 N 週滾動 7 天彙整（純統計、無 LLM）

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
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, date
import concurrent.futures
import json
import logging
import re

from backend.db import get_supabase
from backend.services.llm_service import build_patient_facing_system, call_claude
from backend.utils.diet_nutrient_llm import estimate_nutrients as _estimate_nutrients_llm

logger = logging.getLogger(__name__)
router = APIRouter()


# 同 reports.py / education.py：Vercel lambda 60s 上限，LLM provider fallback chain
# 最壞 ~75s 會把 lambda 砍掉，前端 fetch 永遠不 resolve → 「幫你想想…」spinner
# 轉到天荒地老。包一層硬超時 45s，超時就 raise 讓上層 except 走 fallback pool。
_LLM_HARD_TIMEOUT_S = 45
_LLM_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _call_claude_bounded(system_prompt: str, user_message: str) -> str:
    fut = _LLM_EXECUTOR.submit(call_claude, system_prompt, user_message)
    return fut.result(timeout=_LLM_HARD_TIMEOUT_S)


_DIET_GUIDE_ROLE = (
    "【本次任務：個人化飲食指南】\n"
    "根據病人目前已知的診斷，給出個人化飲食建議。general_tips / warnings.reason\n"
    "都是病人會直接讀到的文字 — 嚴格遵守風格層 [A][B][C]，特別是：\n"
    "  - 不審判（不要說「您不能吃…」這種命令口吻；改用「這個盡量少一點比較好」）\n"
    "  - 不下診斷（reason 只能描述「為什麼這種疾病會建議少吃」）\n"
    "  - warnings 是「建議避開」，不是「禁止」 — 留決定權給醫師 / 病人\n\n"
    "輸出必須是純 JSON（不要 markdown code block），結構如下：\n"
    "{\n"
    '  "daily_targets": {\n'
    '    "protein_g": <整數>,    // 每日蛋白質克數（成人約 0.8-1.2 g/kg；不知體重給 60）\n'
    '    "water_ml":  <整數>,    // 每日水分 ml（一般 1500-2500）\n'
    '    "fiber_g":   <整數>     // 每日膳食纖維克數（一般 20-30）\n'
    "  },\n"
    '  "general_tips": [<字串>], // 3-5 條通用飲食衛教（遵守風格層）\n'
    '  "warnings": [             // 依患者每個疾病分別列\n'
    '    {"disease": "<疾病名稱>", "avoid": [<食物>...], "reason": "<簡短說明，遵守風格層>"}\n'
    "  ],\n"
    '  "meal_suggestions": {     // 三餐建議食物（已避開所有 warnings.avoid）\n'
    '    "breakfast": [<食物>...],   // 5-8 樣\n'
    '    "lunch":     [<食物>...],\n'
    '    "dinner":    [<食物>...]\n'
    "  }\n"
    "}\n"
    "情境專屬規則：\n"
    "1. 一律繁體中文台灣用語\n"
    "2. warnings 只列患者「實際有的疾病」；無病史就回空陣列\n"
    "3. meal_suggestions 的食物必須完全避開 warnings 列出的禁忌\n"
    "4. 不下診斷、不開藥；若涉及警訊請在 reason 提醒「請與醫師確認」\n"
    "5. 寧可保守給日常常見食物，不要瞎掰罕見食材\n"
)


DIET_SYSTEM_PROMPT = build_patient_facing_system(
    _DIET_GUIDE_ROLE,
    patient_context=None,
    include_examples=False,
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


# 疾病 → 該避開的食物 + 原因。確定性對應表，避免把這種教科書級的查表丟給 LLM
# 還可能漏掉或瞎掰。比對採子字串：list 內 key（例：「高血壓」）若出現在患者任一
# diagnosis 字串中（例：「高血壓 stage 1」、「Hypertension（高血壓）」）即命中。
# 用 list-of-tuple 而非 dict 是為了保持插入順序、避免每次回應順序跳動。
DISEASE_FOOD_WARNINGS: List[tuple] = [
    ("高血壓", {
        "avoid": ["醃漬醬瓜 / 鹹蛋 / 鹹魚", "加工肉品（培根、香腸、火腿）", "泡麵與調理包湯底", "鹹味零食、洋芋片", "高湯包 / 雞精"],
        "reason": "減少鈉攝取（每日 < 2300 mg），避免血壓升高、降低心臟與腎臟負擔",
    }),
    ("糖尿病", {
        "avoid": ["含糖飲料（手搖、汽水、果汁）", "蛋糕 / 甜點 / 餅乾", "精製白米飯（建議換糙米或地瓜）", "蜜餞 / 果乾", "酒精"],
        "reason": "避免血糖快速升高；含糖飲料是台灣糖友最常見的失控來源",
    }),
    ("高血脂", {
        "avoid": ["內臟（豬肝、雞胗、腦）", "蛋黃過量（每日 > 1 顆）", "肥肉與油炸物", "椰子油 / 棕櫚油", "奶油酥皮類點心"],
        "reason": "減少飽和脂肪與膽固醇，降低動脈硬化與心血管事件風險",
    }),
    ("痛風", {
        "avoid": ["內臟（肝、腎、腦）", "海鮮（沙丁魚、蝦蟹、貝類）", "啤酒 / 烈酒", "濃肉湯與火鍋湯底", "含糖飲料（果糖會升尿酸）"],
        "reason": "高普林與高果糖食物會讓血中尿酸升高、誘發痛風發作",
    }),
    ("洗腎", {
        "avoid": ["楊桃（神經毒素禁忌）", "高鉀食物（香蕉、深綠葉菜、堅果）", "加工肉品 / 火鍋料（高磷）", "可樂等深色汽水", "過量水分（請遵醫囑限水）"],
        "reason": "透析患者對鉀、磷、水分極敏感；楊桃對腎友是絕對禁忌",
    }),
    ("腎", {
        "avoid": ["楊桃（神經毒素禁忌）", "高鉀食物（香蕉、深綠葉菜、果汁）", "加工食品（高磷）", "可樂等深色汽水", "湯與火鍋湯底（高鈉）"],
        "reason": "減少鉀、磷、鈉與蛋白負擔，避免電解質失衡與惡化腎功能",
    }),
    ("胃食道逆流", {
        "avoid": ["咖啡 / 濃茶", "巧克力", "辛辣 / 麻辣鍋", "油炸物", "酒精", "薄荷"],
        "reason": "這些食物會讓下食道括約肌鬆弛或胃酸增加，加重火燒心",
    }),
    ("胃潰瘍", {
        "avoid": ["辛辣食物", "酒精", "咖啡 / 濃茶", "碳酸飲料", "急性期避免粗硬高纖蔬菜"],
        "reason": "避免刺激胃黏膜、減緩潰瘍癒合",
    }),
    ("肝", {
        "avoid": ["酒精（一律避免）", "生海鮮（生蠔、生魚片）", "發霉食物 / 過期堅果", "加工肉品", "過量保健品 / 草藥"],
        "reason": "酒精與黴菌毒素直接傷肝；肝功能不佳要避免生食感染風險",
    }),
    ("心臟", {
        "avoid": ["高鈉食物（醃漬、加工肉）", "反式脂肪（酥皮、奶精）", "油炸物", "酒精過量", "含糖飲料"],
        "reason": "減少血壓與血脂負擔，降低心血管事件風險",
    }),
    ("中風", {
        "avoid": ["高鈉食物", "肥肉與內臟", "酒精", "含糖飲料"],
        "reason": "控制血壓與血脂，預防二次中風",
    }),
    ("甲狀腺亢進", {
        "avoid": ["海帶 / 紫菜 / 海藻", "高碘食鹽", "咖啡因（咖啡、濃茶）", "酒精"],
        "reason": "高碘會加重亢進；咖啡因會加劇心悸與失眠",
    }),
    ("甲狀腺低下", {
        "avoid": ["大量生十字花科蔬菜（生花椰菜、生高麗菜）", "過量大豆製品", "服藥前後 1 小時的咖啡 / 牛奶"],
        "reason": "這些食物可能干擾甲狀腺荷爾蒙合成或影響藥物吸收",
    }),
    ("骨質疏鬆", {
        "avoid": ["過量咖啡因（> 3 杯/天）", "高鈉食物", "酒精", "碳酸飲料"],
        "reason": "這些會加速鈣質流失；補鈣同時要少這些",
    }),
    ("貧血", {
        "avoid": ["飯後立刻喝茶 / 咖啡", "鈣片與鐵劑同時服用", "全麥麩皮（含植酸）大量併餐"],
        "reason": "鞣酸、鈣與植酸會干擾鐵吸收，建議與鐵質食物分開 1-2 小時",
    }),
    ("失眠", {
        "avoid": ["午後咖啡 / 茶", "晚餐後酒精", "辛辣或過油晚餐", "睡前大餐"],
        "reason": "咖啡因半衰期長達 5-6 小時；酒精會打斷深層睡眠",
    }),
]


def _build_warnings_from_diseases(diseases: List[str]) -> List[dict]:
    """把患者登記的疾病字串對應到該避開的食物清單。

    比對採子字串：DISEASE_FOOD_WARNINGS 的 key（例：「高血壓」）若出現在患者任一
    diagnosis 字串中即命中。用 dict 去重 + 維持命中順序，避免同一規則因不同
    diagnosis 字面（「高血壓」、「Hypertension（高血壓）第二期」）重複出現。
    """
    if not diseases:
        return []
    hits: dict = {}
    for dx in diseases:
        for key, payload in DISEASE_FOOD_WARNINGS:
            if key in dx and key not in hits:
                hits[key] = {
                    "disease": key,
                    "avoid": list(payload["avoid"]),
                    "reason": payload["reason"],
                }
    return list(hits.values())


def _patient_diagnoses(patient_id: str) -> List[str]:
    """彙整患者所有「登記過的疾病」字串（去重、保留發現順序）。

    來源：
      1. medical_records.diagnosis — 看診後寫入的正式診斷
      2. patient_profiles.conditions / current_disease — 使用者在個人檔案
         自行登記的慢性病與目前疾病（自由填、可能逗號 / 頓號 / 換行分隔）
    """
    sb = get_supabase()
    seen: set = set()
    result: List[str] = []

    def _add(s):
        s = (s or "").strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    try:
        rows = (
            sb.table("medical_records")
              .select("diagnosis")
              .eq("patient_id", patient_id)
              .execute()
        )
        for r in (rows.data or []):
            _add(r.get("diagnosis") or "")
    except Exception as e:
        logger.warning(f"讀取 medical_records 失敗：{e}")

    try:
        profile = (
            sb.table("patient_profiles")
              .select("conditions,current_disease")
              .eq("user_id", patient_id)
              .execute()
        )
        for r in (profile.data or []):
            for field in ("conditions", "current_disease"):
                raw = r.get(field) or ""
                # 自由欄位可能用逗號、頓號、分號、換行分隔多項
                for piece in re.split(r"[,，;；、\n\r]+", raw):
                    _add(piece)
    except Exception as e:
        logger.warning(f"讀取 patient_profiles 疾病欄位失敗：{e}")

    return result


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
    """根據患者登記疾病生成飲食指南。

    warnings（要避開的食物）走確定性查表 DISEASE_FOOD_WARNINGS — 食物禁忌
    對應疾病是教科書級的查表問題，不該交給 LLM 還可能漏掉或瞎掰（Rule 5）；
    確定性查表也讓沒連線 / 沒 API key 的環境照樣能正確顯示警告。
    general_tips 與 meal_suggestions 仍透過 LLM 做個人化，失敗時退回 DIET_FALLBACK。
    """
    diagnoses = _patient_diagnoses(patient_id)
    warnings = _build_warnings_from_diseases(diagnoses)

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
    # warnings 一律覆蓋成確定性版本（不採用 LLM 的回答）
    parsed["warnings"] = warnings
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

_PICK_ROLE = (
    "【本次任務：吃什麼神器（推薦一道具體菜色）】\n"
    "病人選擇障礙，需要你**只給一道**具體的菜色。reason 是病人會直接讀到的文字 —\n"
    "嚴格遵守風格層 [A][B][C]，特別是「不下診斷」「不審判」「用陪伴口吻」。\n\n"
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
    "7. 在台灣可以善用便利商店（7-11、全家）的品項：御飯糰、關東煮、茶葉蛋、"
    "低卡便當、御便當、優格、無糖豆漿、地瓜、香蕉、即食雞胸、蛋沙拉三明治、"
    "蕎麥涼麵、味噌湯、低糖燕麥飲、蘿蔔糕等。where_to_get 寫『7-11』或『全家』即可。\n"
    "8. **必須符合患者指定的價位等級**：\n"
    "   - $ → 整餐控制在 100 元台幣內（超商御飯糰、便當店便當、自煮、麵店小份）\n"
    "   - $$ → 100-200 元（一般便當/麵食/簡餐）\n"
    "   - $$$ → 200 元以上（餐廳定食、健康餐盒、輕食店沙拉碗）\n"
    "   - any → 不限\n"
    '   並把估計價位寫在 JSON 多一個欄位 "price_tier": "$/$$/$$$"，整數預估價位 "price_twd": <數字>\n'
    "9. **必須符合患者指定的熱量等級**：\n"
    "   - low → 整餐熱量 ≤ 350 kcal（輕食、沙拉、湯麵、優格）\n"
    "   - mid → 350-650 kcal（一般便當、麵食、定食）\n"
    "   - high → ≥ 650 kcal（重份量便當、油炸、披薩、火鍋）\n"
    "   - any → 不限\n"
    '   並把估計熱量寫在 JSON 多一個欄位 "calorie_tier": "low/mid/high"，整數熱量 "calorie_kcal": <數字>\n'
    "10. **個人不吃的食材黑名單**（dislike）：完全不要包含這些食材，一個都不行。\n"
    "11. **附近選項**（nearby=true）：請只推薦『便利商店、便當店、早餐店、麵店、自助餐』"
    "等台灣街頭隨便走都能找到的選項，不要推日式定食店、輕食店、需要訂位的餐廳。\n"
    "12. **本週已吃過**（recently_eaten）：避免推薦相似的菜色或關鍵食材，給點變化。\n"
)


PICK_SYSTEM_PROMPT = build_patient_facing_system(
    _PICK_ROLE,
    patient_context=None,
    include_examples=False,
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
    {"name": "玉米蛋餅+無糖豆漿",  "components": ["蛋餅皮", "玉米", "蛋", "無糖豆漿"],       "cuisine": "台早", "where_to_get": "早餐店",   "reason": "早餐快速款、蛋白質有",         "price_tier": "$",  "price_twd": 70, "calorie_kcal": 350, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "鹹粥配蘿蔔糕",       "components": ["米", "瘦肉", "香菇", "蘿蔔糕"],           "cuisine": "台早", "where_to_get": "早餐店",   "reason": "溫熱好入口",                    "price_tier": "$",  "price_twd": 80, "calorie_kcal": 420, "calorie_tier": "mid",
     "_unfit": ["hypertension"], "_meals": ["breakfast"]},
    {"name": "雞肉三明治+無糖紅茶", "components": ["全麥吐司", "雞胸肉", "生菜", "番茄"],     "cuisine": "西", "where_to_get": "早餐店",     "reason": "好攜帶、蛋白質充足",            "price_tier": "$",  "price_twd": 90, "calorie_kcal": 320, "calorie_tier": "low",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "燕麥粥+水煮蛋+水果", "components": ["燕麥", "牛奶", "水煮蛋", "香蕉"],         "cuisine": "西", "where_to_get": "自煮",       "reason": "高纖好消化",                    "price_tier": "$",  "price_twd": 50, "calorie_kcal": 330, "calorie_tier": "low",
     "_unfit": [], "_meals": ["breakfast"]},
    {"name": "饅頭夾蛋+無糖豆漿",  "components": ["饅頭", "蛋", "肉鬆", "無糖豆漿"],         "cuisine": "中", "where_to_get": "早餐店",     "reason": "經典中式早餐",                  "price_tier": "$",  "price_twd": 60, "calorie_kcal": 380, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["breakfast"]},

    # ── 午餐 ──
    {"name": "滷肉飯配燙青菜",     "components": ["滷肉", "白飯", "青菜", "滷蛋"],          "cuisine": "台", "where_to_get": "自助餐",     "reason": "便當店標配，澱粉蛋白蔬菜都有",  "price_tier": "$",  "price_twd": 90, "calorie_kcal": 650, "calorie_tier": "high",
     "_unfit": ["hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "蒜泥白肉便當",       "components": ["白肉", "蒜泥醬", "白飯", "高麗菜"],       "cuisine": "台", "where_to_get": "便當店",     "reason": "蒸煮為主、油不重",              "price_tier": "$$", "price_twd": 110, "calorie_kcal": 620, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "雞肉飯便當",         "components": ["雞絲", "雞汁飯", "燙青菜", "蛋"],         "cuisine": "台", "where_to_get": "便當店",     "reason": "嘉義雞肉飯經典款",              "price_tier": "$",  "price_twd": 90, "calorie_kcal": 550, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "牛肉麵（清燉）",     "components": ["牛肉", "麵條", "青菜", "蘿蔔"],           "cuisine": "台", "where_to_get": "麵店",       "reason": "清燉湯頭比紅燒少油鈉",          "price_tier": "$$", "price_twd": 180, "calorie_kcal": 580, "calorie_tier": "mid",
     "_unfit": ["gout", "hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "雞絲涼麵（少醬）",   "components": ["雞絲", "麵條", "小黃瓜", "胡麻醬"],       "cuisine": "台", "where_to_get": "便利商店",   "reason": "夏天清爽選擇",                  "price_tier": "$",  "price_twd": 75, "calorie_kcal": 450, "calorie_tier": "mid",
     "_unfit": ["diabetes"], "_meals": ["lunch"]},
    {"name": "豬肉水餃（10 顆）+ 燙青菜", "components": ["豬肉水餃", "燙青菜"],             "cuisine": "中", "where_to_get": "水餃店",     "reason": "簡單一餐解決",                  "price_tier": "$$", "price_twd": 130, "calorie_kcal": 500, "calorie_tier": "mid",
     "_unfit": ["hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "雞胸肉沙拉碗",       "components": ["雞胸肉", "生菜", "番茄", "玉米", "藜麥"], "cuisine": "西", "where_to_get": "輕食店",     "reason": "高蛋白低油",                    "price_tier": "$$$","price_twd": 220, "calorie_kcal": 380, "calorie_tier": "low",
     "_unfit": [], "_meals": ["lunch"]},

    # ── 晚餐 ──
    {"name": "味噌鮭魚定食",       "components": ["鮭魚", "白飯", "味噌湯", "醃菜"],         "cuisine": "日", "where_to_get": "日式定食店", "reason": "鮭魚蛋白質好、好消化",          "price_tier": "$$$","price_twd": 280, "calorie_kcal": 700, "calorie_tier": "high",
     "_unfit": ["gout", "hypertension"], "_meals": ["lunch", "dinner"]},
    {"name": "番茄炒蛋蓋飯",       "components": ["番茄", "蛋", "白飯", "蔥"],               "cuisine": "中", "where_to_get": "自煮",       "reason": "30 秒能想到的家常",             "price_tier": "$",  "price_twd": 40, "calorie_kcal": 520, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "蒸蛋豆腐+地瓜飯",    "components": ["蒸蛋", "豆腐", "地瓜", "白飯"],           "cuisine": "中", "where_to_get": "自煮",       "reason": "好消化、植物蛋白",              "price_tier": "$",  "price_twd": 50, "calorie_kcal": 430, "calorie_tier": "mid",
     "_unfit": ["ckd"], "_meals": ["dinner"]},
    {"name": "清蒸魚配糙米飯",     "components": ["白肉魚", "糙米飯", "燙青菜"],             "cuisine": "中", "where_to_get": "自煮",       "reason": "低油低鈉、高纖",                "price_tier": "$$", "price_twd": 120, "calorie_kcal": 500, "calorie_tier": "mid",
     "_unfit": ["gout"], "_meals": ["dinner"]},
    {"name": "蔬菜雞肉湯麵",       "components": ["雞胸肉", "麵", "高麗菜", "蘿蔔"],         "cuisine": "中", "where_to_get": "麵店",       "reason": "晚餐清淡好消化",                "price_tier": "$$", "price_twd": 140, "calorie_kcal": 480, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["dinner"]},

    # ── 點心 ──
    {"name": "希臘優格+藍莓",      "components": ["無糖優格", "藍莓", "燕麥粒"],             "cuisine": "西", "where_to_get": "7-11",       "reason": "蛋白質+抗氧化",                 "price_tier": "$$", "price_twd": 110, "calorie_kcal": 220, "calorie_tier": "low",
     "_unfit": [], "_meals": ["snack"]},
    {"name": "茶葉蛋+小番茄",      "components": ["茶葉蛋", "小番茄"],                       "cuisine": "—", "where_to_get": "7-11",       "reason": "簡單高蛋白",                    "price_tier": "$",  "price_twd": 35, "calorie_kcal": 110, "calorie_tier": "low",
     "_unfit": [], "_meals": ["snack"]},
    {"name": "綜合堅果一小把",     "components": ["杏仁", "腰果", "核桃"],                   "cuisine": "—", "where_to_get": "全家",       "reason": "好油脂、有飽足感",              "price_tier": "$",  "price_twd": 60, "calorie_kcal": 200, "calorie_tier": "low",
     "_unfit": ["autoimmune"], "_meals": ["snack"]},
    {"name": "香蕉+無糖豆漿",      "components": ["香蕉", "無糖豆漿"],                       "cuisine": "—", "where_to_get": "7-11",       "reason": "下午低血糖救援",                "price_tier": "$",  "price_twd": 50, "calorie_kcal": 200, "calorie_tier": "low",
     "_unfit": ["ckd"], "_meals": ["snack"]},
    {"name": "夯番薯",             "components": ["地瓜"],                                   "cuisine": "—", "where_to_get": "7-11",       "reason": "高纖低 GI 又有飽足感",          "price_tier": "$",  "price_twd": 35, "calorie_kcal": 180, "calorie_tier": "low",
     "_unfit": ["ckd"], "_meals": ["snack", "breakfast"]},

    # ── 超商（早 / 午 / 晚 都能吃） ──
    {"name": "鮪魚御飯糰+無糖綠茶", "components": ["御飯糰", "鮪魚", "無糖綠茶"],            "cuisine": "—", "where_to_get": "7-11",       "reason": "通勤時最快的早餐",              "price_tier": "$",  "price_twd": 65, "calorie_kcal": 280, "calorie_tier": "low",
     "_unfit": ["gout"], "_meals": ["breakfast", "lunch"]},
    {"name": "鹽味雞胸肉+地瓜+無糖豆漿", "components": ["即食雞胸肉", "地瓜", "無糖豆漿"],   "cuisine": "—", "where_to_get": "7-11",       "reason": "高蛋白健身餐",                  "price_tier": "$$", "price_twd": 130, "calorie_kcal": 450, "calorie_tier": "mid",
     "_unfit": ["ckd"], "_meals": ["lunch", "dinner"]},
    {"name": "低卡蔬菜雞肉便當",   "components": ["雞胸肉", "糙米飯", "青花菜", "南瓜"],     "cuisine": "—", "where_to_get": "全家",       "reason": "便當區熱量最低那一格",          "price_tier": "$$", "price_twd": 130, "calorie_kcal": 380, "calorie_tier": "low",
     "_unfit": [], "_meals": ["lunch", "dinner"]},
    {"name": "蛋沙拉三明治+牛奶",  "components": ["全麥三明治", "蛋沙拉", "鮮奶"],           "cuisine": "西", "where_to_get": "全家",       "reason": "好攜帶補蛋白",                  "price_tier": "$",  "price_twd": 80, "calorie_kcal": 380, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["breakfast", "lunch"]},
    {"name": "關東煮（蛋+蘿蔔+青菜捲）", "components": ["茶葉蛋", "白蘿蔔", "蔬菜捲", "杏鮑菇"], "cuisine": "—", "where_to_get": "7-11",   "reason": "暖胃低油",                      "price_tier": "$",  "price_twd": 80, "calorie_kcal": 160, "calorie_tier": "low",
     "_unfit": ["hypertension"], "_meals": ["lunch", "dinner", "snack"]},
    {"name": "蕎麥涼麵+和風醬",    "components": ["蕎麥麵", "海苔", "蔥花"],                 "cuisine": "日", "where_to_get": "7-11",       "reason": "夏天低 GI 選擇",                "price_tier": "$$", "price_twd": 100, "calorie_kcal": 350, "calorie_tier": "mid",
     "_unfit": [], "_meals": ["lunch"]},
    {"name": "燕麥牛奶+水煮蛋",    "components": ["即食燕麥", "鮮奶", "水煮蛋"],             "cuisine": "—", "where_to_get": "全家",       "reason": "懶人早餐",                      "price_tier": "$",  "price_twd": 70, "calorie_kcal": 320, "calorie_tier": "low",
     "_unfit": [], "_meals": ["breakfast"]},
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


def _filter_pool_by_price(pool: list, price_tier: str) -> list:
    """依價位等級過濾（$/$$/$$$）。'any' 不過濾。"""
    if price_tier in ("any", "", None):
        return pool
    return [m for m in pool if (m.get("price_tier") or "") == price_tier]


def _filter_pool_by_calorie(pool: list, tier: str) -> list:
    """依熱量等級過濾（low/mid/high）。'any' 不過濾。"""
    if tier in ("any", "", None):
        return pool
    return [m for m in pool if (m.get("calorie_tier") or "") == tier]


def _filter_pool_by_dislike(pool: list, dislikes: List[str]) -> list:
    """濾掉名稱或食材命中黑名單關鍵字的選項。"""
    if not dislikes:
        return pool
    out = []
    for m in pool:
        text = (m.get("name") or "") + " " + " ".join(m.get("components") or [])
        if any(d and d in text for d in dislikes):
            continue
        out.append(m)
    return out


# 「附近」過濾：只留下台灣街頭隨處可見的取得管道
NEARBY_VENDORS = {"7-11", "全家", "超商", "便利商店", "便當店", "早餐店", "麵店", "自助餐", "水餃店"}


def _filter_pool_by_nearby(pool: list, nearby: bool) -> list:
    if not nearby:
        return pool
    return [m for m in pool if (m.get("where_to_get") or "") in NEARBY_VENDORS]


def _recent_eaten_foods(patient_id: str, days: int = 7) -> List[str]:
    """讀過去 N 天的飲食紀錄 foods 欄位（去重，限 30 筆避免 prompt 爆）。"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        rows = (
            sb.table("diet_records")
              .select("foods")
              .eq("patient_id", patient_id)
              .gte("eaten_at", since)
              .order("eaten_at", desc=True)
              .limit(30)
              .execute()
        )
        seen, out = set(), []
        for r in (rows.data or []):
            f = (r.get("foods") or "").strip()
            if f and f not in seen:
                seen.add(f)
                out.append(f)
        return out
    except Exception as e:
        logger.warning(f"讀取近期飲食紀錄失敗：{e}")
        return []


VALID_PRICE_TIERS = {"any", "$", "$$", "$$$"}
VALID_CALORIE_TIERS = {"any", "low", "mid", "high"}


@router.get("/pick/{patient_id}")
def pick_meal(
    patient_id: str,
    meal_type:    str  = Query("any", description="breakfast/lunch/dinner/snack/any"),
    price_tier:   str  = Query("any", description="$ / $$ / $$$ / any（價位等級）"),
    calorie_tier: str  = Query("any", description="low / mid / high / any（熱量等級）"),
    nearby:       bool = Query(False, description="是否只推薦街頭隨處可得的選項"),
    avoid_recent: bool = Query(True,  description="是否避開本週吃過的"),
    exclude:      str  = Query("",    description="逗號分隔，已被丟掉的菜色"),
    dislike:      str  = Query("",    description="逗號分隔，個人不吃的食材"),
):
    """吃什麼神器：依病史 + 餐別 + 價位 + 熱量 + 黑名單 + 附近 + 歷史隨機推薦一道菜。"""
    diagnoses = _patient_diagnoses(patient_id)
    excluded  = [x.strip() for x in exclude.split(",") if x.strip()]
    dislikes  = [x.strip() for x in dislike.split(",") if x.strip()]

    # any → 依現在台灣時間自動決定
    resolved_meal = _auto_meal_by_hour() if meal_type == "any" else meal_type
    if resolved_meal not in {"breakfast", "lunch", "dinner", "snack"}:
        resolved_meal = "lunch"

    if price_tier   not in VALID_PRICE_TIERS:   price_tier = "any"
    if calorie_tier not in VALID_CALORIE_TIERS: calorie_tier = "any"

    # 自動避開本週已吃過的
    recent_foods = _recent_eaten_foods(patient_id, days=7) if avoid_recent else []

    meal_zh = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "點心"}[resolved_meal]
    price_zh_map = {"$": "100 元以內", "$$": "100-200 元", "$$$": "200 元以上", "any": "不限"}
    cal_zh_map   = {"low": "輕量 ≤350 kcal", "mid": "一般 350-650 kcal", "high": "高熱量 ≥650 kcal", "any": "不限"}
    user_msg = (
        f"患者已知診斷：{', '.join(diagnoses) if diagnoses else '（無紀錄）'}\n"
        f"想吃的餐別：{resolved_meal}（{meal_zh}）\n"
        f"預算價位：{price_tier}（{price_zh_map[price_tier]}）\n"
        f"熱量等級：{calorie_tier}（{cal_zh_map[calorie_tier]}）\n"
        f"附近選項：{'是（限便利商店/便當店/早餐店等）' if nearby else '否'}\n"
        f"個人不吃食材：{', '.join(dislikes) if dislikes else '（無）'}\n"
        f"本週已吃過：{', '.join(recent_foods) if recent_foods else '（無紀錄）'}\n"
        f"已 reroll 排除：{', '.join(excluded) if excluded else '（無）'}\n"
        "請給一道符合上面所有條件的具體菜色 JSON，"
        "務必同時填 price_tier、price_twd、calorie_tier、calorie_kcal 四個欄位。"
    )

    try:
        raw = _call_claude_bounded(PICK_SYSTEM_PROMPT, user_msg)
        parsed = _parse_diet_json(raw)
    except concurrent.futures.TimeoutError:
        logger.warning(f"吃什麼神器 LLM timeout (>{_LLM_HARD_TIMEOUT_S}s)，走 fallback pool")
        parsed = {}
    except Exception as e:
        logger.error(f"吃什麼神器 LLM 失敗：{e}")
        parsed = {}

    if not parsed or not parsed.get("name"):
        # Fallback：餐別 → 疾病 → 附近 → 黑名單 → 價位 → 熱量 → 排除
        import random
        flags        = _diagnosis_flags(diagnoses)
        meal_pool    = _filter_pool_by_meal(PICK_FALLBACK_POOL, resolved_meal)
        safe_pool    = _filter_pool_by_diagnoses(meal_pool, flags)
        nearby_pool  = _filter_pool_by_nearby(safe_pool, nearby)
        liked_pool   = _filter_pool_by_dislike(nearby_pool, dislikes)
        priced_pool  = _filter_pool_by_price(liked_pool, price_tier)
        cal_pool     = _filter_pool_by_calorie(priced_pool, calorie_tier)
        # 加入歷史避免：對 fallback 用 substring 比對
        def not_recent(m: dict) -> bool:
            if not recent_foods:
                return True
            txt = m.get("name", "")
            return not any(rf and (rf in txt or txt in rf) for rf in recent_foods)
        history_pool = [m for m in cal_pool if not_recent(m)]
        pool = [m for m in history_pool if m["name"] not in excluded]
        # 一連串退讓
        if not pool:
            pool = (history_pool or cal_pool or priced_pool or liked_pool or
                    nearby_pool or safe_pool or meal_pool or PICK_FALLBACK_POOL)
        choice = dict(random.choice(pool))
        for k in ("_unfit", "_meals"):
            choice.pop(k, None)
        choice.setdefault("reason", "先給你一個常見的選擇")
        choice["fallback"] = True
        parsed = choice

    parsed["diagnoses"]    = diagnoses
    parsed["meal_type"]    = resolved_meal
    parsed.setdefault("price_tier",   price_tier   if price_tier   != "any" else None)
    parsed.setdefault("calorie_tier", calorie_tier if calorie_tier != "any" else None)
    return parsed


# ─── 喝什麼神器 + 咖啡因衛教 ────────────────────────────
# 飲料推薦走另一條 prompt + pool；同樣依疾病過濾，並回傳咖啡因 mg。

_DRINK_ROLE = (
    "【本次任務：喝什麼神器（推薦一杯飲料）】\n"
    "病人選擇障礙，需要你**只給一杯**具體飲料。reason 是病人會直接讀到的文字 —\n"
    "嚴格遵守風格層 [A][B][C]，特別是「不下診斷」「不審判」「用陪伴口吻」。\n\n"
    "輸出純 JSON（不要 markdown）：\n"
    "{\n"
    '  "name":          "<飲料名，要具體：例「無糖綠茶」「拿鐵咖啡（中杯）」「無糖豆漿」>",\n'
    '  "components":    [<2-4 個關鍵成分或描述：含糖度/溫度/特色>],\n'
    '  "category":      "<茶/咖啡/豆漿/牛奶/果汁/水/氣泡水/手搖/酒/其他>",\n'
    '  "where_to_get":  "<7-11/全家/手搖店/咖啡店/自製>",\n'
    '  "price_tier":    "<$/$$/$$$>",\n'
    '  "price_twd":     <整數>,\n'
    '  "calorie_kcal":  <整數>,\n'
    '  "caffeine_mg":   <整數，無咖啡因填 0>,\n'
    '  "sugar_level":   "<無糖/微糖/半糖/全糖/不適用>",\n'
    '  "reason":        "<為什麼適合這位患者，1-2 句口語>"\n'
    "}\n"
    "規則：\n"
    "1. 完全避開疾病禁忌：糖尿病→無糖或微糖、痛風→不含啤酒/果糖含量高的飲料、"
    "高血壓→低咖啡因、CKD→低鉀低磷（少柳橙汁/牛奶）、自體免疫→無酒精、"
    "焦慮/失眠→低咖啡因、孕婦/哺乳→無酒精且咖啡因<200mg、心律不整→低咖啡因。\n"
    "2. 不要給黑名單成分，一個都不行。\n"
    "3. 一律繁體中文台灣用語。\n"
    "4. 不要給 exclude 名單裡的飲料。\n"
    "5. 寧可常見好取得（超商/手搖/咖啡店），不要瞎掰罕見品項。\n"
    "6. 必須準確估計 caffeine_mg：無咖啡因飲料填 0。\n"
)


DRINK_SYSTEM_PROMPT = build_patient_facing_system(
    _DRINK_ROLE,
    patient_context=None,
    include_examples=False,
)


# 飲料 fallback pool；caffeine_mg 為粗估
DRINK_FALLBACK_POOL = [
    # 無咖啡因 / 安全選擇
    {"name": "白開水",            "components": ["水"],                        "category": "水",     "where_to_get": "自取",   "price_tier": "$",  "price_twd": 0,   "calorie_kcal": 0,   "caffeine_mg": 0,   "sugar_level": "不適用", "reason": "永遠不會錯",
     "_unfit": []},
    {"name": "無糖氣泡水",        "components": ["氣泡水"],                    "category": "氣泡水", "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 30,  "calorie_kcal": 0,   "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "想要點口感的選擇",
     "_unfit": []},
    {"name": "無糖綠茶",          "components": ["綠茶"],                      "category": "茶",     "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 30,  "calorie_kcal": 0,   "caffeine_mg": 30,  "sugar_level": "無糖",   "reason": "解膩好搭配",
     "_unfit": ["caffeine_sensitive"]},
    {"name": "無糖紅茶",          "components": ["紅茶"],                      "category": "茶",     "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 30,  "calorie_kcal": 0,   "caffeine_mg": 40,  "sugar_level": "無糖",   "reason": "經典款",
     "_unfit": ["caffeine_sensitive"]},
    {"name": "無糖豆漿",          "components": ["黃豆"],                      "category": "豆漿",   "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 30,  "calorie_kcal": 90,  "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "蛋白質補充",
     "_unfit": ["ckd"]},  # 豆製品蛋白磷
    {"name": "無糖優酪乳",        "components": ["優酪乳", "活菌"],            "category": "牛奶",   "where_to_get": "全家",   "price_tier": "$$", "price_twd": 60,  "calorie_kcal": 130, "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "顧腸道",
     "_unfit": ["ckd"]},  # 乳製品鉀磷

    # 茶類
    {"name": "微糖烏龍茶",        "components": ["烏龍茶"],                    "category": "茶",     "where_to_get": "手搖店", "price_tier": "$$", "price_twd": 50,  "calorie_kcal": 80,  "caffeine_mg": 35,  "sugar_level": "微糖",   "reason": "不太甜的茶款",
     "_unfit": ["diabetes", "caffeine_sensitive"]},
    {"name": "麥茶（無糖）",      "components": ["麥茶"],                      "category": "茶",     "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 30,  "calorie_kcal": 0,   "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "完全無咖啡因",
     "_unfit": []},
    {"name": "黑咖啡",            "components": ["阿拉比卡豆"],                "category": "咖啡",   "where_to_get": "7-11",   "price_tier": "$",  "price_twd": 45,  "calorie_kcal": 5,   "caffeine_mg": 130, "sugar_level": "無糖",   "reason": "提神經典",
     "_unfit": ["caffeine_sensitive", "pregnancy"]},
    {"name": "拿鐵（中杯，少糖）", "components": ["濃縮咖啡", "鮮奶"],         "category": "咖啡",   "where_to_get": "咖啡店", "price_tier": "$$", "price_twd": 90,  "calorie_kcal": 150, "caffeine_mg": 90,  "sugar_level": "微糖",   "reason": "咖啡 + 蛋白質",
     "_unfit": ["caffeine_sensitive", "pregnancy", "ckd"]},

    # 手搖飲（注意疾病）
    {"name": "無糖青茶",          "components": ["青茶"],                      "category": "手搖",   "where_to_get": "手搖店", "price_tier": "$$", "price_twd": 40,  "calorie_kcal": 0,   "caffeine_mg": 30,  "sugar_level": "無糖",   "reason": "手搖店無糖選擇",
     "_unfit": ["caffeine_sensitive"]},
    {"name": "微糖蜂蜜檸檬",      "components": ["檸檬", "蜂蜜"],              "category": "手搖",   "where_to_get": "手搖店", "price_tier": "$$", "price_twd": 50,  "calorie_kcal": 90,  "caffeine_mg": 0,   "sugar_level": "微糖",   "reason": "想喝點酸甜",
     "_unfit": ["diabetes"]},

    # 牛奶 / 替代奶
    {"name": "鮮奶（小瓶）",      "components": ["鮮奶"],                      "category": "牛奶",   "where_to_get": "7-11",   "price_tier": "$$", "price_twd": 35,  "calorie_kcal": 130, "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "鈣質補充",
     "_unfit": ["ckd"]},
    {"name": "燕麥奶（無糖）",    "components": ["燕麥奶"],                    "category": "牛奶",   "where_to_get": "全家",   "price_tier": "$$", "price_twd": 60,  "calorie_kcal": 110, "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "乳糖不耐 / 純素友善",
     "_unfit": []},

    # 果汁類（多數疾病要小心）
    {"name": "番茄汁（無鹽）",    "components": ["番茄"],                      "category": "果汁",   "where_to_get": "7-11",   "price_tier": "$$", "price_twd": 40,  "calorie_kcal": 60,  "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "茄紅素",
     "_unfit": ["hypertension"]},
    {"name": "椰子水",            "components": ["椰子水"],                    "category": "果汁",   "where_to_get": "7-11",   "price_tier": "$$", "price_twd": 45,  "calorie_kcal": 70,  "caffeine_mg": 0,   "sugar_level": "無糖",   "reason": "天然電解質",
     "_unfit": ["ckd"]},  # 鉀偏高
]


# 咖啡因衛教資料（給 UI 顯示）
CAFFEINE_GUIDE = {
    "daily_safe_mg": 400,
    "pregnancy_safe_mg": 200,
    "common_sources": [
        {"item": "黑咖啡（中杯）",        "mg": 130},
        {"item": "拿鐵 / 美式",           "mg": 95},
        {"item": "紅茶（一杯）",          "mg": 40},
        {"item": "綠茶（一杯）",          "mg": 30},
        {"item": "可樂（330ml）",         "mg": 35},
        {"item": "巧克力（牛奶）",        "mg": 10},
    ],
    "warnings": [
        {"group": "孕婦 / 哺乳期",   "limit": "≤ 200 mg/天", "note": "過量可能影響胎兒發育、新生兒睡眠"},
        {"group": "兒童 / 青少年",  "limit": "≤ 100 mg/天", "note": "易影響睡眠與發育"},
        {"group": "心律不整 / 心悸", "limit": "盡量避免",   "note": "咖啡因會加快心跳、誘發心悸"},
        {"group": "高血壓",         "limit": "≤ 200 mg/天", "note": "短期可能升高血壓 5-10 mmHg"},
        {"group": "焦慮 / 失眠",    "limit": "下午後不要喝", "note": "半衰期 5-6 小時，會干擾睡眠與焦慮"},
        {"group": "胃食道逆流",     "limit": "盡量少喝",   "note": "咖啡會放鬆下食道括約肌"},
        {"group": "服用某些藥物",   "limit": "問藥師",     "note": "某些抗憂鬱藥、避孕藥會延長咖啡因作用"},
    ],
}


def _drink_unfit_flags(diagnoses: List[str]) -> dict:
    """飲料用的擴充疾病旗標（除了通用六項，加上咖啡因敏感與孕期）。"""
    flags = _diagnosis_flags(diagnoses)
    text = " ".join(diagnoses)
    flags["caffeine_sensitive"] = any(k in text for k in [
        "心律不整", "心悸", "Arrhyth", "焦慮", "Anxiety", "anxiety", "失眠", "Insomnia", "胃食道逆流", "GERD",
    ])
    flags["pregnancy"] = any(k in text for k in ["懷孕", "妊娠", "Pregnan", "pregnan", "哺乳"])
    return flags


@router.get("/drink/{patient_id}")
def pick_drink(
    patient_id: str,
    price_tier:  str  = Query("any", description="$ / $$ / $$$ / any"),
    nearby:      bool = Query(False, description="是否只推附近能取得"),
    avoid_recent: bool = Query(True, description="是否避開本週喝過的"),
    exclude:     str  = Query("",    description="逗號分隔，已被丟掉的飲料"),
    dislike:     str  = Query("",    description="逗號分隔，個人不喝的成分"),
):
    """喝什麼神器：依病史隨機推薦一杯具體飲料，含咖啡因 mg 與糖度。"""
    diagnoses = _patient_diagnoses(patient_id)
    excluded  = [x.strip() for x in exclude.split(",") if x.strip()]
    dislikes  = [x.strip() for x in dislike.split(",") if x.strip()]

    if price_tier not in VALID_PRICE_TIERS:
        price_tier = "any"

    recent_foods = _recent_eaten_foods(patient_id, days=7) if avoid_recent else []

    price_zh_map = {"$": "50 元以內", "$$": "50-100 元", "$$$": "100 元以上", "any": "不限"}
    user_msg = (
        f"患者已知診斷：{', '.join(diagnoses) if diagnoses else '（無紀錄）'}\n"
        f"預算價位：{price_tier}（{price_zh_map[price_tier]}）\n"
        f"附近選項：{'是' if nearby else '否'}\n"
        f"個人不喝成分：{', '.join(dislikes) if dislikes else '（無）'}\n"
        f"本週已紀錄：{', '.join(recent_foods) if recent_foods else '（無）'}\n"
        f"已 reroll 排除：{', '.join(excluded) if excluded else '（無）'}\n"
        "請給一杯符合上面所有條件的具體飲料 JSON。"
    )

    try:
        raw = _call_claude_bounded(DRINK_SYSTEM_PROMPT, user_msg)
        parsed = _parse_diet_json(raw)
    except concurrent.futures.TimeoutError:
        logger.warning(f"喝什麼神器 LLM timeout (>{_LLM_HARD_TIMEOUT_S}s)，走 fallback pool")
        parsed = {}
    except Exception as e:
        logger.error(f"喝什麼神器 LLM 失敗：{e}")
        parsed = {}

    if not parsed or not parsed.get("name"):
        import random
        flags = _drink_unfit_flags(diagnoses)
        active = {k for k, v in flags.items() if v}
        safe = [m for m in DRINK_FALLBACK_POOL if not (set(m.get("_unfit") or []) & active)]
        if nearby:
            safe = [m for m in safe if (m.get("where_to_get") or "") in NEARBY_VENDORS]
        if dislikes:
            safe = _filter_pool_by_dislike(safe, dislikes)
        priced = _filter_pool_by_price(safe, price_tier)
        if recent_foods:
            priced = [m for m in priced
                      if not any(rf and (rf in m.get("name", "") or m.get("name", "") in rf) for rf in recent_foods)]
        pool = [m for m in priced if m["name"] not in excluded]
        if not pool:
            pool = priced or safe or DRINK_FALLBACK_POOL
        choice = dict(random.choice(pool))
        choice.pop("_unfit", None)
        choice.setdefault("reason", "先給你一杯常見的選擇")
        choice["fallback"] = True
        parsed = choice

    parsed["diagnoses"] = diagnoses
    return parsed


@router.get("/caffeine-guide")
def get_caffeine_guide():
    """咖啡因衛教資料（靜態，無個人化）。"""
    return CAFFEINE_GUIDE


@router.get("/records/{patient_id}")
def get_diet_records(
    patient_id: str,
    date_str: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD；不填回近 N 天"),
    days: int = Query(7, ge=1, le=90),
    # JS Date.getTimezoneOffset() 規格：分鐘、UTC 西側為正。台灣 = -480。
    # 前端不傳 → 預設台灣（-480），讓打卡當下立刻顯示在「今日」。
    tz_offset: int = Query(-480, ge=-840, le=840, description="使用者時區（分鐘，JS 規格）"),
):
    sb = get_supabase()
    q = sb.table("diet_records").select("*").eq("patient_id", patient_id)
    if date_str:
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式必須是 YYYY-MM-DD")
        # 把「使用者本地的這一天」換成 UTC 範圍：local + tz_offset = UTC
        local_start = datetime.combine(d, datetime.min.time())
        local_end   = datetime.combine(d + timedelta(days=1), datetime.min.time())
        start = (local_start + timedelta(minutes=tz_offset)).isoformat()
        end   = (local_end   + timedelta(minutes=tz_offset)).isoformat()
        q = q.gte("eaten_at", start).lt("eaten_at", end)
    else:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        q = q.gte("eaten_at", since)

    try:
        rows = q.order("eaten_at", desc=True).execute()
        return {"records": rows.data or []}
    except Exception as e:
        logger.error(f"讀取飲食紀錄失敗：{e}")
        return {"records": [], "error": "讀取飲食紀錄失敗"}


# ─── 週報（純統計、無 LLM） ──────────────────────────────────
# 設計重點：
# - 滾動 7 天（不是自然週）— 第 1 週 = 今天往前 6 天；第 2 週 = 7~13 天前
# - completeness 加權：早午晚各 0.30、點心 0.10（早午晚才是規律進食的核心）
# - top_foods 用簡單切詞（、,，;； 與多空白），長度 >= 2 中文字才計入
# - 純 SQL 聚合，no LLM；raw diet_records 已永久保留，不需 cache 表

MEAL_WEIGHTS = {"breakfast": 0.30, "lunch": 0.30, "dinner": 0.30, "snack": 0.10}
_FOOD_TOKEN_RE = re.compile(r"[、,，;；]|\s+")
_FOOD_STOPWORDS = {"和", "與", "或", "以及", "等", "一些", "一點", "之類"}

# 食物 → (蛋白質 g, 水分 ml, 纖維 g) 粗估表，數值對應「一份常見份量」
# 用關鍵字子字串比對，對長關鍵字優先（"糙米飯" 比 "飯" 先吃），避免重複計分
NUTRIENT_TABLE: list[tuple[list[str], float, float, float]] = [
    # 主食
    (["糙米飯", "白飯", "米飯"], 4, 80, 1),
    (["燕麥粥", "燕麥"], 5, 150, 4),
    (["全麥吐司", "吐司", "麵包", "饅頭", "包子"], 4, 30, 1.5),
    (["義大利麵", "拉麵", "麵條", "炒麵"], 8, 150, 2),
    (["米粉", "粄條", "河粉"], 4, 120, 1),
    (["地瓜", "番薯"], 2, 100, 3),
    (["馬鈴薯"], 2, 100, 2),
    (["麵"], 6, 120, 2),
    (["飯"], 4, 80, 1),
    # 蛋白質（動物）
    (["雞胸", "雞腿", "雞肉", "炸雞", "雞排"], 25, 0, 0),
    (["豬排", "排骨", "豬肉", "肉絲", "絞肉", "里肌"], 22, 0, 0),
    (["牛肉", "牛排"], 25, 0, 0),
    (["羊肉"], 23, 0, 0),
    (["鮭魚", "鯖魚", "鱈魚", "虱目魚", "蒸魚", "煎魚"], 22, 0, 0),
    (["鮪魚"], 22, 0, 0),
    (["蝦仁", "蝦"], 18, 0, 0),
    (["花枝", "魷魚", "章魚"], 16, 0, 0),
    (["蛤蜊", "蛤", "牡蠣", "蚵"], 10, 30, 0),
    (["魚"], 20, 0, 0),
    (["水煮蛋", "荷包蛋", "炒蛋", "蒸蛋", "茶葉蛋", "雞蛋", "蛋"], 6, 30, 0),
    # 蛋白質（植物）+ 乳製品
    (["無糖豆漿", "豆漿"], 7, 240, 1),
    (["豆腐", "豆乾", "豆皮", "毛豆"], 8, 50, 1),
    (["希臘優格", "優格"], 6, 100, 0),
    (["起司", "乳酪"], 6, 0, 0),
    (["鮮奶", "牛奶"], 8, 240, 0),
    (["羊奶"], 7, 240, 0),
    # 蔬菜
    (["燙青菜", "炒青菜", "青菜"], 2, 120, 3),
    (["地瓜葉", "空心菜", "高麗菜", "菠菜", "白菜", "青江菜", "A菜"], 2, 120, 3),
    (["綠花椰", "白花椰", "青花菜", "花椰菜"], 3, 100, 4),
    (["小番茄", "番茄", "蕃茄"], 1, 100, 2),
    (["胡蘿蔔", "紅蘿蔔", "蘿蔔"], 1, 80, 2),
    (["香菇", "金針菇", "鴻喜菇", "杏鮑菇", "菇"], 3, 70, 2),
    (["生菜", "沙拉"], 2, 100, 3),
    (["海帶", "紫菜", "海藻"], 2, 50, 2),
    (["筊白筍", "竹筍", "筍"], 2, 100, 3),
    (["茄子"], 1, 90, 2),
    (["蔬菜"], 2, 100, 3),
    # 水果
    (["蘋果"], 1, 150, 4),
    (["香蕉"], 1, 80, 3),
    (["橘子", "柳丁", "葡萄柚"], 1, 120, 2),
    (["芭樂", "番石榴"], 2, 130, 5),
    (["奇異果"], 1, 70, 3),
    (["木瓜"], 1, 130, 2),
    (["鳳梨"], 1, 130, 2),
    (["芒果"], 1, 150, 2),
    (["葡萄"], 1, 80, 1),
    (["草莓"], 1, 80, 2),
    (["藍莓"], 1, 70, 2),
    (["西瓜"], 1, 200, 1),
    (["水果"], 1, 120, 2),
    # 飲品
    (["白開水", "溫開水", "冷開水", "礦泉水"], 0, 250, 0),
    (["綠茶", "紅茶", "烏龍茶", "茶"], 0, 250, 0),
    (["拿鐵", "美式", "咖啡"], 1, 200, 0),
    (["排骨湯", "雞湯", "蘿蔔湯", "味噌湯", "湯"], 5, 250, 1),
    (["果汁"], 1, 200, 0),
    (["水"], 0, 250, 0),
    # 點心 / 加工
    (["餅乾"], 2, 0, 0.5),
    (["蛋糕", "甜點"], 3, 0, 0.5),
    (["巧克力"], 2, 0, 1),
    (["堅果", "杏仁", "腰果", "核桃", "花生"], 5, 0, 2),
    (["薯條"], 3, 0, 2),
    (["關東煮"], 5, 100, 1),
]

# 攤平並按關鍵字長度由長至短排序：先比對長關鍵字才不會被短關鍵字搶走
_NUTRIENT_INDEX: list[tuple[str, float, float, float]] = sorted(
    [(kw, p, w, f) for kws, p, w, f in NUTRIENT_TABLE for kw in kws],
    key=lambda x: -len(x[0]),
)


def _estimate_nutrients_keyword(foods_str: str) -> tuple[float, float, float]:
    """Keyword fallback：用子字串比對 NUTRIENT_TABLE 粗估營養素。

    每比中一次就把該段替換成同長度的 `·` 標記，避免短關鍵字重新吃到已被長關鍵字
    消耗過的字（例 "糙米飯" 不會再被 "飯" 重複計分）。
    """
    if not foods_str:
        return 0.0, 0.0, 0.0
    s = foods_str
    p_sum = 0.0
    w_sum = 0.0
    f_sum = 0.0
    for kw, p, w, f in _NUTRIENT_INDEX:
        while kw in s:
            p_sum += p
            w_sum += w
            f_sum += f
            s = s.replace(kw, "·" * len(kw), 1)
    return p_sum, w_sum, f_sum


def _estimate_nutrients(foods_str: str) -> tuple[float, float, float]:
    """從一筆 record 的食物文字估算 (蛋白質 g, 水分 ml, 纖維 g)。

    預設走 LLM 結構化分類（diet_nutrient_llm），LLM 不可用時降到 keyword 版。
    由 env DIET_NUTRIENT_LLM=0 可強制 keyword-only。
    """
    return _estimate_nutrients_llm(foods_str, _estimate_nutrients_keyword)


def _utc_iso_to_local_date(eaten_iso: str, tz_offset: int) -> Optional[date]:
    """eaten_at 是 UTC ISO；轉使用者本地日期。tz_offset 是 JS 規格（西側為正）。
    本地時間 = UTC - tz_offset。"""
    if not eaten_iso:
        return None
    try:
        # 處理 'Z' 結尾或 +00:00 結尾
        ed = datetime.fromisoformat(eaten_iso.replace("Z", "+00:00"))
        # 轉本地：utc - tz_offset → 對台灣 (-480) 等於 utc + 8h
        if ed.tzinfo is None:
            ed = ed.replace(tzinfo=None)
            local_dt = ed - timedelta(minutes=tz_offset)
        else:
            local_dt = ed.replace(tzinfo=None) - timedelta(minutes=tz_offset)
        return local_dt.date()
    except (ValueError, AttributeError):
        return None


def _summarize_week(records: list, week_start_local: date, tz_offset: int) -> dict:
    """聚合一週的 records 成可視化資料。"""
    # 7 天每日的 meal set
    day_meals = {(week_start_local + timedelta(days=i)).isoformat(): set()
                 for i in range(7)}
    # 7 天每日的營養素累加（從食物文字粗估）
    day_nutrients = {(week_start_local + timedelta(days=i)).isoformat():
                     {"protein_g": 0.0, "water_ml": 0.0, "fiber_g": 0.0}
                     for i in range(7)}
    totals = {"breakfast": 0, "lunch": 0, "dinner": 0, "snack": 0}
    food_count: dict = {}

    for r in records:
        local_d = _utc_iso_to_local_date(r.get("eaten_at") or "", tz_offset)
        if not local_d:
            continue
        d_key = local_d.isoformat()
        if d_key not in day_meals:
            continue
        mt = r.get("meal_type")
        if mt in MEAL_WEIGHTS:
            day_meals[d_key].add(mt)
            totals[mt] += 1
        # food token 詞頻 + 營養素粗估（兩者都要原始字串）
        foods = (r.get("foods") or "").strip()
        if foods:
            for tok in _FOOD_TOKEN_RE.split(foods):
                tok = tok.strip()
                if len(tok) >= 2 and tok not in _FOOD_STOPWORDS:
                    food_count[tok] = food_count.get(tok, 0) + 1
            p, w, f = _estimate_nutrients(foods)
            dn = day_nutrients[d_key]
            dn["protein_g"] += p
            dn["water_ml"] += w
            dn["fiber_g"] += f

    targets = DIET_FALLBACK["daily_targets"]
    by_day = []
    completeness_sum = 0.0
    for d_key in sorted(day_meals.keys()):
        meals = day_meals[d_key]
        completeness = sum(MEAL_WEIGHTS[m] for m in meals)
        dn = day_nutrients[d_key]
        by_day.append({
            "date": d_key,
            "breakfast": "breakfast" in meals,
            "lunch":     "lunch" in meals,
            "dinner":    "dinner" in meals,
            "snack":     "snack" in meals,
            "completeness": round(completeness, 2),
            "nutrients": {
                "protein_g": round(dn["protein_g"], 1),
                "water_ml":  round(dn["water_ml"]),
                "fiber_g":   round(dn["fiber_g"], 1),
            },
            "intake_pct": {
                "protein": round(min(1.0, dn["protein_g"] / targets["protein_g"]) if targets["protein_g"] else 0.0, 3),
                "water":   round(min(1.0, dn["water_ml"]  / targets["water_ml"])  if targets["water_ml"]  else 0.0, 3),
                "fiber":   round(min(1.0, dn["fiber_g"]   / targets["fiber_g"])   if targets["fiber_g"]   else 0.0, 3),
            },
        })
        completeness_sum += completeness

    top_foods: List[Tuple[str, int]] = sorted(
        food_count.items(), key=lambda x: (-x[1], x[0])
    )[:8]

    return {
        "week_start": week_start_local.isoformat(),
        "week_end":   (week_start_local + timedelta(days=6)).isoformat(),
        "by_day":     by_day,
        "totals":     totals,
        "top_foods":  top_foods,
        "completeness_avg": round(completeness_sum / 7, 2),
        "daily_targets": dict(targets),
    }


@router.get("/weekly/{patient_id}")
def get_diet_weekly(
    patient_id: str,
    weeks: int = Query(4, ge=1, le=12, description="近 N 週（每週滾動 7 天）"),
    tz_offset: int = Query(-480, ge=-840, le=840, description="JS Date.getTimezoneOffset()，台灣 = -480"),
):
    """近 N 週的飲食彙整（純統計，無 LLM）。

    第 i 週（i=0 是本週）：今天往前 i*7 天作為 end，再往前 6 天作為 start。
    回 weeks[] 由近到遠。
    """
    sb = get_supabase()
    today_local = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
    range_start_local = today_local - timedelta(days=weeks * 7 - 1)
    # 本地起點轉 UTC：UTC = local + tz_offset
    local_start_dt = datetime.combine(range_start_local, datetime.min.time())
    utc_start = (local_start_dt + timedelta(minutes=tz_offset)).isoformat()

    try:
        rows = (sb.table("diet_records")
                  .select("*")
                  .eq("patient_id", patient_id)
                  .gte("eaten_at", utc_start)
                  .order("eaten_at", desc=True)
                  .execute())
        all_records = rows.data or []
    except Exception as e:
        logger.error(f"讀取週報資料失敗：{e}")
        return {"weeks": [], "error": "讀取週報資料失敗"}

    weeks_data = []
    for i in range(weeks):
        week_end_local = today_local - timedelta(days=i * 7)
        week_start_local = week_end_local - timedelta(days=6)
        # 從 all_records filter 出落在這週的
        in_week = []
        for r in all_records:
            local_d = _utc_iso_to_local_date(r.get("eaten_at") or "", tz_offset)
            if local_d and week_start_local <= local_d <= week_end_local:
                in_week.append(r)
        weeks_data.append(_summarize_week(in_week, week_start_local, tz_offset))

    return {"weeks": weeks_data}

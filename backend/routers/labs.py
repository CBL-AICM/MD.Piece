from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import logging

from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 報告數值解讀
# 患者輸入任意檢驗項目（含罕見/免疫項目）+ 數值，
# LLM 回傳：參考範圍、是否異常、白話解釋、生活建議、是否需就醫。
# 不下診斷、不開藥；異常時提醒就醫。

LAB_SYSTEM_PROMPT = (
    "你是檢驗報告解讀助手，協助一般民眾看懂自己的檢驗數值。\n"
    "使用者會輸入：檢驗項目名稱、數值、單位、年齡、性別。\n\n"
    "請依以下原則回覆：\n"
    "1. 給出該項目的常見成人參考範圍（如有性別/年齡差異請說明）\n"
    "2. 判斷使用者數值屬於：偏低 / 正常 / 偏高 / 嚴重異常\n"
    "3. 用白話一兩句解釋這個指標代表什麼\n"
    "4. 給生活面建議（飲食、運動、追蹤頻率），具體可行\n"
    "5. 若數值嚴重異常或可能急症（例如鉀過高、血糖極低、肝指數爆高等），\n"
    "   `see_doctor` 設為 true 並在 advice 中強烈建議就醫\n"
    "6. 不確定的罕見項目可以說「此項目較少見，建議洽原檢驗單位確認」，\n"
    "   normal_range 給「不確定」即可，不要瞎掰數字\n"
    "7. 絕對不下診斷、不開藥、不取代醫師判斷\n\n"
    "輸出必須是純 JSON（不要 markdown code block），結構：\n"
    "{\n"
    '  "item": "項目正式名稱（含中英文）",\n'
    '  "normal_range": "參考範圍文字",\n'
    '  "status": "low | normal | high | critical | unknown",\n'
    '  "meaning": "這個指標代表什麼（白話一兩句）",\n'
    '  "advice": "生活建議與後續觀察",\n'
    '  "see_doctor": true | false,\n'
    '  "disclaimer": "本結果僅供參考，請以實際檢驗單位與醫師判讀為準"\n'
    "}\n"
    "全部使用繁體中文。"
)


class LabCheckRequest(BaseModel):
    name: str            # 檢驗項目（中文/英文/縮寫皆可，例：血紅素、Hb、ANA、IgE）
    value: str           # 數值（字串以容納範圍/陰陽性，例：12.3、>200、陽性）
    unit: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None  # male | female | other


class LabCheckResponse(BaseModel):
    item: str
    normal_range: str
    status: str
    meaning: str
    advice: str
    see_doctor: bool
    disclaimer: str


def _build_user_message(req: LabCheckRequest) -> str:
    parts = [f"檢驗項目：{req.name}", f"數值：{req.value}"]
    if req.unit:
        parts.append(f"單位：{req.unit}")
    if req.age is not None:
        parts.append(f"年齡：{req.age}")
    if req.sex:
        sex_label = {"male": "男", "female": "女"}.get(req.sex, req.sex)
        parts.append(f"性別：{sex_label}")
    return "\n".join(parts)


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


@router.post("/check", response_model=LabCheckResponse)
def check_lab_value(body: LabCheckRequest):
    """解讀單一檢驗值是否正常 + 給生活建議"""
    if not body.name.strip() or not body.value.strip():
        raise HTTPException(status_code=400, detail="請輸入檢驗項目與數值")

    user_msg = _build_user_message(body)

    try:
        raw = call_claude(LAB_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.error(f"Lab check LLM call failed: {e}")
        raise HTTPException(status_code=503, detail="解讀服務暫時無法使用，請稍後再試")

    raw = _strip_code_fence(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Lab check returned non-JSON: {raw[:200]}")
        return LabCheckResponse(
            item=body.name,
            normal_range="無法解析",
            status="unknown",
            meaning=raw[:200] if raw else "無法解讀，請稍後再試",
            advice="若有疑慮請洽醫師或原檢驗單位確認",
            see_doctor=False,
            disclaimer="本結果僅供參考，請以實際檢驗單位與醫師判讀為準",
        )

    return LabCheckResponse(
        item=data.get("item", body.name),
        normal_range=data.get("normal_range", "未知"),
        status=data.get("status", "unknown"),
        meaning=data.get("meaning", ""),
        advice=data.get("advice", ""),
        see_doctor=bool(data.get("see_doctor", False)),
        disclaimer=data.get("disclaimer", "本結果僅供參考，請以實際檢驗單位與醫師判讀為準"),
    )

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import logging

from backend.security import current_user
from backend.services.llm_service import (
    build_patient_facing_system,
    call_claude,
    recognize_lab_report,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 報告數值解讀
# 患者輸入任意檢驗項目（含罕見/免疫項目）+ 數值，
# LLM 回傳：參考範圍、是否異常、白話解釋、生活建議、是否需就醫。
# 不下診斷、不開藥；異常時提醒就醫。

_LAB_ROLE_PROMPT = (
    "【本次任務：單一檢驗值的白話解讀】\n"
    "使用者會輸入：檢驗項目名稱、數值、單位、年齡、性別。\n\n"
    "情境專屬規則：\n"
    "1. 給出該項目的常見成人參考範圍（如有性別／年齡差異請說明）\n"
    "2. 判斷使用者數值屬於：偏低 / 正常 / 偏高 / 嚴重異常\n"
    "3. `meaning` 跟 `advice` 是病人會直接看到的白話 → 嚴格遵守風格層 [A][B][C]：\n"
    "   - 不丟百分比；用分級語言（穩定 / 需注意 / 建議盡快回診 / 緊急）\n"
    "   - 不審判（不要說「您的數值不合格」「您的肝功能太差」）\n"
    "   - 不下診斷、不替醫師決定；異常時建議「請醫師看一下」\n"
    "   - 不給假保證（不要說「沒事啦放心」）\n"
    "4. `advice` 給生活面建議（飲食、運動、追蹤頻率），具體可行\n"
    "5. 數值嚴重異常或可能急症（鉀過高、血糖極低、肝指數爆高等）：\n"
    "   `see_doctor` 設為 true，並在 advice 直接、明確建議就醫\n"
    "6. 不確定的罕見項目：normal_range 給「不確定」，並在 meaning / advice 建議\n"
    "   洽原檢驗單位確認 — **不要瞎掰數字**\n\n"
    "輸出必須是**純 JSON**（不要 markdown code block、不要前後說明文字），結構：\n"
    "{\n"
    '  "item": "項目正式名稱（含中英文）",\n'
    '  "normal_range": "參考範圍文字",\n'
    '  "status": "low | normal | high | critical | unknown",\n'
    '  "meaning": "這個指標代表什麼（白話一兩句，遵守風格層）",\n'
    '  "advice": "生活建議與後續觀察（遵守風格層）",\n'
    '  "see_doctor": true | false,\n'
    '  "disclaimer": "此結果由 AI 整理，僅供參考；實際診療請依您的主治醫師為準。"\n'
    "}\n"
)


# 風格層 + role；JSON 輸出固定，include_examples=False 避免污染結構
LAB_SYSTEM_PROMPT = build_patient_facing_system(
    _LAB_ROLE_PROMPT,
    patient_context=None,
    include_examples=False,
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


def _coerce_bool(value, default: bool = False) -> bool:
    """LLM 可能回 true/false（bool）、"true"/"false"（str）、1/0（int）。
    避免 bool("false") == True 的陷阱，明確處理字串。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1", "是", "需要"):
            return True
        if v in ("false", "no", "0", "否", "不需要", ""):
            return False
    return default


@router.post("/check", response_model=LabCheckResponse)
def check_lab_value(body: LabCheckRequest, me: dict = Depends(current_user)):
    """解讀單一檢驗值是否正常 + 給生活建議"""
    if not body.name.strip() or not body.value.strip():
        raise HTTPException(status_code=400, detail="請輸入檢驗項目與數值")

    user_msg = _build_user_message(body)

    try:
        raw = call_claude(LAB_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.error(f"Lab check LLM call failed: {e}")
        raise HTTPException(status_code=503, detail=f"解讀服務暫時無法使用：{type(e).__name__}: {e}")

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
        see_doctor=_coerce_bool(data.get("see_doctor"), default=False),
        disclaimer=data.get("disclaimer", "本結果僅供參考，請以實際檢驗單位與醫師判讀為準"),
    )


# ── 從照片一次解讀整份檢驗報告 ─────────────────────────────


_VALID_STATUSES = {"low", "normal", "high", "critical", "unknown"}


class LabScanRequest(BaseModel):
    image_base64: str
    media_type: Optional[str] = "image/jpeg"


def _coerce_str(value, default: str = "") -> str:
    """LLM 回傳的欄位有時是數字、None、dict——統一轉成可 strip 的 str。"""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_scanned_item(raw: dict) -> dict:
    """把 LLM 回的單筆項目正規化成前端可直接渲染的結構。"""
    name = _coerce_str(raw.get("name")).strip() or "未命名項目"
    value = _coerce_str(raw.get("value")).strip()
    unit_s = _coerce_str(raw.get("unit")).strip()
    unit = unit_s or None
    status = _coerce_str(raw.get("status"), "unknown").strip().lower()
    if status not in _VALID_STATUSES:
        status = "unknown"
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "normal_range": _coerce_str(raw.get("normal_range")).strip() or "未知",
        "status": status,
        "meaning": _coerce_str(raw.get("meaning")).strip(),
        "advice": _coerce_str(raw.get("advice")).strip(),
        "see_doctor": _coerce_bool(raw.get("see_doctor"), default=False),
    }


def _summarize_status(items: list[dict]) -> dict:
    summary = {s: 0 for s in _VALID_STATUSES}
    for it in items:
        summary[it.get("status", "unknown")] += 1
    abnormal = summary["low"] + summary["high"] + summary["critical"]
    return {
        "total": len(items),
        "abnormal": abnormal,
        "by_status": summary,
        "needs_doctor": any(it.get("see_doctor") for it in items),
    }


@router.post("/scan")
def scan_lab_report(body: LabScanRequest, me: dict = Depends(current_user)):
    """拍/上傳檢驗報告，一次抽出所有項目並判讀正常/異常。

    回傳:
    {
      "items": [{"name", "value", "unit", "normal_range",
                 "status", "meaning", "advice", "see_doctor"}],
      "summary": {"total", "abnormal", "by_status", "needs_doctor"},
      "raw_text": "OCR / vision 原始輸出，便於 debug",
      "provider": "google_vision | anthropic | groq | None",
      "errors":   [{"provider", "error"}, ...],
      "disclaimer": "..."
    }
    """
    if not body.image_base64:
        raise HTTPException(status_code=400, detail="缺少 image_base64")

    try:
        result = recognize_lab_report(body.image_base64, body.media_type or "image/jpeg")
    except Exception:
        # 把詳細錯誤留在 server log，不要回給使用者（避免洩漏內部資訊）
        logger.exception("recognize_lab_report failed")
        raise HTTPException(status_code=503, detail="報告辨識服務暫時無法使用，請稍後再試")

    raw_items = result.get("items") or []
    items = [_normalize_scanned_item(it) for it in raw_items if isinstance(it, dict)]

    return {
        "items": items,
        "summary": _summarize_status(items),
        "raw_text": result.get("raw_text", ""),
        "provider": result.get("provider"),
        "errors": result.get("errors", []),
        "disclaimer": "本判讀僅供參考，請以實際檢驗單位與醫師判讀為準",
    }

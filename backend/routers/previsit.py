from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import logging

from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 診前報告
# 患者按下按鈕 → 前端打包近期紀錄（症狀/用藥/memo）→ 後端 LLM 整理成
# 給醫師看的摘要：主訴、用藥、想討論的事、AI 重點提示。
# 後端 stateless，不寫入 DB；資料只在這次 request 裡走過 LLM。

PREVISIT_SYSTEM_PROMPT = (
    "你是患者就醫前的助理，把使用者最近的症狀紀錄、用藥情況、想跟醫師說的事，"
    "整理成一張簡短、結構化、醫師三十秒能看完的「診前摘要」。\n\n"
    "原則：\n"
    "1. 用條列式，每點一行不超過 30 字\n"
    "2. 找出真正需要醫師注意的重點（症狀加重、漏服藥、生理變化）\n"
    "3. AI 提示段落只給線索，不下診斷、不開藥\n"
    "4. 沒有資料的區塊就標「無紀錄」，不要編造\n"
    "5. 全部使用繁體中文\n\n"
    "輸出必須是純 JSON（不要 markdown code block），結構：\n"
    "{\n"
    '  "chief_complaints": ["主訴1", "主訴2", ...],\n'
    '  "medication_status": ["用藥條目1", ...],\n'
    '  "questions_for_doctor": ["想問醫師的事1", ...],\n'
    '  "ai_highlights": ["AI 觀察的重點1", ...],\n'
    '  "summary": "整段 30 字內的一句話總結"\n'
    "}\n"
)


class SymptomRecord(BaseModel):
    name: Optional[str] = None
    severity: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None


class MedicationRecord(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    note: Optional[str] = None


class MemoEntry(BaseModel):
    text: Optional[str] = None
    forDoctor: Optional[bool] = None
    createdAt: Optional[str] = None


class PrevisitRequest(BaseModel):
    days: int = 30
    symptoms: List[SymptomRecord] = []
    medications: List[MedicationRecord] = []
    memos: List[MemoEntry] = []


class PrevisitResponse(BaseModel):
    chief_complaints: List[str]
    medication_status: List[str]
    questions_for_doctor: List[str]
    ai_highlights: List[str]
    summary: str
    disclaimer: str


def _build_user_message(req: PrevisitRequest) -> str:
    parts = [f"時間範圍：最近 {req.days} 天\n"]

    if req.symptoms:
        parts.append("【症狀紀錄】")
        for s in req.symptoms[:30]:
            line = f"- {s.created_at or '?'} {s.name or '未命名'}"
            if s.severity:
                line += f"（嚴重度 {s.severity}）"
            if s.note:
                line += f"：{s.note}"
            parts.append(line)
    else:
        parts.append("【症狀紀錄】無紀錄")
    parts.append("")

    if req.medications:
        parts.append("【用藥】")
        for m in req.medications[:30]:
            line = f"- {m.name or '未知藥'}"
            if m.dosage:
                line += f" {m.dosage}"
            if m.frequency:
                line += f" / {m.frequency}"
            if m.note:
                line += f"（{m.note}）"
            parts.append(line)
    else:
        parts.append("【用藥】無紀錄")
    parts.append("")

    doctor_memos = [m for m in req.memos if m.forDoctor and m.text]
    if doctor_memos:
        parts.append("【想跟醫師說的事】")
        for m in doctor_memos[:20]:
            parts.append(f"- {m.text}")
    else:
        parts.append("【想跟醫師說的事】無紀錄")

    return "\n".join(parts)


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


@router.post("/generate", response_model=PrevisitResponse)
def generate_previsit(body: PrevisitRequest):
    """整理近期紀錄成診前摘要"""
    if not (body.symptoms or body.medications or body.memos):
        raise HTTPException(status_code=400, detail="近期沒有任何紀錄可以整理；先記錄一些症狀或用藥再試試。")

    user_msg = _build_user_message(body)

    try:
        raw = call_claude(PREVISIT_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.error(f"Previsit generation failed: {e}")
        raise HTTPException(status_code=503, detail=f"報告生成暫時無法使用：{type(e).__name__}: {e}")

    raw = _strip_code_fence(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Previsit returned non-JSON: {raw[:200]}")
        return PrevisitResponse(
            chief_complaints=[],
            medication_status=[],
            questions_for_doctor=[],
            ai_highlights=[raw[:200]] if raw else [],
            summary="無法生成結構化摘要，請稍後再試",
            disclaimer="本摘要僅供參考，請以醫師判讀為準",
        )

    def _list(key):
        v = data.get(key, [])
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v if x]

    return PrevisitResponse(
        chief_complaints=_list("chief_complaints"),
        medication_status=_list("medication_status"),
        questions_for_doctor=_list("questions_for_doctor"),
        ai_highlights=_list("ai_highlights"),
        summary=str(data.get("summary", "")),
        disclaimer="本摘要僅供參考，請以醫師判讀為準",
    )

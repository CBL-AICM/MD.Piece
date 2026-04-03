from fastapi import APIRouter

from backend.models import TriageRequest

router = APIRouter()

# 雙層 AI 分流 - 規則引擎 + Claude API（Haiku）個人化基準線判斷


@router.post("/evaluate")
def evaluate_triage(body: TriageRequest):
    # 第一層：規則引擎（急診清單觸發 → 直接 Emergency）
    # 第二層：LLM 依個人基準線判斷 Stable / Follow-up / Emergency
    return {
        "result": "stable",
        "message": "今天狀況穩定，繼續按時服藥",
        "patient_id": body.patient_id,
    }


@router.get("/baseline/{patient_id}")
def get_baseline(patient_id: str):
    # 個人化基準線：前兩週症狀/服藥/情緒平均值
    return {"baseline": {}, "patient_id": patient_id}

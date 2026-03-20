from fastapi import APIRouter

router = APIRouter()

# 三十天整合報告 - LLM 生成臨床摘要、供醫師回診前使用

@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str):
    # 觸發 Claude Haiku 生成 30 天整合文字摘要
    return {"report": None, "generated_at": None}

@router.get("/{patient_id}/checklist")
def get_consultation_checklist(patient_id: str):
    # 建議問診清單：這次最需要確認的三件事
    return {"checklist": []}

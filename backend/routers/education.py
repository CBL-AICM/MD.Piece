from fastapi import APIRouter

router = APIRouter()

# 慢性病衛教 - 靜態卡片文章、ICD-10 個人化衛教

@router.get("/articles")
def get_articles(icd10_code: str = ""):
    # 回傳靜態衛教文章（不使用 LLM，確保內容品質可控）
    return {"articles": []}

@router.get("/idle-hints")
def get_idle_hints():
    # 小禾閒置暗示句子池（20-30 句）
    return {"hints": []}

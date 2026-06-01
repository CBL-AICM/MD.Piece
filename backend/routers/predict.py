"""復發風險預測 API — 對應 docs CLAUDE_predict_ui_ux.md 的 §10 元件資料需求。

  - POST /predict/{patient_id}          → RiskCard / ConfidenceMeter / ColdStartCard
  - GET  /predict/{patient_id}/trend    → RiskTrendChart（時間序列 + 信心帶 + flare）
  - GET  /explain/{prediction_id}       → ShapBarList（因子瀑布條 + 人話 + 可調節）

風險計算為決定性啟發式（規則 5），實作於 backend/utils/recurrence.py。
DB 離線 / 缺表時沉著回 503 或冷啟動狀態，不捏造數字（規則 12）。
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_supabase
from backend.utils import recurrence

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_prediction_id(prediction_id: str):
    """prediction_id 形如 '<patient_id>:<YYYY-MM-DD>'；回傳 (patient_id, as_of)。

    因為風險為決定性，給定病患與日期即可重現當時推估（無需另存快照）。
    """
    if ":" not in prediction_id:
        # 容錯：純 patient_id → 用今天
        return prediction_id, datetime.utcnow()
    pid, _, day = prediction_id.rpartition(":")
    try:
        as_of = datetime.strptime(day, "%Y-%m-%d")
        # 用當天 23:59 讓整天的紀錄都納入
        as_of = as_of.replace(hour=23, minute=59, second=59)
    except ValueError:
        return prediction_id, datetime.utcnow()
    return pid, as_of


@router.post("/predict/{patient_id}")
def post_predict(
    patient_id: str,
    disease: str | None = Query(None, description="前端本地檔案的主要疾病（讓未同步 profile 者也能對準疾病）"),
):
    """產生病患「未來 14 天復發風險」推估（band 為主、百分比次要）。"""
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"predict: DB offline: {e}")
        raise HTTPException(status_code=503, detail="資料庫尚未連線，無法產生預測。")
    return recurrence.predict(sb, patient_id, disease_hint=disease)


@router.post("/predict/{patient_id}/disease-knowledge")
def post_disease_knowledge(
    patient_id: str,
    disease: str | None = Query(None, description="主要疾病；未提供則由 server 端 profile / 就診紀錄解析"),
):
    """整理 / 暖快取病患疾病的「文獻復發知識」（給前端收集流程明確觸發）。

    這是會打 LLM 的慢路徑，刻意與 predict 熱路徑分離，避免重蹈 #487 逾時。
    """
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"disease-knowledge: DB offline: {e}")
        raise HTTPException(status_code=503, detail="資料庫尚未連線。")
    return recurrence.warm_disease_knowledge(sb, patient_id, disease_hint=disease)


@router.get("/predict/{patient_id}/trend")
def get_trend(
    patient_id: str,
    window: int = Query(90, ge=7, le=180, description="時間窗天數：14 / 30 / 90 / 180"),
    disease: str | None = Query(None, description="主要疾病（讓趨勢基線與卡片一致）"),
):
    """風險趨勢時間序列（畫面 B）。"""
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"predict trend: DB offline: {e}")
        raise HTTPException(status_code=503, detail="資料庫尚未連線，無法產生趨勢。")
    return recurrence.trend_series(sb, patient_id, window, disease_hint=disease)


@router.get("/explain/{prediction_id}")
def get_explain(
    prediction_id: str,
    disease: str | None = Query(None, description="主要疾病（讓因子解釋與卡片一致）"),
):
    """因子解釋（畫面 C）— SHAP-like，紅推升/藍降低 + 人話 + 可調節標籤。"""
    patient_id, as_of = _parse_prediction_id(prediction_id)
    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning(f"explain: DB offline: {e}")
        raise HTTPException(status_code=503, detail="資料庫尚未連線，無法產生解釋。")
    return recurrence.explain(sb, patient_id, as_of, disease_hint=disease)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

# 記憶體儲存（無 GPU 環境，結果由 Colab 回傳）
_experiments: list[dict] = []


class ExperimentSubmit(BaseModel):
    """從 Colab 回傳的實驗結果"""
    name: str
    model_config_summary: Optional[str] = None
    val_bpb: Optional[float] = None
    train_loss: Optional[float] = None
    steps: Optional[int] = None
    duration_seconds: Optional[float] = None
    notes: Optional[str] = None
    colab_url: Optional[str] = None


@router.get("/")
def list_experiments():
    """列出所有 autoresearch 實驗結果"""
    return {"experiments": _experiments, "count": len(_experiments)}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    """取得單一實驗結果"""
    for exp in _experiments:
        if exp["id"] == experiment_id:
            return exp
    raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/")
def submit_experiment(data: ExperimentSubmit):
    """接收 Colab 回傳的實驗結果"""
    exp = {
        "id": f"exp-{len(_experiments) + 1:04d}",
        "name": data.name,
        "model_config_summary": data.model_config_summary,
        "val_bpb": data.val_bpb,
        "train_loss": data.train_loss,
        "steps": data.steps,
        "duration_seconds": data.duration_seconds,
        "notes": data.notes,
        "colab_url": data.colab_url,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    _experiments.append(exp)
    return {"message": "Experiment submitted", "experiment": exp}


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: str):
    """刪除實驗結果"""
    for i, exp in enumerate(_experiments):
        if exp["id"] == experiment_id:
            _experiments.pop(i)
            return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Experiment not found")


@router.get("/status/gpu")
def gpu_status():
    """回傳此環境的 GPU 狀態"""
    return {
        "has_gpu": False,
        "message": "此環境無 GPU，請使用 Google Colab 執行 autoresearch 訓練，結果會自動回傳至此 API。",
        "colab_notebook": "autoresearch_colab.ipynb",
    }

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import csv
import io

from backend.services.supabase_service import supabase

router = APIRouter()


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
    kept: Optional[bool] = None


def _fetch_experiments():
    """從 Supabase 取得所有實驗（按時間倒序）"""
    res = supabase.table("experiments").select("*").order("submitted_at", desc=True).execute()
    return res.data or []


@router.get("/")
def list_experiments():
    """列出所有 autoresearch 實驗結果"""
    experiments = _fetch_experiments()
    return {"experiments": experiments, "count": len(experiments)}


@router.get("/stats")
def experiment_stats():
    """取得實驗統計：最佳 val_bpb、趨勢資料"""
    experiments = _fetch_experiments()
    sorted_exps = sorted(experiments, key=lambda e: e.get("submitted_at", ""))
    chart_data = []
    best_bpb = None
    best_name = None
    for e in sorted_exps:
        if e.get("val_bpb") is not None:
            chart_data.append({
                "name": e["name"],
                "val_bpb": e["val_bpb"],
                "train_loss": e.get("train_loss"),
                "submitted_at": e.get("submitted_at"),
                "kept": e.get("kept"),
            })
            if best_bpb is None or e["val_bpb"] < best_bpb:
                best_bpb = e["val_bpb"]
                best_name = e["name"]
    return {
        "total": len(experiments),
        "with_bpb": len(chart_data),
        "best_bpb": best_bpb,
        "best_experiment": best_name,
        "chart_data": chart_data,
    }


@router.get("/status/gpu")
def gpu_status():
    """回傳此環境的 GPU 狀態"""
    return {
        "has_gpu": False,
        "message": "此環境無 GPU，請使用 Google Colab 執行 autoresearch 訓練，結果會自動回傳至此 API。",
        "colab_notebook": "autoresearch_colab.ipynb",
    }


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    """取得單一實驗結果"""
    res = supabase.table("experiments").select("*").eq("id", experiment_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return res.data[0]


@router.post("/")
def submit_experiment(data: ExperimentSubmit):
    """接收 Colab 回傳的實驗結果"""
    row = {
        "name": data.name,
        "model_config_summary": data.model_config_summary,
        "val_bpb": data.val_bpb,
        "train_loss": data.train_loss,
        "steps": data.steps,
        "duration_seconds": data.duration_seconds,
        "notes": data.notes,
        "colab_url": data.colab_url,
        "kept": data.kept,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    res = supabase.table("experiments").insert(row).execute()
    return {"message": "Experiment submitted", "experiment": res.data[0] if res.data else row}


@router.post("/batch")
async def batch_import_tsv(file: UploadFile = File(...)):
    """批次匯入 results.tsv（autoresearch 格式）"""
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")

    imported = 0
    for row in reader:
        exp = {
            "name": row.get("name", row.get("tag", f"import-{imported + 1}")),
            "val_bpb": _safe_float(row.get("val_bpb")),
            "train_loss": _safe_float(row.get("train_loss")),
            "steps": _safe_int(row.get("steps")),
            "duration_seconds": _safe_float(row.get("duration")),
            "notes": row.get("description", row.get("notes", "")),
            "kept": row.get("kept", "").lower() in ("true", "yes", "1", "kept"),
            "submitted_at": row.get("timestamp", datetime.utcnow().isoformat()),
        }
        supabase.table("experiments").insert(exp).execute()
        imported += 1

    return {"message": f"Imported {imported} experiments", "count": imported}


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: str):
    """刪除實驗結果"""
    res = supabase.table("experiments").delete().eq("id", experiment_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"message": "Deleted"}


def _safe_float(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None

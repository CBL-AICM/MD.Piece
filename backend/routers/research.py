from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import csv
import io
import logging
import os
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()

# Supabase or in-memory fallback
_use_memory = False
_memory_store: list = []  # in-memory fallback for experiments
_memory_counter = 0

try:
    from backend.services.supabase_service import supabase as _sb_client
    # Test if Supabase is actually configured
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        raise RuntimeError("No credentials")
    supabase = _sb_client
except Exception:
    supabase = None
    _use_memory = True
    logger.warning("Supabase unavailable — research router using in-memory storage")


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
    """從 Supabase 或記憶體取得所有實驗（按時間倒序）"""
    if _use_memory:
        return sorted(_memory_store, key=lambda experiment_entry: experiment_entry.get("submitted_at", ""), reverse=True)
    try:
        db_result = supabase.table("experiments").select("*").order("submitted_at", desc=True).execute()
        return db_result.data or []
    except Exception as fetch_error:
        logger.error(f"Failed to fetch experiments: {fetch_error}")
        return []


def _insert_experiment(row: dict):
    """插入實驗到 Supabase 或記憶體"""
    if _use_memory:
        row["id"] = str(uuid.uuid4())
        _memory_store.append(row)
        return row
    db_result = supabase.table("experiments").insert(row).execute()
    return db_result.data[0] if db_result.data else row


def _delete_experiment_by_id(exp_id: str):
    """刪除實驗"""
    if _use_memory:
        for index, experiment_entry in enumerate(_memory_store):
            if experiment_entry.get("id") == exp_id:
                return _memory_store.pop(index)
        return None
    db_result = supabase.table("experiments").delete().eq("id", exp_id).execute()
    return db_result.data[0] if db_result.data else None


def _get_experiment_by_id(exp_id: str):
    """取得單一實驗"""
    if _use_memory:
        for experiment_entry in _memory_store:
            if experiment_entry.get("id") == exp_id:
                return experiment_entry
        return None
    db_result = supabase.table("experiments").select("*").eq("id", exp_id).execute()
    return db_result.data[0] if db_result.data else None


@router.get("/")
def list_experiments(
    kept: Optional[bool] = Query(None, description="篩選 kept/reverted"),
    search: Optional[str] = Query(None, description="搜尋實驗名稱或備註"),
    sort_by: Optional[str] = Query("submitted_at", description="排序欄位: submitted_at, val_bpb, train_loss, duration_seconds"),
    limit: Optional[int] = Query(None, description="回傳筆數上限"),
):
    """列出所有 autoresearch 實驗結果，支援篩選、搜尋、排序"""
    experiments = _fetch_experiments()

    if kept is not None:
        experiments = [experiment_entry for experiment_entry in experiments if experiment_entry.get("kept") == kept]

    if search:
        search_query = search.lower()
        experiments = [experiment_entry for experiment_entry in experiments if
                       search_query in (experiment_entry.get("name") or "").lower() or
                       search_query in (experiment_entry.get("notes") or "").lower()]

    if sort_by and sort_by != "submitted_at":
        reverse = sort_by != "val_bpb"  # val_bpb lower is better
        experiments.sort(key=lambda experiment_entry: experiment_entry.get(sort_by) or float("inf"), reverse=reverse)

    if limit and limit > 0:
        experiments = experiments[:limit]

    return {"experiments": experiments, "count": len(experiments)}


@router.get("/stats")
def experiment_stats():
    """取得實驗統計：最佳 val_bpb、趨勢資料、改善率"""
    experiments = _fetch_experiments()
    sorted_exps = sorted(experiments, key=lambda experiment_entry: experiment_entry.get("submitted_at", ""))
    chart_data = []
    best_bpb = None
    best_name = None
    kept_count = 0
    reverted_count = 0
    total_duration = 0.0

    for experiment_entry in sorted_exps:
        if experiment_entry.get("kept") is True:
            kept_count += 1
        elif experiment_entry.get("kept") is False:
            reverted_count += 1
        if experiment_entry.get("duration_seconds"):
            total_duration += experiment_entry["duration_seconds"]
        if experiment_entry.get("val_bpb") is not None:
            chart_data.append({
                "name": experiment_entry["name"],
                "val_bpb": experiment_entry["val_bpb"],
                "train_loss": experiment_entry.get("train_loss"),
                "submitted_at": experiment_entry.get("submitted_at"),
                "kept": experiment_entry.get("kept"),
                "steps": experiment_entry.get("steps"),
                "duration_seconds": experiment_entry.get("duration_seconds"),
            })
            if best_bpb is None or experiment_entry["val_bpb"] < best_bpb:
                best_bpb = experiment_entry["val_bpb"]
                best_name = experiment_entry["name"]

    # 計算改善率（kept / total with decisions）
    decided = kept_count + reverted_count
    improvement_rate = round(kept_count / decided * 100, 1) if decided > 0 else None

    return {
        "total": len(experiments),
        "with_bpb": len(chart_data),
        "best_bpb": best_bpb,
        "best_experiment": best_name,
        "kept_count": kept_count,
        "reverted_count": reverted_count,
        "improvement_rate": improvement_rate,
        "total_duration_hours": round(total_duration / 3600, 2) if total_duration else 0,
        "chart_data": chart_data,
    }


@router.get("/leaderboard")
def leaderboard(top_n: int = Query(10, description="排行榜顯示前 N 名")):
    """val_bpb 排行榜（越低越好）"""
    experiments = _fetch_experiments()
    with_bpb = [experiment_entry for experiment_entry in experiments if experiment_entry.get("val_bpb") is not None]
    with_bpb.sort(key=lambda experiment_entry: experiment_entry["val_bpb"])
    ranking = []
    for rank_index, experiment_entry in enumerate(with_bpb[:top_n]):
        ranking.append({
            "rank": rank_index + 1,
            "name": experiment_entry["name"],
            "val_bpb": experiment_entry["val_bpb"],
            "train_loss": experiment_entry.get("train_loss"),
            "steps": experiment_entry.get("steps"),
            "duration_seconds": experiment_entry.get("duration_seconds"),
            "kept": experiment_entry.get("kept"),
            "submitted_at": experiment_entry.get("submitted_at"),
        })
    return {"leaderboard": ranking, "total_experiments": len(experiments)}


@router.get("/compare")
def compare_experiments(
    ids: str = Query(..., description="要比較的實驗 ID，逗號分隔"),
):
    """比較多個實驗結果"""
    id_list = [id_str.strip() for id_str in ids.split(",") if id_str.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 個實驗 ID")

    results = []
    for exp_id in id_list:
        try:
            exp = _get_experiment_by_id(exp_id)
            if exp:
                results.append(exp)
        except Exception as fetch_error:
            logger.error(f"Failed to fetch experiment {exp_id}: {fetch_error}")

    if len(results) < 2:
        raise HTTPException(status_code=404, detail="找不到足夠的實驗來比較")

    # 找出最佳
    bpb_values = [experiment_entry["val_bpb"] for experiment_entry in results if experiment_entry.get("val_bpb") is not None]
    best_bpb = min(bpb_values) if bpb_values else None

    return {
        "experiments": results,
        "best_bpb": best_bpb,
        "best_experiment": next((experiment_entry["name"] for experiment_entry in results if experiment_entry.get("val_bpb") == best_bpb), None),
    }


@router.get("/export")
def export_tsv():
    """匯出所有實驗為 TSV 格式"""
    experiments = _fetch_experiments()
    output = io.StringIO()
    fieldnames = ["name", "val_bpb", "train_loss", "steps", "duration_seconds", "kept", "notes", "submitted_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    for experiment_entry in experiments:
        writer.writerow(experiment_entry)
    return {"tsv": output.getvalue(), "count": len(experiments)}


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
    try:
        exp = _get_experiment_by_id(experiment_id)
    except Exception as fetch_error:
        logger.error(f"Failed to fetch experiment {experiment_id}: {fetch_error}")
        raise HTTPException(status_code=500, detail="Database error")
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


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
    try:
        saved = _insert_experiment(row)
    except Exception as insert_error:
        logger.error(f"Failed to insert experiment: {insert_error}")
        raise HTTPException(status_code=500, detail="Failed to save experiment")
    return {"message": "Experiment submitted", "experiment": saved}


@router.post("/batch")
async def batch_import_tsv(file: UploadFile = File(...)):
    """批次匯入 results.tsv（autoresearch 格式）"""
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")

    imported = 0
    errors = 0
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
        try:
            _insert_experiment(exp)
            imported += 1
        except Exception as import_error:
            logger.error(f"Failed to import row: {import_error}")
            errors += 1

    return {"message": f"Imported {imported} experiments", "count": imported, "errors": errors}


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: str):
    """刪除實驗結果"""
    try:
        deleted = _delete_experiment_by_id(experiment_id)
    except Exception as delete_error:
        logger.error(f"Failed to delete experiment {experiment_id}: {delete_error}")
        raise HTTPException(status_code=500, detail="Database error")
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"message": "Deleted"}


def _safe_float(raw_value):
    try:
        return float(raw_value) if raw_value else None
    except (ValueError, TypeError):
        return None


def _safe_int(raw_value):
    try:
        return int(raw_value) if raw_value else None
    except (ValueError, TypeError):
        return None

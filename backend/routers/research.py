from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import csv
import io
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

from backend.db import get_supabase


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
    """從資料庫取得所有實驗（按時間倒序）"""
    try:
        sb = get_supabase()
        res = sb.table("experiments").select("*").order("submitted_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Failed to fetch experiments: {e}")
        return []


def _insert_experiment(row: dict):
    """插入實驗到資料庫"""
    sb = get_supabase()
    res = sb.table("experiments").insert(row).execute()
    return res.data[0] if res.data else row


def _delete_experiment_by_id(exp_id: str):
    """刪除實驗"""
    sb = get_supabase()
    res = sb.table("experiments").delete().eq("id", exp_id).execute()
    return res.data[0] if res.data else None


def _get_experiment_by_id(exp_id: str):
    """取得單一實驗"""
    sb = get_supabase()
    res = sb.table("experiments").select("*").eq("id", exp_id).execute()
    return res.data[0] if res.data else None


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
        experiments = [e for e in experiments if e.get("kept") == kept]

    if search:
        q = search.lower()
        experiments = [e for e in experiments if
                       q in (e.get("name") or "").lower() or
                       q in (e.get("notes") or "").lower()]

    if sort_by and sort_by != "submitted_at":
        reverse = sort_by != "val_bpb"  # val_bpb lower is better
        experiments.sort(key=lambda e: e.get(sort_by) or float("inf"), reverse=reverse)

    if limit and limit > 0:
        experiments = experiments[:limit]

    return {"experiments": experiments, "count": len(experiments)}


@router.get("/stats")
def experiment_stats():
    """取得實驗統計：最佳 val_bpb、趨勢資料、改善率"""
    experiments = _fetch_experiments()
    sorted_exps = sorted(experiments, key=lambda e: e.get("submitted_at", ""))
    chart_data = []
    best_bpb = None
    best_name = None
    kept_count = 0
    reverted_count = 0
    total_duration = 0.0

    for e in sorted_exps:
        if e.get("kept") is True:
            kept_count += 1
        elif e.get("kept") is False:
            reverted_count += 1
        if e.get("duration_seconds"):
            total_duration += e["duration_seconds"]
        if e.get("val_bpb") is not None:
            chart_data.append({
                "name": e["name"],
                "val_bpb": e["val_bpb"],
                "train_loss": e.get("train_loss"),
                "submitted_at": e.get("submitted_at"),
                "kept": e.get("kept"),
                "steps": e.get("steps"),
                "duration_seconds": e.get("duration_seconds"),
            })
            if best_bpb is None or e["val_bpb"] < best_bpb:
                best_bpb = e["val_bpb"]
                best_name = e["name"]

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
    with_bpb = [e for e in experiments if e.get("val_bpb") is not None]
    with_bpb.sort(key=lambda e: e["val_bpb"])
    ranking = []
    for i, e in enumerate(with_bpb[:top_n]):
        ranking.append({
            "rank": i + 1,
            "name": e["name"],
            "val_bpb": e["val_bpb"],
            "train_loss": e.get("train_loss"),
            "steps": e.get("steps"),
            "duration_seconds": e.get("duration_seconds"),
            "kept": e.get("kept"),
            "submitted_at": e.get("submitted_at"),
        })
    return {"leaderboard": ranking, "total_experiments": len(experiments)}


@router.get("/compare")
def compare_experiments(
    ids: str = Query(..., description="要比較的實驗 ID，逗號分隔"),
):
    """比較多個實驗結果"""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 個實驗 ID")

    results = []
    for exp_id in id_list:
        try:
            exp = _get_experiment_by_id(exp_id)
            if exp:
                results.append(exp)
        except Exception as e:
            logger.error(f"Failed to fetch experiment {exp_id}: {e}")

    if len(results) < 2:
        raise HTTPException(status_code=404, detail="找不到足夠的實驗來比較")

    # 找出最佳
    bpb_values = [e["val_bpb"] for e in results if e.get("val_bpb") is not None]
    best_bpb = min(bpb_values) if bpb_values else None

    return {
        "experiments": results,
        "best_bpb": best_bpb,
        "best_experiment": next((e["name"] for e in results if e.get("val_bpb") == best_bpb), None),
    }


@router.get("/export")
def export_tsv():
    """匯出所有實驗為 TSV 格式"""
    experiments = _fetch_experiments()
    output = io.StringIO()
    fieldnames = ["name", "val_bpb", "train_loss", "steps", "duration_seconds", "kept", "notes", "submitted_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    for e in experiments:
        writer.writerow(e)
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
    except Exception as e:
        logger.error(f"Failed to fetch experiment {experiment_id}: {e}")
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
    except Exception as e:
        logger.error(f"Failed to insert experiment: {e}")
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
        except Exception as e:
            logger.error(f"Failed to import row: {e}")
            errors += 1

    return {"message": f"Imported {imported} experiments", "count": imported, "errors": errors}


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: str):
    """刪除實驗結果"""
    try:
        deleted = _delete_experiment_by_id(experiment_id)
    except Exception as e:
        logger.error(f"Failed to delete experiment {experiment_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    if not deleted:
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

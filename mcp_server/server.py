import sys
import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# 設定 logging 寫到 stderr（STDIO 模式下不能寫 stdout）
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("md-piece-mcp")

# 初始化 MCP server
mcp = FastMCP("md-piece")

# MD.Piece FastAPI backend URL
API_BASE = "http://localhost:8000"


async def api_get(path: str) -> dict[str, Any] | list | None:
    """發送 GET 請求到 MD.Piece API。"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}{path}", timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GET {path} 失敗: {e}")
            return None


async def api_post(path: str, body: dict) -> dict[str, Any] | None:
    """發送 POST 請求到 MD.Piece API（JSON body）。"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_BASE}{path}", json=body, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"POST {path} 失敗: {e}")
            return None


async def api_delete(path: str) -> dict[str, Any] | None:
    """發送 DELETE 請求到 MD.Piece API。"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(f"{API_BASE}{path}", timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"DELETE {path} 失敗: {e}")
            return None


# ─── 病患工具 ──────────────────────────────────────────────

@mcp.tool()
async def get_patients() -> str:
    """取得所有病患清單。"""
    data = await api_get("/patients/")
    if data is None:
        return "無法取得病患資料，請確認 MD.Piece backend 是否已啟動。"
    patients = data.get("patients", [])
    if not patients:
        return "目前沒有任何病患記錄。"
    lines = []
    for p in patients:
        info = f"- {p['name']}（{p['age']}歲）ID: {p['id']}"
        if p.get("gender"):
            info += f" | 性別: {p['gender']}"
        lines.append(info)
    return "\n".join(lines)


@mcp.tool()
async def create_patient(name: str, age: int, gender: str = "", phone: str = "") -> str:
    """建立新病患。

    Args:
        name: 病患姓名
        age: 病患年齡
        gender: 性別（選填：male 或 female）
        phone: 電話（選填）
    """
    body = {"name": name, "age": age}
    if gender:
        body["gender"] = gender
    if phone:
        body["phone"] = phone
    data = await api_post("/patients/", body)
    if data is None:
        return "建立病患失敗，請確認 MD.Piece backend 是否已啟動。"
    return f"病患已建立：{data.get('name')}，年齡 {data.get('age')}，ID: {data.get('id')}"


@mcp.tool()
async def delete_patient(patient_id: str) -> str:
    """刪除病患。

    Args:
        patient_id: 病患 UUID
    """
    data = await api_delete(f"/patients/{patient_id}")
    if data is None:
        return "刪除失敗。"
    return data.get("message", "病患已刪除")


# ─── 醫師工具 ──────────────────────────────────────────────

@mcp.tool()
async def get_doctors() -> str:
    """取得所有醫師清單。"""
    data = await api_get("/doctors/")
    if data is None:
        return "無法取得醫師資料，請確認 MD.Piece backend 是否已啟動。"
    doctors = data.get("doctors", [])
    if not doctors:
        return "目前沒有任何醫師記錄。"
    lines = []
    for d in doctors:
        lines.append(f"- {d['name']}（{d['specialty']}）ID: {d['id']}")
    return "\n".join(lines)


@mcp.tool()
async def create_doctor(name: str, specialty: str, phone: str = "") -> str:
    """建立新醫師。

    Args:
        name: 醫師姓名
        specialty: 專科（例如：內科、外科、兒科）
        phone: 電話（選填）
    """
    body = {"name": name, "specialty": specialty}
    if phone:
        body["phone"] = phone
    data = await api_post("/doctors/", body)
    if data is None:
        return "建立醫師失敗，請確認 MD.Piece backend 是否已啟動。"
    return f"醫師已建立：{data.get('name')}，專科：{data.get('specialty')}，ID: {data.get('id')}"


# ─── 病歷工具 ──────────────────────────────────────────────

@mcp.tool()
async def create_medical_record(
    patient_id: str,
    symptoms: str,
    diagnosis: str = "",
    prescription: str = "",
    doctor_id: str = "",
    notes: str = "",
) -> str:
    """建立病歷記錄。

    Args:
        patient_id: 病患 UUID
        symptoms: 症狀（逗號分隔，例如：fever, headache）
        diagnosis: 診斷（選填）
        prescription: 處方（選填）
        doctor_id: 醫師 UUID（選填）
        notes: 備註（選填）
    """
    symptom_list = [s.strip() for s in symptoms.split(",") if s.strip()]
    body: dict[str, Any] = {"patient_id": patient_id, "symptoms": symptom_list}
    if diagnosis:
        body["diagnosis"] = diagnosis
    if prescription:
        body["prescription"] = prescription
    if doctor_id:
        body["doctor_id"] = doctor_id
    if notes:
        body["notes"] = notes

    data = await api_post("/records/", body)
    if data is None:
        return "建立病歷失敗。"
    return f"病歷已建立，ID: {data.get('id')}"


@mcp.tool()
async def get_medical_records(patient_id: str = "", doctor_id: str = "") -> str:
    """查詢病歷記錄。

    Args:
        patient_id: 按病患篩選（選填）
        doctor_id: 按醫師篩選（選填）
    """
    params = []
    if patient_id:
        params.append(f"patient_id={patient_id}")
    if doctor_id:
        params.append(f"doctor_id={doctor_id}")
    qs = "&".join(params)
    url = f"/records/?{qs}" if qs else "/records/"

    data = await api_get(url)
    if data is None:
        return "無法取得病歷資料。"
    records = data.get("records", [])
    if not records:
        return "沒有找到病歷記錄。"

    lines = []
    for r in records:
        date = r.get("visit_date", "未記錄")[:10]
        patient = r.get("patients", {}).get("name", "未知")
        doctor = r.get("doctors", {}).get("name", "未指定") if r.get("doctors") else "未指定"
        symptoms = ", ".join(r.get("symptoms", []))
        line = f"- [{date}] {patient} | 醫師: {doctor} | 症狀: {symptoms}"
        if r.get("diagnosis"):
            line += f" | 診斷: {r['diagnosis']}"
        lines.append(line)
    return "\n".join(lines)


@mcp.tool()
async def get_patient_history(patient_id: str) -> str:
    """取得病患的完整就診紀錄。

    Args:
        patient_id: 病患 UUID
    """
    data = await api_get(f"/records/patient/{patient_id}")
    if data is None:
        return "無法取得就診紀錄。"
    records = data.get("records", [])
    if not records:
        return "該病患沒有就診紀錄。"

    lines = []
    for r in records:
        date = r.get("visit_date", "")[:10]
        doctor = r.get("doctors", {}).get("name", "未指定") if r.get("doctors") else "未指定"
        symptoms = ", ".join(r.get("symptoms", []))
        lines.append(f"[{date}] 醫師: {doctor}")
        if symptoms:
            lines.append(f"  症狀: {symptoms}")
        if r.get("diagnosis"):
            lines.append(f"  診斷: {r['diagnosis']}")
        if r.get("prescription"):
            lines.append(f"  處方: {r['prescription']}")
        lines.append("")
    return "\n".join(lines)


# ─── 症狀工具 ──────────────────────────────────────────────

@mcp.tool()
async def get_symptom_advice(symptom: str) -> str:
    """根據症狀取得快速醫療建議。

    Args:
        symptom: 症狀名稱（例如：fever、headache、chest pain、cough）
    """
    data = await api_get(f"/symptoms/advice?symptom={symptom}")
    if data is None:
        return "無法取得症狀建議，請確認 MD.Piece backend 是否已啟動。"
    return f"症狀：{data.get('symptom')}\n建議：{data.get('advice')}"


@mcp.tool()
async def analyze_symptoms(symptoms: str, patient_id: str = "") -> str:
    """使用 AI 分析多個症狀，提供可能病因和建議。

    Args:
        symptoms: 症狀列表（逗號分隔，例如：fever, headache, cough）
        patient_id: 病患 UUID（選填，提供時會記錄分析結果）
    """
    symptom_list = [s.strip() for s in symptoms.split(",") if s.strip()]
    body: dict[str, Any] = {"symptoms": symptom_list}
    if patient_id:
        body["patient_id"] = patient_id

    data = await api_post("/symptoms/analyze", body)
    if data is None:
        return "AI 分析失敗。"

    lines = [f"緊急程度：{data.get('urgency', 'unknown')}"]
    lines.append(f"建議科別：{data.get('recommended_department', 'N/A')}")
    conditions = data.get("conditions", [])
    if conditions:
        lines.append("可能病因：")
        for c in conditions:
            lines.append(f"  - {c.get('name')} (可能性: {c.get('likelihood')})")
    if data.get("advice"):
        lines.append(f"建議：{data['advice']}")
    if data.get("disclaimer"):
        lines.append(f"免責聲明：{data['disclaimer']}")
    return "\n".join(lines)


@mcp.tool()
async def get_experiments(kept: str = "") -> str:
    """取得 AutoResearch 實驗結果清單。

    Args:
        kept: 篩選條件（選填："true" 只顯示保留的，"false" 只顯示還原的）
    """
    params = f"?kept={kept}" if kept in ("true", "false") else ""
    data = await api_get(f"/research/{params}")
    if data is None:
        return "無法取得實驗資料，請確認 MD.Piece backend 是否已啟動。"
    experiments = data.get("experiments", [])
    if not experiments:
        return "目前沒有任何實驗結果。請從 Colab 執行訓練後回傳。"
    lines = []
    for e in experiments:
        metrics = []
        if e.get("val_bpb") is not None:
            metrics.append(f"bpb={e['val_bpb']:.4f}")
        if e.get("train_loss") is not None:
            metrics.append(f"loss={e['train_loss']:.4f}")
        if e.get("steps"):
            metrics.append(f"{e['steps']} steps")
        status = "kept" if e.get("kept") else ("reverted" if e.get("kept") is False else "")
        date = (e.get("submitted_at") or "")[:10]
        line = f"- {e['name']} [{status}] {' | '.join(metrics)} ({date})"
        lines.append(line)
    return f"共 {len(experiments)} 個實驗：\n" + "\n".join(lines)


@mcp.tool()
async def get_experiment_stats() -> str:
    """取得 AutoResearch 實驗統計摘要：最佳成績、改善率、訓練時間等。"""
    data = await api_get("/research/stats")
    if data is None:
        return "無法取得統計資料。"
    lines = [
        f"總實驗數: {data.get('total', 0)}",
        f"有 bpb 數據: {data.get('with_bpb', 0)}",
        f"最佳 val_bpb: {data.get('best_bpb', 'N/A')} ({data.get('best_experiment', 'N/A')})",
        f"保留: {data.get('kept_count', 0)} | 還原: {data.get('reverted_count', 0)}",
        f"改善率: {data.get('improvement_rate', 'N/A')}%",
        f"總訓練時間: {data.get('total_duration_hours', 0)} 小時",
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_experiment_leaderboard(top_n: int = 5) -> str:
    """取得 val_bpb 排行榜（越低越好）。

    Args:
        top_n: 顯示前幾名（預設 5）
    """
    data = await api_get(f"/research/leaderboard?top_n={top_n}")
    if data is None:
        return "無法取得排行榜資料。"
    ranking = data.get("leaderboard", [])
    if not ranking:
        return "尚無排行資料。"
    lines = []
    for r in ranking:
        dur = f"{r['duration_seconds']:.0f}s" if r.get("duration_seconds") else "-"
        lines.append(f"#{r['rank']} {r['name']}: bpb={r['val_bpb']:.4f} ({dur})")
    return f"Top {len(ranking)} 排行榜：\n" + "\n".join(lines)


@mcp.tool()
async def submit_experiment_result(
    name: str,
    val_bpb: float = 0,
    train_loss: float = 0,
    steps: int = 0,
    duration_seconds: float = 0,
    notes: str = "",
    kept: bool = False,
) -> str:
    """提交 AutoResearch 實驗結果。

    Args:
        name: 實驗名稱
        val_bpb: 驗證 bits-per-byte 分數
        train_loss: 訓練損失
        steps: 訓練步數
        duration_seconds: 訓練時間（秒）
        notes: 備註
        kept: 是否保留此實驗
    """
    body = {"name": name, "kept": kept}
    if val_bpb:
        body["val_bpb"] = val_bpb
    if train_loss:
        body["train_loss"] = train_loss
    if steps:
        body["steps"] = steps
    if duration_seconds:
        body["duration_seconds"] = duration_seconds
    if notes:
        body["notes"] = notes
    data = await api_post("/research/", body)
    if data is None:
        return "提交實驗結果失敗。"
    return f"實驗已提交：{data.get('message', name)}"


@mcp.tool()
async def get_symptom_history(patient_id: str) -> str:
    """取得病患的 AI 症狀分析歷史。

    Args:
        patient_id: 病患 UUID
    """
    data = await api_get(f"/symptoms/history/{patient_id}")
    if data is None:
        return "無法取得分析歷史。"
    history = data.get("history", [])
    if not history:
        return "該病患沒有症狀分析紀錄。"

    lines = []
    for h in history:
        date = h.get("created_at", "")[:10]
        symptoms = ", ".join(h.get("symptoms", []))
        ai = h.get("ai_response", {})
        urgency = ai.get("urgency", "N/A") if ai else "N/A"
        lines.append(f"[{date}] 症狀: {symptoms} | 緊急程度: {urgency}")
    return "\n".join(lines)


# ─── 啟動 ──────────────────────────────────────────────────

def main():
    logger.info("MD.Piece MCP Server 啟動中...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

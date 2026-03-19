import sys
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


async def api_get(path: str) -> dict[str, Any] | None:
    """發送 GET 請求到 MD.Piece API。"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}{path}", timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GET {path} 失敗: {e}")
            return None


async def api_post(path: str, params: dict) -> dict[str, Any] | None:
    """發送 POST 請求到 MD.Piece API。"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_BASE}{path}", params=params, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"POST {path} 失敗: {e}")
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
    return "\n".join(f"- {p}" for p in patients)


@mcp.tool()
async def create_patient(name: str, age: int) -> str:
    """建立新病患。

    Args:
        name: 病患姓名
        age: 病患年齡
    """
    data = await api_post("/patients/", {"name": name, "age": age})
    if data is None:
        return "建立病患失敗，請確認 MD.Piece backend 是否已啟動。"
    return f"✅ 病患已建立：{data.get('name')}，年齡 {data.get('age')}，狀態：{data.get('status')}"


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
    return "\n".join(f"- {d}" for d in doctors)


@mcp.tool()
async def create_doctor(name: str, specialty: str) -> str:
    """建立新醫師。

    Args:
        name: 醫師姓名
        specialty: 專科（例如：內科、外科、兒科）
    """
    data = await api_post("/doctors/", {"name": name, "specialty": specialty})
    if data is None:
        return "建立醫師失敗，請確認 MD.Piece backend 是否已啟動。"
    return f"✅ 醫師已建立：{data.get('name')}，專科：{data.get('specialty')}，狀態：{data.get('status')}"


# ─── 症狀工具 ──────────────────────────────────────────────

@mcp.tool()
async def get_symptom_advice(symptom: str) -> str:
    """根據症狀取得醫療建議。

    Args:
        symptom: 症狀名稱（例如：fever、headache、chest pain、cough）
    """
    data = await api_get(f"/symptoms/advice?symptom={symptom}")
    if data is None:
        return "無法取得症狀建議，請確認 MD.Piece backend 是否已啟動。"
    return f"症狀：{data.get('symptom')}\n建議：{data.get('advice')}"


# ─── 啟動 ──────────────────────────────────────────────────

def main():
    logger.info("MD.Piece MCP Server 啟動中...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

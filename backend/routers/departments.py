from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import DepartmentCreate, DepartmentUpdate

router = APIRouter()

# 預設台灣常見科別
DEFAULT_DEPARTMENTS = [
    {"name": "內科", "code": "IM", "description": "內科疾病診治"},
    {"name": "外科", "code": "SU", "description": "外科手術與術後照護"},
    {"name": "小兒科", "code": "PE", "description": "兒童與青少年醫療"},
    {"name": "婦產科", "code": "OB", "description": "婦女健康與產科"},
    {"name": "骨科", "code": "OR", "description": "骨骼肌肉系統疾病"},
    {"name": "皮膚科", "code": "DE", "description": "皮膚、毛髮、指甲疾病"},
    {"name": "神經科", "code": "NE", "description": "神經系統疾病診治"},
    {"name": "眼科", "code": "OP", "description": "眼部疾病與視力"},
    {"name": "耳鼻喉科", "code": "EN", "description": "耳鼻喉頭頸疾病"},
    {"name": "精神科", "code": "PS", "description": "心理與精神健康"},
    {"name": "心臟科", "code": "CA", "description": "心臟血管疾病"},
    {"name": "腫瘤科", "code": "ON", "description": "癌症與腫瘤治療"},
    {"name": "急診科", "code": "ER", "description": "緊急醫療處置"},
    {"name": "家醫科", "code": "FM", "description": "全人照護與慢性病管理"},
    {"name": "復健科", "code": "RE", "description": "物理治療與復健"},
]


@router.get("/")
def get_departments():
    sb = get_supabase()
    result = sb.table("departments").select("*").order("name").execute()
    return {"departments": result.data}


@router.get("/{department_id}")
def get_department(department_id: str):
    sb = get_supabase()
    result = sb.table("departments").select("*").eq("id", department_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該科別")
    return result.data[0]


@router.get("/{department_id}/doctors")
def get_department_doctors(department_id: str):
    """取得某科別下所有醫師。"""
    sb = get_supabase()
    dept = sb.table("departments").select("*").eq("id", department_id).execute()
    if not dept.data:
        raise HTTPException(status_code=404, detail="找不到該科別")
    doctors = sb.table("doctors").select("*").eq("department_id", department_id).order("name").execute()
    return {"department": dept.data[0], "doctors": doctors.data}


@router.post("/")
def create_department(body: DepartmentCreate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("departments").insert(data).execute()
    return result.data[0]


@router.put("/{department_id}")
def update_department(department_id: str, body: DepartmentUpdate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    result = sb.table("departments").update(data).eq("id", department_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該科別")
    return result.data[0]


@router.delete("/{department_id}")
def delete_department(department_id: str):
    sb = get_supabase()
    result = sb.table("departments").delete().eq("id", department_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該科別")
    return {"message": "科別已刪除", "id": department_id}


@router.post("/seed")
def seed_departments():
    """初始化預設科別資料。"""
    sb = get_supabase()
    existing = sb.table("departments").select("code").execute()
    existing_codes = {d["code"] for d in existing.data if d.get("code")}
    to_insert = [d for d in DEFAULT_DEPARTMENTS if d["code"] not in existing_codes]
    if not to_insert:
        return {"message": "科別資料已存在，無需初始化", "count": 0}
    result = sb.table("departments").insert(to_insert).execute()
    return {"message": f"已新增 {len(result.data)} 個科別", "count": len(result.data)}

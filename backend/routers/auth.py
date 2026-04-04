from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import UserCreate

router = APIRouter()


@router.post("/register")
def register(body: UserCreate):
    sb = get_supabase()
    if body.role not in ("doctor", "patient"):
        raise HTTPException(status_code=400, detail="角色必須是 doctor 或 patient")
    data = body.model_dump(exclude_none=True)
    result = sb.table("users").insert(data).execute()
    return result.data[0]


@router.get("/user/{user_id}")
def get_user(user_id: str):
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return result.data[0]


@router.get("/users")
def list_users():
    sb = get_supabase()
    result = sb.table("users").select("*").order("created_at", desc=True).execute()
    return {"users": result.data}

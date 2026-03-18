from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_patients():
    return {"patients": []}

@router.post("/")
def create_patient(name: str, age: int):
    return {"name": name, "age": age, "status": "registered"}

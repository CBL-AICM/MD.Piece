from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_doctors():
    return {"doctors": []}

@router.post("/")
def create_doctor(name: str, specialty: str):
    return {"name": name, "specialty": specialty, "status": "registered"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import patients, doctors, symptoms, records, research, storm

app = FastAPI(title="MD.Piece API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(storm.router, prefix="/storm", tags=["storm"])


@app.get("/")
def root():
    return {"message": "MD.Piece API is running", "version": "2.0.0"}

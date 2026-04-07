from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth_student, auth_teacher, teacher

app = FastAPI(title="Liter API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_teacher.router, prefix="/api/v1")
app.include_router(auth_student.router, prefix="/api/v1")
app.include_router(teacher.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Liter API"}

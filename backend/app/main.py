import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

from app.core.config import settings
from app.routers import auth_student, auth_teacher, student, teacher

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Supabase 연결 확인
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        # health check — 간단한 메타 요청
        client.table("teachers").select("id").limit(1).execute()
        logger.info("✅ Supabase connected (URL: %s...)", settings.SUPABASE_URL[:30])
    except Exception as e:
        logger.warning("⚠️  Supabase connection check failed: %s", e)
    yield
    # Shutdown
    logger.info("👋 Shutting down Liter API")


app = FastAPI(title="Liter API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://liter-psi.vercel.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_teacher.router, prefix="/api/v1")
app.include_router(auth_student.router, prefix="/api/v1")
app.include_router(teacher.router, prefix="/api/v1")
app.include_router(student.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Liter API", "env": settings.APP_ENV}

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.supabase import create_supabase
from app.routers import auth_student, auth_teacher, internal, student, teacher

logger = logging.getLogger("uvicorn.error")


def _mask_prefix(value: str, prefix: int = 30) -> str:
    if not value:
        return ""
    return value[:prefix]


def _log_supabase_startup_check(label: str, key: str) -> None:
    logger.info("[STARTUP] %s set: %s, length: %s", label, bool(key), len(key) if key else 0)
    if not settings.SUPABASE_URL or not key:
        logger.warning("[STARTUP] %s ping skipped due to missing configuration", label)
        return
    try:
        client = create_supabase(key)
        res = client.table("teachers").select("id").limit(1).execute()
        logger.info(
            "[STARTUP] %s ping OK (url=%s..., rows=%s)",
            label,
            _mask_prefix(settings.SUPABASE_URL),
            len(res.data) if res and res.data else 0,
        )
    except Exception as e:
        logger.exception("[STARTUP] %s ping FAILED: %s: %s", label, type(e).__name__, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Supabase 연결 확인
    logger.info("[STARTUP] SUPABASE_URL set: %s", bool(settings.SUPABASE_URL))
    _log_supabase_startup_check("SUPABASE_ANON_KEY", settings.SUPABASE_ANON_KEY)
    _log_supabase_startup_check("SUPABASE_SERVICE_ROLE_KEY", settings.SUPABASE_SERVICE_ROLE_KEY)
    yield
    # Shutdown
    logger.info("👋 Shutting down Liter API")


app = FastAPI(title="Liter API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://liter-psi.vercel.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    # SSE 호환: EventSource가 보내는 Accept, Cache-Control, Last-Event-ID 포함
    allow_headers=["Content-Type", "Authorization", "Accept", "Cache-Control", "Last-Event-ID"],
)

app.include_router(auth_teacher.router, prefix="/api/v1")
app.include_router(auth_student.router, prefix="/api/v1")
app.include_router(teacher.router, prefix="/api/v1")
app.include_router(student.router, prefix="/api/v1")
app.include_router(internal.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Liter API", "env": settings.APP_ENV}

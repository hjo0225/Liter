from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from supabase import create_client

from app.core.config import settings

router = APIRouter(prefix="/internal", tags=["internal"])

SESSION_TIMEOUT_MINUTES = 60


def _service_client():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


@router.post("/cleanup-sessions")
def cleanup_sessions():
    service = _service_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()

    expired_res = (
        service.table("sessions")
        .select("id")
        .eq("status", "in_progress")
        .lt("started_at", cutoff)
        .execute()
    )
    expired_sessions = expired_res.data or []
    expired_ids = [row["id"] for row in expired_sessions if row.get("id")]

    if expired_ids:
        (
            service.table("sessions")
            .update({"status": "abandoned"})
            .in_("id", expired_ids)
            .execute()
        )

    return {
        "ok": True,
        "cutoff": cutoff,
        "abandoned_count": len(expired_ids),
    }

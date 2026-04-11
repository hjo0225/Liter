"""
P6 학생 입력 채널.

POST /student/sessions/{id}/discussion/turns
  body : { text, client_ts? }
  처리 : 세션 검증 → 채널 대기 확인 → Moderation → DB 저장 → 큐 push
  응답 : 202 { status: "accepted" }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.deps import get_current_student
from app.core.llm_logging import log_session_event
from app.core.state import get_channel
from app.core.supabase import supabase

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

_openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Schema
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TurnSubmitRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    client_ts: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POST /sessions/{session_id}/discussion/turns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post(
    "/sessions/{session_id}/discussion/turns",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_turn(
    session_id: str,
    body: TurnSubmitRequest,
    student_id: str = Depends(get_current_student),
):
    """학생 발화를 받아 SSE 오케스트레이터를 깨운다."""

    # ── 1. 세션 검증 ──────────────────────────────────────
    res = (
        supabase.table("sessions")
        .select("id, student_id, status")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    session = res.data
    if session["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    if session["status"] != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="SESSION_NOT_IN_PROGRESS",
        )

    # ── 2. 채널 확인 (P9: waiting_for_user 여부 무관하게 항상 허용) ─
    ch = get_channel(session_id)
    if ch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="NO_ACTIVE_SESSION",
        )

    # ── 3. OpenAI Moderation ──────────────────────────────
    try:
        mod = await _openai.moderations.create(input=body.text)
        if mod.results[0].flagged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MODERATION_BLOCKED",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("Moderation API 실패, 통과 처리: session_id=%s", session_id, exc_info=True)

    # ── 4. messages 테이블에 즉시 저장 ───────────────────
    last_res = (
        supabase.table("messages")
        .select("round")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    user_round = last_res.data[0]["round"] if last_res.data else 1

    row: dict = {
        "session_id": session_id,
        "speaker": "user",
        "content": body.text.strip(),
        "round": user_round,
        "role": "user",
        "server_ts": datetime.now(timezone.utc).isoformat(),
    }
    if body.client_ts:
        row["client_ts"] = body.client_ts
    supabase.table("messages").insert(row).execute()

    log_session_event(session_id, "user_turn", {
        "round": user_round,
        "length": len(body.text.strip()),
        "client_ts": body.client_ts,
    })

    # ── 5. 오케스트레이터 깨우기 ─────────────────────────
    ch.queue.put_nowait({"text": body.text.strip(), "client_ts": body.client_ts})

    return {"status": "accepted"}

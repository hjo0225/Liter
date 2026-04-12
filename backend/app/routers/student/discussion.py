"""
Discussion 라우터 — P5 SSE 프로토콜 확장.

POST /sessions/{id}/discussion  : 기존 호환 유지 (fetch 기반 SSE)
GET  /sessions/{id}/discussion  : EventSource 호환 SSE
  - 30초 heartbeat
  - 클라이언트 disconnect 감지 → 백그라운드 task 취소
  - token을 query param으로 수락 (EventSource는 헤더 설정 불가)
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.auth import JWTError, decode_student_token
from app.core.deps import get_current_student
from app.core.llm_logging import log_session_event
from app.core.state import create_channel, remove_channel
from app.core.supabase import supabase
from app.schemas.llm import PassageGeneration
from app.schemas.session import DiscussionRequest
from app.services.discussion import run_discussion

# ── P10: 침묵 타임아웃 상수 ───────────────────────────────────
_IDLE_TICK_SEC = 15        # user_idle 이벤트 발송 주기 (초)
_NUDGE_AT_SEC  = 30        # 이 시점에 moderator nudge 발화
_SKIP_AT_SEC   = 90        # 이 시점에 학생 발화 skip + 다음 라운드 진행

# ── P10: nudge 메시지 풀 ──────────────────────────────────────
_NUDGE_POOL = [
    "{name}아, 괜찮아요. 천천히 생각해도 돼요! 방금 친구들 이야기 중 마음에 걸리는 부분이 있었나요?",
    "서두르지 않아도 괜찮아요, {name}! 떠오르는 생각이 있으면 편하게 말해줘요.",
    "{name}아, 정답은 없어요. 느낀 점이나 궁금한 점을 자유롭게 이야기해줄 수 있나요?",
]

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_HEARTBEAT_INTERVAL = 30  # seconds


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SSE 포맷 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _heartbeat() -> str:
    return _sse({"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()})


def _error(code: str, message: str = "") -> str:
    return _sse({"type": "error", "code": code, "message": message})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  인증 — query param 토큰 (GET SSE 전용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _decode_student_token(token: str) -> str:
    """JWT 검증 → student_id 반환. 실패 시 HTTPException."""
    try:
        return decode_student_token(token)
    except (JWTError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN") from e


def get_student_from_query(token: str = Query(..., description="학생 JWT")) -> str:
    return _decode_student_token(token)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  공통: 세션 검증 + context 구성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _validate_session(session_id: str, student_id: str) -> dict:
    """세션 조회·소유권·상태 검증. 실패 시 HTTPException."""
    res = (
        supabase.table("sessions")
        .select("id, student_id, status, passage_id")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    data = res.data
    if data["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    if data["status"] != "in_progress":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SESSION_NOT_IN_PROGRESS")
    return data


def _build_context(student_id: str, session_id: str, passage_id: str) -> dict:
    """세션 context dict 구성. supabase 동기 호출 3회."""
    student_res = (
        supabase.table("students")
        .select("name, level, weak_areas")
        .eq("id", student_id)
        .single()
        .execute()
    )
    s = student_res.data or {}

    passage_res = (
        supabase.table("passages")
        .select("generated_content")
        .eq("id", passage_id)
        .single()
        .execute()
    )
    passage_content = ""
    if passage_res.data and passage_res.data.get("generated_content"):
        try:
            p = PassageGeneration.model_validate_json(passage_res.data["generated_content"])
            passage_content = p.passage
        except Exception:
            logger.exception("generated_content 파싱 실패: session_id=%s", session_id)

    qr_res = (
        supabase.table("question_results")
        .select("question_type, is_correct")
        .eq("session_id", session_id)
        .execute()
    )
    question_results = qr_res.data or []
    all_correct = all(q.get("is_correct") for q in question_results) if question_results else False

    return {
        "student_name": s.get("name") or "학생",
        "passage_content": passage_content,
        "question_results": question_results,
        "all_correct": all_correct,
        "student_level": s.get("level", 2),
        "weak_areas": s.get("weak_areas") or [],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DB 헬퍼 (라우터 내부 전용 — nudge / skip 저장)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _save_message_to_db(
    session_id: str,
    speaker: str,
    content: str,
    round_num: int,
    role: str = "assistant",
) -> None:
    try:
        supabase.table("messages").insert({
            "session_id": session_id,
            "speaker": speaker,
            "content": content,
            "round": round_num,
            "role": role,
            "server_ts": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        logger.warning(
            "messages 저장 실패: session_id=%s speaker=%s", session_id, speaker, exc_info=True
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET — EventSource 호환 SSE (heartbeat + disconnect cancel)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/sessions/{session_id}/discussion")
async def discussion_sse_get(
    session_id: str,
    request: Request,
    demo_mode: bool = Query(default=False, description="데모 모드"),
    student_id: str = Depends(get_student_from_query),
):
    """
    EventSource 호환 SSE 엔드포인트 (P6 지속 연결).

    - 세션 전체를 하나의 SSE 연결로 유지한다.
    - 학생 입력은 POST /discussion/turns 로 별도 수신 후 큐로 전달.
    - 30초마다 heartbeat 전송.
    - 클라이언트 disconnect 시 채널 정리.
    """
    session_data = _validate_session(session_id, student_id)
    context = _build_context(student_id, session_id, session_data["passage_id"])

    # 세션 채널 생성 (turns 엔드포인트와 공유)
    ch = create_channel(session_id)

    async def generate():
        hb_task: asyncio.Task | None = None

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await inner_queue.put({"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()})

        inner_queue: asyncio.Queue = asyncio.Queue()

        try:
            hb_task = asyncio.create_task(_heartbeat())

            user_content = ""   # 첫 라운드: 학생 발화 없음
            current_round = 1   # waiting_for_user 이벤트에서 업데이트

            while True:
                if await request.is_disconnected():
                    logger.info("GET SSE disconnect: session_id=%s", session_id)
                    return

                # ── 라운드 실행 ────────────────────────────
                got_waiting = False
                got_final = False

                async def _run_round() -> None:
                    nonlocal got_waiting, got_final, current_round
                    try:
                        async for event in run_discussion(
                            session_id=session_id,
                            user_content=user_content,
                            context=context,
                            demo_mode=demo_mode,
                        ):
                            await inner_queue.put(event)
                            if event.get("type") == "waiting_for_user":
                                got_waiting = True
                                current_round = event.get("round", current_round)
                            elif event.get("type") == "is_final":
                                got_final = True
                    except Exception:
                        logger.exception("run_discussion 실패: session_id=%s", session_id)
                        await inner_queue.put({"type": "error", "code": "llm_failure", "message": "토의 생성 실패"})
                    finally:
                        await inner_queue.put(None)

                prod_task = asyncio.create_task(_run_round())

                # ── 이벤트 drain ───────────────────────────
                while True:
                    if await request.is_disconnected():
                        prod_task.cancel()
                        return

                    try:
                        event = await asyncio.wait_for(inner_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue

                    if event is None:
                        break

                    yield _sse(event)

                    if event.get("type") == "is_final":
                        return

                if got_final:
                    return

                # ── P10: 학생 입력 대기 (15s 단위 idle 감지) ──
                if got_waiting:
                    ch.waiting_for_user = True
                    idle_elapsed = 0
                    nudge_sent = False
                    user_received = False

                    try:
                        while True:
                            if await request.is_disconnected():
                                return

                            try:
                                await asyncio.wait_for(ch.queue.get(), timeout=_IDLE_TICK_SEC)
                                user_received = True
                                break
                            except asyncio.TimeoutError:
                                idle_elapsed += _IDLE_TICK_SEC
                                yield _sse({"type": "user_idle", "idle_seconds": idle_elapsed})
                                log_session_event(session_id, "user_idle", {
                                    "round": current_round,
                                    "idle_seconds": idle_elapsed,
                                })
                                logger.debug(
                                    "user_idle: session_id=%s idle=%ds", session_id, idle_elapsed
                                )

                                # 30s: moderator nudge 발화
                                if idle_elapsed >= _NUDGE_AT_SEC and not nudge_sent:
                                    nudge_sent = True
                                    student_name = context.get("student_name", "학생")
                                    nudge_text = random.choice(_NUDGE_POOL).format(name=student_name)
                                    _save_message_to_db(session_id, "moderator", nudge_text, current_round)
                                    yield _sse({
                                        "type": "turn_end",
                                        "speaker": "moderator",
                                        "content": nudge_text,
                                        "turn_id": str(uuid.uuid4()),
                                        "round": current_round,
                                    })
                                    logger.info(
                                        "nudge sent: session_id=%s round=%d", session_id, current_round
                                    )

                                # 90s: 자동 skip
                                if idle_elapsed >= _SKIP_AT_SEC:
                                    logger.info(
                                        "user_skip: session_id=%s round=%d", session_id, current_round
                                    )
                                    break
                    finally:
                        ch.waiting_for_user = False

                    if not user_received:
                        # 학생 발화 없이 90초 경과 → skip 저장 후 다음 라운드
                        _save_message_to_db(session_id, "user", "(응답 없음)", current_round, role="user")
                        log_session_event(session_id, "user_skip", {
                            "round": current_round,
                            "idle_seconds": idle_elapsed,
                        })
                        yield _sse({"type": "user_skip", "round": current_round})

                    # turns 엔드포인트 또는 skip이 DB에 이미 저장했으므로 빈 content로 재호출
                    user_content = ""
                    continue

                break

        finally:
            if hb_task:
                hb_task.cancel()
            remove_channel(session_id)
            logger.debug("GET SSE 채널 정리: session_id=%s", session_id)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POST — 기존 호환 fetch 기반 SSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/sessions/{session_id}/discussion")
async def discussion_sse_post(
    session_id: str,
    body: DiscussionRequest,
    request: Request,
    student_id: str = Depends(get_current_student),
):
    """
    fetch 기반 SSE (Authorization 헤더 지원).
    기존 클라이언트 호환 유지.
    """
    session_data = _validate_session(session_id, student_id)
    context = _build_context(student_id, session_id, session_data["passage_id"])

    async def generate():
        try:
            async for event in run_discussion(
                session_id=session_id,
                user_content=body.content,
                context=context,
                demo_mode=body.demo_mode,
            ):
                if await request.is_disconnected():
                    logger.info("POST SSE disconnect: session_id=%s", session_id)
                    return
                yield _sse(event)
        except Exception:
            logger.exception("POST SSE 실패: session_id=%s", session_id)
            yield _error("llm_failure", "토의 생성 중 오류가 발생했습니다.")

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)

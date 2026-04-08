import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.agents.discussion_agent import call_moderator, call_peer_a, call_peer_b
from app.core.constants import MAX_DISCUSSION_TOPICS
from app.core.deps import get_current_student
from app.core.supabase import supabase
from app.schemas.llm import PassageGeneration
from app.schemas.session import DiscussionRequest

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/discussion")
async def discussion(
    session_id: str,
    body: DiscussionRequest,
    request: Request,
    student_id: str = Depends(get_current_student),
):
    # 1. 세션 검증
    session_res = (
        supabase.table("sessions")
        .select("id, student_id, status, passage_id")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not session_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    session_data = session_res.data
    if session_data["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    if session_data["status"] != "in_progress":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SESSION_NOT_IN_PROGRESS")

    # 2. context 구성
    student_res = (
        supabase.table("students")
        .select("level, weak_areas")
        .eq("id", student_id)
        .single()
        .execute()
    )
    s = student_res.data or {}

    passage_res = (
        supabase.table("passages")
        .select("generated_content")
        .eq("id", session_data["passage_id"])
        .single()
        .execute()
    )
    passage_content = ""
    if passage_res.data and passage_res.data.get("generated_content"):
        try:
            p_data = PassageGeneration.model_validate_json(passage_res.data["generated_content"])
            passage_content = p_data.passage
        except Exception:
            logger.exception("Invalid generated_content in discussion: session_id=%s", session_id)

    qr_res = (
        supabase.table("question_results")
        .select("question_type, is_correct")
        .eq("session_id", session_id)
        .execute()
    )
    question_results = qr_res.data or []
    all_correct = all(q.get("is_correct") for q in question_results) if question_results else False

    context = {
        "passage_content": passage_content,
        "question_results": question_results,
        "all_correct": all_correct,
        "student_level": s.get("level", 2),
        "weak_areas": s.get("weak_areas") or [],
    }

    # 3. 현재까지의 메시지 이력 조회
    msg_res = (
        supabase.table("messages")
        .select("speaker, content, round, role")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    existing_messages = msg_res.data or []

    # 4. 현재 주제 번호 계산 (1~3)
    current_topic = 1
    if existing_messages:
        current_topic = max(m["round"] for m in existing_messages)
        if body.content:
            # 학생 발화가 있으면 다음 주제로 이동
            current_topic += 1

    async def generate():
        nonlocal existing_messages
        try:
            # 학생 발화 저장
            if body.content and body.content.strip():
                supabase.table("messages").insert({
                    "session_id": session_id,
                    "role": "user",
                    "speaker": "user",
                    "content": body.content.strip(),
                    "round": current_topic - 1,  # 이전 주제에 속함
                }).execute()
                existing_messages.append({
                    "speaker": "user",
                    "content": body.content.strip(),
                    "round": current_topic - 1,
                    "role": "user",
                })

            # 3가지 주제 모두 토의 완료 시 종료
            if current_topic > MAX_DISCUSSION_TOPICS:
                yield _sse_event({"is_final": True})
                return

            if await request.is_disconnected():
                logger.info("Client disconnected before LLM call, session_id=%s", session_id)
                return

            ai_messages_to_save = []

            if current_topic == 1:
                # 주제 1: 모더레이터가 첫 번째 주제 소개 → 또래A 의견
                mod_content = await asyncio.to_thread(call_moderator, context, existing_messages, current_topic)
                if await request.is_disconnected():
                    logger.info("Client disconnected after moderator call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "moderator", "content": mod_content, "round": current_topic})
                ai_messages_to_save.append(("moderator", mod_content))

                peer_a_content = await asyncio.to_thread(
                    call_peer_a,
                    context,
                    existing_messages + [{"speaker": "moderator", "content": mod_content, "round": current_topic}],
                    current_topic,
                )
                if await request.is_disconnected():
                    logger.info("Client disconnected after peer_a call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "peer_a", "content": peer_a_content, "round": current_topic})
                ai_messages_to_save.append(("peer_a", peer_a_content))
            else:
                # 주제 2~3: 또래B 반응 → 모더레이터가 다음 주제로 전환 또는 마무리
                peer_b_content = await asyncio.to_thread(call_peer_b, context, existing_messages, current_topic)
                if await request.is_disconnected():
                    logger.info("Client disconnected after peer_b call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "peer_b", "content": peer_b_content, "round": current_topic})
                ai_messages_to_save.append(("peer_b", peer_b_content))

                mod_content = await asyncio.to_thread(
                    call_moderator,
                    context,
                    existing_messages + [{"speaker": "peer_b", "content": peer_b_content, "round": current_topic}],
                    current_topic,
                )
                if await request.is_disconnected():
                    logger.info("Client disconnected after moderator call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "moderator", "content": mod_content, "round": current_topic})
                ai_messages_to_save.append(("moderator", mod_content))

            # AI 메시지 DB 저장
            for speaker, content in ai_messages_to_save:
                supabase.table("messages").insert({
                    "session_id": session_id,
                    "role": "assistant",
                    "speaker": speaker,
                    "content": content,
                    "round": current_topic,
                }).execute()

            if current_topic >= MAX_DISCUSSION_TOPICS:
                yield _sse_event({"is_final": True})
            else:
                yield _sse_event({"next_speaker": "user", "round": current_topic, "is_final": False})
        except Exception:
            logger.exception("Discussion stream failed for session_id=%s topic=%s", session_id, current_topic)
            yield _sse_event({"error": "DISCUSSION_FAILED", "is_final": False})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

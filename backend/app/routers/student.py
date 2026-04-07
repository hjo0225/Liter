import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from supabase import create_client

from app.agents.diagnosis_agent import diagnose_student
from app.agents.discussion_agent import call_moderator, call_peer_a, call_peer_b
from app.agents.feedback_agent import analyze_discussion
from app.agents.passage_agent import generate_passage_and_questions
from app.core.config import settings
from app.core.deps import get_current_student
from app.schemas.session import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    DiscussionRequest,
    PassageOut,
    QuestionOut,
    QuestionResultOut,
    SessionEndResponse,
    SessionStartResponse,
    StudentMeResponse,
)

router = APIRouter(prefix="/student", tags=["student"])
logger = logging.getLogger("uvicorn.error")


def _service_client():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ──────────────────────────────────────────────
# GET /student/me
# ──────────────────────────────────────────────
@router.get("/me", response_model=StudentMeResponse)
def get_me(student_id: str = Depends(get_current_student)):
    service = _service_client()
    today = date.today().isoformat()
    seven_days_ago = (date.today() - timedelta(days=6)).isoformat()

    student_res = (
        service.table("students")
        .select("name, level, streak_count, weak_areas, classroom_id")
        .eq("id", student_id)
        .single()
        .execute()
    )
    if not student_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="STUDENT_NOT_FOUND")

    count_res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )

    weekly_res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .gte("session_date", seven_days_ago)
        .execute()
    )

    total_completed_res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .execute()
    )

    recent_scores_res = (
        service.table("sessions")
        .select("score_reasoning, score_vocabulary, score_context")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .order("ended_at", desc=True)
        .limit(3)
        .execute()
    )

    s = student_res.data
    classroom_name = None
    if s.get("classroom_id"):
        classroom_res = (
            service.table("classrooms")
            .select("name")
            .eq("id", s["classroom_id"])
            .maybe_single()
            .execute()
        )
        if classroom_res.data:
            classroom_name = classroom_res.data["name"]

    recent_scores = recent_scores_res.data or []
    recent_average_score = None
    if recent_scores:
        recent_average_score = round(
            sum(
                (
                    (sess["score_reasoning"] or 0)
                    + (sess["score_vocabulary"] or 0)
                    + (sess["score_context"] or 0)
                )
                / 3
                for sess in recent_scores
            )
            / len(recent_scores),
            1,
        )

    return StudentMeResponse(
        name=s["name"],
        level=s["level"],
        streak_count=s["streak_count"] or 0,
        today_session_count=count_res.count or 0,
        classroom_name=classroom_name,
        weak_areas=s.get("weak_areas") or [],
        recent_average_score=recent_average_score,
        weekly_completed_count=weekly_res.count or 0,
        total_completed_count=total_completed_res.count or 0,
    )


# ──────────────────────────────────────────────
# GET /student/sessions/today-count
# ──────────────────────────────────────────────
@router.get("/sessions/today-count")
def today_session_count(student_id: str = Depends(get_current_student)):
    service = _service_client()
    today = date.today().isoformat()
    res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )
    return {"count": res.count or 0}


# ──────────────────────────────────────────────
# POST /student/sessions
# ──────────────────────────────────────────────
@router.post("/sessions", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(student_id: str = Depends(get_current_student)):
    service = _service_client()
    today = date.today().isoformat()

    # 1. 오늘 세션 수 확인
    count_res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )
    today_count = count_res.count or 0
    if today_count >= 3:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="DAILY_LIMIT_REACHED")

    daily_index = today_count + 1

    # 2. 학생 정보 조회
    student_res = (
        service.table("students")
        .select("level, teacher_override_level")
        .eq("id", student_id)
        .single()
        .execute()
    )
    if not student_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="STUDENT_NOT_FOUND")

    student = student_res.data
    difficulty = student["teacher_override_level"] if student["teacher_override_level"] else student["level"]

    # 3. 직전 세션의 passage_id 조회 (제외용)
    last_session_res = (
        service.table("sessions")
        .select("passage_id")
        .eq("student_id", student_id)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    last_passage_id = (
        last_session_res.data[0]["passage_id"] if last_session_res.data else None
    )

    # 4. passage 선택 (difficulty 매칭 + 직전 제외)
    passage_query = (
        service.table("passages")
        .select("*")
        .eq("difficulty", difficulty)
    )
    if last_passage_id:
        passage_query = passage_query.neq("id", last_passage_id)

    passage_res = passage_query.execute()

    if not passage_res.data:
        # 제외 없이 재시도
        passage_res = (
            service.table("passages")
            .select("*")
            .eq("difficulty", difficulty)
            .execute()
        )
    if not passage_res.data:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="NO_PASSAGE_AVAILABLE")

    # 랜덤 선택
    import random
    passage = random.choice(passage_res.data)

    # 5. generated_content 없으면 생성
    if not passage.get("generated_content"):
        try:
            generated = generate_passage_and_questions(
                difficulty=passage["difficulty"],
                genre=passage["genre"],
                topic=passage["topic"],
                structure_prompt=passage["structure_prompt"],
            )
        except RuntimeError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GENERATION_FAILED")

        content_json = json.dumps(generated, ensure_ascii=False)
        service.table("passages").update({"generated_content": content_json}).eq("id", passage["id"]).execute()
        passage["generated_content"] = content_json

    content_data = json.loads(passage["generated_content"])

    # 6. session INSERT
    now_iso = datetime.now(timezone.utc).isoformat()
    session_res = (
        service.table("sessions")
        .insert({
            "student_id": student_id,
            "passage_id": passage["id"],
            "status": "in_progress",
            "session_date": today,
            "daily_index": daily_index,
            "started_at": now_iso,
        })
        .execute()
    )
    session_id = session_res.data[0]["id"]

    # 7. question_results 3개 INSERT
    for i, q in enumerate(content_data["questions"]):
        service.table("question_results").insert({
            "session_id": session_id,
            "question_index": i + 1,
            "question_type": q["type"],
            "question_text": q["question"],
            "choices": q["choices"],
            "correct_index": q["correct_index"],
            "selected_index": None,
            "is_correct": None,
        }).execute()

    # 8. 응답 구성
    questions_out = [
        QuestionOut(
            index=i + 1,
            type=q["type"],
            text=q["question"],
            choices=q["choices"],
        )
        for i, q in enumerate(content_data["questions"])
    ]
    passage_out = PassageOut(
        title=passage["title"],
        genre=passage["genre"],
        difficulty=passage["difficulty"],
        content=content_data["passage"],
    )

    return SessionStartResponse(
        session_id=session_id,
        passage=passage_out,
        questions=questions_out,
    )


# ──────────────────────────────────────────────
# POST /student/sessions/{session_id}/answer
# ──────────────────────────────────────────────
@router.post("/sessions/{session_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    session_id: str,
    body: AnswerSubmitRequest,
    student_id: str = Depends(get_current_student),
):
    service = _service_client()

    # 1. 세션 검증
    session_res = (
        service.table("sessions")
        .select("id, student_id, status")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not session_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    session = session_res.data
    if session["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    if session["status"] != "in_progress":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SESSION_NOT_IN_PROGRESS")

    # 2. 입력 검증
    if body.question_index not in (1, 2, 3):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="INVALID_QUESTION_INDEX")
    if body.selected_index not in (0, 1, 2):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="INVALID_SELECTED_INDEX")

    # 3. question_results 조회
    qr_res = (
        service.table("question_results")
        .select("id, correct_index")
        .eq("session_id", session_id)
        .eq("question_index", body.question_index)
        .maybe_single()
        .execute()
    )
    if not qr_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QUESTION_NOT_FOUND")

    correct_index = qr_res.data["correct_index"]
    is_correct = body.selected_index == correct_index

    # 4. question_results UPDATE
    service.table("question_results").update({
        "selected_index": body.selected_index,
        "is_correct": is_correct,
    }).eq("id", qr_res.data["id"]).execute()

    # 5. 3문제 모두 답했는지 확인 → 첫 세션이면 진단 실행
    answered_res = (
        service.table("question_results")
        .select("is_correct, question_type")
        .eq("session_id", session_id)
        .not_.is_("is_correct", "null")
        .execute()
    )
    if len(answered_res.data) == 3:
        _maybe_diagnose(student_id, session_id, answered_res.data, service)

    return AnswerSubmitResponse(ok=True)


def _maybe_diagnose(student_id: str, session_id: str, answered: list[dict], service) -> None:
    """첫 세션이면 진단 에이전트를 실행한다 (세션은 completed로 마킹하지 않음 — 토의 후 end API가 처리)."""
    completed_res = (
        service.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .execute()
    )
    if (completed_res.count or 0) > 0:
        return  # 이미 완료된 세션이 있으면 진단 불필요

    try:
        result = diagnose_student([
            {"question_type": r["question_type"], "is_correct": r["is_correct"]}
            for r in answered
        ])
        service.table("students").update({
            "level": result["level"],
            "weak_areas": result["weak_areas"],
        }).eq("id", student_id).execute()
    except RuntimeError:
        logger.warning(
            "Diagnosis failed for student_id=%s session_id=%s", student_id, session_id, exc_info=True
        )


# ──────────────────────────────────────────────
# POST /student/sessions/{session_id}/discussion  (SSE)
# ──────────────────────────────────────────────
@router.post("/sessions/{session_id}/discussion")
async def discussion(
    session_id: str,
    body: DiscussionRequest,
    request: Request,
    student_id: str = Depends(get_current_student),
):
    service = _service_client()

    # 1. 세션 검증
    session_res = (
        service.table("sessions")
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
        service.table("students")
        .select("level, weak_areas")
        .eq("id", student_id)
        .single()
        .execute()
    )
    s = student_res.data or {}

    passage_res = (
        service.table("passages")
        .select("generated_content")
        .eq("id", session_data["passage_id"])
        .single()
        .execute()
    )
    passage_content = ""
    if passage_res.data and passage_res.data.get("generated_content"):
        p_data = json.loads(passage_res.data["generated_content"])
        passage_content = p_data.get("passage", "")

    qr_res = (
        service.table("question_results")
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
        service.table("messages")
        .select("speaker, content, round, role")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    existing_messages = msg_res.data or []

    # 4. 현재 라운드 계산
    current_round = 1
    if existing_messages:
        current_round = max(m["round"] for m in existing_messages)
        if body.content:
            # 학생 발화가 있으면 다음 라운드
            current_round += 1

    async def generate():
        nonlocal existing_messages
        try:
            # 학생 발화 저장
            if body.content and body.content.strip():
                service.table("messages").insert({
                    "session_id": session_id,
                    "role": "user",
                    "speaker": "user",
                    "content": body.content.strip(),
                    "round": current_round - 1,  # 이전 라운드에 속함
                }).execute()
                existing_messages.append({
                    "speaker": "user",
                    "content": body.content.strip(),
                    "round": current_round - 1,
                    "role": "user",
                })

            # 10라운드 초과 시 종료
            if current_round > 10:
                yield _sse_event({"is_final": True})
                return

            if await request.is_disconnected():
                logger.info("Client disconnected before LLM call, session_id=%s", session_id)
                return

            ai_messages_to_save = []

            if current_round == 1:
                # 첫 라운드: 모더레이터 → 또래A
                mod_content = await asyncio.to_thread(call_moderator, context, existing_messages, current_round)
                if await request.is_disconnected():
                    logger.info("Client disconnected after moderator call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "moderator", "content": mod_content, "round": current_round})
                ai_messages_to_save.append(("moderator", mod_content))

                peer_a_content = await asyncio.to_thread(
                    call_peer_a,
                    context,
                    existing_messages + [{"speaker": "moderator", "content": mod_content, "round": current_round}],
                    current_round,
                )
                if await request.is_disconnected():
                    logger.info("Client disconnected after peer_a call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "peer_a", "content": peer_a_content, "round": current_round})
                ai_messages_to_save.append(("peer_a", peer_a_content))
            else:
                # 이후 라운드: 또래B → 모더레이터
                peer_b_content = await asyncio.to_thread(call_peer_b, context, existing_messages, current_round)
                if await request.is_disconnected():
                    logger.info("Client disconnected after peer_b call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "peer_b", "content": peer_b_content, "round": current_round})
                ai_messages_to_save.append(("peer_b", peer_b_content))

                mod_content = await asyncio.to_thread(
                    call_moderator,
                    context,
                    existing_messages + [{"speaker": "peer_b", "content": peer_b_content, "round": current_round}],
                    current_round,
                )
                if await request.is_disconnected():
                    logger.info("Client disconnected after moderator call, session_id=%s", session_id)
                    return
                yield _sse_event({"speaker": "moderator", "content": mod_content, "round": current_round})
                ai_messages_to_save.append(("moderator", mod_content))

            # AI 메시지 DB 저장
            for speaker, content in ai_messages_to_save:
                service.table("messages").insert({
                    "session_id": session_id,
                    "role": "assistant",
                    "speaker": speaker,
                    "content": content,
                    "round": current_round,
                }).execute()

            if current_round >= 10:
                yield _sse_event({"is_final": True})
            else:
                yield _sse_event({"next_speaker": "user", "round": current_round, "is_final": False})
        except Exception:
            logger.exception("Discussion stream failed for session_id=%s round=%s", session_id, current_round)
            yield _sse_event({"error": "DISCUSSION_FAILED", "is_final": False})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────
# POST /student/sessions/{session_id}/end
# ──────────────────────────────────────────────
@router.post("/sessions/{session_id}/end", response_model=SessionEndResponse)
def end_session(
    session_id: str,
    student_id: str = Depends(get_current_student),
):
    service = _service_client()

    # 1. 세션 검증
    session_res = (
        service.table("sessions")
        .select("id, student_id, status, session_date")
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

    # 2. 토의 발화(user) 추출
    msg_res = (
        service.table("messages")
        .select("content")
        .eq("session_id", session_id)
        .eq("speaker", "user")
        .execute()
    )
    user_messages = [m["content"] for m in (msg_res.data or [])]

    # 3. question_results 조회
    qr_res = (
        service.table("question_results")
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    question_results = qr_res.data or []
    all_correct = all(q.get("is_correct") for q in question_results) if question_results else False

    # 4. 피드백 에이전트 호출
    scores_data = analyze_discussion(
        user_messages=user_messages,
        question_results=[
            {"question_type": q["question_type"], "is_correct": q.get("is_correct")}
            for q in question_results
        ],
    )

    # 5. 세션 completed 처리
    now_iso = datetime.now(timezone.utc).isoformat()
    service.table("sessions").update({
        "status": "completed",
        "ended_at": now_iso,
        "all_correct": all_correct,
        "score_reasoning": scores_data["score_reasoning"],
        "score_vocabulary": scores_data["score_vocabulary"],
        "score_context": scores_data["score_context"],
    }).eq("id", session_id).execute()

    # 6. Streak 갱신
    student_res = (
        service.table("students")
        .select("streak_count, streak_last_date, teacher_override_level, level")
        .eq("id", student_id)
        .single()
        .execute()
    )
    student = student_res.data or {}

    session_date = date.fromisoformat(session_data["session_date"])
    yesterday = session_date - timedelta(days=1)
    streak_last = student.get("streak_last_date")

    old_streak = student.get("streak_count") or 0
    if streak_last is None:
        new_streak = 1
    elif date.fromisoformat(streak_last) == yesterday:
        new_streak = old_streak + 1
    elif date.fromisoformat(streak_last) == session_date:
        new_streak = old_streak
    else:
        new_streak = 1

    # 7. level 재조정 (teacher_override_level 없을 때만)
    new_level = student.get("level", 2)
    if not student.get("teacher_override_level"):
        recent_res = (
            service.table("sessions")
            .select("score_reasoning, score_vocabulary, score_context")
            .eq("student_id", student_id)
            .eq("status", "completed")
            .order("ended_at", desc=True)
            .limit(3)
            .execute()
        )
        recent = recent_res.data or []
        # 현재 세션 점수도 포함
        recent_with_current = [
            {
                "score_reasoning": scores_data["score_reasoning"],
                "score_vocabulary": scores_data["score_vocabulary"],
                "score_context": scores_data["score_context"],
            }
        ] + recent
        if len(recent_with_current) >= 3:
            avg = sum(
                (r.get("score_reasoning", 0) + r.get("score_vocabulary", 0) + r.get("score_context", 0)) / 3
                for r in recent_with_current[:3]
            ) / 3
            if avg >= 8.0 and new_level < 3:
                new_level = new_level + 1
            elif avg <= 5.0 and new_level > 1:
                new_level = new_level - 1

    # 8. students UPDATE
    service.table("students").update({
        "streak_count": new_streak,
        "streak_last_date": session_date.isoformat(),
        "level": new_level,
    }).eq("id", student_id).execute()

    # 9. 응답 구성
    qr_out = [
        QuestionResultOut(
            question_index=q["question_index"],
            question_type=q["question_type"],
            question_text=q["question_text"],
            choices=q["choices"],
            correct_index=q["correct_index"],
            selected_index=q.get("selected_index"),
            is_correct=q.get("is_correct"),
        )
        for q in sorted(question_results, key=lambda x: x["question_index"])
    ]

    return SessionEndResponse(
        score_reasoning=scores_data["score_reasoning"],
        score_vocabulary=scores_data["score_vocabulary"],
        score_context=scores_data["score_context"],
        feedback=scores_data["feedback"],
        streak_count=new_streak,
        question_results=qr_out,
    )


# ──────────────────────────────────────────────
# DELETE /student/sessions/{session_id}  — 이탈 처리
# ──────────────────────────────────────────────
@router.delete("/sessions/{session_id}")
def abandon_session(
    session_id: str,
    student_id: str = Depends(get_current_student),
):
    service = _service_client()

    session_res = (
        service.table("sessions")
        .select("id, student_id, status")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not session_res.data:
        return {"ok": True}  # 이미 없으면 무시
    session_data = session_res.data
    if session_data["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    if session_data["status"] == "in_progress":
        service.table("sessions").update({"status": "abandoned"}).eq("id", session_id).execute()

    return {"ok": True}

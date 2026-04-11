import logging
import random
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.agents.diagnosis_agent import diagnose_student
from app.agents.passage_agent import generate_passage_and_questions
from app.core.config import settings
from app.core.constants import DAILY_SESSION_LIMIT
from app.core.deps import get_current_student
from app.core.supabase import supabase
from app.schemas.llm import PassageGeneration
from app.schemas.session import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    PassageOut,
    QuestionOut,
    SessionStartResponse,
    StudentMeResponse,
)

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.get("/me", response_model=StudentMeResponse)
def get_me(student_id: str = Depends(get_current_student)):
    from datetime import timedelta
    today = date.today()
    today_iso = today.isoformat()
    week_ago = (today - timedelta(days=6)).isoformat()

    student_res = (
        supabase.table("students")
        .select("name, level, streak_count, weak_areas, classroom_id")
        .eq("id", student_id)
        .single()
        .execute()
    )
    if not student_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="STUDENT_NOT_FOUND")

    s = student_res.data

    # 오늘 세션 수
    count_res = (
        supabase.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today_iso)
        .neq("status", "abandoned")
        .execute()
    )

    # 최근 3세션 평균 점수
    recent_sessions_res = (
        supabase.table("sessions")
        .select("score_reasoning, score_vocabulary, score_context")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .not_.is_("score_reasoning", "null")
        .order("ended_at", desc=True)
        .limit(3)
        .execute()
    )
    recent_sessions = recent_sessions_res.data or []
    if recent_sessions:
        recent_average_score = round(
            sum(
                (r["score_reasoning"] + r["score_vocabulary"] + r["score_context"]) / 3
                for r in recent_sessions
            ) / len(recent_sessions),
            1,
        )
    else:
        recent_average_score = None

    # 이번 주 완료 세션 수 (오늘 포함 최근 7일)
    weekly_res = (
        supabase.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .gte("session_date", week_ago)
        .lte("session_date", today_iso)
        .execute()
    )

    # 누적 완료 세션 수
    total_res = (
        supabase.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("status", "completed")
        .execute()
    )

    # 학급명
    classroom_name = None
    if s.get("classroom_id"):
        classroom_res = (
            supabase.table("classrooms")
            .select("name")
            .eq("id", s["classroom_id"])
            .maybe_single()
            .execute()
        )
        if classroom_res.data:
            classroom_name = classroom_res.data.get("name")

    return StudentMeResponse(
        name=s["name"],
        level=s["level"],
        streak_count=s["streak_count"] or 0,
        today_session_count=count_res.count or 0,
        classroom_name=classroom_name,
        weak_areas=s.get("weak_areas") or [],
        recent_average_score=recent_average_score,
        weekly_completed_count=weekly_res.count or 0,
        total_completed_count=total_res.count or 0,
    )


@router.get("/sessions/today-count")
def today_session_count(student_id: str = Depends(get_current_student)):
    today = date.today().isoformat()
    res = (
        supabase.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )
    return {"count": res.count or 0}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    student_id: str = Depends(get_current_student),
):
    """
    세션 상태 조회 — 새로고침 복구(P12 Scenario 4) 전용.

    can_resume=True  → SSE 채널이 살아 있음 → 프론트엔드에서 "이어서 토의하기" 제공.
    can_resume=False → 채널 없음(서버 재시작 또는 연결 만료) → "처음부터 시작" 정책.
    """
    from app.core.state import get_channel

    res = (
        supabase.table("sessions")
        .select("id, student_id, status, started_at, ended_at, passage_id")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SESSION_NOT_FOUND")
    data = res.data
    if data["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")

    ch = get_channel(session_id)
    can_resume = ch is not None

    return {
        "session_id": session_id,
        "status": data["status"],
        "can_resume": can_resume,
        "started_at": data.get("started_at"),
        "ended_at": data.get("ended_at"),
    }


@router.post("/sessions", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(student_id: str = Depends(get_current_student)):
    today = date.today().isoformat()

    # 1. 오늘 세션 수 확인
    count_res = (
        supabase.table("sessions")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )
    today_count = count_res.count or 0
    if today_count >= DAILY_SESSION_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="DAILY_LIMIT_REACHED")

    daily_index = today_count + 1

    # 2. 학생 정보 조회
    student_res = (
        supabase.table("students")
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
        supabase.table("sessions")
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
        supabase.table("passages")
        .select("*")
        .eq("difficulty", difficulty)
    )
    if last_passage_id:
        passage_query = passage_query.neq("id", last_passage_id)

    passage_res = passage_query.execute()

    if not passage_res.data:
        # 제외 없이 재시도
        passage_res = (
            supabase.table("passages")
            .select("*")
            .eq("difficulty", difficulty)
            .execute()
        )
    if not passage_res.data:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="NO_PASSAGE_AVAILABLE")

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

        generated_content = PassageGeneration.model_validate(generated)
        content_json = generated_content.model_dump_json()
        supabase.table("passages").update({"generated_content": content_json}).eq("id", passage["id"]).execute()
        passage["generated_content"] = content_json

    try:
        content_data = PassageGeneration.model_validate_json(passage["generated_content"])
    except Exception:
        logger.exception("Invalid generated_content for passage_id=%s", passage["id"])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="INVALID_PASSAGE_CONTENT")

    # 6. session INSERT
    now_iso = datetime.now(timezone.utc).isoformat()
    session_res = (
        supabase.table("sessions")
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
    for i, q in enumerate(content_data.questions):
        supabase.table("question_results").insert({
            "session_id": session_id,
            "question_index": i + 1,
            "question_type": q.type,
            "question_text": q.question,
            "choices": q.choices,
            "correct_index": q.correct_index,
            "selected_index": None,
            "is_correct": None,
        }).execute()

    questions_out = [
        QuestionOut(
            index=i + 1,
            type=q.type,
            text=q.question,
            choices=q.choices,
        )
        for i, q in enumerate(content_data.questions)
    ]
    passage_out = PassageOut(
        title=passage["title"],
        genre=passage["genre"],
        difficulty=passage["difficulty"],
        content=content_data.passage,
    )

    return SessionStartResponse(
        session_id=session_id,
        passage=passage_out,
        questions=questions_out,
    )


@router.post("/sessions/{session_id}/answer", response_model=AnswerSubmitResponse)
def submit_answer(
    session_id: str,
    body: AnswerSubmitRequest,
    student_id: str = Depends(get_current_student),
):
    # 1. 세션 검증
    session_res = (
        supabase.table("sessions")
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
        supabase.table("question_results")
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
    update_payload: dict = {
        "selected_index": body.selected_index,
        "is_correct": is_correct,
    }
    if body.shown_at:
        update_payload["shown_at"] = body.shown_at
    if body.answered_at:
        update_payload["answered_at"] = body.answered_at
    supabase.table("question_results").update(update_payload).eq("id", qr_res.data["id"]).execute()

    # 5. 3문제 모두 답했는지 확인 → 첫 세션이면 진단 실행
    answered_res = (
        supabase.table("question_results")
        .select("is_correct, question_type")
        .eq("session_id", session_id)
        .not_.is_("is_correct", "null")
        .execute()
    )
    if len(answered_res.data) == 3:
        _maybe_diagnose(student_id, session_id, answered_res.data)

    return AnswerSubmitResponse(ok=True, is_correct=is_correct, correct_index=correct_index)


def _maybe_diagnose(student_id: str, session_id: str, answered: list[dict]) -> None:
    """첫 세션이면 진단 에이전트를 실행한다 (세션은 completed로 마킹하지 않음 — 토의 후 end API가 처리)."""
    completed_res = (
        supabase.table("sessions")
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
        supabase.table("students").update({
            "level": result["level"],
            "weak_areas": result["weak_areas"],
        }).eq("id", student_id).execute()
    except RuntimeError:
        logger.warning(
            "Diagnosis failed for student_id=%s session_id=%s", student_id, session_id, exc_info=True
        )


@router.delete("/sessions/{session_id}")
def abandon_session(
    session_id: str,
    student_id: str = Depends(get_current_student),
):
    session_res = (
        supabase.table("sessions")
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
        supabase.table("sessions").update({
            "status": "abandoned",
            "abandoned_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session_id).execute()

    return {"ok": True}


class _AbandonBeaconBody(BaseModel):
    token: str = ""


@router.post("/sessions/{session_id}/abandon", status_code=204)
def abandon_session_beacon(
    session_id: str,
    body: _AbandonBeaconBody,
):
    """navigator.sendBeacon 전용 이탈 처리.

    sendBeacon 은 커스텀 헤더를 지원하지 않으므로
    Authorization 대신 body.token 으로 학생 JWT 를 받는다.
    """
    # 토큰 검증
    try:
        payload = jwt.decode(
            body.token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        if payload.get("type") != "student":
            return Response(status_code=403)
        student_id: str | None = payload.get("sub")
        if not student_id:
            return Response(status_code=403)
    except JWTError:
        return Response(status_code=401)

    session_res = (
        supabase.table("sessions")
        .select("id, student_id, status")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not session_res.data:
        return Response(status_code=204)
    if session_res.data["student_id"] != student_id:
        return Response(status_code=403)
    if session_res.data["status"] == "in_progress":
        supabase.table("sessions").update({
            "status": "abandoned",
            "abandoned_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session_id).execute()

    return Response(status_code=204)

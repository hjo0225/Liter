import logging
import secrets
import string
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_teacher
from app.core.supabase import supabase
from app.schemas.auth import TeacherProfile
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomCreateResponse,
    ClassroomItem,
    DashboardSummary,
    DashboardResponse,
    LevelOverrideRequest,
    ScoreHistoryItem,
    StudentDashboardItem,
    WeakAreaSummaryItem,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])
logger = logging.getLogger(__name__)

MAX_JOIN_CODE_RETRIES = 10


def _generate_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    for attempt in range(MAX_JOIN_CODE_RETRIES):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        try:
            exists = (
                supabase.table("classrooms")
                .select("id")
                .eq("join_code", code)
                .execute()
            )
        except Exception:
            logger.exception("Failed to check join code uniqueness: code=%s", code)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="참여 코드 생성 중 오류가 발생했습니다.",
            )

        if not exists or not exists.data:
            return code

        logger.warning(
            "Join code collision: code=%s retry=%s/%s",
            code,
            attempt + 1,
            MAX_JOIN_CODE_RETRIES,
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="참여 코드 생성에 실패했습니다. 다시 시도해 주세요.",
    )


def _get_owned_classroom(classroom_id: str, teacher_id: str) -> dict:
    classroom_res = (
        supabase.table("classrooms")
        .select("id, name")
        .eq("id", classroom_id)
        .eq("teacher_id", teacher_id)
        .maybe_single()
        .execute()
    )
    if not classroom_res.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    return classroom_res.data


def _get_students_for_dashboard(classroom_id: str) -> list[dict]:
    students_res = (
        supabase.table("students")
        .select("id, name, level, teacher_override_level, weak_areas, streak_count")
        .eq("classroom_id", classroom_id)
        .execute()
    )
    return students_res.data or []


def _get_today_sessions_by_student(student_ids: list[str], today: str) -> dict[str, list[dict]]:
    today_sessions_by_student: dict[str, list[dict]] = defaultdict(list)
    if not student_ids:
        return today_sessions_by_student

    today_sessions_res = (
        supabase.table("sessions")
        .select("student_id, status")
        .in_("student_id", student_ids)
        .eq("session_date", today)
        .neq("status", "abandoned")
        .execute()
    )
    for session in today_sessions_res.data or []:
        today_sessions_by_student[session["student_id"]].append(session)
    return today_sessions_by_student


def _get_completed_counts(student_ids: list[str]) -> dict[str, int]:
    completed_counts: dict[str, int] = defaultdict(int)
    if not student_ids:
        return completed_counts

    completed_counts_res = (
        supabase.table("sessions")
        .select("student_id")
        .in_("student_id", student_ids)
        .eq("status", "completed")
        .execute()
    )
    for session in completed_counts_res.data or []:
        completed_counts[session["student_id"]] += 1
    return completed_counts


def _get_score_sessions_by_student(student_ids: list[str], four_weeks_ago: str) -> dict[str, list[dict]]:
    score_sessions_by_student: dict[str, list[dict]] = defaultdict(list)
    if not student_ids:
        return score_sessions_by_student

    score_sessions_res = (
        supabase.table("sessions")
        .select("student_id, session_date, score_reasoning, score_vocabulary, score_context")
        .in_("student_id", student_ids)
        .eq("status", "completed")
        .gte("session_date", four_weeks_ago)
        .not_.is_("score_reasoning", "null")
        .order("session_date", desc=True)
        .execute()
    )
    for session in score_sessions_res.data or []:
        score_sessions_by_student[session["student_id"]].append(session)
    return score_sessions_by_student


def _calculate_recent_average(sessions: list[dict]) -> float | None:
    recent_sessions = sessions[:3]
    if not recent_sessions:
        return None

    return round(
        sum(
            (
                (session["score_reasoning"] or 0)
                + (session["score_vocabulary"] or 0)
                + (session["score_context"] or 0)
            )
            / 3
            for session in recent_sessions
        )
        / len(recent_sessions),
        1,
    )


def _build_score_history(sessions: list[dict]) -> list[ScoreHistoryItem]:
    date_scores: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        if (
            session["score_reasoning"] is not None
            and session["score_vocabulary"] is not None
            and session["score_context"] is not None
        ):
            avg = (
                session["score_reasoning"] + session["score_vocabulary"] + session["score_context"]
            ) / 3
            date_scores[session["session_date"]].append(avg)

    return [
        ScoreHistoryItem(date=date, avg_score=round(sum(scores) / len(scores), 1))
        for date, scores in sorted(date_scores.items())
    ]


def _build_student_items(
    students: list[dict],
    today_sessions_by_student: dict[str, list[dict]],
    completed_counts: dict[str, int],
    score_sessions_by_student: dict[str, list[dict]],
) -> tuple[list[StudentDashboardItem], dict[str, int]]:
    student_items: list[StudentDashboardItem] = []
    weak_area_counts: dict[str, int] = defaultdict(int)

    for student in students:
        sessions = score_sessions_by_student.get(student["id"], [])
        weak_areas = student.get("weak_areas") or []
        for area in weak_areas:
            weak_area_counts[area] += 1

        today_sessions = today_sessions_by_student.get(student["id"], [])
        recent_avg = _calculate_recent_average(sessions)
        student_items.append(
            StudentDashboardItem(
                id=student["id"],
                name=student["name"],
                level=student["level"],
                teacher_override_level=student.get("teacher_override_level"),
                weak_areas=weak_areas,
                streak_count=student.get("streak_count") or 0,
                recent_avg=recent_avg,
                needs_attention=recent_avg is not None and recent_avg <= 5,
                completed_sessions=completed_counts.get(student["id"], 0),
                today_completed=any(session["status"] == "completed" for session in today_sessions),
                score_history=_build_score_history(sessions),
            )
        )

    return student_items, weak_area_counts


def _build_dashboard_summary(
    student_items: list[StudentDashboardItem],
    today_sessions_by_student: dict[str, list[dict]],
) -> DashboardSummary:
    attention_count = sum(1 for student in student_items if student.needs_attention)
    students_with_avg = [student for student in student_items if student.recent_avg is not None]
    average_recent_score = (
        round(
            sum(student.recent_avg or 0 for student in students_with_avg) / len(students_with_avg),
            1,
        )
        if students_with_avg
        else 0.0
    )
    average_streak = (
        round(sum(student.streak_count for student in student_items) / len(student_items), 1)
        if student_items
        else 0.0
    )
    active_today = sum(1 for sessions in today_sessions_by_student.values() if sessions)
    completed_today = sum(
        1
        for sessions in today_sessions_by_student.values()
        if any(session["status"] == "completed" for session in sessions)
    )

    return DashboardSummary(
        total_students=len(student_items),
        active_today=active_today,
        completed_today=completed_today,
        average_recent_score=average_recent_score,
        average_streak=average_streak,
        attention_count=attention_count,
    )


def _build_weak_area_summary(weak_area_counts: dict[str, int]) -> list[WeakAreaSummaryItem]:
    return [
        WeakAreaSummaryItem(area=area, count=count)
        for area, count in sorted(weak_area_counts.items(), key=lambda item: (-item[1], item[0]))
    ]


@router.get("/classrooms", response_model=list[ClassroomItem])
def list_classrooms(current: TeacherProfile = Depends(get_current_teacher)):
    res = (
        supabase.table("classrooms")
        .select("id, name, join_code, students(count)")
        .eq("teacher_id", current.user_id)
        .execute()
    )

    result = []
    for row in res.data:
        student_count = row["students"][0]["count"] if row.get("students") else 0
        result.append(
            ClassroomItem(
                id=row["id"],
                name=row["name"],
                join_code=row["join_code"],
                student_count=student_count,
            )
        )
    return result


@router.post("/classrooms", response_model=ClassroomCreateResponse, status_code=status.HTTP_201_CREATED)
def create_classroom(body: ClassroomCreate, current: TeacherProfile = Depends(get_current_teacher)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="학급 이름을 입력해주세요.")

    join_code = _generate_join_code()

    try:
        res = (
            supabase.table("classrooms")
            .insert({"name": name, "teacher_id": current.user_id, "join_code": join_code})
            .execute()
        )
    except Exception:
        logger.exception(
            "Failed to create classroom: teacher_id=%s join_code=%s",
            current.user_id,
            join_code,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="학급 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )

    row = res.data[0] if res.data else None
    if row is None:
        try:
            created = (
                supabase.table("classrooms")
                .select("id, join_code")
                .eq("teacher_id", current.user_id)
                .eq("join_code", join_code)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception(
                "Failed to fetch created classroom: teacher_id=%s join_code=%s",
                current.user_id,
                join_code,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="학급 생성 후 정보를 확인하지 못했습니다. 새로고침 후 다시 확인해주세요.",
            )
        row = created.data

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="학급은 생성되었지만 응답을 확인하지 못했습니다. 새로고침 후 다시 확인해주세요.",
        )

    return ClassroomCreateResponse(id=row["id"], join_code=row["join_code"])


@router.get("/classrooms/{classroom_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(classroom_id: str, current: TeacherProfile = Depends(get_current_teacher)):
    today = datetime.now().date().isoformat()
    classroom = _get_owned_classroom(classroom_id, current.user_id)
    students = _get_students_for_dashboard(classroom_id)
    student_ids = [student["id"] for student in students]
    four_weeks_ago = (datetime.now() - timedelta(weeks=4)).date().isoformat()
    today_sessions_by_student = _get_today_sessions_by_student(student_ids, today)
    completed_counts = _get_completed_counts(student_ids)
    score_sessions_by_student = _get_score_sessions_by_student(student_ids, four_weeks_ago)
    student_items, weak_area_counts = _build_student_items(
        students,
        today_sessions_by_student,
        completed_counts,
        score_sessions_by_student,
    )

    return DashboardResponse(
        classroom_name=classroom["name"],
        summary=_build_dashboard_summary(student_items, today_sessions_by_student),
        weak_area_summary=_build_weak_area_summary(weak_area_counts),
        students=student_items,
    )


@router.patch("/students/{student_id}/level")
def override_student_level(
    student_id: str,
    body: LevelOverrideRequest,
    current: TeacherProfile = Depends(get_current_teacher),
):
    student_res = (
        supabase.table("students")
        .select("id, classroom_id")
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    if not student_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="STUDENT_NOT_FOUND")

    classroom_res = (
        supabase.table("classrooms")
        .select("id")
        .eq("id", student_res.data["classroom_id"])
        .eq("teacher_id", current.user_id)
        .maybe_single()
        .execute()
    )
    if not classroom_res.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")

    supabase.table("students").update({"teacher_override_level": body.level}).eq("id", student_id).execute()
    return {"ok": True}

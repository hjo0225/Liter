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

    # 소유권 확인
    classroom_res = (
        supabase.table("classrooms")
        .select("id, name")
        .eq("id", classroom_id)
        .eq("teacher_id", current.user_id)
        .maybe_single()
        .execute()
    )
    if not classroom_res.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")

    classroom_name = classroom_res.data["name"]

    # 학생 목록 조회
    students_res = (
        supabase.table("students")
        .select("id, name, level, teacher_override_level, weak_areas, streak_count")
        .eq("classroom_id", classroom_id)
        .execute()
    )
    student_ids = [student["id"] for student in students_res.data]

    four_weeks_ago = (datetime.now() - timedelta(weeks=4)).date().isoformat()
    today_sessions_by_student: dict[str, list[dict]] = defaultdict(list)
    completed_counts: dict[str, int] = defaultdict(int)
    score_sessions_by_student: dict[str, list[dict]] = defaultdict(list)

    if student_ids:
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

        completed_counts_res = (
            supabase.table("sessions")
            .select("student_id")
            .in_("student_id", student_ids)
            .eq("status", "completed")
            .execute()
        )
        for session in completed_counts_res.data or []:
            completed_counts[session["student_id"]] += 1

        # 4주 세션 이력 전체 한 번에 조회 (N+1 방지)
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
        for sess in score_sessions_res.data or []:
            score_sessions_by_student[sess["student_id"]].append(sess)

    student_items: list[StudentDashboardItem] = []
    weak_area_counts: dict[str, int] = defaultdict(int)
    for s in students_res.data:
        sessions = score_sessions_by_student.get(s["id"], [])

        # 최근 3세션 평균
        recent_sessions = sessions[:3]
        if recent_sessions:
            recent_avg = round(
                sum(
                    (
                        (sess["score_reasoning"] or 0)
                        + (sess["score_vocabulary"] or 0)
                        + (sess["score_context"] or 0)
                    )
                    / 3
                    for sess in recent_sessions
                )
                / len(recent_sessions),
                1,
            )
        else:
            recent_avg = None

        # 날짜별 평균 집계 (4주 이력)
        date_scores: dict[str, list[float]] = defaultdict(list)
        for sess in sessions:
            if (
                sess["score_reasoning"] is not None
                and sess["score_vocabulary"] is not None
                and sess["score_context"] is not None
            ):
                avg = (sess["score_reasoning"] + sess["score_vocabulary"] + sess["score_context"]) / 3
                date_scores[sess["session_date"]].append(avg)

        score_history = [
            ScoreHistoryItem(date=d, avg_score=round(sum(v) / len(v), 1))
            for d, v in sorted(date_scores.items())
        ]

        weak_areas = s.get("weak_areas") or []
        for area in weak_areas:
            weak_area_counts[area] += 1

        today_sessions = today_sessions_by_student.get(s["id"], [])

        student_items.append(
            StudentDashboardItem(
                id=s["id"],
                name=s["name"],
                level=s["level"],
                teacher_override_level=s.get("teacher_override_level"),
                weak_areas=weak_areas,
                streak_count=s.get("streak_count") or 0,
                recent_avg=recent_avg,
                needs_attention=recent_avg is not None and recent_avg <= 5,
                completed_sessions=completed_counts.get(s["id"], 0),
                today_completed=any(session["status"] == "completed" for session in today_sessions),
                score_history=score_history,
            )
        )

    attention_count = sum(1 for student in student_items if student.needs_attention)
    students_with_avg = [student for student in student_items if student.recent_avg is not None]
    average_recent_score = round(
        sum(student.recent_avg or 0 for student in students_with_avg) / len(students_with_avg),
        1,
    ) if students_with_avg else 0.0
    average_streak = round(
        sum(student.streak_count for student in student_items) / len(student_items),
        1,
    ) if student_items else 0.0
    active_today = sum(1 for sessions in today_sessions_by_student.values() if sessions)
    completed_today = sum(
        1
        for sessions in today_sessions_by_student.values()
        if any(session["status"] == "completed" for session in sessions)
    )
    weak_area_summary = [
        WeakAreaSummaryItem(area=area, count=count)
        for area, count in sorted(weak_area_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return DashboardResponse(
        classroom_name=classroom_name,
        summary=DashboardSummary(
            total_students=len(student_items),
            active_today=active_today,
            completed_today=completed_today,
            average_recent_score=average_recent_score,
            average_streak=average_streak,
            attention_count=attention_count,
        ),
        weak_area_summary=weak_area_summary,
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

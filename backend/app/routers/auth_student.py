from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.auth import issue_student_token
from app.core.supabase import supabase

router = APIRouter(prefix="/auth/student", tags=["auth-student"])


class StudentJoinRequest(BaseModel):
    name: str
    join_code: str


class StudentJoinResponse(BaseModel):
    student_id: str
    access_token: str

@router.post("/join", response_model=StudentJoinResponse, status_code=status.HTTP_200_OK)
def student_join(body: StudentJoinRequest):
    classroom = (
        supabase.table("classrooms")
        .select("id")
        .eq("join_code", body.join_code.upper())
        .maybe_single()
        .execute()
    )
    if not classroom.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CLASSROOM_NOT_FOUND")

    classroom_id = classroom.data["id"]
    name = body.name.strip()

    existing = (
        supabase.table("students")
        .select("id")
        .eq("classroom_id", classroom_id)
        .eq("name", name)
        .order("created_at")
        .limit(1)
        .execute()
    )

    if existing.data:
        student_id = existing.data[0]["id"]
    else:
        res = (
            supabase.table("students")
            .insert({"classroom_id": classroom_id, "name": name, "level": 2})
            .execute()
        )
        student_id = res.data[0]["id"]

    return StudentJoinResponse(
        student_id=student_id,
        access_token=_issue_student_token(student_id),
    )

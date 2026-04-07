import logging

from fastapi import APIRouter, HTTPException, status

from app.core.supabase import supabase, supabase_anon
from app.schemas.auth import (
    OkResponse,
    TeacherAuthResponse,
    TeacherLoginRequest,
    TeacherSignupRequest,
)

router = APIRouter(prefix="/auth/teacher", tags=["auth-teacher"])
logger = logging.getLogger(__name__)


def _looks_like_duplicate_error(exc: Exception) -> bool:
    err_msg = str(exc).lower()
    duplicate_tokens = ("duplicate", "already", "exists", "unique", "conflict")
    return any(token in err_msg for token in duplicate_tokens)


def _map_signup_error(exc: Exception) -> tuple[int, str]:
    err_msg = str(exc).lower()
    if "already registered" in err_msg or "already exists" in err_msg or "user already registered" in err_msg:
        return status.HTTP_400_BAD_REQUEST, "이미 가입된 이메일입니다."
    if "password should be at least" in err_msg or "weak password" in err_msg:
        return status.HTTP_400_BAD_REQUEST, "비밀번호는 최소 8자 이상이어야 합니다."
    return status.HTTP_400_BAD_REQUEST, "회원가입에 실패했습니다. 잠시 후 다시 시도해 주세요."


def _map_login_error(exc: Exception) -> tuple[int, str]:
    err_msg = str(exc).lower()
    if "invalid login credentials" in err_msg:
        return status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 일치하지 않습니다."
    return status.HTTP_401_UNAUTHORIZED, "로그인에 실패했습니다."


def _get_teacher_by_id(user_id: str):
    return (
        supabase.table("teachers")
        .select("id, email, name")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )



def _build_auth_response(user_id: str, email: str, name: str, session) -> TeacherAuthResponse:
    if session is None or not session.access_token or not session.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인증 세션 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )
    return TeacherAuthResponse(
        user_id=user_id,
        email=email,
        name=name,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=getattr(session, "expires_in", None),
    )


@router.post("/signup", response_model=TeacherAuthResponse, status_code=status.HTTP_201_CREATED)
def teacher_signup(body: TeacherSignupRequest):
    email = body.email.strip().lower()
    name = body.name.strip()
    user_id: str | None = None
    try:
        auth_res = supabase_anon.auth.sign_up(
            {
                "email": email,
                "password": body.password,
                "options": {"data": {"name": name}},
            }
        )
        if auth_res.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="회원가입에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            )
        user_id = auth_res.user.id
        logger.info("Teacher auth signup created user: email=%s user_id=%s", email, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Teacher auth signup failed for %s", email)
        http_status, message = _map_signup_error(e)
        raise HTTPException(status_code=http_status, detail=message)

    try:
        supabase.table("teachers").insert({"id": user_id, "name": name, "email": email}).execute()
    except Exception as e:
        logger.exception("Teacher profile insert failed for %s (user_id=%s)", email, user_id)
        if user_id:
            try:
                supabase.auth.admin.delete_user(user_id)
            except Exception:
                logger.exception("Failed to rollback auth user after teacher insert failure: %s", user_id)
        if _looks_like_duplicate_error(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 가입된 이메일입니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="회원가입에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )

    return _build_auth_response(
        user_id=user_id,
        email=email,
        name=name,
        session=auth_res.session,
    )


@router.post("/login", response_model=TeacherAuthResponse)
def teacher_login(body: TeacherLoginRequest):
    try:
        email = body.email.strip().lower()
        res = supabase_anon.auth.sign_in_with_password({"email": email, "password": body.password})
        if res.user is None or res.session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인에 실패했습니다.")
        teacher = _get_teacher_by_id(res.user.id)
        if not teacher.data:
            logger.error("Teacher profile missing at login: user_id=%s email=%s", res.user.id, email)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="로그인에 실패했습니다.")
        return _build_auth_response(
            user_id=teacher.data["id"],
            email=teacher.data["email"],
            name=teacher.data["name"],
            session=res.session,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Teacher login failed for %s", body.email.strip().lower())
        http_status, message = _map_login_error(e)
        raise HTTPException(status_code=http_status, detail=message)


@router.post("/logout", response_model=OkResponse)
def teacher_logout():
    try:
        supabase_anon.auth.sign_out()
        return OkResponse()
    except Exception as e:
        logger.exception("Teacher logout failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="로그아웃에 실패했습니다.")

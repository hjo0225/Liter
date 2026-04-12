import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.supabase import supabase, supabase_anon
from app.schemas.auth import TeacherProfile

logger = logging.getLogger("uvicorn.error")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/teacher/login")


def get_current_teacher(token: str = Depends(oauth2_scheme)) -> TeacherProfile:
    """Supabase access token 검증 후 teacher 프로필 반환."""
    try:
        user = supabase_anon.auth.get_user(token).user
        if user is None or not user.id:
            raise ValueError("missing sub")
        teacher = (
            supabase.table("teachers")
            .select("id, email, name")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )
        if not teacher.data:
            raise ValueError("teacher profile not found")
        return TeacherProfile(
            user_id=teacher.data["id"],
            email=teacher.data["email"],
            name=teacher.data["name"],
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_student(token: str = Depends(oauth2_scheme)) -> str:
    """커스텀 student JWT 검증 → student_id (sub) 반환."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        if payload.get("type") != "student":
            logger.warning("[AUTH] student token rejected: type=%s", payload.get("type"))
            raise ValueError("not a student token")
        student_id: str | None = payload.get("sub")
        if not student_id:
            raise ValueError("missing sub")
        return student_id
    except JWTError as e:
        logger.warning("[AUTH] student JWT decode failed: %s | secret_set=%s", e, bool(settings.JWT_SECRET))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        logger.warning("[AUTH] student token invalid: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )

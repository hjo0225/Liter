from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.supabase import supabase_anon

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/teacher/login")


def get_current_teacher(token: str = Depends(oauth2_scheme)) -> str:
    """Supabase JWT 검증 → teacher_id (sub) 반환."""
    try:
        user = supabase_anon.auth.get_user(token).user
        if user is None or not user.id:
            raise ValueError("missing sub")
        return user.id
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
            raise ValueError("not a student token")
        student_id: str | None = payload.get("sub")
        if not student_id:
            raise ValueError("missing sub")
        return student_id
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )

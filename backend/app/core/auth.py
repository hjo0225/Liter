from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings
from app.core.constants import STUDENT_TOKEN_EXPIRE_DAYS


def issue_student_token(student_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=STUDENT_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": student_id, "type": "student", "exp": exp},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def decode_student_token(token: str) -> str:
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


__all__ = ["decode_student_token", "issue_student_token", "JWTError"]

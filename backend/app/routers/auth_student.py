from fastapi import APIRouter, HTTPException, status
from supabase import create_client

from app.core.config import settings
from app.schemas.auth import SignInRequest, StudentSignUpRequest, TokenResponse

router = APIRouter(prefix="/auth/student", tags=["auth-student"])


def _supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def student_signup(body: StudentSignUpRequest):
    client = _supabase()
    res = client.auth.sign_up(
        {
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {"name": body.name, "role": "student", "classroom_code": body.classroom_code}
            },
        }
    )
    if res.user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sign-up failed")
    session = res.session
    if session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email confirmation required")
    return TokenResponse(access_token=session.access_token)


@router.post("/signin", response_model=TokenResponse)
def student_signin(body: SignInRequest):
    client = _supabase()
    res = client.auth.sign_in_with_password({"email": body.email, "password": body.password})
    if res.session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=res.session.access_token)

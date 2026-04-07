from pydantic import BaseModel, EmailStr


# --- Teacher Auth ---

class TeacherSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class TeacherVerifyRequest(BaseModel):
    email: EmailStr
    token: str


class TeacherResendRequest(BaseModel):
    email: EmailStr


class TeacherLoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Student Auth ---

class StudentSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    classroom_code: str


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


# --- Responses ---

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TeacherSignUpResponse(BaseModel):
    message: str
    user_id: str


class OkResponse(BaseModel):
    ok: bool = True

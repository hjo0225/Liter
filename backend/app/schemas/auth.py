from pydantic import BaseModel, EmailStr


class TeacherSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class StudentSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    classroom_code: str


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

from pydantic import BaseModel


class ClassroomCreate(BaseModel):
    name: str


class ClassroomResponse(BaseModel):
    id: str
    name: str
    code: str
    teacher_id: str

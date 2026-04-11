from pydantic import BaseModel


class QuestionOut(BaseModel):
    index: int        # 1~3
    type: str         # "info" | "reasoning" | "vocabulary"
    text: str
    choices: list[str]  # 3개


class PassageOut(BaseModel):
    title: str
    genre: str
    difficulty: int
    content: str


class SessionStartResponse(BaseModel):
    session_id: str
    passage: PassageOut
    questions: list[QuestionOut]


class AnswerSubmitRequest(BaseModel):
    question_index: int        # 1~3
    selected_index: int        # 0~2
    shown_at: str | None = None    # 클라이언트 측정 - 문제 노출 시각 (ISO 8601)
    answered_at: str | None = None # 클라이언트 측정 - 선택 완료 시각 (ISO 8601)


class AnswerSubmitResponse(BaseModel):
    ok: bool = True
    is_correct: bool
    correct_index: int


class DiscussionRequest(BaseModel):
    content: str = ""


class QuestionResultOut(BaseModel):
    question_index: int
    question_type: str
    question_text: str
    choices: list[str]
    correct_index: int
    selected_index: int | None
    is_correct: bool | None


class SessionEndResponse(BaseModel):
    score_reasoning: float
    score_vocabulary: float
    score_context: float
    feedback: str
    streak_count: int
    question_results: list[QuestionResultOut]


class StudentMeResponse(BaseModel):
    name: str
    level: int
    streak_count: int
    today_session_count: int
    classroom_name: str | None = None
    weak_areas: list[str] = []
    recent_average_score: float | None = None
    weekly_completed_count: int = 0
    total_completed_count: int = 0

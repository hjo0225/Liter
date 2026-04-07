from pydantic import BaseModel


class ClassroomCreate(BaseModel):
    name: str


class ClassroomCreateResponse(BaseModel):
    id: str
    join_code: str


class ClassroomItem(BaseModel):
    id: str
    name: str
    join_code: str
    student_count: int


class ScoreHistoryItem(BaseModel):
    date: str
    avg_score: float


class StudentDashboardItem(BaseModel):
    id: str
    name: str
    level: int
    teacher_override_level: int | None
    weak_areas: list[str]
    streak_count: int
    recent_avg: float | None
    needs_attention: bool
    completed_sessions: int
    today_completed: bool
    score_history: list[ScoreHistoryItem]


class LevelOverrideRequest(BaseModel):
    level: int | None


class DashboardSummary(BaseModel):
    total_students: int
    active_today: int
    completed_today: int
    average_recent_score: float
    average_streak: float
    attention_count: int


class WeakAreaSummaryItem(BaseModel):
    area: str
    count: int


class DashboardResponse(BaseModel):
    classroom_name: str
    summary: DashboardSummary
    weak_area_summary: list[WeakAreaSummaryItem]
    students: list[StudentDashboardItem]

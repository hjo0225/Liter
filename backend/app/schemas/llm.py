from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


Score = Annotated[float, Field(ge=0.0, le=10.0)]


class PassageQuestion(BaseModel):
    type: Literal["info", "reasoning", "vocabulary"]
    question: str
    choices: list[str] = Field(min_length=3, max_length=3)
    correct_index: Literal[0, 1, 2]

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be empty")
        return value

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: list[str]) -> list[str]:
        cleaned = [choice.strip() for choice in value]
        if any(not choice for choice in cleaned):
            raise ValueError("choices must not be empty")
        return cleaned


class PassageGeneration(BaseModel):
    passage: str
    questions: list[PassageQuestion] = Field(min_length=3, max_length=3)

    @field_validator("passage")
    @classmethod
    def validate_passage(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("passage must not be empty")
        return value

    @field_validator("questions")
    @classmethod
    def validate_question_order(cls, value: list[PassageQuestion]) -> list[PassageQuestion]:
        expected_order = ["info", "reasoning", "vocabulary"]
        actual_order = [question.type for question in value]
        if actual_order != expected_order:
            raise ValueError(f"questions must follow order {expected_order}")
        return value


class DiagnosisResult(BaseModel):
    level: Literal[1, 2, 3]
    weak_areas: list[Literal["info", "reasoning", "vocabulary"]]


class DiscussionMessage(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty")
        return value


class DiscussionAnalysis(BaseModel):
    score_reasoning: Score
    score_vocabulary: Score
    score_context: Score
    feedback: str

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("feedback must not be empty")
        return value

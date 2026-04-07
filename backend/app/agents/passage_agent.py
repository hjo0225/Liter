from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

_DIFFICULTY_LABEL = {
    1: "하 (초3~4 어휘, 문장 평균 15자 이하, 단순 나열 구조)",
    2: "중 (초5~6 어휘, 문장 평균 15~25자, 원인-결과 구조)",
    3: "상 (중1 수준 어휘, 문장 평균 25자 이상, 비교·대조·주장 구조)",
}

_SYSTEM_PROMPT = """당신은 초등학생 문해력 교육 전문가입니다.
아래 조건에 맞는 지문과 객관식 3문제를 생성하세요.

규칙:
- 지문은 250~400자 사이로 작성하세요.
- 문제는 반드시 info(사실 확인) → reasoning(추론) → vocabulary(어휘) 순서로 3개 작성하세요.
- 선택지는 각 문제마다 정확히 3개이어야 합니다.
- correct_index는 0, 1, 2 중 하나입니다.
"""

MAX_ATTEMPTS = 3


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


def generate_passage_and_questions(
    difficulty: int,
    genre: str,
    topic: str,
    structure_prompt: str,
) -> dict:
    """지문과 객관식 3문제를 생성한다.

    Returns:
        {
            "passage": str,
            "questions": [
                {"type": "info"|"reasoning"|"vocabulary",
                 "question": str,
                 "choices": [str, str, str],
                 "correct_index": int},
                ...  # exactly 3
            ]
        }

    Raises:
        RuntimeError("GENERATION_FAILED") after MAX_ATTEMPTS attempts.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_message = (
        f"난이도: {_DIFFICULTY_LABEL[difficulty]}\n"
        f"장르: {genre}\n"
        f"주제: {topic}\n"
        f"구조 지침: {structure_prompt}\n\n"
        "위 조건에 맞는 지문과 3문제를 JSON으로 생성해주세요."
    )

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                response_format=PassageGeneration,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.8,
                max_tokens=1200,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("empty structured output")
            return parsed.model_dump()
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError("GENERATION_FAILED") from last_error

from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiagnosisResult

_SYSTEM_PROMPT = """당신은 초등학생 문해력 진단 전문가입니다.
학생의 첫 번째 세션 결과를 분석해 수준과 약점을 반환하세요.

level 판정 기준:
- 3문제 모두 정답: level 3
- 2문제 정답: level 2
- 1문제 이하 정답: level 1

weak_areas: 틀린 문제의 type 값 배열 (info, reasoning, vocabulary 중)

"""

MAX_ATTEMPTS = 3


def diagnose_student(question_results: list[dict]) -> dict:
    """첫 세션 결과로 학생 수준과 약점을 진단한다.

    Args:
        question_results: [{"question_type": str, "is_correct": bool}, ...]

    Returns:
        {"level": 1|2|3, "weak_areas": ["info"|"reasoning"|"vocabulary", ...]}

    Raises:
        RuntimeError("DIAGNOSIS_FAILED") after MAX_ATTEMPTS attempts.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    results_text = "\n".join(
        f"- 문제 {i + 1} ({r['question_type']}): {'정답' if r['is_correct'] else '오답'}"
        for i, r in enumerate(question_results)
    )
    user_message = f"학생 결과:\n{results_text}\n\n위 결과를 바탕으로 level과 weak_areas를 JSON으로 반환하세요."

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                response_format=DiagnosisResult,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,
                max_tokens=100,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("empty structured output")
            return parsed.model_dump()
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError("DIAGNOSIS_FAILED") from last_error

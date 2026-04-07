import logging

from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiscussionAnalysis

logger = logging.getLogger("uvicorn.error")

_SYSTEM_PROMPT = """당신은 초등학생 문해력 토의 평가 전문가입니다.
학생의 토의 발화와 객관식 결과를 분석해 3가지 영역별 점수를 산출하세요.

채점 기준:
- 추론력 (0~10): 객관식 추론 문항 정오답 40% + 토의 중 이유를 들어 답변한 횟수·구체성 60%
  (단순 사실 반복=0점, 자기 언어로 근거 제시=만점)
- 어휘력 (0~10): 객관식 어휘 문항 정오답 60% + 토의 중 지문에 없는 단어 다양성 40%
- 맥락파악 (0~10): 객관식 정보파악 문항 정오답 40% + 앞뒤 문장을 연결해 답변했는지 60%
  (단편적 반응=감점)

피드백은 학생에게 격려하는 2~3문장으로 작성하세요.

"""


def analyze_discussion(
    user_messages: list[str],
    question_results: list[dict],
) -> dict:
    """토의 발화와 객관식 결과로 점수 3종을 산출한다.

    Returns:
        {
            "score_reasoning": float (0~10),
            "score_vocabulary": float (0~10),
            "score_context": float (0~10),
            "feedback": str,
        }
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    qr_lines = []
    for qr in question_results:
        qr_lines.append(
            f"- {qr['question_type']} 유형: {'정답' if qr['is_correct'] else '오답'}"
        )

    user_text = "\n".join(user_messages) if user_messages else "(토의 발화 없음)"

    user_prompt = (
        f"[객관식 결과]\n" + "\n".join(qr_lines) +
        f"\n\n[학생 토의 발화]\n{user_text}\n\n"
        "위 내용을 바탕으로 점수를 산출해 주세요."
    )

    last_error: Exception | None = None
    for _ in range(3):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                response_format=DiscussionAnalysis,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=400,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("empty structured output")
            result = parsed.model_dump()
            # 값 범위 클램핑
            for key in ("score_reasoning", "score_vocabulary", "score_context"):
                result[key] = round(max(0.0, min(10.0, float(result.get(key, 5.0)))), 1)
            return result
        except Exception as e:
            last_error = e
            continue

    # 3회 모두 실패 시 기본값 반환
    logger.error("analyze_discussion failed after 3 attempts, returning defaults", exc_info=last_error)
    return {
        "score_reasoning": 5.0,
        "score_vocabulary": 5.0,
        "score_context": 5.0,
        "feedback": "오늘 토의에 열심히 참여했어요!",
    }

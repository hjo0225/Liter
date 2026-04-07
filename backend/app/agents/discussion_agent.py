from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiscussionMessage

_DIFFICULTY_VOCAB = {1: "초3~4 수준 어휘", 2: "초5~6 수준 어휘", 3: "중1 수준 어휘"}

_MODERATOR_SYSTEM = """당신은 초등학교 문해력 토의 진행자(모더레이터)입니다.
학생 이름은 '지수'이고, 또래 AI 학생 민지와 준서가 함께 참여합니다.

역할 규칙:
- 중립적이고 공정하게 발언 기회를 배분합니다.
- 정답을 직접 말하지 않습니다.
- 한 번에 한 명에게만 발언을 요청합니다.
- 매 라운드 끝에는 반드시 학생(지수)에게 발언을 요청합니다.
- 응답은 2~4문장, 자연스러운 초등학교 교사 말투로 작성하세요.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요.

전략:
- all_correct=true: "왜 ①이 답이고 ②는 아닐까?" 형태의 메타인지 심화 질문
- all_correct=false: 오답 유형(weak_areas)과 관련된 주제를 자연스럽게 유도
- 라운드가 10이면 토의를 마무리하는 멘트를 합니다."""

_PEER_A_SYSTEM = """당신은 민지라는 초등학생입니다. 적극적이고 자신 있는 성격입니다.

역할 규칙:
- 근거를 들어 의견을 제시합니다. (예: "왜냐하면...", "글에서 ...라고 했거든요")
- 틀릴 수도 있지만 자신 있게 말합니다.
- 응답은 2~3문장으로 작성하세요.
- 학생의 추론력과 반론 능력을 자극하는 의견을 냅니다.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요."""

_PEER_B_SYSTEM = """당신은 준서라는 초등학생입니다. 소극적이고 궁금한 게 많은 성격입니다.

역할 규칙:
- 모르면 솔직히 모른다고 합니다.
- 주로 질문 형태로 반응합니다. (예: "그런데...", "혹시...", "왜 그런 거야?")
- 응답은 1~2문장으로 짧게 작성하세요.
- 학생이 설명하는 역할을 맡게 유도합니다.
"""


def _build_context_text(context: dict) -> str:
    lines = [
        f"[지문]\n{context['passage_content']}",
        f"\n[객관식 결과]",
    ]
    for qr in context.get("question_results", []):
        lines.append(
            f"- {qr['question_type']} 유형: {'정답' if qr['is_correct'] else '오답'}"
        )
    lines.append(f"\n전체 정답 여부: {'모두 정답' if context['all_correct'] else '오답 있음'}")
    lines.append(f"학생 수준: {_DIFFICULTY_VOCAB.get(context['student_level'], '중')}")
    if context.get("weak_areas"):
        lines.append(f"취약 영역: {', '.join(context['weak_areas'])}")
    return "\n".join(lines)


def _build_history_text(messages: list[dict]) -> str:
    if not messages:
        return "(대화 없음)"
    speaker_map = {
        "moderator": "모더레이터",
        "peer_a": "민지",
        "peer_b": "준서",
        "user": "지수(학생)",
    }
    return "\n".join(
        f"{speaker_map.get(m['speaker'], m['speaker'])}: {m['content']}"
        for m in messages
    )


def _call_openai(system: str, user_prompt: str) -> str:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        response_format=DiscussionMessage,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=300,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("empty structured output")
    return parsed.content


def call_moderator(context: dict, messages: list[dict], round_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    user_prompt = (
        f"{ctx_text}\n\n[현재 라운드]: {round_num}\n\n[대화 이력]\n{history}\n\n"
        f"모더레이터로서 이번 라운드를 시작하는 발언을 해주세요. "
        f"{'토의를 마무리해 주세요.' if round_num >= 10 else '또래 민지에게 발언을 요청하세요.'}"
    )
    return _call_openai(_MODERATOR_SYSTEM, user_prompt)


def call_peer_a(context: dict, messages: list[dict], round_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(min(context["student_level"] + 1, 3), "중1 수준")
    system = _PEER_A_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 라운드]: {round_num}\n\n[대화 이력]\n{history}\n\n"
        "민지로서 의견을 제시해 주세요."
    )
    return _call_openai(system, user_prompt)


def call_peer_b(context: dict, messages: list[dict], round_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(context["student_level"], "초5~6 수준")
    system = _PEER_B_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 라운드]: {round_num}\n\n[대화 이력]\n{history}\n\n"
        "준서로서 학생(지수)의 발언에 반응해 주세요."
    )
    return _call_openai(system, user_prompt)

from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiscussionMessage

_DIFFICULTY_VOCAB = {1: "초3~4 수준 어휘", 2: "초5~6 수준 어휘", 3: "중1 수준 어휘"}

_MODERATOR_SYSTEM = """당신은 초등학교 문해력 수업을 진행하는 선생님입니다. 토의 진행자(모더레이터) 역할을 맡고 있습니다.
학생 이름은 '지수'이고, 또래 AI 학생 민지와 준서가 함께 참여합니다.

페르소나 규칙:
- 반드시 선생님 말투로만 말합니다. 항상 존댓말을 사용하세요. (예: "~해볼까요?", "~어떻게 생각하나요?", "~말해볼까요?")
- 절대로 반말을 사용하지 마세요.
- 다정하고 격려하는 선생님의 목소리를 유지하세요.

역할 규칙:
- 지문에서 선정한 주제 3가지를 순서대로 하나씩 토의합니다.
- 중립적이고 공정하게 발언 기회를 배분합니다.
- 정답을 직접 말하지 않습니다.
- 한 번에 한 명에게만 발언을 요청합니다.
- 매 주제 끝에는 반드시 학생(지수)에게 발언을 요청합니다.
- 응답은 2~4문장으로 작성하세요.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요.

전략:
- all_correct=true: "왜 ①이 답이고 ②는 아닐까?" 형태의 메타인지 심화 질문
- all_correct=false: 오답 유형(weak_areas)과 관련된 주제를 자연스럽게 유도
- 주제 1: 지문의 핵심 내용이나 중심 생각에 대해 토의를 시작합니다.
- 주제 2: 지문의 세부 내용이나 어휘, 표현에 대해 심화 토의를 합니다.
- 주제 3: 지문과 학생의 실생활을 연결하는 주제로 마무리 토의를 하고, 토의를 마무리합니다."""

_PEER_A_SYSTEM = """당신은 민지라는 초등학생입니다. 적극적이고 자신 있는 성격입니다.

페르소나 규칙:
- 반드시 친구들에게 반말을 사용하세요. (예: "나는 ~라고 생각해", "~거든", "~잖아", "~야")
- 선생님(모더레이터)에게는 존댓말을 사용하세요.
- 절대로 친구(지수, 준서)에게 높임말을 쓰지 마세요.

역할 규칙:
- 근거를 들어 의견을 제시합니다. (예: "왜냐하면...", "글에서 ...라고 했거든")
- 틀릴 수도 있지만 자신 있게 말합니다.
- 응답은 2~3문장으로 작성하세요.
- 학생의 추론력과 반론 능력을 자극하는 의견을 냅니다.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요."""

_PEER_B_SYSTEM = """당신은 준서라는 초등학생입니다. 소극적이고 궁금한 게 많은 성격입니다.

페르소나 규칙:
- 반드시 친구들에게 반말을 사용하세요. (예: "나는 잘 모르겠어", "그런데 왜 그런 거야?", "혹시 ~야?")
- 선생님(모더레이터)에게는 존댓말을 사용하세요.
- 절대로 친구(지수, 민지)에게 높임말을 쓰지 마세요.

역할 규칙:
- 모르면 솔직히 모른다고 합니다.
- 주로 질문 형태로 반응합니다. (예: "그런데...", "혹시...", "왜 그런 거야?")
- 응답은 1~2문장으로 짧게 작성하세요.
- 학생이 설명하는 역할을 맡게 유도합니다.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요."""


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
        "moderator": "선생님(모더레이터)",
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


def call_moderator(context: dict, messages: list[dict], topic_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)

    if topic_num == 1:
        instruction = "지문에서 주제 1가지를 선정하여 첫 번째 토의 주제를 소개하고 민지에게 먼저 의견을 물어보세요."
    elif topic_num == 2:
        instruction = "첫 번째 주제 토의를 마무리하고 두 번째 주제로 자연스럽게 넘어가세요. 민지에게 먼저 의견을 물어보세요."
    elif topic_num >= 3:
        instruction = "두 번째 주제 토의를 마무리하고 세 번째 마지막 주제를 소개하세요. 이번이 마지막 주제임을 알려주고 민지에게 의견을 물어보세요. 세 번째 주제 토의 후에는 전체 토의를 마무리하는 멘트를 해주세요."
    else:
        instruction = "민지에게 발언을 요청하세요."

    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제 (총 3개 주제)\n\n[대화 이력]\n{history}\n\n"
        f"선생님으로서 {instruction}"
    )
    return _call_openai(_MODERATOR_SYSTEM, user_prompt)


def call_peer_a(context: dict, messages: list[dict], topic_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(min(context["student_level"] + 1, 3), "중1 수준")
    system = _PEER_A_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}\n\n"
        "민지로서 친구들에게 반말로 의견을 제시해 주세요."
    )
    return _call_openai(system, user_prompt)


def call_peer_b(context: dict, messages: list[dict], topic_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(context["student_level"], "초5~6 수준")
    system = _PEER_B_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}\n\n"
        "준서로서 친구들에게 반말로 학생(지수)의 발언에 반응해 주세요."
    )
    return _call_openai(system, user_prompt)

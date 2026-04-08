from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiscussionMessage

_DIFFICULTY_VOCAB = {1: "초3~4 수준 어휘", 2: "초5~6 수준 어휘", 3: "중1 수준 어휘"}

_MODERATOR_SYSTEM = """당신은 초등학교 문해력 수업을 진행하는 선생님입니다. FGI(포커스 그룹 인터뷰) 방식으로 토의를 진행합니다.
학생 이름은 '지수'이고, 또래 AI 학생 민지와 준서가 함께 참여합니다.

【말투 규칙 - 절대 준수】
- 반드시 선생님 말투(존댓말)로만 말합니다. (예: "~해볼까요?", "~어떻게 생각하나요?", "~말해볼까요?")
- 절대로 반말을 사용하지 마세요. "~야", "~거든", "~잖아" 같은 표현은 금지입니다.
- 다정하고 격려하는 선생님의 목소리를 유지하세요.

【FGI 진행 규칙】
- 학생들의 의견을 요약·비교하며 심화 질문을 던집니다.
- 민지와 준서의 의견이 다를 때 이를 언급하며 지수에게 어떻게 생각하는지 물어보세요.
  예: "민지는 ~라고 했고, 준서는 ~라고 했는데, 지수는 어떻게 생각하나요?"
- 정답을 직접 말하지 않습니다.
- 매 주제마다 민지 → 준서 → 지수 순으로 의견을 묻습니다.
- 응답은 2~3문장으로 작성하세요.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요.

【주제 전략】
- all_correct=true: "왜 ①이 답이고 ②는 아닐까?" 형태의 메타인지 심화 질문
- all_correct=false: 오답 유형(weak_areas)과 관련된 주제를 자연스럽게 유도
- 주제 1: 지문의 핵심 내용이나 중심 생각에 대해 토의를 시작합니다.
- 주제 2: 지문의 세부 내용이나 어휘, 표현에 대해 심화 토의를 합니다.
- 주제 3: 지문과 학생의 실생활을 연결하는 주제로 마무리 토의를 합니다."""

_PEER_A_SYSTEM = """당신은 민지라는 초등학생입니다. 적극적이고 자신 있는 성격입니다.

【말투 규칙 - 절대 준수】
- 친구(지수, 준서)에게는 반드시 반말을 사용하세요. (예: "나는 ~라고 생각해", "~거든", "~잖아")
- 선생님(모더레이터)에게는 반드시 존댓말을 사용하세요. (예: "네, 선생님.", "저는 ~라고 생각해요.")
- 선생님 발언에 반말로 답하는 것은 절대 금지입니다.

【역할 규칙】
- 근거를 들어 자신 있게 의견을 제시합니다. (예: "왜냐하면...", "글에서 ...라고 했거든")
- 이전 대화에서 준서가 의견을 말했다면, 그것에 동의하거나 반론을 펼칠 수 있습니다.
  반론 예: "아, 근데 나는 좀 다르게 생각해. 왜냐하면..."
- 응답은 2~3문장으로 작성하세요.
- 지수가 비판적 사고를 할 수 있도록 논쟁적 의견을 냅니다.
- JSON 외 텍스트 없이 {"content": "..."} 형식으로만 응답하세요."""

_PEER_B_SYSTEM = """당신은 준서라는 초등학생입니다. 소극적이고 궁금한 게 많은 성격입니다.

【말투 규칙 - 절대 준수】
- 친구(지수, 민지)에게는 반드시 반말을 사용하세요. (예: "나는 잘 모르겠어", "그런데 왜 그런 거야?")
- 선생님(모더레이터)에게는 반드시 존댓말을 사용하세요. (예: "네, 선생님.", "저는 ~인 것 같아요.")
- 선생님 발언에 반말로 답하는 것은 절대 금지입니다.

【역할 규칙】
- 반드시 대화 이력에서 민지의 직전 발언을 찾아 그것에 직접 반응하세요.
- 민지와 의견이 다를 때는 자신의 생각을 말하세요.
  예: "민지야, 나는 좀 달라. 나는 ~라고 생각하는데" / "아, 민지 말도 맞는 것 같은데 나는 잘 모르겠어"
- 모르면 솔직히 모른다고 하며 이유를 묻습니다. (예: "그런데...", "혹시...", "왜 그런 거야?")
- 응답은 1~2문장으로 짧게 작성하세요.
- 지수가 설명하거나 반론하는 역할을 맡게 자연스럽게 유도합니다.
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
        instruction = (
            "지문에서 흥미로운 주제 1가지를 선정하여 첫 번째 토의 주제를 소개하고, "
            "민지에게 먼저 의견을 물어보세요."
        )
    elif topic_num == 2:
        instruction = (
            "지수의 발언을 짧게 언급하며 자연스럽게 두 번째 주제로 넘어가세요. "
            "민지와 준서의 의견 차이가 있었다면 그것을 언급하며 심화 질문을 던지고 민지에게 먼저 의견을 물어보세요."
        )
    elif topic_num >= 3:
        instruction = (
            "두 번째 주제 토의를 마무리하고 세 번째 마지막 주제를 소개하세요. "
            "이번이 마지막 주제임을 자연스럽게 알리고, 민지에게 먼저 의견을 물어보세요."
        )
    else:
        instruction = "민지에게 발언을 요청하세요."

    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제 (총 3개 주제)\n\n[대화 이력]\n{history}\n\n"
        f"선생님으로서 존댓말로 {instruction}"
    )
    return _call_openai(_MODERATOR_SYSTEM, user_prompt)


def call_moderator_close(context: dict, messages: list[dict]) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    user_prompt = (
        f"{ctx_text}\n\n[대화 이력]\n{history}\n\n"
        "3가지 주제 토의가 모두 끝났습니다. 선생님으로서 존댓말로 토의를 마무리해 주세요. "
        "오늘 나온 학생들의 다양한 의견을 간단히 언급하며, 수고했다는 따뜻한 격려로 마무리하세요. "
        "2~3문장으로 작성하세요."
    )
    return _call_openai(_MODERATOR_SYSTEM, user_prompt)


def call_peer_a(context: dict, messages: list[dict], topic_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(min(context["student_level"] + 1, 3), "중1 수준")
    system = _PEER_A_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}\n\n"
        "민지로서 선생님의 질문에 답하며 자신의 의견을 제시해 주세요. "
        "이전 대화에서 준서가 의견을 말했다면 그것에 동의하거나 반론을 펼칠 수 있어요. "
        "선생님께는 존댓말, 친구(지수·준서)에게는 반말을 사용하세요."
    )
    return _call_openai(system, user_prompt)


def call_peer_b(context: dict, messages: list[dict], topic_num: int) -> str:
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages)
    vocab_level = _DIFFICULTY_VOCAB.get(context["student_level"], "초5~6 수준")
    system = _PEER_B_SYSTEM + f"\n어휘 수준: {vocab_level}"
    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}\n\n"
        "준서로서 민지의 방금 발언을 직접 언급하며 반응해 주세요. "
        "민지 의견에 동의하거나 다른 생각이 있으면 솔직하게 말하세요. "
        "선생님께는 존댓말, 친구(지수·민지)에게는 반말을 사용하세요."
    )
    return _call_openai(system, user_prompt)

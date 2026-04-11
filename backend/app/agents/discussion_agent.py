"""토의 에이전트.

각 캐릭터의 시스템 프롬프트는 backend/prompts/*.md 에서 로드한다.
student_name 등 런타임 변수는 .format() 으로 주입된다.
"""
from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.schemas.llm import DiscussionMessage, DiscussionPlan

logger = logging.getLogger("uvicorn.error")

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_DIFFICULTY_VOCAB = {1: "초3~4 수준 어휘", 2: "초5~6 수준 어휘", 3: "중1 수준 어휘"}


# ────────────────────────────────────────────────────────────────
# 프롬프트 파일 로더
# ────────────────────────────────────────────────────────────────

def _load_prompt(name: str, **kwargs: str) -> str:
    """prompts/{name}.md 를 읽어 kwargs 변수를 치환해 반환."""
    path = _PROMPTS_DIR / f"{name}.md"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("Prompt file not found: %s", path)
        raise
    if kwargs:
        raw = raw.format(**kwargs)
    return raw


# Public alias — discussion.py 등 외부에서 import 가능
load_prompt = _load_prompt


# ────────────────────────────────────────────────────────────────
# 컨텍스트 빌더
# ────────────────────────────────────────────────────────────────

def _build_context_text(context: dict) -> str:
    lines = [
        f"[지문]\n{context['passage_content']}",
        "\n[객관식 결과]",
    ]
    for qr in context.get("question_results", []):
        lines.append(f"- {qr['question_type']} 유형: {'정답' if qr['is_correct'] else '오답'}")
    lines.append(f"\n전체 정답 여부: {'모두 정답' if context['all_correct'] else '오답 있음'}")
    lines.append(f"학생 수준: {_DIFFICULTY_VOCAB.get(context['student_level'], '중')}")
    if context.get("weak_areas"):
        lines.append(f"취약 영역: {', '.join(context['weak_areas'])}")
    return "\n".join(lines)


def _build_history_text(messages: list[dict], student_name: str) -> str:
    if not messages:
        return "(대화 없음)"
    speaker_map = {
        "moderator": "선생님(모더레이터)",
        "peer_a": "민지",
        "peer_b": "준서",
        "user": f"{student_name}(학생)",
    }
    return "\n".join(
        f"{speaker_map.get(m['speaker'], m['speaker'])}: {m['content']}"
        for m in messages
    )


def _last_message_by(messages: list[dict], speaker: str) -> str | None:
    for m in reversed(messages):
        if m.get("speaker") == speaker:
            return m["content"]
    return None


# ────────────────────────────────────────────────────────────────
# Few-shot 예시 (캐릭터별 5쌍 — gpt-4o-mini는 few-shot에 특히 잘 반응)
# ────────────────────────────────────────────────────────────────

def _few_shots_moderator(student_name: str) -> list[dict]:
    """모더레이터 few-shot 5쌍 (user/assistant 페어)."""
    return [
        # 1. 주제 1 오프닝 — 민지에게 첫 질문
        {"role": "user", "content": (
            "[주제 1/3 시작 | 대화 없음 | 지문: 운석은 태양계 형성 당시 생긴 조각, 과학자들이 연구 중]\n"
            "지시: 첫 번째 주제를 소개하고 민지에게 먼저 의견을 물으세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "오늘 지문에서 운석을 연구하면 태양계의 비밀을 알 수 있다고 했는데요, '
            f'이게 왜 중요한지 함께 이야기해볼까요? 민지는 어떻게 생각하나요?"}}'
        )},
        # 2. 주제 1 — 민지·준서 발언 후 학생 차례
        {"role": "user", "content": (
            f"[주제 1/3 | 민지: '태양계 형성 과정을 알 수 있어요' | 준서: '잘 모르겠어요' | {student_name} 차례]\n"
            f"지시: 두 친구 의견을 언급하며 {student_name}에게 물으세요."
        )},
        {"role": "assistant", "content": (
            f'{{"content": "민지는 태양계가 만들어진 과정을 알 수 있다고 했고, 준서는 아직 잘 모르겠다고 했네요. '
            f'{student_name}는 두 친구 중 어느 쪽 생각이 더 와닿나요?"}}'
        )},
        # 3. 주제 2로 전환 — 학생 발언 후 민지에게
        {"role": "user", "content": (
            f"[주제 2/3 시작 | {student_name} 발언 후]\n"
            "지시: 자연스럽게 두 번째 주제로 넘어가며 민지에게 물으세요."
        )},
        {"role": "assistant", "content": (
            f'{{"content": "{student_name}가 좋은 생각을 나눠줬어요! 그럼 이번엔 조금 더 깊이 들어가서, '
            "글에서 '유성'과 '운석'이라는 단어가 어떻게 다르게 쓰였는지 이야기해볼까요? 민지는 어떻게 읽었나요?\"}}"
        )},
        # 4. 주제 2 심화 — 의견 차이 활용
        {"role": "user", "content": (
            "[주제 2/3 | 민지: '생명체 흔적이 중요해요' | 준서: '그냥 돌이랑 다를 게 없어요']\n"
            f"지시: 의견 차이를 언급하며 {student_name}에게 심화 질문을 하세요."
        )},
        {"role": "assistant", "content": (
            f'{{"content": "민지는 생명체 흔적이 중요하다고 했고, 준서는 그냥 돌과 다를 게 없는 것 같다고 했네요. '
            f'{student_name}는 어느 쪽이 더 설득력 있다고 느끼나요?"}}'
        )},
        # 5. 주제 3 — 마지막 주제 소개
        {"role": "user", "content": (
            "[주제 3/3 시작 | 마지막 주제]\n"
            "지시: 마지막 주제임을 자연스럽게 알리고 민지에게 먼저 물으세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "오늘의 마지막 주제예요! 지금까지 운석의 과학적 의미에 대해 이야기했는데, '
            "이런 우주 연구가 우리 일상생활과 어떤 관계가 있을지 생각해볼까요? 민지는 어떻게 생각해요?\"}}"
        )},
    ]


def _few_shots_peer_a(student_name: str) -> list[dict]:
    """민지 few-shot 5쌍."""
    return [
        # 1. 선생님 첫 질문 — 근거 있는 답변
        {"role": "user", "content": (
            '[선생님: "운석 연구가 왜 중요한지 이야기해볼까요? 민지는 어떻게 생각하나요?"]\n'
            "지시: 지문 근거를 들어 자신 있게 의견을 제시하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "네, 선생님. 저는 운석으로 태양계가 어떻게 만들어졌는지 알 수 있다는 게 가장 중요하다고 생각해요. '
            "글에서 '약 46억 년 전 태양계가 만들어질 때 함께 생긴 조각'이라고 했거든요.\"}"
        )},
        # 2. 준서 부분 동의+질문 → 근거 보강
        {"role": "user", "content": (
            '[준서: "맞는 것 같긴 한데, 민지야. 그 46억 년이 진짜라는 건 어떻게 알아?"]\n'
            "지시: 준서의 질문에 직접 반응하며 근거를 보강하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "준서야, 그건 과학자들이 운석 성분을 분석해서 알아내는 거야. '
            "글에서 '과학자들은 운석을 연구해서 지구와 태양계가 어떻게 만들어졌는지 알아내고 있다'고 했잖아.\"}"
        )},
        # 3. 준서 반론 → 맞대응
        {"role": "user", "content": (
            '[준서: "민지야, 나는 좀 달라. 그냥 돌멩이랑 뭐가 달라?"]\n'
            "지시: 준서의 반론에 반박하며 지문 근거를 제시하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "아, 준서야 나는 완전 달라! 이게 46억 년 전 태양계 조각이잖아. '
            "게다가 글에서 '생명체와 관련된 물질이 들어있기도 하다'고 했거든. 그냥 돌이랑은 비교도 안 되지.\"}"
        )},
        # 4. 학생 짧은 답 → 비판적 사고 유발
        {"role": "user", "content": (
            f'[{student_name}(학생): "음… 저는 잘 모르겠어요."]\n'
            "지시: 학생 발언에 반응하며 비판적 사고를 유발하는 의견을 제시하세요."
        )},
        {"role": "assistant", "content": (
            f'{{"content": "{student_name}야, 나는 생명체 흔적 부분이 제일 중요한 것 같아! '
            "만약 그게 사실이면 우주에 우리만 있는 게 아닐 수도 있잖아. 그게 엄청난 발견 아니야?\"}"
        )},
        # 5. 주제 3 — 지문·실생활 연결
        {"role": "user", "content": (
            '[선생님: "이런 우주 연구가 우리 일상과 어떤 관계가 있을지 민지는 어떻게 생각해요?"]\n'
            "지시: 지문과 실생활을 연결하는 의견을 제시하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "네, 선생님. 저는 운석 연구 덕분에 지구가 어떻게 만들어졌는지 알면 '
            "미래 우주 탐험 때 어디를 탐색해야 할지 알 수 있을 것 같아요. 글에서 생명체 흔적이 발견될 수 있다고 했으니까요.\"}"
        )},
    ]


def _few_shots_peer_b(student_name: str) -> list[dict]:
    """준서 few-shot 5쌍."""
    return [
        # 1. 민지 자신감 발언 → 부분 동의+질문
        {"role": "user", "content": (
            '[민지: "운석이 46억 년 된 태양계 조각이라는 게 중요해. 글에서 직접 나왔잖아."]\n'
            "지시: 민지 발언에 반응하며 궁금증을 질문하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "맞는 것 같긴 한데, 민지야. 그 46억 년이 진짜라는 건 어떻게 아는 거야?"}'
        )},
        # 2. 민지 주장 → 반론
        {"role": "user", "content": (
            '[민지: "운석에서 생명체 흔적이 나오면 우주에 우리만 있는 게 아니라는 증거잖아!"]\n'
            "지시: 민지의 주장에 반론을 제시하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "민지야, 나는 좀 달라. 흔적이 있다고 진짜 생명체가 있다는 건 아니잖아. 글에서도 그냥 \'관련된 물질\'이라고만 했거든."}'
        )},
        # 3. 학생 설명 → 연쇄 질문
        {"role": "user", "content": (
            f'[{student_name}(학생): "유성은 하늘에서 타는 거고, 운석은 다 타지 않고 떨어진 거예요."]\n'
            "지시: 학생의 설명에 반응하며 궁금증을 이어가세요."
        )},
        {"role": "assistant", "content": (
            f'{{"content": "{student_name}야, 그렇구나. 그럼 운석이 되려면 엄청 커야 해? 작은 건 다 타버리는 거야?"}}'
        )},
        # 4. 선생님 질문 → 솔직한 모름
        {"role": "user", "content": (
            '[선생님: "운석에서 발견된 물질이 우리에게 어떤 의미가 있을까요? 준서는 어떻게 생각하나요?"]\n'
            "지시: 솔직하게 모른다고 하며 질문을 이어가세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "저는 솔직히 잘 모르겠어요, 선생님. 글에서 생명체 관련 물질이 있다고는 했는데, 그게 실제로 뭘 의미하는지는 어려워서요."}'
        )},
        # 5. 민지 발언 → 새로운 의문 추가
        {"role": "user", "content": (
            '[민지: "글에서 물의 흔적이 있다고 했잖아. 그게 생명체 증거가 될 수 있어."]\n'
            "지시: 민지 발언에 반응하며 새로운 의문을 제기하세요."
        )},
        {"role": "assistant", "content": (
            '{"content": "민지 말 듣고 신기하긴 한데, 그 물이 지금도 있는 건 아니잖아? 흔적만 있으면 생명체가 살았다는 걸 어떻게 확신해?"}'
        )},
    ]


# ────────────────────────────────────────────────────────────────
# OpenAI 호출 헬퍼
# ────────────────────────────────────────────────────────────────

def _call_openai(
    system: str,
    user_prompt: str,
    few_shots: list[dict] | None = None,
) -> str:
    """
    시스템 → few-shot 예시 → 실제 user 메시지 순으로 전달.
    client.beta.chat.completions.parse로 DiscussionMessage 스키마 강제.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    messages: list[dict] = [{"role": "system", "content": system}]
    if few_shots:
        messages.extend(few_shots)
    messages.append({"role": "user", "content": user_prompt})

    completion = client.beta.chat.completions.parse(
        model=settings.AGENT_MODEL,
        response_format=DiscussionMessage,
        messages=messages,
        temperature=0.85,
        max_tokens=300,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("empty structured output")
    return parsed.content


def _call_openai_plan(system: str, user_prompt: str) -> DiscussionPlan:
    """디렉터 전용: DiscussionPlan 구조화 출력."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        response_format=DiscussionPlan,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=400,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("empty director plan output")
    return parsed


# ────────────────────────────────────────────────────────────────
# 디렉터 — 토의 주제 플랜 생성 (세션당 1회)
# ────────────────────────────────────────────────────────────────

def call_director(context: dict) -> DiscussionPlan:
    """지문·학생 데이터를 분석해 3개 토의 주제를 설계한다."""
    student_level = context.get("student_level", 2)
    ctx_text = _build_context_text(context)
    system = _load_prompt("director")
    user_prompt = (
        f"{ctx_text}\n\n"
        "위 지문과 학생 데이터를 바탕으로 3개의 토의 주제를 설계해 주세요. "
        f"학생 수준은 {_DIFFICULTY_VOCAB.get(student_level, '초5~6 수준 어휘')}입니다."
    )
    return _call_openai_plan(system, user_prompt)


# ────────────────────────────────────────────────────────────────
# 모더레이터
# ────────────────────────────────────────────────────────────────

def call_moderator(
    context: dict,
    messages: list[dict],
    topic_num: int,
    plan: DiscussionPlan | None = None,
) -> str:
    student_name = context.get("student_name", "학생")
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages, student_name)
    system = _load_prompt("moderator", student_name=student_name)

    # 주제별 지시 — 디렉터 플랜이 있으면 우선 사용
    if plan:
        topic_text = {1: plan.topic_1, 2: plan.topic_2, 3: plan.topic_3}.get(topic_num, plan.topic_3)
        if topic_num == 1:
            instruction = f"아래 주제로 토의를 시작하고 민지에게 먼저 의견을 물어보세요.\n주제: {topic_text}"
        elif topic_num == 2:
            instruction = (
                f"{student_name}의 발언을 짧게 언급하며 자연스럽게 두 번째 주제로 넘어가세요. "
                f"주제: {topic_text} — 민지에게 먼저 의견을 물어보세요."
            )
        else:
            instruction = (
                f"이번이 마지막 주제임을 자연스럽게 알리고 아래 주제로 넘어가세요. "
                f"주제: {topic_text} — 민지에게 먼저 의견을 물어보세요."
            )
    else:
        # 폴백: 플랜 없을 때 기존 템플릿 사용
        if topic_num == 1:
            instruction = "지문에서 흥미로운 주제 1가지를 선정하여 첫 번째 토의 주제를 소개하고, 민지에게 먼저 의견을 물어보세요."
        elif topic_num == 2:
            instruction = (
                f"{student_name}의 발언을 짧게 언급하며 자연스럽게 두 번째 주제로 넘어가세요. "
                "민지와 준서의 의견 차이가 있었다면 그것을 언급하며 심화 질문을 던지고 민지에게 먼저 의견을 물어보세요."
            )
        else:
            instruction = (
                "두 번째 주제 토의를 마무리하고 세 번째 마지막 주제를 소개하세요. "
                "이번이 마지막 주제임을 자연스럽게 알리고, 민지에게 먼저 의견을 물어보세요."
            )

    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제 (총 3개 주제)\n\n[대화 이력]\n{history}\n\n"
        f"선생님으로서 존댓말로 {instruction}"
    )
    return _call_openai(system, user_prompt, few_shots=_few_shots_moderator(student_name))


def call_moderator_close(context: dict, messages: list[dict]) -> str:
    student_name = context.get("student_name", "학생")
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages, student_name)
    system = _load_prompt("moderator", student_name=student_name)
    user_prompt = (
        f"{ctx_text}\n\n[대화 이력]\n{history}\n\n"
        "3가지 주제 토의가 모두 끝났습니다. 선생님으로서 존댓말로 토의를 마무리해 주세요. "
        "오늘 나온 학생들의 다양한 의견을 간단히 언급하며, 수고했다는 따뜻한 격려로 마무리하세요. "
        "2~3문장으로 작성하세요."
    )
    return _call_openai(system, user_prompt, few_shots=_few_shots_moderator(student_name))


# ────────────────────────────────────────────────────────────────
# 또래 AI — 민지 (peer_a)
# ────────────────────────────────────────────────────────────────

def call_peer_a(context: dict, messages: list[dict], topic_num: int) -> str:
    student_name = context.get("student_name", "학생")
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages, student_name)
    vocab_level = _DIFFICULTY_VOCAB.get(min(context["student_level"] + 1, 3), "중1 수준")
    system = _load_prompt("peer_a", student_name=student_name) + f"\n어휘 수준: {vocab_level}"

    last_peer_b = _last_message_by(messages, "peer_b")
    last_user = _last_message_by(messages, "user")

    reaction_instruction = ""
    if last_peer_b:
        reaction_instruction = (
            f"\n\n[준서의 직전 발언]: \"{last_peer_b}\"\n"
            "위 준서 발언에 반드시 직접 반응하며 시작하세요. "
            "동의한다면 이유를 더해 공감하고, 생각이 다르다면 '아, 나는 좀 다른데' 식으로 반론을 펼치세요."
        )
    elif last_user:
        reaction_instruction = (
            f"\n\n[{student_name}의 직전 발언]: \"{last_user}\"\n"
            f"{student_name}의 발언에 반응하며 시작하세요. 동의하거나 다른 시각을 제시하세요."
        )

    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}"
        f"{reaction_instruction}\n\n"
        f"민지로서 위 지시에 따라 발언하세요. 선생님께는 존댓말, 친구({student_name}·준서)에게는 반말을 사용하세요."
    )
    return _call_openai(system, user_prompt, few_shots=_few_shots_peer_a(student_name))


# ────────────────────────────────────────────────────────────────
# 또래 AI — 준서 (peer_b)
# ────────────────────────────────────────────────────────────────

def call_peer_b(context: dict, messages: list[dict], topic_num: int) -> str:
    student_name = context.get("student_name", "학생")
    ctx_text = _build_context_text(context)
    history = _build_history_text(messages, student_name)
    vocab_level = _DIFFICULTY_VOCAB.get(context["student_level"], "초5~6 수준")
    system = _load_prompt("peer_b", student_name=student_name) + f"\n어휘 수준: {vocab_level}"

    last_peer_a = _last_message_by(messages, "peer_a")
    last_user = _last_message_by(messages, "user")

    if last_peer_a:
        reaction_instruction = (
            f"\n\n[민지의 직전 발언]: \"{last_peer_a}\"\n"
            "위 민지 발언에 반드시 직접 반응하며 시작하세요. "
            "동의한다면 '맞아, 나도~' 식으로, 생각이 다르다면 '민지야, 나는 좀 달라~' 식으로 반론을 펼치세요. "
            "절반 이상의 확률로 다른 관점을 제시하세요."
        )
    elif last_user:
        reaction_instruction = (
            f"\n\n[{student_name}의 직전 발언]: \"{last_user}\"\n"
            f"{student_name}의 발언에 반응하며 시작하세요."
        )
    else:
        reaction_instruction = ""

    user_prompt = (
        f"{ctx_text}\n\n[현재 주제]: {topic_num}번째 주제\n\n[대화 이력]\n{history}"
        f"{reaction_instruction}\n\n"
        f"준서로서 위 지시에 따라 발언하세요. 선생님께는 존댓말, 친구({student_name}·민지)에게는 반말을 사용하세요."
    )
    return _call_openai(system, user_prompt, few_shots=_few_shots_peer_b(student_name))

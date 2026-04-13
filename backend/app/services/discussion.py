"""
Discussion Orchestrator — Fixed Sequence Loop
고정 턴 시퀀스 기반 토의 진행. Director LLM 불필요.

구조:
  _get_round_speakers — 라운드별 발화 순서 (홀수: M→A→B→M, 짝수: M→B→A→M)
  _next_decision    — 고정 시퀀스에서 다음 화자 결정 (LLM 없음)
  _build_instruction— (speaker, step, round) → instruction 문자열
  stream_agent_turn — 에이전트 LLM 호출 → 큐로 이벤트 push
  run_discussion    — 메인 async generator 루프
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError

from app.agents.discussion_agent import (
    call_moderator_close,
    load_prompt,
)
from app.core.config import settings
from app.core.constants import MAX_DISCUSSION_TOPICS
from app.core.llm_logging import alog_llm_call
from app.core.state import get_channel
from app.core.supabase import supabase

_async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

logger = logging.getLogger("uvicorn.error")

# 출력에서 이름 태그 제거용 정규식 (예: "선생님: ", "[민지] ", "준서:")
_SPEAKER_TAG_RE = re.compile(
    r"^\s*(?:\[)?(?:선생님|모더레이터|사회자|민지|준서)(?:\])?\s*[:：]\s*"
)


def _strip_speaker_tag(text: str, student_name: str) -> str:
    """LLM 출력 앞에 붙은 '선생님:', '민지:' 등 이름 태그를 제거."""
    text = _SPEAKER_TAG_RE.sub("", text)
    if student_name:
        text = re.sub(
            rf"^\s*(?:\[)?{re.escape(student_name)}(?:\])?\s*[:：]\s*", "", text
        )
    return text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  고정 턴 시퀀스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 라운드당 4턴: moderator(오프닝) → first_peer → second_peer → moderator(정리+질문)
# 짝수 라운드는 준서(peer_b)가 먼저 발화하여 순서에 변화를 줌
_PEER_NAMES: dict[str, str] = {"peer_a": "민지", "peer_b": "준서"}


def _get_round_speakers(round_num: int) -> list[str]:
    """라운드별 발화 순서. 짝수 라운드는 준서 선발."""
    if round_num % 2 == 0:
        return ["moderator", "peer_b", "peer_a", "moderator"]
    return ["moderator", "peer_a", "peer_b", "moderator"]


@dataclass
class TurnDecision:
    """고정 시퀀스에서 결정된 다음 턴 정보."""
    next_speaker: str   # "moderator" | "peer_a" | "peer_b" | "wait_for_user" | "close"
    intent: str = "summarize"
    target: str | None = None
    reason: str = ""


def _next_decision(state: "DiscussionState") -> TurnDecision:
    """고정 시퀀스 기반 다음 화자 결정. Director LLM 불필요."""
    if state.round > MAX_DISCUSSION_TOPICS:
        return TurnDecision("close", reason="all rounds complete")

    speakers = _get_round_speakers(state.round)
    step = state.round_turn_index
    if step < len(speakers):
        return TurnDecision(
            speakers[step],
            reason=f"round {state.round} step {step}",
        )
    return TurnDecision("wait_for_user", intent="ask_user", reason="student turn")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class TurnRecord:
    speaker: str
    content: str
    round: int
    role: str = "assistant"


@dataclass
class DiscussionState:
    """
    토론 진행 상태. 매 요청마다 DB 메시지 이력에서 재구성된다.

    round            : 현재 라운드 번호 (1~MAX_DISCUSSION_TOPICS). 초과하면 마무리.
    round_turn_index : 라운드 내 AI 턴 위치 (0~3)
                       0=사회자 오프닝, 1=민지, 2=준서, 3=사회자 정리
    demo_mode        : True이면 학생 턴을 건너뛰고 자가 진행.
    """

    session_id: str
    context: dict
    history: list[TurnRecord] = field(default_factory=list)
    round: int = 1
    round_turn_index: int = 0
    is_final: bool = False
    demo_mode: bool = False

    @classmethod
    def from_db_messages(
        cls,
        session_id: str,
        context: dict,
        messages: list[dict],
        demo_mode: bool = False,
    ) -> DiscussionState:
        if not messages:
            return cls(session_id=session_id, context=context, demo_mode=demo_mode)

        history = [
            TurnRecord(
                speaker=m["speaker"],
                content=m["content"],
                round=m["round"],
                role=m.get("role", "assistant"),
            )
            for m in messages
        ]

        max_round = max(t.round for t in history)
        speakers_in_max_round = {t.speaker for t in history if t.round == max_round}

        if "user" in speakers_in_max_round:
            # 학생이 이미 발화했으면 다음 라운드 시작
            return cls(
                session_id=session_id,
                context=context,
                history=history,
                round=max_round + 1,
                round_turn_index=0,
                demo_mode=demo_mode,
            )

        # 이번 라운드에서 AI 발화 수를 세어 turn_index 결정
        # (moderator가 2회 발화하므로 unique speaker 수가 아닌 실제 턴 수 사용)
        ai_turns_in_round = sum(
            1 for t in history
            if t.round == max_round and t.speaker != "user"
        )

        return cls(
            session_id=session_id,
            context=context,
            history=history,
            round=max_round,
            round_turn_index=ai_turns_in_round,
            demo_mode=demo_mode,
        )

    def history_as_dicts(self) -> list[dict]:
        return [
            {"speaker": t.speaker, "content": t.content, "round": t.round, "role": t.role}
            for t in self.history
        ]

    def record_ai_turn(self, speaker: str, content: str) -> None:
        self.history.append(TurnRecord(speaker=speaker, content=content, round=self.round))
        self.round_turn_index += 1

    def advance_round(self) -> None:
        """학생 발화 처리 완료 후(혹은 데모 모드 스킵 후) 다음 라운드로."""
        self.round += 1
        self.round_turn_index = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Instruction 빌더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SENTENCE_LIMIT = "2~3문장으로 자연스럽게 말하세요."


def _opinions_in_round(state: DiscussionState, rnd: int) -> dict[str, str]:
    """특정 라운드에서 각 참여자의 실제 발언 내용을 수집."""
    result: dict[str, str] = {}
    for t in state.history:
        if t.round == rnd and t.speaker in ("peer_a", "peer_b", "user"):
            result[t.speaker] = t.content[:120]
    return result


def _this_round_content(state: DiscussionState, speaker_key: str) -> str:
    """현재 라운드에서 특정 화자의 발언 내용."""
    for t in state.history:
        if t.round == state.round and t.speaker == speaker_key:
            return t.content[:120]
    return ""


def _prev_round_student_input(state: DiscussionState, current_round: int) -> str:
    """이전 라운드에서 학생이 한 발언."""
    prev = current_round - 1
    if prev < 1:
        return ""
    for t in state.history:
        if t.round == prev and t.speaker == "user":
            return t.content[:120]
    return ""


def _build_instruction(
    speaker: str,
    step: int,          # 0~3 (라운드 내 턴 인덱스)
    round_num: int,     # 1~3
    state: DiscussionState,
    student_name: str,
) -> str:
    """(speaker, step, round) → 에이전트에게 전달할 instruction 문자열."""
    speakers = _get_round_speakers(round_num)
    first_peer = speakers[1]
    second_peer = speakers[2]
    first_name = _PEER_NAMES[first_peer]
    second_name = _PEER_NAMES[second_peer]

    # ── Step 0: moderator 오프닝 ───────────────────────────
    if step == 0:
        if round_num == 1:
            return (
                f"자기소개 없이 바로 토의를 시작하세요.\n"
                f"지문의 핵심 내용을 자연스럽게 언급하며 토의 주제를 소개하고, "
                f"{first_name}에게 먼저 의견을 물어보세요.\n"
                f"금지: 민지, 준서, {student_name}의 의견을 절대 미리 말하지 마세요. "
                f"아직 아무도 발언하지 않았습니다. 질문만 하세요.\n"
                f"{_SENTENCE_LIMIT}"
            )
        elif round_num == 2:
            r1 = _opinions_in_round(state, 1)
            parts = []
            for key in [first_peer, second_peer]:
                if key in r1:
                    parts.append(f"{_PEER_NAMES[key]}: \"{r1[key]}\"")
            if "user" in r1:
                parts.append(f"{student_name}: \"{r1['user']}\"")
            r1_text = " / ".join(parts)
            return (
                f"1단계 의견 정리: {r1_text}\n"
                f"위 의견들을 자연스럽게 정리하고 반박 단계를 안내하세요.\n"
                f"다른 생각이 있으면 반박해 보자고 {first_name}에게 먼저 물어보세요.\n"
                f"금지: 1단계에서 실제로 한 말만 인용하세요. 없는 내용을 지어내지 마세요.\n"
                f"{_SENTENCE_LIMIT}"
            )
        else:  # round >= 3
            return (
                f"토의 전체를 돌아보며 결론 단계를 안내하세요.\n"
                f"지금까지 나온 이야기를 한마디로 정리하고, "
                f"각자 결론을 말해 보자고 {first_name}부터 요청하세요.\n"
                f"{_SENTENCE_LIMIT}"
            )

    # ── Step 1: �� 번째 또래 발화 ───���─────────────────────
    if step == 1:
        if round_num == 1:
            return (
                f"선생님이 소개한 주제에 대해 자기 생각을 말하세요.\n"
                f"지문에서 근거를 찾아 자연스럽게 의견을 펼치세요.\n"
                f"{student_name}에게 질문하지 마세요. {_SENTENCE_LIMIT}"
            )
        elif round_num == 2:
            r1 = _opinions_in_round(state, 1)
            parts = []
            for k, v in r1.items():
                name = _PEER_NAMES.get(k, student_name)
                parts.append(f"{name}: \"{v}\"")
            r1_text = " / ".join(parts)
            return (
                f"1단계 의견: {r1_text}\n"
                f"자신과 다른 의견이 있으면 지문 근거로 반박하고, "
                f"같은 의견이면 보충하세요.\n"
                f"{student_name}에게 질문하지 마세요. {_SENTENCE_LIMIT}"
            )
        else:  # round >= 3
            return (
                f"토의를 통해 자신의 생각이 어떻게 정리되었는지 결론을 말하세요.\n"
                f"인상 깊었던 점이나 생각이 바뀐 부분이 있으면 언급하세요.\n"
                f"{_SENTENCE_LIMIT}"
            )

    # ── Step 2: 두 번째 또래 발화 ─────────────────────────
    if step == 2:
        first_said = _this_round_content(state, first_peer)
        prev_student = _prev_round_student_input(state, round_num)

        prev_context = ""
        if prev_student:
            prev_context = (
                f"이전 라운드에서 {student_name}이(가) "
                f"\"{prev_student}\"라고 했습니다.\n"
            )

        if round_num == 1:
            return (
                f"{first_name}의 의견에 자연스럽게 반응하며 자신의 의견을 말하세요.\n"
                f"직전에 {first_name}이(가) \"{first_said}\"라고 했습니다.\n"
                f"{prev_context}"
                f"공감하면 동의하며 추가하고, 다르면 다른 생각을 말하세요.\n"
                f"{student_name}에게 질문하지 마세요. {_SENTENCE_LIMIT}"
            )
        elif round_num == 2:
            return (
                f"{first_name}의 반박에 자연스럽게 반응하세요.\n"
                f"직전에 {first_name}이(가) \"{first_said}\"라고 했습니다.\n"
                f"{prev_context}"
                f"공감이면 동의하고, 다르면 다른 의견을 지문 근거와 함께 말하세요.\n"
                f"{student_name}에게 질문하지 마세요. {_SENTENCE_LIMIT}"
            )
        else:  # round >= 3
            return (
                f"{first_name}의 결론에 반응하며 자신의 결론을 말하세요.\n"
                f"직전에 {first_name}이(가) \"{first_said}\"라고 했습니다.\n"
                f"{prev_context}"
                f"토의를 통해 배운 점이나 생각이 바뀐 부분을 자연스럽게 말하세요.\n"
                f"{_SENTENCE_LIMIT}"
            )

    # ── Step 3: moderator 정리 + 학생에게 질문 ─────────────
    if step == 3:
        first_said = _this_round_content(state, first_peer)
        second_said = _this_round_content(state, second_peer)
        if round_num == 1:
            return (
                f"{first_name}과(와) {second_name}이(가) 방금 말한 내용을 "
                f"있는 그대로 정리하고 {student_name}에게 의견을 물어보세요.\n"
                f"{first_name}이(가) 실제로 한 말: \"{first_said}\"\n"
                f"{second_name}이(가) 실제로 한 말: \"{second_said}\"\n"
                f"금지: 위 실제 발언에 없는 내용을 지어내지 마세요.\n"
                f"{_SENTENCE_LIMIT}"
            )
        elif round_num == 2:
            return (
                f"{first_name}과(와) {second_name}의 반박을 정리하고 "
                f"{student_name}에게 반박할 기회를 주세요.\n"
                f"{first_name}이(가) 실제로 한 말: \"{first_said}\"\n"
                f"{second_name}이(가) 실제로 한 말: \"{second_said}\"\n"
                f"금지: 위 실제 발언에 없는 내용을 지어내지 마세요.\n"
                f"{_SENTENCE_LIMIT}"
            )
        else:  # round >= 3
            return (
                f"{first_name}과(와) {second_name}의 결론을 정리하고 "
                f"{student_name}에게 결론을 물어보세요.\n"
                f"{first_name}이(가) 실제로 한 말: \"{first_said}\"\n"
                f"{second_name}이(가) 실제로 한 말: \"{second_said}\"\n"
                f"금지: 위 실제 발언에 없는 내용을 지어내지 마세요.\n"
                f"{_SENTENCE_LIMIT}"
            )

    # 폴백
    return f"자연스럽게 발언하세요. {_SENTENCE_LIMIT}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Agent Turn Streaming
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_history_messages(state: DiscussionState) -> list[dict]:
    """DiscussionState.history → OpenAI 메시지 형식 변환 (최근 10턴)."""
    speaker_labels = {
        "moderator": "선생님",
        "peer_a": "민지",
        "peer_b": "준서",
        "user": state.context.get("student_name", "학생"),
    }
    result = []
    for t in state.history[-10:]:
        role = "user" if t.speaker == "user" else "assistant"
        label = speaker_labels.get(t.speaker, t.speaker)
        result.append({"role": role, "content": f"{label}: {t.content}"})
    return result


async def stream_agent_turn(
    decision: TurnDecision,
    state: DiscussionState,
    out_queue: asyncio.Queue,  # type: ignore[type-arg]
) -> str:
    """
    캐릭터별 LLM 스트리밍 호출 → turn_start / token / turn_end 이벤트를 큐에 push.

    반환값: 생성된 전체 발화 텍스트.
    """
    speaker = decision.next_speaker
    student_name = state.context.get("student_name", "학생")
    system_prompt = load_prompt(speaker, student_name=student_name)

    # 지문·학생 정보를 시스템 프롬프트에 주입
    passage = state.context.get("passage_content", "")
    if passage:
        system_prompt += f"\n\n[오늘 토의 지문]\n{passage}"
    qr_lines = []
    for qr in state.context.get("question_results", []):
        result_str = "정답" if qr.get("is_correct") else "오답"
        qr_lines.append(f"- {qr.get('question_type', '')} 유형: {result_str}")
    if qr_lines:
        system_prompt += "\n\n[객관식 결과]\n" + "\n".join(qr_lines)

    # ── instruction 생성 ──────────────────────────────────
    instruction = _build_instruction(
        speaker=speaker,
        step=state.round_turn_index,
        round_num=state.round,
        state=state,
        student_name=student_name,
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        *build_history_messages(state),
        {"role": "user", "content": instruction},
    ]

    turn_id = str(uuid.uuid4())
    await out_queue.put({"type": "turn_start", "speaker": speaker, "turn_id": turn_id, "round": state.round})

    full_text = ""
    t0 = time.time()
    seed = random.randint(0, 2 ** 31 - 1)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    # ── rate limit 재시도 (지수 백오프 2회) ─────────────────
    _RATE_LIMIT_RETRIES = 2
    stream = None
    for _attempt in range(_RATE_LIMIT_RETRIES + 1):
        try:
            stream = await _async_client.chat.completions.create(
                model=settings.AGENT_MODEL,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.8,
                max_tokens=200,
                seed=seed,
            )
            break
        except OpenAIRateLimitError:
            if _attempt == _RATE_LIMIT_RETRIES:
                raise
            _delay = 1.0 * (2 ** _attempt)
            logger.warning(
                "rate limit retry %d/%d in %.1fs: session=%s speaker=%s",
                _attempt + 1, _RATE_LIMIT_RETRIES, _delay, state.session_id, speaker,
            )
            await asyncio.sleep(_delay)
    async for chunk in stream:
        if chunk.usage:
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                await out_queue.put({"type": "token", "speaker": speaker, "text": delta, "turn_id": turn_id})

    latency_ms = int((time.time() - t0) * 1000)

    # LLM이 {"content": "..."} JSON 형식으로 출력하면 content 값만 추출
    try:
        parsed = json.loads(full_text.strip())
        display_text = parsed.get("content", full_text) if isinstance(parsed, dict) else full_text
    except (json.JSONDecodeError, ValueError):
        display_text = full_text

    # "선생님:", "민지:" 등 이름 태그가 붙었으면 제거
    display_text = _strip_speaker_tag(display_text, student_name)

    await out_queue.put({"type": "turn_end", "speaker": speaker, "content": display_text, "turn_id": turn_id, "round": state.round})

    _save_message(
        session_id=state.session_id,
        speaker=speaker,
        content=display_text,
        round_num=state.round,
        role="assistant",
        intent=decision.intent,
        target=decision.target,
    )
    await alog_llm_call(
        session_id=state.session_id,
        agent=speaker,
        model=settings.AGENT_MODEL,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        seed=seed,
    )

    return display_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Loop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_discussion(
    session_id: str,
    user_content: str,
    context: dict,
    demo_mode: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    고정 시퀀스 메인 루프. SSE 이벤트 dict를 yield한다.

    라운드당 흐름:
      moderator(오프닝) → first_peer → second_peer → moderator(정리) → wait_for_user
      짝수 라운드는 준서 선발로 순서 변형. × 3라운드 → close
    """
    # ── 1. 학생 발화 저장 ─────────────────────────────────
    if user_content and user_content.strip():
        last_res = (
            supabase.table("messages")
            .select("round")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        user_round = last_res.data[0]["round"] if last_res.data else 1
        _save_message(
            session_id=session_id,
            speaker="user",
            content=user_content.strip(),
            round_num=user_round,
            role="user",
        )

    # ── 2. DB 이력에서 상태 재구성 ─────────────────────────
    msg_res = (
        supabase.table("messages")
        .select("speaker, content, round, role")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    state = DiscussionState.from_db_messages(
        session_id=session_id,
        context=context,
        messages=msg_res.data or [],
        demo_mode=demo_mode,
    )

    # ── 3. 고정 시퀀스 루프 ────────────────────────────────
    out_queue: asyncio.Queue = asyncio.Queue()
    _is_first_turn = True

    while not state.is_final:
        # 첫 턴 제외, 다음 turn_start 전 0.5~1.2s 랜덤 지연 (대화 리듬)
        if not _is_first_turn:
            await asyncio.sleep(0.5 + random.random() * 0.7)
        _is_first_turn = False

        decision = _next_decision(state)

        # ── 학생 대기 ──────────────────────────────────────
        if decision.next_speaker == "wait_for_user":
            if state.demo_mode:
                prev_round = state.round
                state.advance_round()
                yield {"type": "round_change", "from_round": prev_round, "to_round": state.round}
                continue
            yield {"type": "waiting_for_user", "round": state.round}
            return

        # ── 종료: 사회자 마무리 발언 + scores + is_final ────
        elif decision.next_speaker == "close":
            loop = asyncio.get_event_loop()
            t0 = loop.time()
            close_content = await asyncio.to_thread(
                call_moderator_close, context, state.history_as_dicts()
            )
            close_content = _strip_speaker_tag(
                close_content, context.get("student_name", "학생")
            )
            latency_ms = int((loop.time() - t0) * 1000)

            _save_message(
                session_id=session_id,
                speaker="moderator",
                content=close_content,
                round_num=MAX_DISCUSSION_TOPICS,
                role="assistant",
            )
            await alog_llm_call(
                session_id=session_id,
                agent="moderator_close",
                model=settings.AGENT_MODEL,
                latency_ms=latency_ms,
            )

            turn_id = str(uuid.uuid4())
            yield {"type": "turn_end", "speaker": "moderator", "content": close_content,
                   "turn_id": turn_id, "round": MAX_DISCUSSION_TOPICS}

            # 점수 계산 → scores 이벤트
            try:
                from app.agents.feedback_agent import analyze_discussion
                user_msgs = [t.content for t in state.history if t.speaker == "user"]
                qr = [
                    {"question_type": q["question_type"], "is_correct": q.get("is_correct")}
                    for q in context.get("question_results", [])
                ]
                scores_data = await asyncio.to_thread(analyze_discussion, user_msgs, qr)
                yield {"type": "scores", **scores_data}
            except Exception:
                logger.warning("scores 계산 실패: session_id=%s", session_id, exc_info=True)

            yield {"type": "is_final"}
            state.is_final = True
            return

        # ── AI 에이전트 발화 ────────────────────────────────
        else:
            try:
                content = await stream_agent_turn(decision, state, out_queue)
            except OpenAIRateLimitError:
                logger.error("rate limit 재시도 소진: session=%s", session_id)
                yield {"type": "error", "code": "llm_rate_limit",
                       "message": "OpenAI 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."}
                return
            state.record_ai_turn(decision.next_speaker, content)
            while not out_queue.empty():
                yield out_queue.get_nowait()

            # ── 소프트 인터럽트 체크 (턴 사이) ─────────────
            ch = get_channel(session_id)
            if ch is not None and not ch.queue.empty():
                try:
                    item = ch.queue.get_nowait()
                    itext = (item.get("text") or "").strip()
                    if itext:
                        state.history.append(TurnRecord("user", itext, state.round, "user"))
                        yield {"type": "user_input", "text": itext, "round": state.round}
                        # 인터럽트 발생 → 현재 라운드를 학생이 발화한 것으로 처리, 다음 라운드로
                        state.advance_round()
                        logger.debug("소프트 인터럽트 → 라운드 전진: session_id=%s", session_id)
                except asyncio.QueueEmpty:
                    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DB Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _save_message(
    session_id: str,
    speaker: str,
    content: str,
    round_num: int,
    role: str,
    intent: str | None = None,
    target: str | None = None,
    client_ts: str | None = None,
) -> None:
    row: dict = {
        "session_id": session_id,
        "speaker": speaker,
        "content": content,
        "round": round_num,
        "role": role,
        "server_ts": datetime.now(timezone.utc).isoformat(),
    }
    if intent is not None:
        row["intent"] = intent
    if target is not None:
        row["target"] = target
    if client_ts is not None:
        row["client_ts"] = client_ts
    supabase.table("messages").insert(row).execute()

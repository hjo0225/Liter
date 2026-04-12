"""
Discussion Orchestrator — Director Loop
P4 기반 + P3 LLM Director 통합.

구조:
  DiscussionState   — 토론 진행 상태 (라운드, 발화 순서, 이력)
  stream_agent_turn — 에이전트 LLM 호출 → 큐로 이벤트 push
  run_discussion    — 메인 async generator 루프
  Director 결정     — services.director.decide() (AsyncOpenAI, gpt-4o-mini)
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
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
from app.services.director import DirectorDecision, DirectorInput, decide as llm_decide

_async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

logger = logging.getLogger("uvicorn.error")


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

    round            : 현재 토픽 번호 (1~MAX_DISCUSSION_TOPICS). 초과하면 마무리.
    round_turn_index : 라운드 내 위치
                       0=사회자 차례, 1=민지 차례, 2=준서 차례, 3=학생 차례
    demo_mode        : True이면 학생 턴을 건너뛰고 AI 3명이 자가 진행.
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

        # 이번 라운드에서 누가 발화했는지로 turn_index 계산
        turn_index = 0
        if "moderator" in speakers_in_max_round:
            turn_index = max(turn_index, 1)
        if "peer_a" in speakers_in_max_round:
            turn_index = max(turn_index, 2)
        if "peer_b" in speakers_in_max_round:
            turn_index = max(turn_index, 3)

        return cls(
            session_id=session_id,
            context=context,
            history=history,
            round=max_round,
            round_turn_index=turn_index,
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
#  Director Input 빌더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _make_director_input(
    state: DiscussionState,
    interrupted_by_user: bool = False,
    interrupt_text: str = "",
) -> DirectorInput:
    """DiscussionState → DirectorInput 변환."""
    recent = state.history[-5:]
    return DirectorInput(
        session_id=state.session_id,
        round=state.round,
        round_turn_index=state.round_turn_index,
        last_speaker=state.history[-1].speaker if state.history else None,
        recent_speakers=[t.speaker for t in recent],
        recent_summary=[f"{t.speaker}: {t.content[:40]}" for t in recent],
        all_correct=state.context.get("all_correct", False),
        weak_areas=state.context.get("weak_areas", []),
        demo_mode=state.demo_mode,
        interrupted_by_user=interrupted_by_user,
        interrupt_text=interrupt_text,
    )


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
        result.append({"role": role, "content": f"[{label}] {t.content}"})
    return result


async def stream_agent_turn(
    decision: DirectorDecision,
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

    # 지문·학생 정보를 시스템 프롬프트에 주입 (첫 턴부터 context 확보)
    passage = state.context.get("passage_content", "")
    if passage:
        system_prompt += f"\n\n[오늘 토의 지문]\n{passage}"
    qr_lines = []
    for qr in state.context.get("question_results", []):
        result_str = "정답" if qr.get("is_correct") else "오답"
        qr_lines.append(f"- {qr.get('question_type', '')} 유형: {result_str}")
    if qr_lines:
        system_prompt += "\n\n[객관식 결과]\n" + "\n".join(qr_lines)

    # ── 3단계 구조에 맞춘 발화 패턴 생성 ─────────────────────
    CHAR_LIMIT = "공백 포함 50자 이내로 말하세요."
    is_first_turn = not state.history
    round_num = state.round
    speakers_this_round = {t.speaker for t in state.history if t.round == round_num}
    student_has_spoken = any(t.speaker == "user" and t.round == round_num for t in state.history)

    # 직전 발언 인용 (peer 간 대화 연결용)
    last_turn = state.history[-1] if state.history else None
    last_speaker_label = ""
    last_content_short = ""
    if last_turn:
        last_speaker_label = {"moderator": "선생님", "peer_a": "민지", "peer_b": "준서", "user": student_name}.get(last_turn.speaker, last_turn.speaker)
        last_content_short = last_turn.content[:40]

    if is_first_turn and speaker == "moderator":
        instruction = (
            f"자기소개 없이 바로 토의를 시작하세요.\n"
            f"반드시 다음 패턴을 따르세요: \"글에서 [구체적 장면/상황 설명]하는 장면이 나와요. [그 장면에서 인물의 행동/감정에 대한 질문]? 민지부터 말해 볼까요?\"\n"
            f"예시: \"글에서 민수가 지민에게 농구를 하자고 했는데 지민이 화를 내는 장면이 나와요. 지민이 왜 화가 났을까요? 민지부터 말해 볼까요?\"\n"
            f"핵심: 지문 속 구체적인 장면과 상황을 먼저 설명해서 토의 맥락을 잡아 주세요.\n"
            f"{CHAR_LIMIT}"
        )
    elif is_first_turn:
        instruction = f"위 지문을 바탕으로 자신의 의견을 말하세요. {CHAR_LIMIT}"

    elif round_num == 1:  # ── 1단계: 의견 나누기 ──────────────────
        if speaker == "peer_a" and not student_has_spoken:
            instruction = (
                f"선생님이 소개한 주제에 대해 의견을 말하세요.\n"
                f"반드시 다음 패턴을 따르세요: \"저는 [의견]이라고 생각해요. 글에서 '[지문 근거 인용]'이라고 했거든요.\"\n"
                f"예시: \"저는 주인공이 용감했다고 생각해요. 글에서 '두려움을 참고 앞으로 나갔다'라고 했거든요.\"\n"
                f"{student_name}에게 질문하지 마세요. {CHAR_LIMIT}"
            )
        elif speaker == "peer_b" and not student_has_spoken:
            instruction = (
                f"민지의 의견에 반응하며 자신의 의견을 말하세요.\n"
                f"직전에 민지가 \"{last_content_short}\"라고 했습니다.\n"
                f"반드시 다음 패턴을 따르세요: \"민지가 [민지 의견 요약]라고 했는데, 나는 [동의/반대 + 자기 의견]. [궁금한 점 질문]?\"\n"
                f"예시: \"민지가 용감했다고 했는데, 나는 좀 달라. 어쩔 수 없이 간 거 아닐까? 다른 선택이 있었을까?\"\n"
                f"{student_name}에게 질문하지 마세요. {CHAR_LIMIT}"
            )
        elif speaker == "moderator":
            instruction = (
                f"민지·준서 의견을 정리하고 {student_name}에게 의견을 물어보세요.\n"
                f"반드시 다음 패턴을 따르세요: \"민지는 [요약], 준서는 [요약]. {student_name}, [의견을 묻는 질문]?\"\n"
                f"예시: \"민지는 용감했다, 준서는 어쩔 수 없었다고 했네요. {student_name}, 어떻게 생각해요?\"\n"
                f"{CHAR_LIMIT}"
            )
        else:
            instruction = f"자연스럽게 발언하세요. {CHAR_LIMIT}"

    elif round_num == 2:  # ── 2단계: 반박하기 ──────────────────────
        if speaker == "moderator" and "moderator" not in speakers_this_round:
            instruction = (
                f"1단계 의견을 정리하고 반박 단계를 안내하세요.\n"
                f"반드시 다음 패턴을 따르세요: \"[1단계 의견 한 줄 정리]. 이제 서로 반박해 볼까요? {student_name}, 누구 의견에 반박하고 싶어요?\"\n"
                f"예시: \"다양한 의견이 나왔네요. 이제 서로 반박해 볼까요? {student_name}, 민지와 준서 중 누구 의견에 반박하고 싶어요?\"\n"
                f"{CHAR_LIMIT}"
            )
        elif speaker == "peer_a" and not student_has_spoken:
            instruction = (
                f"1단계에서 나온 의견 중 하나를 반박하세요.\n"
                f"직전에 {last_speaker_label}가 \"{last_content_short}\"라고 했습니다.\n"
                f"반드시 다음 패턴을 따르세요: \"[상대 이름]가 [상대 의견]라고 했는데, 나는 반대야. 글에서 '[지문 근거]'라고 했잖아.\"\n"
                f"예시: \"준서가 어쩔 수 없었다고 했는데, 나는 반대야. 글에서 '스스로 결심했다'라고 했잖아.\"\n"
                f"{student_name}에게 질문하지 마세요. {CHAR_LIMIT}"
            )
        elif speaker == "peer_b" and not student_has_spoken:
            instruction = (
                f"민지의 반박에 반응하며 자신의 반박을 하세요.\n"
                f"직전에 민지가 \"{last_content_short}\"라고 했습니다.\n"
                f"반드시 다음 패턴을 따르세요: \"민지가 [반박 요약]라고 했는데... [동의/반대 + 자기 반박]. 근데 [질문]?\"\n"
                f"예시: \"민지가 스스로 결심했다고 했는데... 글쎄, 나는 주변 상황 때문이라고 봐. 근데 왜 그 장면이 나왔을까?\"\n"
                f"{student_name}에게 질문하지 마세요. {CHAR_LIMIT}"
            )
        else:
            instruction = f"자연스럽게 발언하세요. {CHAR_LIMIT}"

    elif round_num >= 3:  # ── 3단계: 결론 내기 ──────────────────────
        if speaker == "moderator" and "moderator" not in speakers_this_round:
            instruction = (
                f"토의를 마무리하며 결론을 안내하세요.\n"
                f"반드시 다음 패턴을 따르세요: \"[토의 과정 한마디 정리]. 이제 각자 결론을 말해 볼까요? 민지부터 해 볼까요?\"\n"
                f"예시: \"다양한 의견과 반박이 오갔네요. 이제 각자 결론을 말해 볼까요? 민지부터 해 볼까요?\"\n"
                f"{CHAR_LIMIT}"
            )
        elif speaker == "peer_a":
            instruction = (
                f"오늘 토의에서 내린 결론을 말하세요.\n"
                f"반드시 다음 패턴을 따르세요: \"나는 결국 [최종 결론]이라고 생각해. [토의에서 바뀌거나 확신하게 된 점].\"\n"
                f"예시: \"나는 결국 주인공이 용감했다고 생각해. 준서 말 듣고 고민했는데, 그래도 스스로 선택한 게 중요한 것 같아.\"\n"
                f"{CHAR_LIMIT}"
            )
        elif speaker == "peer_b":
            instruction = (
                f"민지 결론에 반응하며 자신의 결론을 말하세요.\n"
                f"직전에 민지가 \"{last_content_short}\"라고 했습니다.\n"
                f"반드시 다음 패턴을 따르세요: \"민지가 [결론 요약]라고 했는데, [동의/다른 결론]. [토의에서 배운 점].\"\n"
                f"예시: \"민지가 용감했다고 했는데, 나도 좀 그런 것 같아. 처음엔 달랐는데 이야기하다 보니 생각이 바뀌었어.\"\n"
                f"{CHAR_LIMIT}"
            )
        else:
            instruction = f"자연스럽게 발언하세요. {CHAR_LIMIT}"

    else:
        instruction = f"자연스럽게 발언하세요. {CHAR_LIMIT}"

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

    # ── P12: rate limit 재시도 (지수 백오프 2회) ─────────────
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
                max_tokens=120,
                seed=seed,
            )
            break  # 성공
        except OpenAIRateLimitError:
            if _attempt == _RATE_LIMIT_RETRIES:
                raise  # 재시도 소진 → 호출자에서 llm_rate_limit 처리
            _delay = 1.0 * (2 ** _attempt)  # 1s, 2s
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
    Director Loop 메인 루프. SSE 이벤트 dict를 yield한다.

    흐름:
      1. 학생 발화(user_content)가 있으면 DB에 저장
      2. DB 전체 이력에서 DiscussionState 재구성
      3. Director.decide(state) → 다음 행동 결정
      4. AI 발화 → yield 이벤트 / 학생 대기 → yield + return / 종료 → yield is_final
      5. demo_mode=True 이면 학생 턴 건너뛰고 3라운드 자가 완주
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

    # ── 3. Director Loop ───────────────────────────────────
    out_queue: asyncio.Queue = asyncio.Queue()
    _is_first_turn = True
    pending_interrupt: str | None = None  # P9: 소프트 인터럽트 대기 텍스트

    while not state.is_final:
        # P8: 첫 턴 제외, 다음 turn_start 전 0.5~1.2s 랜덤 지연 (사람 대화 리듬)
        if not _is_first_turn:
            await asyncio.sleep(0.5 + random.random() * 0.7)
        _is_first_turn = False

        decision = await llm_decide(
            _make_director_input(
                state,
                interrupted_by_user=pending_interrupt is not None,
                interrupt_text=pending_interrupt or "",
            )
        )
        pending_interrupt = None  # 소비 완료

        # ── 학생 대기 ──────────────────────────────────────
        if decision.next_speaker == "wait_for_user":
            if state.demo_mode:
                # 데모 모드: 학생 턴 건너뛰고 다음 라운드
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

            # ── P9: 소프트 인터럽트 체크 (턴 사이에만) ─────
            ch = get_channel(session_id)
            if ch is not None and not ch.queue.empty():
                try:
                    item = ch.queue.get_nowait()
                    itext = (item.get("text") or "").strip()
                    if itext:
                        # turns 엔드포인트가 이미 DB 저장함 → 인메모리 상태만 갱신
                        state.history.append(TurnRecord("user", itext, state.round, "user"))
                        yield {"type": "user_input", "text": itext, "round": state.round}
                        pending_interrupt = itext
                        logger.debug("소프트 인터럽트 감지: session_id=%s text=%r", session_id, itext[:40])
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

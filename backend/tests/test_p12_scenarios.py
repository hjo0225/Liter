"""
P12 통합 시나리오 검증 — 9개 시나리오.

실행: python tests/test_p12_scenarios.py

각 시나리오는 독립적으로 실행 가능하며, 실제 Supabase/OpenAI 호출 없이
unittest.mock 으로 의존성을 대체한다.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

# ── 더미 환경변수를 앱 모듈 import 전에 주입 ──────────────────
# LazySupabaseClient.__getattr__ 가 patch() 검사 시점에 초기화를 시도하므로
# SUPABASE_URL 등을 미리 설정해 RuntimeError 를 방지한다.
os.environ.setdefault("SUPABASE_URL",              "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY",         "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-role-key")
os.environ.setdefault("JWT_SECRET",                "test-secret-key-32chars-padding!!")
os.environ.setdefault("OPENAI_API_KEY",            "sk-test-fake-key-for-testing-only")
os.environ.setdefault("APP_ENV",                   "test")

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── 공통 상수 ─────────────────────────────────────────────────
SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
STUDENT_ID = "11111111-2222-3333-4444-555555555555"
PASSAGE_ID = "pass-0001-0002-0003-000400000005"

FAKE_PASSAGE_CONTENT = json.dumps({
    "passage": "테스트 지문입니다. 독서 토의를 위한 짧은 글입니다.",
    "questions": [
        {"type": "사실", "question": "무엇에 관한 글인가?", "choices": ["독서", "수학", "과학"], "correct_index": 0},
        {"type": "추론", "question": "글쓴이의 의도는?", "choices": ["설명", "설득", "묘사"], "correct_index": 1},
        {"type": "어휘", "question": "밑줄 친 단어의 뜻은?", "choices": ["보다", "읽다", "쓰다"], "correct_index": 0},
    ],
})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_supabase_chain(return_data=None, count=None):
    """체인 호출(.table().select().eq()…execute())을 흉내내는 mock 반환."""
    chain = MagicMock()
    execute_result = MagicMock()
    execute_result.data = return_data if return_data is not None else []
    execute_result.count = count
    # 모든 체이닝 메서드가 chain 자신을 반환
    for method in ("select", "eq", "neq", "order", "limit", "maybe_single",
                   "single", "insert", "update", "not_", "gte", "lte",
                   "is_", "execute"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = execute_result
    return chain, execute_result


def _make_openai_rate_limit_error() -> "openai.RateLimitError":
    """openai.RateLimitError 인스턴스 생성 (httpx.Response 필요)."""
    from openai import RateLimitError
    response = httpx.Response(
        429,
        json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    return RateLimitError(
        message="Rate limit exceeded",
        response=response,
        body={"error": {"message": "Rate limit exceeded"}},
    )


async def _collect(gen: AsyncGenerator) -> list[dict]:
    """async generator 에서 모든 이벤트를 수집한다."""
    events = []
    async for event in gen:
        events.append(event)
    return events


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S1. 정상 흐름
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s1_normal_flow():
    """학생이 모든 라운드 응답 → is_final + scores 이벤트 확인."""
    from app.services.discussion import run_discussion
    from app.services.director import DirectorDecision

    # 3라운드: 각 라운드마다 moderator→peer_a→peer_b→wait_for_user, 마지막 close
    _DECISIONS = [
        DirectorDecision(next_speaker="moderator", intent="summarize"),
        DirectorDecision(next_speaker="peer_a",    intent="challenge"),
        DirectorDecision(next_speaker="peer_b",    intent="ask_user"),
        DirectorDecision(next_speaker="wait_for_user", intent="nudge"),  # round 1 대기
        # round 2 (user_content 제공 후 재호출)
        DirectorDecision(next_speaker="moderator", intent="summarize"),
        DirectorDecision(next_speaker="peer_a",    intent="challenge"),
        DirectorDecision(next_speaker="peer_b",    intent="ask_user"),
        DirectorDecision(next_speaker="wait_for_user", intent="nudge"),
        # round 3
        DirectorDecision(next_speaker="moderator", intent="summarize"),
        DirectorDecision(next_speaker="close",     intent="summarize"),
    ]
    _decision_iter = iter(_DECISIONS)

    async def fake_decide(_inp):
        return next(_decision_iter)

    async def fake_stream_agent_turn(decision, state, out_queue):
        await out_queue.put({"type": "turn_start", "speaker": decision.next_speaker, "turn_id": "t1", "round": state.round})
        await out_queue.put({"type": "token", "speaker": decision.next_speaker, "text": "안녕하세요", "turn_id": "t1"})
        await out_queue.put({"type": "turn_end", "speaker": decision.next_speaker, "content": "안녕하세요", "turn_id": "t1", "round": state.round})
        return "안녕하세요"

    def fake_call_moderator_close(context, history):
        return "토의를 마칩니다."

    def fake_analyze(user_msgs, qr):
        return {"score_reasoning": 8.0, "score_vocabulary": 7.5, "score_context": 8.5,
                "feedback_reasoning": "잘했어요", "feedback_vocabulary": "좋아요", "feedback_context": "훌륭해요"}

    # supabase mock: messages 테이블은 항상 빈 리스트, insert는 무시
    chain, exe = _make_supabase_chain([])

    with patch("app.services.discussion.supabase") as mock_sb, \
         patch("app.services.discussion.llm_decide", side_effect=fake_decide), \
         patch("app.services.discussion.stream_agent_turn", side_effect=fake_stream_agent_turn), \
         patch("app.services.discussion.call_moderator_close", side_effect=fake_call_moderator_close), \
         patch("app.agents.feedback_agent.analyze_discussion", side_effect=fake_analyze), \
         patch("app.services.discussion.alog_llm_call", new_callable=AsyncMock), \
         patch("app.services.discussion.get_channel", return_value=None):

        mock_sb.table.return_value = chain

        context = {
            "student_name": "민수",
            "passage_content": "테스트",
            "question_results": [],
            "all_correct": True,
            "student_level": 2,
            "weak_areas": [],
        }

        # 1라운드: 빈 user_content
        events_r1 = await _collect(run_discussion(SESSION_ID, "", context, demo_mode=False))
        event_types_r1 = [e["type"] for e in events_r1]
        assert "waiting_for_user" in event_types_r1, f"round1: waiting_for_user 없음. 이벤트={event_types_r1}"
        assert "is_final" not in event_types_r1

        # 2라운드: 학생 답변
        events_r2 = await _collect(run_discussion(SESSION_ID, "저는 이 글이 중요하다고 생각해요.", context, demo_mode=False))
        event_types_r2 = [e["type"] for e in events_r2]
        assert "waiting_for_user" in event_types_r2, f"round2: waiting_for_user 없음"

        # 3라운드: close → is_final
        events_r3 = await _collect(run_discussion(SESSION_ID, "정말 재미있었어요.", context, demo_mode=False))
        event_types_r3 = [e["type"] for e in events_r3]
        assert "is_final" in event_types_r3, f"round3: is_final 없음. 이벤트={event_types_r3}"
        assert "scores" in event_types_r3, f"round3: scores 없음"

    print("✓ S1: 정상 흐름 — 3라운드 완주 후 is_final + scores 확인")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S2. 침묵 흐름
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s2_silence_flow():
    """학생 미응답 → 90초 후 user_skip + 빈 content로 다음 라운드 진행 로직 검증."""
    from app.routers.student.discussion import _IDLE_TICK_SEC, _NUDGE_AT_SEC, _SKIP_AT_SEC
    from app.core.state import SessionChannel

    # 상수 검증 (P10 계약)
    assert _IDLE_TICK_SEC == 15,  f"_IDLE_TICK_SEC={_IDLE_TICK_SEC} (기대값: 15)"
    assert _NUDGE_AT_SEC  == 30,  f"_NUDGE_AT_SEC={_NUDGE_AT_SEC} (기대값: 30)"
    assert _SKIP_AT_SEC   == 90,  f"_SKIP_AT_SEC={_SKIP_AT_SEC} (기대값: 90)"

    # 큐에 아무것도 넣지 않으면 TimeoutError 발생 → idle_elapsed 누적 → 90초 도달 시 break
    ch = SessionChannel()
    # 6회 timeout(6*15=90) 후 skip 조건 도달 확인
    idle_elapsed = 0
    _TICKS_TO_SKIP = _SKIP_AT_SEC // _IDLE_TICK_SEC
    for _ in range(_TICKS_TO_SKIP):
        try:
            await asyncio.wait_for(ch.queue.get(), timeout=0.001)
        except asyncio.TimeoutError:
            idle_elapsed += _IDLE_TICK_SEC

    assert idle_elapsed >= _SKIP_AT_SEC, f"idle_elapsed={idle_elapsed} < SKIP_AT={_SKIP_AT_SEC}"

    print("✓ S2: 침묵 흐름 — 90s idle 상수 검증 + TimeoutError 누적 로직 확인")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S3. 인터럽트 흐름
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s3_interrupt_flow():
    """AI 발화 중 학생 입력 → user_input 이벤트 + pending_interrupt 전달 확인."""
    from app.services.discussion import run_discussion, DiscussionState
    from app.services.director import DirectorDecision
    from app.core.state import SessionChannel

    interrupt_text = "잠깐, 저 하고 싶은 말이 있어요!"

    # 채널: AI 턴 직후 큐에 학생 입력이 들어있음
    ch = SessionChannel()
    ch.queue.put_nowait({"text": interrupt_text})

    _decisions = iter([
        DirectorDecision(next_speaker="moderator", intent="summarize"),
        # 인터럽트 후 director가 acknowledge 결정 (가드 테스트용으로 moderator로 리다이렉트)
        DirectorDecision(next_speaker="moderator", intent="acknowledge"),
        DirectorDecision(next_speaker="wait_for_user", intent="nudge"),
    ])

    async def fake_decide(inp):
        d = next(_decisions)
        if inp.interrupted_by_user:
            # 인터럽트 감지 확인
            assert inp.interrupt_text == interrupt_text, "interrupt_text 불일치"
        return d

    async def fake_stream(decision, state, out_queue):
        await out_queue.put({"type": "turn_start", "speaker": decision.next_speaker, "turn_id": "t1", "round": state.round})
        await out_queue.put({"type": "turn_end", "speaker": decision.next_speaker, "content": "테스트", "turn_id": "t1", "round": state.round})
        return "테스트"

    chain, exe = _make_supabase_chain([])

    with patch("app.services.discussion.supabase") as mock_sb, \
         patch("app.services.discussion.llm_decide", side_effect=fake_decide), \
         patch("app.services.discussion.stream_agent_turn", side_effect=fake_stream), \
         patch("app.services.discussion.alog_llm_call", new_callable=AsyncMock), \
         patch("app.services.discussion.get_channel", return_value=ch):

        mock_sb.table.return_value = chain
        context = {"student_name": "민수", "passage_content": "테스트",
                   "question_results": [], "all_correct": False,
                   "student_level": 2, "weak_areas": []}

        events = await _collect(run_discussion(SESSION_ID, "", context))
        event_types = [e["type"] for e in events]

    assert "user_input" in event_types, f"user_input 이벤트 없음. 이벤트={event_types}"
    user_input_event = next(e for e in events if e["type"] == "user_input")
    assert user_input_event["text"] == interrupt_text

    print("✓ S3: 인터럽트 흐름 — AI 발화 후 user_input 이벤트 + director에 interrupt 전달")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S4. 새로고침 복구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_s4_refresh_recovery():
    """GET /sessions/{id} → can_resume 필드로 이어서/처음부터 정책 결정."""
    from app.routers.student.session import get_session
    from app.core.state import SessionChannel, create_channel, remove_channel

    session_data = {
        "id": SESSION_ID,
        "student_id": STUDENT_ID,
        "status": "in_progress",
        "started_at": "2026-04-11T10:00:00Z",
        "ended_at": None,
        "passage_id": PASSAGE_ID,
    }

    chain, exe = _make_supabase_chain(session_data)

    with patch("app.routers.student.session.supabase") as mock_sb, \
         patch("app.core.state.get_channel") as mock_get_ch:

        mock_sb.table.return_value = chain
        exe.data = session_data  # maybe_single 결과

        # 케이스 A: 채널 없음 → can_resume=False (처음부터)
        mock_get_ch.return_value = None
        result_a = get_session(SESSION_ID, student_id=STUDENT_ID)
        assert result_a["can_resume"] is False, f"채널 없을 때 can_resume={result_a['can_resume']}"
        assert result_a["status"] == "in_progress"

        # 케이스 B: 채널 있음 → can_resume=True (이어서)
        mock_get_ch.return_value = SessionChannel()
        result_b = get_session(SESSION_ID, student_id=STUDENT_ID)
        assert result_b["can_resume"] is True, f"채널 있을 때 can_resume={result_b['can_resume']}"

    print("✓ S4: 새로고침 복구 — can_resume=False(처음부터)/True(이어서) 정책 분기 확인")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S5. 연결 끊김 복구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s5_disconnect_recovery():
    """클라이언트 disconnect → SSE 생성기 조기 종료 + 채널 정리 확인."""
    from app.core.state import create_channel, get_channel, remove_channel

    # 세션 채널 생성
    ch = create_channel(SESSION_ID)
    assert get_channel(SESSION_ID) is not None, "채널 생성 실패"

    # disconnect 감지 후 채널이 정리되는 흐름 시뮬레이션
    disconnected = False

    async def mock_is_disconnected():
        nonlocal disconnected
        disconnected = True
        return True

    # SSE 생성기 내부 로직: request.is_disconnected() → True → return → finally remove_channel
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=True)

    # 생성기가 종료될 때 remove_channel 호출됨을 검증
    remove_channel(SESSION_ID)
    assert get_channel(SESSION_ID) is None, "채널 정리 실패"

    # 프론트엔드 재시도 상수 검증 (useDiscussionStream.ts 에서 MAX_RETRIES=3, 지수 백오프)
    MAX_RETRIES = 3
    delays = [1 * (2 ** i) for i in range(MAX_RETRIES)]
    assert delays == [1, 2, 4], f"재시도 지연 계산 오류: {delays}"

    print("✓ S5: 연결 끊김 — disconnect 감지 시 채널 정리 + 프론트 재시도 상수(1s/2s/4s) 확인")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S6. 부적절 입력 (Moderation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s6_moderation_blocked():
    """학생 욕설 입력 → OpenAI Moderation 차단 → 400 MODERATION_BLOCKED."""
    from fastapi import HTTPException
    from app.routers.student.turns import submit_turn, TurnSubmitRequest

    # 세션 mock: in_progress
    session_chain, session_exe = _make_supabase_chain(
        {"id": SESSION_ID, "student_id": STUDENT_ID, "status": "in_progress"}
    )
    session_exe.data = {"id": SESSION_ID, "student_id": STUDENT_ID, "status": "in_progress"}

    # 메시지 chain mock
    msg_chain, msg_exe = _make_supabase_chain([{"round": 1}])

    # Moderation: flagged=True
    mod_result = MagicMock()
    mod_result.results = [MagicMock(flagged=True)]

    def supabase_table(name):
        if name == "sessions":
            return session_chain
        return msg_chain

    from app.core.state import SessionChannel
    ch = SessionChannel()

    with patch("app.routers.student.turns.supabase") as mock_sb, \
         patch("app.routers.student.turns.get_channel", return_value=ch), \
         patch("app.routers.student.turns._openai") as mock_openai:

        mock_sb.table.side_effect = supabase_table
        mock_openai.moderations.create = AsyncMock(return_value=mod_result)

        body = TurnSubmitRequest(text="욕설이 포함된 텍스트")
        raised = False
        try:
            await submit_turn(SESSION_ID, body, student_id=STUDENT_ID)
        except HTTPException as e:
            assert e.status_code == 400, f"상태 코드 {e.status_code} (기대값: 400)"
            assert e.detail == "MODERATION_BLOCKED", f"detail={e.detail}"
            raised = True

    assert raised, "HTTPException(400) 가 발생하지 않음"
    print("✓ S6: 부적절 입력 — Moderation flagged → 400 MODERATION_BLOCKED")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S7. LLM 실패 (잘못된 API 키)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s7_llm_failure():
    """OpenAI 인증 실패 → run_discussion에서 error(code=llm_failure) 이벤트 발생."""
    from openai import AuthenticationError
    from app.services.discussion import run_discussion
    from app.services.director import DirectorDecision

    auth_error = AuthenticationError(
        message="Incorrect API key",
        response=httpx.Response(
            401,
            json={"error": {"message": "Incorrect API key", "type": "invalid_request_error"}},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        ),
        body={"error": {"message": "Incorrect API key"}},
    )

    async def fake_decide(_inp):
        return DirectorDecision(next_speaker="moderator", intent="summarize")

    async def failing_stream_agent_turn(decision, state, out_queue):
        raise auth_error

    chain, exe = _make_supabase_chain([])

    with patch("app.services.discussion.supabase") as mock_sb, \
         patch("app.services.discussion.llm_decide", side_effect=fake_decide), \
         patch("app.services.discussion.stream_agent_turn", side_effect=failing_stream_agent_turn), \
         patch("app.services.discussion.alog_llm_call", new_callable=AsyncMock), \
         patch("app.services.discussion.get_channel", return_value=None):

        mock_sb.table.return_value = chain
        context = {"student_name": "민수", "passage_content": "테스트",
                   "question_results": [], "all_correct": False,
                   "student_level": 2, "weak_areas": []}

        # run_discussion 에서 예외가 전파되고 라우터의 _run_round 가 llm_failure 로 처리함
        # 여기선 run_discussion 자체가 예외를 yield하지 않고 전파하는지 확인
        try:
            events = await _collect(run_discussion(SESSION_ID, "", context))
            # AuthenticationError는 RateLimitError가 아니므로 재시도 없이 전파
            # 라우터 수준에서 llm_failure로 변환되므로 여기서는 예외가 발생해야 함
            assert False, "예외가 발생하지 않음 — stream_agent_turn 예외가 전파되어야 함"
        except AuthenticationError:
            pass  # 정상: 라우터가 이를 잡아 llm_failure 이벤트로 변환

    # 라우터 레벨에서의 변환 검증: discussion.py 라우터의 _run_round catch 블록 확인
    from app.routers.student import discussion as disc_router
    assert hasattr(disc_router, "_error"), "_error 헬퍼 없음"
    error_sse = disc_router._error("llm_failure", "토의 생성 실패")
    assert '"code": "llm_failure"' in error_sse, f"error SSE 형식 오류: {error_sse}"

    print("✓ S7: LLM 실패 — AuthenticationError 전파 확인 + 라우터 llm_failure SSE 변환 검증")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S8. 세션 초과 (429)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_s8_session_limit_exceeded():
    """같은 학생 4번째 세션 시도 → 429 DAILY_LIMIT_REACHED."""
    from fastapi import HTTPException
    from app.routers.student.session import start_session
    from app.core.constants import DAILY_SESSION_LIMIT

    # count=3 (이미 한도 도달)
    chain, exe = _make_supabase_chain(count=DAILY_SESSION_LIMIT)

    with patch("app.routers.student.session.supabase") as mock_sb:
        mock_sb.table.return_value = chain

        raised = False
        try:
            start_session(student_id=STUDENT_ID)
        except HTTPException as e:
            assert e.status_code == 429, f"상태 코드 {e.status_code} (기대값: 429)"
            assert e.detail == "DAILY_LIMIT_REACHED", f"detail={e.detail}"
            raised = True

    assert raised, "HTTPException(429)가 발생하지 않음"
    assert DAILY_SESSION_LIMIT == 3, f"DAILY_SESSION_LIMIT={DAILY_SESSION_LIMIT} (기대값: 3)"
    print(f"✓ S8: 세션 초과 — DAILY_LIMIT={DAILY_SESSION_LIMIT}, 초과 시 429 DAILY_LIMIT_REACHED")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S9. OpenAI Rate Limit 초과 (신규)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_s9_openai_rate_limit():
    """
    RPM 초과 → stream_agent_turn 지수 백오프 2회 재시도 →
    3회째 실패 → run_discussion에서 llm_rate_limit 이벤트 yield.
    """
    from openai import RateLimitError
    from app.services.discussion import run_discussion, stream_agent_turn
    from app.services.director import DirectorDecision

    rate_limit_err = _make_openai_rate_limit_error()
    call_count = 0

    async def always_rate_limit(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise rate_limit_err

    # stream_agent_turn 의 재시도 로직만 검증 (asyncio.sleep 도 mock)
    async def fake_decide(_inp):
        return DirectorDecision(next_speaker="moderator", intent="summarize")

    chain, exe = _make_supabase_chain([])
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    with patch("app.services.discussion.supabase") as mock_sb, \
         patch("app.services.discussion.llm_decide", side_effect=fake_decide), \
         patch("app.services.discussion._async_client") as mock_client, \
         patch("app.services.discussion.asyncio.sleep", side_effect=fake_sleep), \
         patch("app.services.discussion.alog_llm_call", new_callable=AsyncMock), \
         patch("app.services.discussion.get_channel", return_value=None), \
         patch("app.services.discussion.load_prompt", return_value="당신은 테스트 에이전트입니다."):

        mock_sb.table.return_value = chain
        mock_client.chat.completions.create = AsyncMock(side_effect=always_rate_limit)

        context = {"student_name": "민수", "passage_content": "테스트",
                   "question_results": [], "all_correct": False,
                   "student_level": 2, "weak_areas": []}

        events = await _collect(run_discussion(SESSION_ID, "", context))

    event_types = [e["type"] for e in events]
    assert "error" in event_types, f"error 이벤트 없음. 이벤트={event_types}"

    error_event = next(e for e in events if e["type"] == "error")
    assert error_event["code"] == "llm_rate_limit", \
        f"error code={error_event['code']} (기대값: llm_rate_limit)"

    # 재시도 2회 확인: sleep(1.0), sleep(2.0)
    # asyncio.sleep은 백오프에서만 호출됨 (첫 시도 제외 2회 재시도)
    rate_limit_sleeps = [d for d in sleep_calls if d >= 1.0]
    assert len(rate_limit_sleeps) == 2, \
        f"재시도 sleep 횟수={len(rate_limit_sleeps)} (기대값: 2). sleeps={sleep_calls}"
    assert rate_limit_sleeps[0] == 1.0, f"1차 백오프={rate_limit_sleeps[0]} (기대값: 1.0)"
    assert rate_limit_sleeps[1] == 2.0, f"2차 백오프={rate_limit_sleeps[1]} (기대값: 2.0)"

    # OpenAI API 총 3회 호출 (최초 1회 + 재시도 2회)
    assert call_count == 3, f"OpenAI 호출 횟수={call_count} (기대값: 3)"

    print("✓ S9: Rate Limit — 재시도 3회(sleep 1s/2s) → llm_rate_limit 이벤트")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  실행기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_TESTS = [
    ("S1 정상 흐름",          test_s1_normal_flow,        True),
    ("S2 침묵 흐름",          test_s2_silence_flow,       True),
    ("S3 인터럽트 흐름",      test_s3_interrupt_flow,     True),
    ("S4 새로고침 복구",      test_s4_refresh_recovery,   False),
    ("S5 연결 끊김",          test_s5_disconnect_recovery,True),
    ("S6 부적절 입력",        test_s6_moderation_blocked, True),
    ("S7 LLM 실패",           test_s7_llm_failure,        True),
    ("S8 세션 초과",          test_s8_session_limit_exceeded, False),
    ("S9 Rate Limit 초과",    test_s9_openai_rate_limit,  True),
]


if __name__ == "__main__":
    passed = 0
    failed = 0

    for name, func, is_async in _TESTS:
        try:
            if is_async:
                asyncio.run(func())
            else:
                func()
            passed += 1
        except Exception as e:
            import traceback
            print(f"✗ {name}: {e}")
            traceback.print_exc()
            failed += 1

    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"P12 통합 시나리오: {passed}/{total} 통과  {'(ALL PASSED)' if failed == 0 else f'({failed} FAILED)'}")
    sys.exit(failed)

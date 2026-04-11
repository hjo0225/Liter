"""
Director 엔진 — "다음에 누가 무엇을 말할지" 결정하는 저비용 LLM 모듈.

사용 방법:
    from app.services.director import decide, DirectorInput

    decision = decide(
        DirectorInput(
            passage_summary="운석에 관한 지문",
            history=[{"speaker": "moderator", "content": "..."}, ...],
            round=1,
            last_speaker="moderator",
            user_idle_seconds=0.0,
            turns_in_round=1,
        ),
        session_id="uuid-string",   # DB 저장용, None이면 저장 생략
    )

director_calls 테이블 스키마 (migrations/001_p1_schema.sql 참조):
    id           UUID PK
    session_id   UUID FK → sessions
    round        INTEGER
    input_state  JSONB   ← DirectorInput 전체
    decision     JSONB   ← DirectorDecision 전체
    latency_ms   INTEGER
    model        TEXT
    created_at   TIMESTAMPTZ
"""

import json
import logging
import time
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.supabase import supabase

logger = logging.getLogger("uvicorn.error")

# ──────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────

Speaker = Literal["moderator", "peer_a", "peer_b", "user"]
_AI_SPEAKERS: list[Speaker] = ["moderator", "peer_a", "peer_b"]


class HistoryItem(BaseModel):
    speaker: str
    content: str


class DirectorInput(BaseModel):
    passage_summary: str
    history: list[HistoryItem]
    round: int
    last_speaker: str
    user_idle_seconds: float = 0.0
    turns_in_round: int


class DirectorDecision(BaseModel):
    next_speaker: Speaker
    intent: str        # 다음 발화자가 해야 할 것 (한 문장)
    target: str        # 누구에게 말하는지
    should_advance_round: bool
    reason: str        # 결정 이유 (한 문장)


# ──────────────────────────────────────────────────────
# Guard rules (코드 레벨 — LLM이 어겨도 강제 교정)
# ──────────────────────────────────────────────────────

def _apply_guards(decision: DirectorDecision, inp: DirectorInput) -> DirectorDecision:
    """
    세 가지 가드 룰을 순서대로 적용한다.
    룰 위반 시 decision 필드를 교정하되, 나머지 필드는 보존한다.
    """

    # Guard 1: round >= 4 → 강제 종료
    if inp.round >= 4:
        return DirectorDecision(
            next_speaker="moderator",
            intent="토의를 마무리하며 수고했다고 격려합니다.",
            target="전체",
            should_advance_round=True,
            reason=f"Guard-1: round={inp.round} >= 4, 세션 강제 종료",
        )

    # Guard 2: 학생 발언 직후 → AI가 반드시 응답 (wait_for_user 금지)
    if inp.last_speaker == "user" and decision.next_speaker == "user":
        corrected = "moderator"
        logger.warning(
            "Director guard-2: user→user 연속 차단, moderator로 교정 (원래 이유: %s)",
            decision.reason,
        )
        decision = DirectorDecision(
            next_speaker=corrected,
            intent=decision.intent,
            target=decision.target,
            should_advance_round=decision.should_advance_round,
            reason=f"Guard-2: 학생 발언 직후 user 재지정 차단 → {corrected}. 원래: {decision.reason}",
        )

    # Guard 3: 같은 발화자 연속 2회 금지 (user 제외)
    if (
        decision.next_speaker != "user"
        and decision.next_speaker == inp.last_speaker
    ):
        cur_idx = _AI_SPEAKERS.index(inp.last_speaker) if inp.last_speaker in _AI_SPEAKERS else 0
        corrected = _AI_SPEAKERS[(cur_idx + 1) % len(_AI_SPEAKERS)]
        logger.warning(
            "Director guard-3: 동일 발화자(%s) 연속 차단 → %s (원래 이유: %s)",
            inp.last_speaker, corrected, decision.reason,
        )
        decision = DirectorDecision(
            next_speaker=corrected,
            intent=decision.intent,
            target=decision.target,
            should_advance_round=decision.should_advance_round,
            reason=f"Guard-3: 연속 동일 발화자({inp.last_speaker}) 차단 → {corrected}. 원래: {decision.reason}",
        )

    return decision


# ──────────────────────────────────────────────────────
# LLM 호출 (Anthropic Claude Haiku — JSON-only)
# ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
당신은 한국 초등학교 독서 토의 세션의 Director입니다.
다음 발화자와 그 의도를 결정하고, 반드시 아래 JSON 형식으로만 응답하세요.
JSON 외 어떤 텍스트도 출력하지 마세요.

발화자 목록:
- moderator : 선생님(사회자), 토의 안내·심화 질문
- peer_a    : 민지, 자신감 있는 또래 학생
- peer_b    : 준서, 소극적이고 궁금한 게 많은 또래 학생
- user      : 실제 학생 (입력 차례를 줄 때만 사용)

판단 기준:
- 같은 발화자를 연속으로 지정하지 마세요.
- 학생(user) 발언 직후에는 반드시 AI 발화자를 지정하세요.
- turns_in_round >= 3이고 user도 발언했다면 should_advance_round=true를 고려하세요.
- round >= 4이면 should_advance_round=true로 설정하세요.

응답 형식 (반드시 이 JSON만):
{
  "next_speaker": "moderator" | "peer_a" | "peer_b" | "user",
  "intent": "다음 발화자가 해야 할 행동 (한국어 한 문장)",
  "target": "말을 거는 대상 (한국어)",
  "should_advance_round": true | false,
  "reason": "이 결정을 내린 이유 (한국어 한 문장)"
}\
"""


def _build_user_prompt(inp: DirectorInput) -> str:
    history_lines = "\n".join(
        f"  [{m.speaker}] {m.content}"
        for m in inp.history[-10:]  # 최근 10개만 전달
    ) or "  (없음)"

    return (
        f"[지문 요약] {inp.passage_summary}\n\n"
        f"[현재 라운드] {inp.round}\n"
        f"[이번 라운드 발화 수] {inp.turns_in_round}\n"
        f"[마지막 발화자] {inp.last_speaker}\n"
        f"[사용자 대기 시간(초)] {inp.user_idle_seconds:.0f}\n\n"
        f"[최근 대화 이력]\n{history_lines}\n\n"
        "다음 발화자를 결정하고 JSON으로만 응답하세요."
    )


def _call_llm_once(inp: DirectorInput) -> dict:
    """단일 LLM 호출 → 파싱된 dict 반환. 실패 시 예외."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=settings.DIRECTOR_MODEL,
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(inp)}],
    )
    raw = message.content[0].text.strip()
    return json.loads(raw)


# ──────────────────────────────────────────────────────
# DB 저장
# ──────────────────────────────────────────────────────

def _save_to_db(
    inp: DirectorInput,
    decision: DirectorDecision,
    latency_ms: int,
    session_id: str | None,
) -> None:
    if session_id is None:
        return
    try:
        supabase.table("director_calls").insert({
            "session_id": session_id,
            "round": inp.round,
            "input_state": inp.model_dump(),
            "decision": decision.model_dump(),
            "latency_ms": latency_ms,
            "model": settings.DIRECTOR_MODEL,
        }).execute()
    except Exception:
        logger.exception("director_calls DB 저장 실패 (session_id=%s)", session_id)


# ──────────────────────────────────────────────────────
# Fallback
# ──────────────────────────────────────────────────────

def _fallback_decision(inp: DirectorInput) -> DirectorDecision:
    """LLM 2회 모두 실패 시 코드 기반 기본값."""
    cur_idx = _AI_SPEAKERS.index(inp.last_speaker) if inp.last_speaker in _AI_SPEAKERS else -1
    next_sp = _AI_SPEAKERS[(cur_idx + 1) % len(_AI_SPEAKERS)]
    return DirectorDecision(
        next_speaker=next_sp,
        intent="대화를 자연스럽게 이어갑니다.",
        target="전체",
        should_advance_round=False,
        reason="Fallback: LLM 2회 호출 모두 실패",
    )


# ──────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────

def decide(inp: DirectorInput, session_id: str | None = None) -> DirectorDecision:
    """
    Director 메인 진입점.

    1. LLM 호출 (최대 2회)
    2. Pydantic 검증
    3. 가드 룰 적용
    4. director_calls 테이블에 저장
    5. DirectorDecision 반환

    session_id=None이면 DB 저장 생략 (테스트용).
    """
    t0 = time.monotonic()
    decision: DirectorDecision | None = None

    for attempt in range(2):
        try:
            raw = _call_llm_once(inp)
            decision = DirectorDecision.model_validate(raw)
            break
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning("Director LLM 시도 %d 실패: %s", attempt + 1, exc)

    if decision is None:
        decision = _fallback_decision(inp)

    decision = _apply_guards(decision, inp)
    latency_ms = int((time.monotonic() - t0) * 1000)
    _save_to_db(inp, decision, latency_ms, session_id)
    return decision

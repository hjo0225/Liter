"""
P3 Director Engine — LLM 기반 토의 진행 결정 엔진.

OpenAI AsyncOpenAI + DIRECTOR_MODEL 환경변수.
response_format={"type":"json_object"}로 JSON 강제.
가드 룰 적용 → director_calls 테이블 저장.

사용:
    from app.services.director import decide, DirectorInput
    decision = await decide(DirectorInput(session_id=..., round=1, ...))
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.constants import MAX_DISCUSSION_TOPICS
from app.core.supabase import supabase

logger = logging.getLogger("uvicorn.error")

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

ValidSpeaker = Literal["moderator", "peer_a", "peer_b", "wait_for_user", "close"]
ValidIntent = Literal["challenge", "agree", "ask_user", "summarize", "redirect", "nudge"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  I/O 스키마
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DirectorInput(BaseModel):
    """Director LLM에 전달하는 상태 스냅샷."""

    session_id: str
    round: int
    round_turn_index: int
    last_speaker: str | None = None
    recent_speakers: list[str] = []    # 최근 5턴 발화자 목록
    recent_summary: list[str] = []     # 최근 5턴 "speaker: 내용앞40자"
    all_correct: bool = False
    weak_areas: list[str] = []
    demo_mode: bool = False
    max_rounds: int = MAX_DISCUSSION_TOPICS


class DirectorDecision(BaseModel):
    """Director LLM의 결정. apply_guards() 통과 후 최종 사용."""

    next_speaker: ValidSpeaker
    intent: ValidIntent = "summarize"
    target: str | None = None
    reason: str = ""

    @field_validator("next_speaker", mode="before")
    @classmethod
    def _validate_speaker(cls, v: object) -> str:
        allowed = {"moderator", "peer_a", "peer_b", "wait_for_user", "close"}
        if str(v) not in allowed:
            raise ValueError(f"next_speaker must be one of {allowed}, got {v!r}")
        return str(v)

    @field_validator("intent", mode="before")
    @classmethod
    def _coerce_intent(cls, v: object) -> str:
        allowed = {"challenge", "agree", "ask_user", "summarize", "redirect", "nudge"}
        return str(v) if str(v) in allowed else "summarize"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  System Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIRECTOR_PROMPT = """당신은 초등학생 독서 토의를 이끄는 Director AI입니다.
현재 토의 상태(JSON)를 분석해 다음 발화자와 의도를 결정하세요.

【발화자 선택지】
- moderator    : 선생님. 주제 소개, 의견 요약, 심화 질문
- peer_a       : 민지(적극적). 자신 있게 의견 제시, 논쟁
- peer_b       : 준서(소극적). 궁금점 질문, 동의 또는 반론
- wait_for_user: 실제 학생의 답변 대기
- close        : 토의 마무리 (round > max_rounds 일 때만 선택)

【의도 선택지】
challenge | agree | ask_user | summarize | redirect | nudge

【라운드당 권장 순서】
moderator → peer_a → peer_b → wait_for_user → (다음 라운드)

【절대 금지】
- 연속으로 같은 발화자 선택
- 학생(user) 발언 직후 wait_for_user 선택
- round ≤ max_rounds 인데 close 선택

반드시 JSON만 출력하세요 (다른 텍스트 금지):
{"next_speaker": "...", "intent": "...", "target": "user", "reason": "한 줄 이유"}"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  가드 룰
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 연속 발화 방지: 현재 발화자 → 강제 대체 발화자
_REDIRECT_TO: dict[str, ValidSpeaker] = {
    "moderator": "peer_a",
    "peer_a": "peer_b",
    "peer_b": "wait_for_user",
    "wait_for_user": "moderator",
    "user": "moderator",
}


def apply_guards(decision: DirectorDecision, inp: DirectorInput) -> DirectorDecision:
    """
    가드 룰을 순서대로 적용. 우선순위: round 초과 > 연속 발화 > user 직후 wait.

    반환: 가드가 적용된(또는 원본) DirectorDecision.
    """
    # Guard 1: round ≥ 4 → 강제 종료
    if inp.round > inp.max_rounds:
        return decision.model_copy(
            update={
                "next_speaker": "close",
                "reason": "[guard] round exceeded max_rounds",
            }
        )

    # Guard 2: 같은 발화자 연속 2회 금지
    if inp.last_speaker and decision.next_speaker == inp.last_speaker:
        redirected: ValidSpeaker = _REDIRECT_TO.get(inp.last_speaker, "moderator")  # type: ignore[assignment]
        logger.debug("[guard] consecutive %s → %s", inp.last_speaker, redirected)
        decision = decision.model_copy(
            update={
                "next_speaker": redirected,
                "intent": "redirect",
                "reason": f"[guard] consecutive {inp.last_speaker} blocked → {redirected}",
            }
        )

    # Guard 3: 학생 발언 직후 wait_for_user 금지
    if inp.last_speaker == "user" and decision.next_speaker == "wait_for_user":
        decision = decision.model_copy(
            update={
                "next_speaker": "moderator",
                "intent": "summarize",
                "reason": "[guard] user just spoke; wait_for_user forbidden",
            }
        )

    return decision


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def decide(inp: DirectorInput) -> DirectorDecision:
    """
    OpenAI LLM으로 다음 발화자/의도 결정.

    실패 시 rule-based 폴백 → 가드 적용 → director_calls 저장.
    """
    t0 = time.time()
    decision: DirectorDecision

    try:
        resp = await _client.chat.completions.create(
            model=settings.DIRECTOR_MODEL,
            messages=[
                {"role": "system", "content": DIRECTOR_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(inp.model_dump(), ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content or "{}"
        decision = DirectorDecision.model_validate_json(raw)
    except Exception:
        logger.warning("Director LLM 실패 → rule-based 폴백", exc_info=True)
        decision = _rule_based_fallback(inp)

    decision = apply_guards(decision, inp)
    latency_ms = int((time.time() - t0) * 1000)
    await _save_director_call(inp, decision, latency_ms)
    return decision


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  내부 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_FALLBACK_SEQ: list[tuple[ValidSpeaker, ValidIntent]] = [
    ("moderator", "summarize"),
    ("peer_a", "challenge"),
    ("peer_b", "ask_user"),
    ("wait_for_user", "nudge"),
]


def _rule_based_fallback(inp: DirectorInput) -> DirectorDecision:
    """LLM 실패 시 round_turn_index 기반 rule-based 결정."""
    if inp.round > inp.max_rounds:
        return DirectorDecision(next_speaker="close", reason="[fallback] round exceeded")
    idx = min(inp.round_turn_index, len(_FALLBACK_SEQ) - 1)
    speaker, intent = _FALLBACK_SEQ[idx]
    return DirectorDecision(next_speaker=speaker, intent=intent, reason="[fallback] rule-based")


async def _save_director_call(
    inp: DirectorInput,
    decision: DirectorDecision,
    latency_ms: int,
) -> None:
    try:
        await asyncio.to_thread(
            lambda: supabase.table("director_calls").insert({
                "session_id": inp.session_id,
                "round": inp.round,
                "input_state": inp.model_dump(),
                "decision": decision.model_dump(),
                "latency_ms": latency_ms,
                "model": settings.DIRECTOR_MODEL,
            }).execute()
        )
    except Exception:
        logger.warning("director_calls 저장 실패", exc_info=True)

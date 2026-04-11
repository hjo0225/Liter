"""
P11 LLM 호출 중앙 로깅 — llm_calls / session_events 테이블 기록.

fire-and-forget 방식: 기록 실패가 메인 흐름을 중단하지 않는다.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.supabase import supabase

logger = logging.getLogger("uvicorn.error")

# ── 모델별 가격 (USD / 1M 토큰) ──────────────────────────────
_PRICE: dict[str, tuple[float, float]] = {
    # model: (input_price, output_price)
    "gpt-4o-mini":          (0.150, 0.600),
    "gpt-4o-mini-2024-07-18": (0.150, 0.600),
    "gpt-4o":               (5.000, 15.000),
    "gpt-4o-2024-11-20":    (2.500, 10.000),
}


def calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """모델별 가격으로 USD 비용 계산. 알 수 없는 모델은 None 반환."""
    price = _PRICE.get(model)
    if price is None:
        return None
    in_price, out_price = price
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  llm_calls 로거
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def log_llm_call(
    *,
    session_id: str,
    agent: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    seed: int | None = None,
) -> None:
    """동기 — fire-and-forget llm_calls 기록."""
    try:
        cost = None
        if prompt_tokens is not None and completion_tokens is not None:
            cost = calc_cost(model, prompt_tokens, completion_tokens)
        row: dict = {
            "session_id": session_id,
            "agent": agent,
            "model": model,
            "latency_ms": latency_ms,
            "provider": "openai",
        }
        if prompt_tokens is not None:
            row["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            row["completion_tokens"] = completion_tokens
        if cost is not None:
            row["cost_usd"] = cost
        if seed is not None:
            row["seed"] = seed
        supabase.table("llm_calls").insert(row).execute()
    except Exception:
        logger.warning(
            "llm_calls 기록 실패: session_id=%s agent=%s", session_id, agent, exc_info=True
        )


async def alog_llm_call(
    *,
    session_id: str,
    agent: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    seed: int | None = None,
) -> None:
    """비동기 — fire-and-forget llm_calls 기록."""
    await asyncio.to_thread(
        log_llm_call,
        session_id=session_id,
        agent=agent,
        model=model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        seed=seed,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  session_events 로거
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def log_session_event(
    session_id: str,
    event_type: str,
    payload: dict | None = None,
) -> None:
    """동기 — session_events 기록."""
    try:
        supabase.table("session_events").insert({
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload or {},
        }).execute()
    except Exception:
        logger.warning(
            "session_events 기록 실패: session_id=%s event_type=%s", session_id, event_type, exc_info=True
        )


async def alog_session_event(
    session_id: str,
    event_type: str,
    payload: dict | None = None,
) -> None:
    """비동기 — session_events 기록."""
    await asyncio.to_thread(log_session_event, session_id, event_type, payload)

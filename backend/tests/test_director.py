"""
Director 엔진 유닛 테스트 — 5개 시나리오
LLM·DB 호출을 mock하여 가드 룰과 스키마 검증만 테스트.

실행:
    cd backend
    pip install pytest
    pytest tests/test_director.py -v
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.director import (
    DirectorDecision,
    DirectorInput,
    HistoryItem,
    _apply_guards,
    _fallback_decision,
    decide,
)


# ──────────────────────────────────────────────────────
# 공통 픽스처
# ──────────────────────────────────────────────────────

def _make_inp(**overrides) -> DirectorInput:
    defaults = dict(
        passage_summary="운석은 태양계 형성 당시 생긴 암석 조각이다.",
        history=[
            HistoryItem(speaker="moderator", content="운석 연구가 왜 중요할까요?"),
            HistoryItem(speaker="peer_a", content="태양계가 어떻게 만들어졌는지 알 수 있어요."),
        ],
        round=1,
        last_speaker="peer_a",
        user_idle_seconds=3.0,
        turns_in_round=2,
    )
    defaults.update(overrides)
    return DirectorInput(**defaults)


def _llm_response(decision: dict) -> MagicMock:
    """Anthropic 클라이언트 messages.create() 가짜 응답 생성."""
    msg = MagicMock()
    msg.content = [SimpleNamespace(text=json.dumps(decision, ensure_ascii=False))]
    client_mock = MagicMock()
    client_mock.messages.create.return_value = msg
    return client_mock


# ──────────────────────────────────────────────────────
# 시나리오 1: 정상 흐름 — peer_b 차례
# ──────────────────────────────────────────────────────

def test_scenario1_normal_flow():
    """moderator → peer_a 다음, LLM이 peer_b 지정 → 그대로 통과."""
    llm_decision = {
        "next_speaker": "peer_b",
        "intent": "민지 의견에 반응합니다.",
        "target": "peer_a",
        "should_advance_round": False,
        "reason": "peer_a 다음은 peer_b 차례입니다.",
    }
    inp = _make_inp(last_speaker="peer_a")

    with (
        patch("app.services.director.anthropic.Anthropic", return_value=_llm_response(llm_decision)),
        patch("app.services.director._save_to_db"),
    ):
        result = decide(inp, session_id=None)

    assert result.next_speaker == "peer_b"
    assert result.should_advance_round is False
    assert isinstance(result.reason, str) and result.reason


# ──────────────────────────────────────────────────────
# 시나리오 2: Guard-2 — 학생 발언 직후 LLM이 user 재지정
# ──────────────────────────────────────────────────────

def test_scenario2_guard_user_after_user():
    """last_speaker=user인데 LLM이 next_speaker=user로 잘못 결정 → moderator로 교정."""
    llm_decision = {
        "next_speaker": "user",       # ← 위반
        "intent": "학생에게 다시 묻습니다.",
        "target": "user",
        "should_advance_round": False,
        "reason": "학생의 의견을 더 듣고 싶습니다.",
    }
    inp = _make_inp(last_speaker="user", turns_in_round=3)

    with (
        patch("app.services.director.anthropic.Anthropic", return_value=_llm_response(llm_decision)),
        patch("app.services.director._save_to_db"),
    ):
        result = decide(inp, session_id=None)

    assert result.next_speaker != "user", "Guard-2: user→user 연속은 차단돼야 한다"
    assert result.next_speaker == "moderator"
    assert "Guard-2" in result.reason


# ──────────────────────────────────────────────────────
# 시나리오 3: Guard-3 — 연속 동일 발화자 차단
# ──────────────────────────────────────────────────────

def test_scenario3_guard_consecutive_same_speaker():
    """last_speaker=peer_a인데 LLM이 peer_a를 다시 지정 → peer_b로 교정."""
    llm_decision = {
        "next_speaker": "peer_a",     # ← 위반
        "intent": "추가 의견을 제시합니다.",
        "target": "전체",
        "should_advance_round": False,
        "reason": "peer_a가 더 말하고 싶어합니다.",
    }
    inp = _make_inp(last_speaker="peer_a")

    with (
        patch("app.services.director.anthropic.Anthropic", return_value=_llm_response(llm_decision)),
        patch("app.services.director._save_to_db"),
    ):
        result = decide(inp, session_id=None)

    assert result.next_speaker != "peer_a", "Guard-3: 연속 동일 발화자는 차단돼야 한다"
    assert result.next_speaker == "peer_b"
    assert "Guard-3" in result.reason


# ──────────────────────────────────────────────────────
# 시나리오 4: Guard-1 — round >= 4 강제 종료
# ──────────────────────────────────────────────────────

def test_scenario4_guard_round_overflow():
    """round=4이면 LLM 결과와 무관하게 강제 종료."""
    llm_decision = {
        "next_speaker": "peer_a",
        "intent": "새 주제를 시작합니다.",
        "target": "user",
        "should_advance_round": False,
        "reason": "아직 할 말이 있습니다.",
    }
    inp = _make_inp(round=4, last_speaker="user")

    with (
        patch("app.services.director.anthropic.Anthropic", return_value=_llm_response(llm_decision)),
        patch("app.services.director._save_to_db"),
    ):
        result = decide(inp, session_id=None)

    assert result.should_advance_round is True, "Guard-1: round>=4이면 강제 종료"
    assert result.next_speaker == "moderator"
    assert "Guard-1" in result.reason


# ──────────────────────────────────────────────────────
# 시나리오 5: LLM 2회 실패 → Fallback
# ──────────────────────────────────────────────────────

def test_scenario5_llm_failure_fallback():
    """LLM이 두 번 모두 예외를 발생시키면 fallback decision을 반환한다."""
    inp = _make_inp(last_speaker="peer_b", turns_in_round=3)

    broken_client = MagicMock()
    broken_client.messages.create.side_effect = RuntimeError("API timeout")

    with (
        patch("app.services.director.anthropic.Anthropic", return_value=broken_client),
        patch("app.services.director._save_to_db"),
    ):
        result = decide(inp, session_id=None)

    # Fallback 결과도 유효한 DirectorDecision이어야 한다
    assert isinstance(result, DirectorDecision)
    assert result.next_speaker in ("moderator", "peer_a", "peer_b", "user")
    # Guard-3: last_speaker=peer_b이면 fallback은 moderator
    assert result.next_speaker != "peer_b", "Fallback도 가드가 적용돼야 한다"
    assert result.next_speaker == "moderator"


# ──────────────────────────────────────────────────────
# 보조: _apply_guards 직접 단위 테스트
# ──────────────────────────────────────────────────────

def test_apply_guards_all_pass():
    """가드 위반이 없으면 원본 decision이 그대로 반환된다."""
    inp = _make_inp(round=2, last_speaker="peer_a")
    decision = DirectorDecision(
        next_speaker="peer_b",
        intent="peer_a 의견에 반응합니다.",
        target="peer_a",
        should_advance_round=False,
        reason="정상 순서",
    )
    result = _apply_guards(decision, inp)
    assert result.next_speaker == "peer_b"
    assert "Guard" not in result.reason

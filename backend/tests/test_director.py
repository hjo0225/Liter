"""
P3 Director 가드 룰 검증 — 5가지 시나리오.

LLM 호출 없이 apply_guards()만 테스트한다.
실행: python tests/test_director.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.director import DirectorDecision, DirectorInput, apply_guards


def _inp(**kw) -> DirectorInput:
    base = dict(session_id="test", round=1, round_turn_index=0,
                last_speaker=None, recent_speakers=[], recent_summary=[],
                all_correct=False, weak_areas=[], demo_mode=False, max_rounds=3)
    base.update(kw)
    return DirectorInput(**base)


def _dec(next_speaker, intent="summarize") -> DirectorDecision:
    return DirectorDecision(next_speaker=next_speaker, intent=intent)


def test_s1_empty_history():
    """이력 없음 + moderator 결정 → 가드 없이 통과."""
    r = apply_guards(_dec("moderator"), _inp(last_speaker=None))
    assert r.next_speaker == "moderator"
    assert not r.reason.startswith("[guard]")
    print("✓ S1: empty history, no guard fired")


def test_s2_consecutive_blocked():
    """peer_a 직후 peer_a → Guard2: peer_b로 교정."""
    r = apply_guards(_dec("peer_a", "challenge"), _inp(last_speaker="peer_a"))
    assert r.next_speaker == "peer_b"
    assert r.intent == "redirect"
    assert "[guard]" in r.reason
    print("✓ S2: consecutive peer_a → peer_b")


def test_s3_user_wait_forbidden():
    """user 직후 wait_for_user → Guard3: moderator+summarize."""
    r = apply_guards(_dec("wait_for_user"), _inp(last_speaker="user"))
    assert r.next_speaker == "moderator"
    assert r.intent == "summarize"
    assert "[guard]" in r.reason
    print("✓ S3: user→wait_for_user → moderator")


def test_s4_round_overflow():
    """round=4 → Guard1: 어떤 결정이든 close 강제."""
    r = apply_guards(_dec("peer_a"), _inp(round=4, last_speaker="peer_b"))
    assert r.next_speaker == "close"
    assert "round exceeded" in r.reason
    print("✓ S4: round=4 → close")


def test_s5_normal_flow():
    """peer_a → peer_b 정상 흐름, 가드 미발동."""
    r = apply_guards(_dec("peer_b", "ask_user"), _inp(last_speaker="peer_a"))
    assert r.next_speaker == "peer_b"
    assert r.intent == "ask_user"
    assert not r.reason.startswith("[guard]")
    print("✓ S5: peer_a→peer_b, no guard")


if __name__ == "__main__":
    tests = [test_s1_empty_history, test_s2_consecutive_blocked,
             test_s3_user_wait_forbidden, test_s4_round_overflow, test_s5_normal_flow]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'ALL PASSED' if not failed else f'{failed} FAILED'} ({len(tests)-failed}/{len(tests)})")
    sys.exit(failed)

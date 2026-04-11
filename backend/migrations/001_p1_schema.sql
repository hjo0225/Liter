-- =============================================================
-- P1. 기반 정리 — 새로운 토론 로직을 받을 그릇 만들기
-- Supabase SQL Editor에서 실행하세요.
-- =============================================================

-- 1. messages 테이블에 컬럼 추가 (= discussion_turns)
--    intent     : 발화 의도 (challenge/agree/ask_user/summarize/redirect/nudge)
--    target     : 응답 대상 발화자 (user/moderator/peer_a/peer_b)
--    is_interrupted : 중단된 발화 여부
--    client_ts  : 클라이언트 기준 타임스탬프
--    server_ts  : 서버 수신 타임스탬프
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS intent          TEXT,
  ADD COLUMN IF NOT EXISTS target          TEXT,
  ADD COLUMN IF NOT EXISTS is_interrupted  BOOLEAN      NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS client_ts       TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS server_ts       TIMESTAMPTZ;

-- 2. director_calls 테이블 신규 생성
--    Director가 매 턴 어떤 상태를 보고 어떤 결정을 내렸는지 기록
CREATE TABLE IF NOT EXISTS director_calls (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id   UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  round        INTEGER     NOT NULL,
  input_state  JSONB,
  decision     JSONB,
  latency_ms   INTEGER,
  model        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_director_calls_session_id
  ON director_calls(session_id);

-- 3. llm_calls 테이블 신규 생성
--    모든 LLM 호출 로그 (agent, 모델, 토큰, 지연시간)
CREATE TABLE IF NOT EXISTS llm_calls (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id         UUID        REFERENCES sessions(id) ON DELETE CASCADE,
  agent              TEXT,
  model              TEXT,
  prompt_tokens      INTEGER,
  completion_tokens  INTEGER,
  latency_ms         INTEGER,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_session_id
  ON llm_calls(session_id);

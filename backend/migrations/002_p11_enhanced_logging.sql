-- =============================================================
-- P11. 로깅 강화 — 연구 분석용 데이터 적재
-- Supabase SQL Editor에서 실행하세요.
-- =============================================================

-- 1. llm_calls — provider, cost_usd, seed 추가
ALTER TABLE llm_calls
  ADD COLUMN IF NOT EXISTS provider  TEXT          DEFAULT 'openai',
  ADD COLUMN IF NOT EXISTS cost_usd  NUMERIC(10,6),
  ADD COLUMN IF NOT EXISTS seed      INTEGER;

-- 2. director_calls — 토큰 수 + 비용 추가
ALTER TABLE director_calls
  ADD COLUMN IF NOT EXISTS prompt_tokens      INTEGER,
  ADD COLUMN IF NOT EXISTS completion_tokens  INTEGER,
  ADD COLUMN IF NOT EXISTS cost_usd           NUMERIC(10,6);

-- 3. session_events — 사용자 행동 이벤트 (idle, skip, turn 등)
CREATE TABLE IF NOT EXISTS session_events (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_type  TEXT        NOT NULL,   -- 'user_idle' | 'user_skip' | 'user_turn' | ...
  payload     JSONB       DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_events_session
  ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_type
  ON session_events(session_id, event_type);
CREATE INDEX IF NOT EXISTS idx_session_events_created
  ON session_events(created_at DESC);

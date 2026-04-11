-- =============================================================
-- P12 후속 — question_results 응답 시각 컬럼 추가
-- Supabase SQL Editor에서 실행하세요.
-- =============================================================

-- question_results 에 클라이언트 측정 타임스탬프 추가
ALTER TABLE question_results
  ADD COLUMN IF NOT EXISTS shown_at    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS answered_at TIMESTAMPTZ;

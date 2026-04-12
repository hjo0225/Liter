# CLAUDE.md — Liter (리터) 프로젝트 가이드

## 프로젝트 개요

**Liter**는 초등학생(4~6학년) 대상 AI 기반 문해력 교육 플랫폼이다.
지문 읽기 → 객관식 퀴즈 → **3명의 AI 에이전트와 그룹 토의** 순서로 세션이 진행된다.
핵심 가치: 단순 정답 확인이 아닌, 또래 토론을 통해 추론·어휘·맥락 이해력을 기른다.

- 배포: Frontend → Vercel (`liter-psi.vercel.app`), Backend → GCP Cloud Run
- DB: Supabase (PostgreSQL + Auth)
- LLM: OpenAI API (`gpt-4o-mini`)

---

## 기술 스택

| 영역 | 스택 |
|------|------|
| Frontend | Vue 3 (Composition API) + TypeScript + Pinia + TailwindCSS + Vite |
| Backend | FastAPI (Python 3.11) + async/await + uvicorn |
| Database | Supabase (PostgreSQL, RLS, Auth) |
| LLM | OpenAI API — Agent: `gpt-4o-mini` (Director LLM 제거됨) |
| 실시간 통신 | SSE (Server-Sent Events) — fetch + ReadableStream 방식 |
| 인프라 | GCP Cloud Run + Vercel + Cloud Scheduler |

---

## 디렉토리 구조

```
backend/
├── app/
│   ├── agents/           # AI 에이전트 로직 (discussion, diagnosis, passage, feedback)
│   ├── core/             # 공통 (config, constants, state, supabase, llm_logging, deps)
│   ├── routers/          # FastAPI 라우터
│   │   ├── student/      # 학생 엔드포인트 (session, discussion, turns, scoring)
│   │   ├── auth_student.py
│   │   ├── auth_teacher.py
│   │   └── teacher.py
│   ├── schemas/          # Pydantic 모델 (auth, session, llm, classroom)
│   ├── services/         # 비즈니스 로직 (director, discussion)
│   └── main.py           # FastAPI 앱 정의
├── prompts/              # 에이전트 시스템 프롬프트 (.md 파일)
├── tests/                # Pytest 테스트
├── main.py               # Cloud Run 진입점
└── Dockerfile

frontend/
├── src/
│   ├── api/              # Axios 클라이언트
│   ├── components/       # Vue 컴포넌트
│   ├── composables/      # Composition API 로직 (useDiscussionStream 등)
│   ├── pages/            # 라우트 뷰 (Student*, Teacher*)
│   ├── router/           # Vue Router
│   ├── stores/           # Pinia 스토어 (discussion, student, teacher)
│   └── main.ts
└── package.json
```

---

## 핵심 아키텍처

### 세션 흐름
```
1. 지문 읽기 (250~400자)
2. 객관식 퀴즈 3문항 (정보 추출 / 추론 / 어휘)
3. AI 그룹 토의 (3라운드 고정)
4. 세션 종료 → 점수 산출 + 레벨 조정
```

### 토의 구조 — 고정 턴 시퀀스 (Director LLM 없음)

Director LLM을 제거하고 **고정 시퀀스**로 턴을 결정한다. `_next_decision(state)` 함수가 `round_turn_index`로 다음 화자를 결정.

```
ROUND_SPEAKERS = ["moderator", "peer_a", "peer_b", "moderator"]

라운드당 4턴:
  Step 0: 선생님 (오프닝/전환)     — 주제 소개, 반박 안내, 결론 안내
  Step 1: 민지 (peer_a)           — 의견/반박/결론
  Step 2: 준서 (peer_b)           — 민지에 반응 + 자기 의견
  Step 3: 선생님 (정리+질문)       — 실제 발언 요약 + 학생에게 질문
  → wait_for_user (학생 입력 대기)
  × 3라운드 → close (마무리 + 점수)
```

**라운드별 내용:**
- 라운드 1 (의견 나누기): 주제 소개 → 각자 의견 → 학생에게 질문
- 라운드 2 (반박하기): 1단계 의견 정리 → 반박 → 학생에게 반박 요청
- 라운드 3 (결론 내기): 결론 안내 → 각자 결론 → 학생에게 결론 요청

**instruction 생성:** `_build_instruction(speaker, step, round_num, state, student_name)` 함수가 (speaker, step, round)을 키로 정확히 하나의 instruction을 생성한다.

### 멀티 에이전트 시스템

- **턴 결정** (`services/discussion.py`의 `_next_decision`): 고정 시퀀스 기반. LLM 호출 없음.
- **Agents** (`services/discussion.py` + `agents/discussion_agent.py`): moderator, peer_a, peer_b 각각 독립 LLM 호출. 역할 혼동 방지를 위해 대화 공유 X.
- **프롬프트**: `backend/prompts/*.md` 파일 기반. `{student_name}` 등 런타임 치환.
- **Director 파일** (`services/director.py`): 레거시. 현재 discussion.py에서 사용하지 않음. 테스트에서만 참조.

### 에이전트 발화 규칙

1. **모더레이터**: 아직 발언하지 않은 참여자의 의견을 절대 미리 언급하지 않음. Step 3에서 실제 발언 내용을 instruction에 직접 주입하여 hallucination 방지.
2. **민지 (peer_a)**: 내용에 맞게 공감/반대/보충 자연스럽게 선택. 무조건 반대하지 않음. 지문 근거 필수.
3. **준서 (peer_b)**: 민지 발언에 반응 후 자기 의견. 솔직한 "잘 모르겠어" 허용. 질문 포함.
4. **출력 금지**: `[민지]`, `[선생님]` 등 이름 태그 출력 금지. 발언 내용만 출력.

### Soft Interrupt (P9 패턴)
학생이 AI 발화 도중 끼어들면 스트림을 끊지 않고, `SessionChannel` 큐에 저장 → 턴 사이에 감지 시 즉시 `advance_round()`로 다음 라운드 전진.

---

## 주요 상수 (`backend/app/core/constants.py`)

| 상수 | 값 | 설명 |
|------|-----|------|
| DAILY_SESSION_LIMIT | 3 | 일일 세션 제한 |
| MAX_DISCUSSION_TOPICS | 3 | 최대 토의 라운드 |
| LEVEL_UP_THRESHOLD | 8.0 | 레벨업 기준 점수 |
| LEVEL_DOWN_THRESHOLD | 5.0 | 레벨다운 기준 점수 |
| MIN_LEVEL / MAX_LEVEL | 1 / 3 | 난이도 범위 |
| SESSION_TIMEOUT_MINUTES | 60 | 유휴 세션 만료 시간 |

---

## API 엔드포인트 요약

```
POST /api/v1/auth/teacher/signup          교사 가입
POST /api/v1/auth/teacher/verify-otp      OTP 인증
POST /api/v1/auth/student/join            참여코드 → JWT

GET  /api/v1/student/me                   학생 프로필
POST /api/v1/student/sessions             세션 시작
POST /api/v1/student/sessions/{id}/answers  퀴즈 답안 제출
GET  /api/v1/student/sessions/{id}/discussion  SSE 토의 스트림
POST /api/v1/student/sessions/{id}/discussion/turns  학생 발화 입력

GET  /api/v1/teacher/classrooms           반 목록
GET  /api/v1/teacher/classrooms/{id}      반 상세 + 학생 분석

POST /api/v1/internal/cleanup-abandoned-sessions  (cron)
POST /api/v1/internal/adjust-levels       (cron)
```

---

## 개발 실행 방법

### Backend
```bash
cd backend
pip install -r requirements.txt
# 환경변수: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
#           OPENAI_API_KEY, JWT_SECRET, APP_ENV=dev
uvicorn app.main:app --reload    # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 (Vite 프록시로 백엔드 연결)
```

---

## 코딩 컨벤션 및 주의사항

### 필수 패턴
- **Double Submit Guard**: async 핸들러 첫 줄에 `if (loading.value) return` 가드 필수
- **수정 후 커밋**: 코드 수정 완료 후 별도 요청 없이 바로 `git commit` 수행
- **에이전트 발화 50자 제한**: 각 에이전트 발화는 50자 이내 (프롬프트에 명시)
- **존댓말 통일**: 모든 AI 에이전트는 존댓말(습니다체) 사용

### 설계 원칙
- 세션은 **일회성(ephemeral)** — 중도 이탈 시 삭제, 재개 불가
- 에이전트 간 대화 컨텍스트 **공유 금지** — 역할 혼동 방지
- **턴 순서는 고정 시퀀스** — LLM으로 결정하지 않음. `ROUND_SPEAKERS` 배열 인덱싱.
- SSE는 fetch + ReadableStream 방식 — EventSource 아님 (JWT 전달 제약)

### Git 커밋 스타일
```
feat: 새 기능 설명
fix: 버그 수정 설명
style: UI/스타일 변경
docs: 문서 변경
```

---

## DB 주요 테이블

```
students       — id, name, level, streak_count, weak_areas[], classroom_id
sessions       — id, student_id, status, passage_content, question_results, scores, feedback
messages       — id, session_id, speaker, content, round, role, intent, target
director_calls — id, session_id, round, input_state, decision, latency_ms, cost_usd
llm_calls      — id, session_id, agent, model, latency_ms, tokens
classrooms     — id, teacher_id, name, join_code
teachers       — id, email, password_hash, classroom_id
```

---

## 해결된 주요 버그 (히스토리)

1. **에이전트 역할 혼동**: 3명이 같은 LLM 컨텍스트 공유 → 독립 호출로 해결
2. **중복 세션 생성(Double Submit)**: 네트워크 지연 + 버튼 스팸 → loading 가드 + 버튼 disabled 처리
3. **레벨 수동 설정 덮어쓰기**: cron이 교사 수동 설정 무시 → `is_manual_override` 플래그 추가
4. **모더레이터 의견 hallucination**: 아직 발언하지 않은 참여자 의견을 미리 지어냄 → instruction에 "금지" 명시 + 실제 발언 내용 주입
5. **기계적 반대 버그**: "절반 이상 반대" 프롬프트 규칙 → 내용 무관하게 반대 → 규칙 제거, 내용 기반 자연스러운 반응으로 변경
6. **이름 태그 누출**: `[민지] 발언내용` 형태로 프롬프트 유출 → 히스토리 포맷 `[민지]` → `민지:` 변경 + 출력 금지 규칙 추가
7. **Director LLM 불필요**: 턴 순서가 고정인데 LLM으로 결정 → guard가 어차피 덮어씀 → Director LLM 제거, 고정 시퀀스로 변경
8. **AI 발화 JSON 래퍼 출력**: content 필드만 추출하도록 파싱 추가

---

## 에이전트 캐릭터

| 역할 | 이름 | 성격 |
|------|------|------|
| moderator | 사회자 | 중립적, 진행 역할, 존댓말 |
| peer_a | 민지 | 적극적, 의견 주장형 |
| peer_b | 준서 | 소극적, 질문형 |

각 에이전트의 시스템 프롬프트는 `backend/prompts/{role}.md`에 정의.
발화 패턴(instruction)은 `discussion.py`의 `_build_instruction(speaker, step, round)` 함수에서 동적 생성.

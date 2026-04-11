# SSE Protocol — Tododok Discussion Stream

> **버전**: P5  
> **엔드포인트 2종**: POST (fetch 기반) / GET (EventSource 기반)  
> **미디어 타입**: `text/event-stream`  
> **이벤트 포맷**: `data: {JSON}\n\n` (SSE 표준 `data:` 라인만 사용)

---

## 엔드포인트

### POST `/api/v1/student/sessions/{session_id}/discussion`
- **인증**: `Authorization: Bearer <student_jwt>` 헤더
- **Body** (JSON):
  ```json
  { "content": "학생 발화 텍스트", "demo_mode": false }
  ```
- 기존 fetch 기반 클라이언트 호환 유지

### GET `/api/v1/student/sessions/{session_id}/discussion`
- **인증**: `?token=<student_jwt>` 쿼리 파라미터 (EventSource는 헤더 설정 불가)
- **Query params**:
  - `content` (string, default `""`) — 학생 발화 내용
  - `demo_mode` (bool, default `false`) — AI 자가 진행 모드
  - `token` (string, required) — 학생 JWT
- 30초마다 `heartbeat` 자동 전송
- 클라이언트 disconnect 시 백그라운드 task 자동 취소

---

## 이벤트 11종

모든 이벤트는 `type` 필드를 가진다.

---

### 1. `turn_start`
AI 에이전트가 발화를 시작하는 시점. 토큰 스트리밍 직전에 전송된다.

```json
{
  "type": "turn_start",
  "speaker": "peer_a",
  "turn_id": "uuid-v4",
  "round": 1
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `speaker` | `"moderator" \| "peer_a" \| "peer_b"` | 발화자 |
| `turn_id` | `string` | 이 턴의 고유 ID (token·turn_end와 매칭용) |
| `round` | `int` | 현재 토픽 번호 (1~3) |

---

### 2. `token`
LLM이 생성한 토큰 단위 스트림. UI에서 타이핑 효과에 활용.

```json
{
  "type": "token",
  "speaker": "peer_a",
  "text": "나는",
  "turn_id": "uuid-v4"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `text` | `string` | 토큰 텍스트 조각 |
| `turn_id` | `string` | 대응하는 `turn_start`의 ID |

---

### 3. `turn_end`
발화 완료. 전체 텍스트 포함.

```json
{
  "type": "turn_end",
  "speaker": "peer_a",
  "content": "나는 그렇게 생각해. 왜냐하면...",
  "turn_id": "uuid-v4",
  "round": 1
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `content` | `string` | 전체 발화 텍스트 |
| `turn_id` | `string` | 대응하는 `turn_start`의 ID |

---

### 4. `interrupted`
발화가 중단된 경우 (클라이언트 disconnect 또는 moderator 개입).

```json
{
  "type": "interrupted",
  "speaker": "peer_a",
  "partial_content": "나는 그렇게..."
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `partial_content` | `string` | 중단 시점까지의 텍스트 |

---

### 5. `waiting_for_user`
학생 차례. 클라이언트는 입력창을 활성화한다.

```json
{
  "type": "waiting_for_user",
  "round": 1
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `round` | `int` | 현재 토픽 번호 |

> POST 엔드포인트: 이 이벤트 후 스트림이 종료된다. 학생이 답변하면 새 POST 요청.  
> GET 엔드포인트 demo_mode: 이 이벤트 대신 `round_change`가 전송된다.

---

### 6. `user_idle`
학생이 일정 시간 응답하지 않은 경우 (서버 감지 시 선택적 전송).

```json
{
  "type": "user_idle",
  "idle_seconds": 30
}
```

---

### 7. `round_change`
데모 모드에서 라운드(토픽)가 전환될 때 전송된다.

```json
{
  "type": "round_change",
  "from_round": 1,
  "to_round": 2
}
```

---

### 8. `scores`
3라운드 완료 후 점수 계산 결과. `is_final` 직전에 전송된다.

```json
{
  "type": "scores",
  "score_reasoning": 7.5,
  "score_vocabulary": 8.0,
  "score_context": 6.5,
  "feedback": "오늘 토의에서 추론력이 돋보였어요!"
}
```

| 필드 | 타입 | 범위 | 설명 |
|------|------|------|------|
| `score_reasoning` | `float` | 0~10 | 추론력 점수 |
| `score_vocabulary` | `float` | 0~10 | 어휘력 점수 |
| `score_context` | `float` | 0~10 | 맥락파악 점수 |
| `feedback` | `string` | — | AI 생성 피드백 (2~3문장) |

---

### 9. `is_final`
토의 완전 종료. 스트림이 닫힌다.

```json
{
  "type": "is_final"
}
```

클라이언트는 이 이벤트 수신 후 `POST /sessions/{id}/end`를 호출해 streak·level 업데이트를 완료한다.

---

### 10. `error`
오류 발생. `code` 필드로 오류 종류를 구분한다.

```json
{
  "type": "error",
  "code": "llm_rate_limit",
  "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
}
```

| `code` | 설명 |
|--------|------|
| `llm_rate_limit` | OpenAI rate limit 초과 |
| `llm_failure` | LLM 호출 실패 (timeout, 서버 오류 등) |
| `moderation_blocked` | 콘텐츠 정책 위반 감지 |
| `session_expired` | 세션 만료 또는 비정상 상태 |
| `unknown` | 기타 예상치 못한 오류 |

---

### 11. `heartbeat`
30초마다 연결 유지용으로 GET 엔드포인트에서 자동 전송.

```json
{
  "type": "heartbeat",
  "ts": "2025-04-11T12:00:00.000Z"
}
```

클라이언트는 이 이벤트를 무시하거나 연결 상태 표시에만 활용한다.

---

## 일반 토의 흐름 (POST, 비데모)

```
[라운드 1]
  → turn_start (moderator)
  → token × N
  → turn_end (moderator)
  → turn_start (peer_a)
  → token × N
  → turn_end (peer_a)
  → turn_start (peer_b)
  → token × N
  → turn_end (peer_b)
  → waiting_for_user         ← 스트림 종료, 학생 입력 대기

[학생 답변 POST]
[라운드 2~3 반복]

[라운드 3 완료 후]
  → turn_end (moderator close)
  → scores
  → is_final                 ← 스트림 종료
```

## 데모 모드 흐름 (GET, demo_mode=true)

```
[라운드 1]
  → turn_start / token × N / turn_end (moderator)
  → turn_start / token × N / turn_end (peer_a)
  → turn_start / token × N / turn_end (peer_b)
  → round_change {from:1, to:2}
[라운드 2]
  → ... (동일 반복)
  → round_change {from:2, to:3}
[라운드 3]
  → ...
  → round_change {from:3, to:4}
  → turn_end (moderator close)
  → scores
  → is_final
```

---

## CORS 헤더

SSE 호환을 위해 다음 헤더가 허용된다:

```
Content-Type, Authorization, Accept, Cache-Control, Last-Event-ID
```

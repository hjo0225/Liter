# 멀티에이전트 기반 초개인화 문해력 솔루션

<div align="center">

![Vue](https://img.shields.io/badge/Frontend-Vue%203-42B883?style=for-the-badge&logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Build-Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![OpenAI](https://img.shields.io/badge/LLM-OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Deploy-GCP%20Cloud%20Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)
![Vercel](https://img.shields.io/badge/Frontend%20Deploy-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

</div>

초등 4~6학년 학생의 기능적 문해력 향상을 위해 설계된 AI 학습 플랫폼입니다.  
학생은 지문 읽기, 객관식 문항 풀이, AI 또래 그룹 토의를 통해 학습하고, 교사는 학급 대시보드에서 수준 변화와 취약 영역을 확인할 수 있습니다.

## 프로젝트 개요

이 프로젝트는 객관식 기반 진단과 멀티 에이전트 토의를 결합해, 단순 정오답 확인을 넘어 학생의 추론력, 어휘력, 맥락 파악 능력을 함께 평가하는 것을 목표로 합니다.

핵심 흐름은 다음과 같습니다.

1. 학생이 지문을 읽습니다.
2. 객관식 문항 3개를 풉니다.
3. AI 모더레이터와 AI 또래 2명과 그룹 토의를 진행합니다.
4. 세션 종료 후 점수와 streak가 저장됩니다.
5. 교사는 대시보드에서 학급 현황과 개별 학생의 약점을 확인합니다.

## 주요 사용자

| 사용자 | 목적 | 접속 방식 |
| --- | --- | --- |
| 학생 | 매일 세션 수행, 문해력 향상, streak 유지 | 교사 발급 코드 입력 |
| 담임교사 | 학급 모니터링, 학생 수준 확인, 난이도 조정 | 이메일 회원가입 및 로그인 |

## 핵심 기능

### 학생 기능

- 지문 읽기 기반 학습 세션
- 3문항 객관식 문해력 진단
- AI 모더레이터, 또래 A, 또래 B와의 그룹 토의
- 세션별 점수 확인
- 연속 학습 streak 관리
- 하루 최대 3세션 제한

### 교사 기능

- 이메일 인증 기반 회원가입 및 로그인
- 학급 생성 및 `join_code` 발급
- 학생별 수준, 취약 영역, streak 확인
- 최근 학습 추이 확인
- 학생 난이도 수동 조정

## 문제 해결 방식

기존 문해력 학습은 정답 여부 중심으로 끝나는 경우가 많습니다.  
이 프로젝트는 정답을 맞혔는지뿐 아니라, 학생이 왜 그렇게 생각했는지, 어떤 단어를 활용했는지, 문장과 문맥을 어떻게 연결했는지를 대화 기반으로 드러내도록 설계했습니다.

이를 위해 세 가지 요소를 결합합니다.

- 객관식 문항으로 기초 진단 수행
- AI 또래 토의로 사고 과정을 유도
- 세션 종료 후 다면 평가로 개인별 취약 영역 분석

## 세션 플로우

```text
세션 시작
  -> 지문 읽기
  -> 객관식 3문항 풀이
  -> AI 그룹 토의 (최대 10라운드)
  -> 세션 종료
  -> 점수 저장 및 streak 갱신
```

### 객관식 문항 구성

- 정보 파악 1문항
- 추론 1문항
- 어휘 1문항

### 그룹 토의 구성

- 모더레이터: 발언 기회 분배, 토의 진행
- 또래 A: 적극적으로 의견 제시
- 또래 B: 질문 중심 반응
- 학생: 자신의 생각과 근거를 직접 표현

## 점수 체계

학생 평가는 객관식 결과와 토의 발화를 함께 반영합니다.

| 평가 영역 | 구성 |
| --- | --- |
| 추론력 | 추론 문항 정오답 + 토의 중 근거 제시 |
| 어휘력 | 어휘 문항 정오답 + 발화 내 어휘 다양성 |
| 맥락 파악 | 정보 파악 문항 정오답 + 문장 간 연결 능력 |

최근 3세션 평균 점수를 기준으로 학생 level이 자동 재조정되며, 교사가 수동 설정한 경우에는 자동 조정이 비활성화됩니다.

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | Vue 3, Vite |
| Backend | FastAPI, Python |
| Database/Auth | Supabase, Postgres, Supabase Auth |
| LLM | OpenAI API |
| Frontend Deploy | Vercel |
| Backend Deploy | GCP Cloud Run |
| Scheduler | GCP Cloud Scheduler |

## 시스템 구조

```text
Teacher Dashboard
        |
        v
  Frontend (Vue 3)
        |
        v
 Backend API (FastAPI)
   |        |        |
   |        |        +-> OpenAI API
   |        |
   |        +-> Supabase Auth
   |
   +-> Supabase Postgres
```

## 데이터 구조 요약

```text
teachers
  -> classrooms
      -> students
          -> sessions
              -> messages
              -> question_results
              -> passages
```

## API 개요

### 교사

- `POST /api/v1/auth/teacher/signup`
- `POST /api/v1/auth/teacher/verify`
- `POST /api/v1/auth/teacher/login`
- `POST /api/v1/auth/teacher/reset-password`
- `GET /api/v1/teacher/classrooms`
- `POST /api/v1/teacher/classrooms`
- `GET /api/v1/teacher/classrooms/{id}/dashboard`
- `PATCH /api/v1/teacher/students/{id}/level`

### 학생

- `POST /api/v1/auth/student/join`
- `GET /api/v1/student/me`
- `POST /api/v1/student/sessions`
- `POST /api/v1/student/sessions/{id}/answer`
- `POST /api/v1/student/sessions/{id}/discussion`
- `POST /api/v1/student/sessions/{id}/end`
- `DELETE /api/v1/student/sessions/{id}`
- `GET /api/v1/student/me/history`

## 기대 효과

- 학생별 문해력 취약 영역을 더 세밀하게 진단
- 정답 중심 학습이 아닌 사고 과정 중심 학습 유도
- 교사가 학급 전체와 개별 학생 상태를 빠르게 파악
- 반복 학습과 streak 시스템을 통한 학습 습관 형성

## 프로젝트 폴더 구조

```text
.
├─ .docs/
│  └─ PRD.md
├─ backend/
└─ frontend/
```

## 문서

- 기획 문서: [`./.docs/PRD.md`](./.docs/PRD.md)

## 향후 개발 범위

- 학생용 학습 세션 UI 구현
- 교사용 대시보드 구현
- OpenAI 기반 토의 에이전트 구성
- Supabase 데이터 모델 및 인증 연결
- SSE 기반 실시간 토의 스트리밍 구현

## License

공모전 제출용 프로젝트입니다. 별도 라이선스 정책은 팀 합의에 따라 추가할 수 있습니다.

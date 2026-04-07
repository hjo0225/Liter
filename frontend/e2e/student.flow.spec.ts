import { test, expect } from '@playwright/test'
import { mockStudentRoutes, mockDiscussionSSE } from './helpers/routes'
import { injectStudentAuth, clearAuth } from './helpers/auth'
import {
  MOCK_SSE_ROUND1,
  MOCK_SSE_ROUND2_FINAL,
  MOCK_SSE_QUICK_FINAL,
  MOCK_END_SESSION_RESPONSE,
} from './fixtures/mock-data'

// ─────────────────────────────────────────────
// 학생 플로우 E2E 테스트
// ─────────────────────────────────────────────

test.describe('학생 플로우', () => {
  test.beforeEach(async ({ page }) => {
    // 페이지 로드 전에 localStorage를 초기화한다 (addInitScript는 goto 이전에 실행)
    await page.addInitScript(() => localStorage.clear())
  })

  // ──────── 1. 학급 입장 (Onboarding) ────────

  test('1. 학급 코드 + 이름 입력 → /student/home 이동', async ({ page }) => {
    await mockStudentRoutes(page)
    await page.goto('/student/join')

    // 6자리 코드 입력 (소문자 → 자동 대문자 변환 확인)
    const codeInput = page.locator('input[maxlength="6"]')
    await codeInput.fill('abc123')
    await expect(codeInput).toHaveValue('ABC123')

    // 이름 입력
    await page.locator('input[maxlength="20"]').fill('테스트학생')

    // 제출
    await page.locator('button[type="submit"]').click()

    // /student/home으로 이동 + JWT 저장 확인
    await expect(page).toHaveURL('/student/home')
    const token = await page.evaluate(() => localStorage.getItem('liter_student_token'))
    expect(token).toBeTruthy()
  })

  test('1a. 잘못된 코드(404) → 에러 메시지, 페이지 유지', async ({ page }) => {
    await page.route('**/api/v1/auth/student/join', (route) =>
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'CLASSROOM_NOT_FOUND' }),
      }),
    )
    await page.goto('/student/join')
    await page.locator('input[maxlength="6"]').fill('WRONG1')
    await page.locator('input[maxlength="20"]').fill('학생')
    await page.locator('button[type="submit"]').click()

    await expect(page.locator('text=올바른 학급 코드')).toBeVisible()
    await expect(page).toHaveURL('/student/join')
  })

  // ──────── 2. 홈 화면 ────────

  test('2. 홈 화면 — streak·오늘 학습 현황 표시', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await page.goto('/student/home')

    // 학생 이름 표시
    await expect(page.locator('text=테스트학생')).toBeVisible()
    // streak 표시
    await expect(page.locator('text=3').first()).toBeVisible()
    // 학습 시작 버튼 존재
    await expect(page.locator('button:has-text("학습 시작")')).toBeVisible()
  })

  test('2a. 인증 없이 /student/home 접근 → /student/join 리다이렉트', async ({ page }) => {
    await page.goto('/student/home')
    await expect(page).toHaveURL('/student/join')
  })

  test('2b. 오늘 3회 완료 → "오늘은 여기까지" 표시, 학습 시작 숨김', async ({ page }) => {
    await injectStudentAuth(page)
    await page.route('**/api/v1/student/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          name: '테스트학생',
          level: 2,
          streak_count: 3,
          today_session_count: 3,
          classroom_name: '5학년 2반',
          weak_areas: ['reasoning'],
          recent_average_score: 7.4,
          weekly_completed_count: 4,
          total_completed_count: 19,
        }),
      }),
    )
    await page.route('**/api/v1/student/sessions/today-count', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 3 }),
      }),
    )
    await page.goto('/student/home')

    await expect(page.locator('text=오늘은 여기까지')).toBeVisible()
    await expect(page.locator('button:has-text("학습 시작")')).not.toBeVisible()
  })

  // ──────── 3. 지문 읽기 (Reading Phase) ────────

  test('3. 학습 시작 → 지문 제목·내용 표시 → "다 읽었어요" → MCQ 전환', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await page.goto('/student/home')

    await page.locator('button:has-text("학습 시작")').click()
    await expect(page).toHaveURL('/student/session')

    // 지문 제목·내용 확인
    await expect(page.locator('text=광합성의 비밀')).toBeVisible()
    await expect(page.locator('text=식물은 햇빛을 이용해')).toBeVisible()

    // 다 읽었어요 클릭 → MCQ
    await page.locator('button:has-text("다 읽었어요")').click()
    await expect(page.locator('text=문제 1 / 3')).toBeVisible()
    await expect(page.locator('text=광합성이 일어나는 장소는')).toBeVisible()
  })

  // ──────── 4. 객관식 (MCQ Phase) ────────

  test('4. 3문제 순서대로 답변 → 토의 페이지 이동', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await mockDiscussionSSE(page, MOCK_SSE_QUICK_FINAL)
    await page.goto('/student/home')
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()

    // Q1: 3번째 선택지 (잎)
    await expect(page.locator('text=문제 1 / 3')).toBeVisible()
    await page.locator('div.flex.flex-col.gap-2 button').nth(2).click()
    await page.locator('button:has-text("확인")').click()

    // Q2
    await expect(page.locator('text=문제 2 / 3')).toBeVisible()
    await page.locator('div.flex.flex-col.gap-2 button').nth(1).click()
    await page.locator('button:has-text("확인")').click()

    // Q3
    await expect(page.locator('text=문제 3 / 3')).toBeVisible()
    await page.locator('div.flex.flex-col.gap-2 button').nth(0).click()
    await page.locator('button:has-text("확인")').click()

    // 마지막 문제 제출 후 토의 페이지
    await expect(page).toHaveURL('/student/discussion')
  })

  test('4a. 선택지 미선택 시 확인 버튼 비활성화', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await page.goto('/student/home')
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()

    await expect(page.locator('button:has-text("확인")')).toBeDisabled()
  })

  test('4b. "이전 단계" → 지문 읽기 복귀', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await page.goto('/student/home')
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()

    await expect(page.locator('text=문제 1 / 3')).toBeVisible()
    await page.locator('button:has-text("이전 단계")').click()
    await expect(page.locator('button:has-text("다 읽었어요")')).toBeVisible()
  })

  // ──────── 5. 토의 (Discussion - SSE) ────────

  test('5. 토의 — SSE 메시지 수신 + is_final → /student/result', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await mockDiscussionSSE(page, MOCK_SSE_QUICK_FINAL)
    await page.goto('/student/home')

    // 전체 플로우 진행
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()
    for (let i = 0; i < 3; i++) {
      await page.locator('div.flex.flex-col.gap-2 button').first().click()
      await page.locator('button:has-text("확인")').click()
    }

    // 토의 페이지
    await expect(page).toHaveURL('/student/discussion')

    // AI 메시지 수신 확인
    await expect(page.locator('text=오늘 광합성에 대해 잘 공부했어요')).toBeVisible({ timeout: 10_000 })

    // is_final → endSession(1500ms) → /student/result
    await expect(page).toHaveURL('/student/result', { timeout: 10_000 })
  })

  test('5a. 토의 — 사용자 입력 차례 → 메시지 전송 → is_final', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)

    // 첫 번째 호출: next_speaker:user 포함
    await mockDiscussionSSE(page, MOCK_SSE_ROUND1)

    await page.goto('/student/home')
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()
    for (let i = 0; i < 3; i++) {
      await page.locator('div.flex.flex-col.gap-2 button').first().click()
      await page.locator('button:has-text("확인")').click()
    }

    await expect(page).toHaveURL('/student/discussion')
    // 모더레이터 메시지 수신
    await expect(
      page.locator('text=오늘 지문에서 광합성에 대해 배웠는데'),
    ).toBeVisible({ timeout: 10_000 })

    // 사용자 입력 차례: 입력창 활성화
    const input = page.locator('input[placeholder*="의견"]')
    await expect(input).toBeEnabled({ timeout: 5_000 })

    // 두 번째 SSE 세팅 후 메시지 전송
    await mockDiscussionSSE(page, MOCK_SSE_ROUND2_FINAL)
    await input.fill('엽록체가 정말 신기해요!')
    await input.press('Enter')

    // is_final → /student/result
    await expect(page).toHaveURL('/student/result', { timeout: 15_000 })
  })

  // ──────── 6. 결과 페이지 ────────

  test('6. 결과 페이지 — 점수·피드백 표시 → "다음 학습 하러 가기"', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await mockDiscussionSSE(page, MOCK_SSE_QUICK_FINAL)

    // 전체 플로우로 result에 도달
    await page.goto('/student/home')
    await page.locator('button:has-text("학습 시작")').click()
    await page.locator('button:has-text("다 읽었어요")').click()
    for (let i = 0; i < 3; i++) {
      await page.locator('div.flex.flex-col.gap-2 button').first().click()
      await page.locator('button:has-text("확인")').click()
    }
    await expect(page).toHaveURL('/student/result', { timeout: 15_000 })

    // 점수 카드 (여러 요소가 있을 수 있으므로 first() 사용)
    await expect(page.locator('text=추론력').first()).toBeVisible()
    await expect(page.locator('text=어휘력').first()).toBeVisible()
    await expect(page.locator('text=맥락파악').first()).toBeVisible()
    // 피드백
    await expect(page.locator('text=오늘 광합성에 대해 깊이 생각해줬어요')).toBeVisible()

    // 다음 학습 → 홈
    await mockStudentRoutes(page)
    await page.locator('button:has-text("다음 학습 하러 가기")').click()
    await expect(page).toHaveURL('/student/home')
  })

  test('6a. 점수 없이 /student/result 직접 접근 → /student/home 리다이렉트', async ({ page }) => {
    await injectStudentAuth(page)
    await mockStudentRoutes(page)
    await page.goto('/student/result')

    await expect(page).toHaveURL('/student/home')
  })
})

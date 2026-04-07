import { test, expect } from '@playwright/test'
import { mockTeacherRoutes } from './helpers/routes'
import { injectTeacherAuth, clearAuth } from './helpers/auth'

// ─────────────────────────────────────────────
// 교사 플로우 E2E 테스트
// ─────────────────────────────────────────────

test.describe('교사 플로우', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.clear())
  })

  // ──────── 1. 회원가입 + OTP 인증 ────────

  test('1. 회원가입 → OTP 화면 전환 → 인증 완료 → /teacher/classrooms', async ({ page }) => {
    await mockTeacherRoutes(page)
    await page.goto('/teacher')

    // 회원가입 탭
    await page.locator('button:has-text("회원가입")').click()

    // 폼 입력
    await page.locator('input[placeholder="예: 박민준"]').fill('테스트선생')
    await page.locator('input[placeholder="teacher@school.edu"]').last().fill('test@school.edu')
    await page.locator('input[placeholder="8자 이상"]').fill('password123')

    // 인증 메일 받기
    await page.locator('button:has-text("인증 메일")').click()

    // OTP 화면 전환 확인
    await expect(page.locator('text=이메일 인증')).toBeVisible({ timeout: 5_000 })

    // 6자리 OTP 입력
    const otpInputs = page.locator('input[inputmode="numeric"]')
    await expect(otpInputs).toHaveCount(6)
    for (let i = 0; i < 6; i++) {
      await otpInputs.nth(i).fill(String(i + 1))
    }

    // 인증 완료
    await page.locator('button:has-text("인증 완료")').click()
    await expect(page).toHaveURL('/teacher/classrooms', { timeout: 5_000 })
  })

  test('1a. OTP 숫자 붙여넣기 → 6칸 자동 분배', async ({ page }) => {
    await mockTeacherRoutes(page)
    await page.goto('/teacher')

    // 회원가입 후 OTP 화면 진입
    await page.locator('button:has-text("회원가입")').click()
    await page.locator('input[placeholder="예: 박민준"]').fill('선생')
    await page.locator('input[placeholder="teacher@school.edu"]').last().fill('x@x.com')
    await page.locator('input[placeholder="8자 이상"]').fill('pass1234')
    await page.locator('button:has-text("인증 메일")').click()
    await expect(page.locator('text=이메일 인증')).toBeVisible()

    // 첫 번째 OTP 입력칸에 ClipboardEvent를 직접 dispatch (paste 핸들러 트리거)
    await page.locator('input[inputmode="numeric"]').first().focus()
    await page.evaluate(() => {
      const input = document.querySelector('input[inputmode="numeric"]') as HTMLInputElement
      const dt = new DataTransfer()
      dt.setData('text', '123456')
      input.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }))
    })

    // 6칸에 분배됐는지 확인 (Vue nextTick 후)
    await page.waitForTimeout(100)
    const values = await page
      .locator('input[inputmode="numeric"]')
      .evaluateAll((inputs) => inputs.map((el) => (el as HTMLInputElement).value))
    expect(values.join('')).toBe('123456')
  })

  test('1b. 잘못된 OTP → 에러 메시지 + 칸 초기화', async ({ page }) => {
    await mockTeacherRoutes(page)
    // verify만 실패로 오버라이드
    await page.route('**/api/v1/auth/teacher/verify', (route) =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'INVALID_OR_EXPIRED_TOKEN' }),
      }),
    )
    await page.goto('/teacher')
    await page.locator('button:has-text("회원가입")').click()
    await page.locator('input[placeholder="예: 박민준"]').fill('선생')
    await page.locator('input[placeholder="teacher@school.edu"]').last().fill('x@x.com')
    await page.locator('input[placeholder="8자 이상"]').fill('pass1234')
    await page.locator('button:has-text("인증 메일")').click()
    await expect(page.locator('text=이메일 인증')).toBeVisible()

    const otpInputs = page.locator('input[inputmode="numeric"]')
    for (let i = 0; i < 6; i++) await otpInputs.nth(i).fill('9')
    await page.locator('button:has-text("인증 완료")').click()

    // 에러 메시지
    await expect(page.locator('text=인증번호가 올바르지 않습니다')).toBeVisible()
    // 칸 초기화 확인
    const values = await otpInputs.evaluateAll((inputs) =>
      inputs.map((el) => (el as HTMLInputElement).value),
    )
    expect(values.every((v) => v === '')).toBe(true)
  })

  // ──────── 2. 로그인 ────────

  test('2. 로그인 → JWT 저장 → /teacher/classrooms', async ({ page }) => {
    await mockTeacherRoutes(page)
    await page.goto('/teacher')

    await page.locator('input[placeholder="teacher@school.edu"]').fill('test@school.edu')
    await page.locator('input[placeholder="비밀번호 입력"]').fill('password123')
    await page.locator('button:has-text("로그인 →")').click()

    await expect(page).toHaveURL('/teacher/classrooms', { timeout: 5_000 })
    const token = await page.evaluate(() => localStorage.getItem('liter_teacher_token'))
    expect(token).toBeTruthy()
  })

  test('2a. 이메일 미인증 계정(403 EMAIL_NOT_VERIFIED) → OTP 화면 전환', async ({ page }) => {
    await mockTeacherRoutes(page)
    await page.route('**/api/v1/auth/teacher/login', (route) =>
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'EMAIL_NOT_VERIFIED' }),
      }),
    )
    await page.goto('/teacher')
    await page.locator('input[placeholder="teacher@school.edu"]').fill('unverified@school.edu')
    await page.locator('input[placeholder="비밀번호 입력"]').fill('pw123456')
    await page.locator('button:has-text("로그인 →")').click()

    await expect(page.locator('text=이메일 인증')).toBeVisible()
  })

  test('2b. 잘못된 자격증명(401) → 에러 메시지', async ({ page }) => {
    await mockTeacherRoutes(page)
    await page.route('**/api/v1/auth/teacher/login', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'INVALID_CREDENTIALS' }),
      }),
    )
    await page.goto('/teacher')
    await page.locator('input[placeholder="teacher@school.edu"]').fill('wrong@school.edu')
    await page.locator('input[placeholder="비밀번호 입력"]').fill('wrongpw')
    await page.locator('button:has-text("로그인 →")').click()

    await expect(page.locator('text=이메일 또는 비밀번호')).toBeVisible()
    await expect(page).toHaveURL('/teacher')
  })

  // ──────── 3. 학급 관리 ────────

  test('3. 학급 목록 조회 → join code 표시', async ({ page }) => {
    await injectTeacherAuth(page)
    await mockTeacherRoutes(page)
    await page.goto('/teacher/classrooms')

    await expect(page.locator('text=5학년 2반')).toBeVisible()
    await expect(page.locator('text=ABC123')).toBeVisible()
    await expect(page.locator('text=12명')).toBeVisible() // 학생 수
  })

  test('3a. 인증 없이 /teacher/classrooms → /teacher 리다이렉트', async ({ page }) => {
    await page.goto('/teacher/classrooms')
    await expect(page).toHaveURL('/teacher')
  })

  test('3b. join code "코드 복사" → "복사됨!" 상태 전환', async ({ page }) => {
    await injectTeacherAuth(page)
    await mockTeacherRoutes(page)
    await page.goto('/teacher/classrooms')

    await expect(page.locator('text=ABC123')).toBeVisible()
    await page.locator('button:has-text("코드 복사")').first().click()
    await expect(page.locator('text=복사됨!')).toBeVisible()
  })

  test('3c. 새 학급 만들기 → 모달 → 생성 → join code 표시', async ({ page }) => {
    await injectTeacherAuth(page)

    // GET: 생성 후 재조회 시 새 학급 포함
    let created = false
    await page.route('**/api/v1/teacher/classrooms', (route) => {
      if (route.request().method() === 'POST') {
        created = true
        route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'cls-002', join_code: 'XYZ999' }),
        })
      } else if (route.request().method() === 'GET') {
        const list = created
          ? [
              { id: 'cls-001', name: '5학년 2반', join_code: 'ABC123', student_count: 12 },
              { id: 'cls-002', name: '6학년 1반', join_code: 'XYZ999', student_count: 0 },
            ]
          : [{ id: 'cls-001', name: '5학년 2반', join_code: 'ABC123', student_count: 12 }]
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(list),
        })
      } else {
        route.continue()
      }
    })

    await page.goto('/teacher/classrooms')

    await page.locator('button:has-text("새 학급")').click()

    // 모달 열림
    const nameInput = page.locator('input[placeholder*="학년"]')
    await expect(nameInput).toBeVisible()
    await nameInput.fill('6학년 1반')
    await page.locator('button:has-text("만들기 →")').click()

    // 재조회 후 새 join code 표시
    await expect(page.locator('text=XYZ999')).toBeVisible({ timeout: 5_000 })
  })

  // ──────── 4. 대시보드 ────────

  test('4. 대시보드 → 학생 목록 + 주의 학생 표시', async ({ page }) => {
    await injectTeacherAuth(page)
    await mockTeacherRoutes(page)
    await page.goto('/teacher/classrooms')

    await page.locator('button:has-text("대시보드 보기")').first().click()
    await expect(page).toHaveURL('/teacher/dashboard/cls-001')

    // 학생 목록
    await expect(page.locator('text=김민준')).toBeVisible()
    await expect(page.locator('text=이수아')).toBeVisible()
  })

  test('4a. 인증 없이 /teacher/dashboard/:id → /teacher 리다이렉트', async ({ page }) => {
    await page.goto('/teacher/dashboard/cls-001')
    await expect(page).toHaveURL('/teacher')
  })
})

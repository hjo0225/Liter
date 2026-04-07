import type { Page } from '@playwright/test'
import {
  MOCK_JOIN_RESPONSE,
  MOCK_ME_RESPONSE,
  MOCK_SESSION_RESPONSE,
  MOCK_ANSWER_RESPONSE,
  MOCK_END_SESSION_RESPONSE,
  MOCK_TEACHER_CLASSROOMS,
  MOCK_CLASSROOM_CREATE_RESPONSE,
  MOCK_DASHBOARD_RESPONSE,
} from '../fixtures/mock-data'

const API = '**/api/v1'

// TeacherAuthPage.vue는 로그인/인증 응답 JWT를 atob()로 디코딩한다.
// Node.js Buffer로 올바른 base64url 인코딩 토큰을 생성한다.
function makeTeacherJwt() {
  const header = Buffer.from('{"alg":"HS256","typ":"JWT"}').toString('base64url')
  const payload = Buffer.from(
    JSON.stringify({
      sub: 'tea-001',
      user_metadata: { name: 'teacher' },
      exp: 9999999999,
    }),
  ).toString('base64url')
  return `${header}.${payload}.fake`
}

export const TEACHER_JWT = makeTeacherJwt()

export async function mockStudentRoutes(page: Page) {
  await page.route(`${API}/auth/student/join`, (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_JOIN_RESPONSE),
    }),
  )

  await page.route(`${API}/student/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ME_RESPONSE),
    }),
  )

  await page.route(`${API}/student/sessions/today-count`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 0 }),
    }),
  )

  await page.route(`${API}/student/sessions`, (route) => {
    if (route.request().method() === 'POST') {
      route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SESSION_RESPONSE),
      })
    } else {
      route.continue()
    }
  })

  await page.route(`${API}/student/sessions/ses-001/answer`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ANSWER_RESPONSE),
    }),
  )

  await page.route(`${API}/student/sessions/ses-001/end`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_END_SESSION_RESPONSE),
    }),
  )

  await page.route(`${API}/student/sessions/ses-001`, (route) => {
    if (route.request().method() === 'DELETE') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    } else {
      route.continue()
    }
  })
}

/**
 * SSE 토의 엔드포인트를 모킹한다.
 * StudentDiscussion.vue의 fetch + ReadableStream reader 루프가
 * 단일 버퍼를 받아도 모든 이벤트를 처리한다.
 */
export async function mockDiscussionSSE(page: Page, sseBody: string) {
  await page.route(`${API}/student/sessions/ses-001/discussion`, (route) =>
    route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
      body: sseBody,
    }),
  )
}

export async function mockTeacherRoutes(page: Page) {
  await page.route(`${API}/auth/teacher/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: TEACHER_JWT }),
    }),
  )

  await page.route(`${API}/auth/teacher/signup`, (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    }),
  )

  await page.route(`${API}/auth/teacher/verify`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: TEACHER_JWT }),
    }),
  )

  await page.route(`${API}/auth/teacher/resend`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    }),
  )

  await page.route(`${API}/teacher/classrooms`, (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_TEACHER_CLASSROOMS),
      })
    } else if (route.request().method() === 'POST') {
      route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CLASSROOM_CREATE_RESPONSE),
      })
    } else {
      route.continue()
    }
  })

  await page.route(`${API}/teacher/classrooms/cls-001/dashboard`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_DASHBOARD_RESPONSE),
    }),
  )

  await page.route(`${API}/teacher/students/**/level`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    }),
  )
}

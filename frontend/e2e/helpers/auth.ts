import type { Page } from '@playwright/test'
import {
  MOCK_STUDENT_TOKEN,
  MOCK_STUDENT_INFO,
  MOCK_TEACHER_TOKEN,
  MOCK_TEACHER_INFO,
} from '../fixtures/mock-data'

/**
 * 페이지 로드 전에 localStorage에 학생 토큰을 주입한다.
 * addInitScript를 사용하므로 반드시 page.goto() 이전에 호출해야 한다.
 */
export async function injectStudentAuth(page: Page) {
  await page.addInitScript(
    ({ token, info }) => {
      localStorage.setItem('liter_student_token', token)
      localStorage.setItem('liter_student_info', JSON.stringify(info))
    },
    { token: MOCK_STUDENT_TOKEN, info: MOCK_STUDENT_INFO },
  )
}

/**
 * 페이지 로드 전에 localStorage에 교사 토큰을 주입한다.
 */
export async function injectTeacherAuth(page: Page) {
  await page.addInitScript(
    ({ token, info }) => {
      localStorage.setItem('liter_teacher_token', token)
      localStorage.setItem('liter_teacher_info', JSON.stringify(info))
    },
    { token: MOCK_TEACHER_TOKEN, info: MOCK_TEACHER_INFO },
  )
}

/**
 * localStorage의 모든 인증 데이터를 제거한다.
 * 페이지가 이미 로드된 상태에서 호출한다.
 */
export async function clearAuth(page: Page) {
  await page.evaluate(() => {
    localStorage.removeItem('liter_student_token')
    localStorage.removeItem('liter_student_info')
    localStorage.removeItem('liter_teacher_token')
    localStorage.removeItem('liter_teacher_info')
  })
}

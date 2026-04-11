/**
 * useDiscussionStream — P6 아키텍처 (지속 GET SSE + POST /turns)
 *
 * 연결 구조:
 *   GET  /sessions/{id}/discussion?token=JWT  → 세션 전체 지속 EventSource
 *   POST /sessions/{id}/discussion/turns       → 학생 발화 단독 전송 (202)
 *
 * EventSource를 직접 사용하지 않고 fetch + ReadableStream을 쓰는 이유:
 *   - CORS preflight 없이 토큰을 URL에 노출하기 싫을 경우 대안 가능
 *   - 재연결 시 정확한 타이밍 제어 (지수 백오프 1s → 2s → 4s)
 *
 * 처리하는 이벤트 유형 (11가지):
 *  1. event=turn_start      — AI 발화 시작 (스트리밍)
 *  2. event=token           — 텍스트 청크
 *  3. event=turn_end        — AI 발화 완료 (스트리밍)
 *  4. type=turn_end         — 마무리 발화 (close, 단일 완성본)
 *  5. type=waiting_for_user — 학생 입력 대기
 *  6. type=is_final         — 세션 종료
 *  7. type=scores           — 점수 데이터 (무시: /end 엔드포인트에서 처리)
 *  8. type=round_change     — 라운드 전환 (데모 모드)
 *  9. type=heartbeat        — keepalive (무시)
 * 10. type=error            — 서버 오류
 * 11. unknown               — 미지 이벤트 (무시)
 */

import { onUnmounted } from 'vue'
import { useDiscussionStore } from '@/stores/discussion'
import { useStudentStore } from '@/stores/student'
import { API_BASE_URL } from '@/api/config'

const MAX_RETRIES = 3
const BACKOFF_BASE_MS = 1_000   // 1s → 2s → 4s

export function useDiscussionStream(sessionId: string) {
  const ds = useDiscussionStore()
  const studentStore = useStudentStore()

  let abort: AbortController | null = null
  let retryCount = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  // ── 이벤트 디스패처 ──────────────────────────────────────
  function dispatch(raw: string) {
    let ev: Record<string, unknown>
    try { ev = JSON.parse(raw) } catch { return }

    const evType = ev.event as string | undefined   // 스트리밍 turn 이벤트
    const msgType = ev.type as string | undefined   // 오케스트레이터 제어 이벤트

    if (evType === 'turn_start') {
      // 1. 스트리밍 발화 시작
      ds.onTurnStart(ev.speaker as any, ev.turn_id as string, ev.round as number)

    } else if (evType === 'token') {
      // 2. 텍스트 청크
      ds.onToken(ev.text as string)

    } else if (evType === 'turn_end') {
      // 3. 스트리밍 발화 완료
      ds.onTurnEnd(ev.full_text as string, ev.round as number)

    } else if (msgType === 'turn_end') {
      // 4. close 마무리 발화 (단일 완성본 — content 필드 사용)
      ds.onLegacyMessage(ev.speaker as any, ev.content as string, ev.round as number)

    } else if (msgType === 'waiting_for_user') {
      // 5. 학생 입력 대기
      ds.onWaitForUser(ev.round as number)

    } else if (msgType === 'is_final') {
      // 6. 세션 종료
      ds.onFinal()

    } else if (msgType === 'error') {
      // 10. 서버 오류
      ds.onError(typeof ev.message === 'string' ? ev.message : undefined)

    } else if (msgType === 'round_change') {
      // 8. 데모 모드 라운드 전환 → round 갱신
      ds.onRoundChange(ev.to_round as number)
    }
    // 7(scores) / 9(heartbeat) / 11(unknown) → 무시
  }

  // ── SSE 스트림 리더 ──────────────────────────────────────
  async function _readStream(response: Response): Promise<'done' | 'network_error'> {
    if (!response.body) return 'network_error'
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) return 'done'

        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw) dispatch(raw)
        }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return 'done'
      return 'network_error'
    } finally {
      reader.releaseLock()
    }
  }

  // ── GET SSE 연결 ──────────────────────────────────────────
  async function connect() {
    if (destroyed) return

    abort?.abort()
    abort = new AbortController()
    ds.startLoading()

    const token = studentStore.token ?? ''
    const url = `${API_BASE_URL}/student/sessions/${sessionId}/discussion?token=${encodeURIComponent(token)}`

    let response: Response
    try {
      response = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'text/event-stream' },
        signal: abort.signal,
      })
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      _scheduleRetry()
      return
    }

    if (!response.ok) {
      ds.onError()
      return
    }

    const result = await _readStream(response)
    if (result === 'network_error' && !destroyed) {
      _scheduleRetry()
    } else {
      retryCount = 0
    }
  }

  // ── 지수 백오프 재연결 ───────────────────────────────────
  function _scheduleRetry() {
    if (destroyed || retryCount >= MAX_RETRIES) {
      ds.onError('연결이 끊어졌어요. 새로고침 후 다시 시도해주세요.')
      return
    }
    const delay = BACKOFF_BASE_MS * Math.pow(2, retryCount)  // 1s, 2s, 4s
    retryCount++
    retryTimer = setTimeout(() => { if (!destroyed) connect() }, delay)
  }

  // ── 학생 발화 전송 (POST /discussion/turns) ──────────────
  async function sendTurn(text: string): Promise<boolean> {
    const token = studentStore.token
    try {
      const res = await fetch(
        `${API_BASE_URL}/student/sessions/${sessionId}/discussion/turns`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ text, client_ts: new Date().toISOString() }),
        },
      )
      if (res.status === 409) {
        // 아직 학생 차례가 아님 — 조용히 무시
        return false
      }
      if (!res.ok) {
        ds.onError('발화 전송에 실패했어요. 다시 시도해주세요.')
        return false
      }
      ds.startLoading()   // 다음 AI 턴이 올 때까지 로딩 표시
      return true
    } catch {
      ds.onError('네트워크 오류가 발생했어요.')
      return false
    }
  }

  // ── 연결 해제 ────────────────────────────────────────────
  function disconnect() {
    destroyed = true
    abort?.abort()
    if (retryTimer !== null) { clearTimeout(retryTimer); retryTimer = null }
  }

  onUnmounted(disconnect)

  return { connect, sendTurn, disconnect }
}

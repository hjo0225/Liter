import { defineStore } from 'pinia'
import { ref } from 'vue'
import { type DisplayMessage, type Speaker } from '@/components/discussion/types'

export { type DisplayMessage, type Speaker }

export const useDiscussionStore = defineStore('discussion', () => {
  // ── 화면 표시용 메시지 배열 ────────────────────────────────
  const bubbles = ref<DisplayMessage[]>([])

  // ── 진행 중 발화 (스트리밍 중) ────────────────────────────
  const currentTurn = ref<{
    speaker: Speaker | null
    partial_text: string
    turn_id: string | null
    round: number
  }>({ speaker: null, partial_text: '', turn_id: null, round: 1 })

  // ── UI 상태 ───────────────────────────────────────────────
  const inputEnabled = ref(false)         // 입력창 활성화
  const userIdleSeconds = ref(0)          // 침묵 시각화용
  const round = ref(1)
  const isFinal = ref(false)
  const error = ref<string | null>(null)
  const isLoading = ref(false)            // 연결 중 / 디렉터 대기 → 로딩 점 표시

  let _idCounter = 0
  let _pendingId: number | null = null    // 현재 스트리밍 중인 bubble id
  let _idleTimer: ReturnType<typeof setInterval> | null = null

  // ── P8: 토큰 출력 속도 조절 (50~80ms 간격) ───────────────
  let _tokenQueue: string[] = []
  let _drainTimer: ReturnType<typeof setInterval> | null = null
  let _typingTimer: ReturnType<typeof setTimeout> | null = null

  function _startDrain() {
    if (_drainTimer !== null) return
    _drainTimer = setInterval(() => {
      if (_tokenQueue.length === 0) return
      const chunk = _tokenQueue.shift()!
      if (_pendingId !== null) {
        const b = bubbles.value.find(b => b.id === _pendingId)
        if (b) {
          b.isTyping = false
          b.content += chunk
        }
      }
    }, 60)  // 60ms ≈ 50~80ms 중간값
  }

  function _stopDrain() {
    if (_drainTimer !== null) { clearInterval(_drainTimer); _drainTimer = null }
    if (_typingTimer !== null) { clearTimeout(_typingTimer); _typingTimer = null }
    _tokenQueue = []
  }

  const _nextId = () => ++_idCounter

  // ── idle timer ─────────────────────────────────────────────
  function _startIdleTimer() {
    _stopIdleTimer()
    userIdleSeconds.value = 0
    _idleTimer = setInterval(() => { userIdleSeconds.value++ }, 1000)
  }

  function _stopIdleTimer() {
    if (_idleTimer !== null) { clearInterval(_idleTimer); _idleTimer = null }
    userIdleSeconds.value = 0
  }

  // ── 이벤트 핸들러 ─────────────────────────────────────────

  /** fetch 시작 직전 — 로딩 점 표시 */
  function startLoading() {
    isLoading.value = true
    error.value = null
  }

  /**
   * 1. turn_start: 빈 bubble 생성, 0.5~1.5s 타이핑 인디케이터 후 토큰 drain 시작.
   */
  function onTurnStart(speaker: Speaker, turnId: string, r: number) {
    isLoading.value = false
    _stopIdleTimer()
    _stopDrain()
    inputEnabled.value = false
    round.value = r

    const id = _nextId()
    _pendingId = id
    currentTurn.value = { speaker, partial_text: '', turn_id: turnId, round: r }
    // isTyping: true → 타이핑 인디케이터 표시
    bubbles.value.push({ id, speaker, content: '', round: r, isTyping: true })

    // 0.5~1.5s 랜덤 지연 후 토큰 drain 시작
    const delay = 500 + Math.random() * 1000
    _typingTimer = setTimeout(() => {
      _typingTimer = null
      _startDrain()
    }, delay)
  }

  /**
   * 2. token: 큐에 적재 (drain 타이머가 꺼내서 출력).
   */
  function onToken(text: string) {
    currentTurn.value.partial_text += text
    _tokenQueue.push(text)
  }

  /**
   * 3. turn_end: 큐 즉시 비우고 bubble 확정.
   * LLM 스트림이 끝나면 남은 토큰은 한번에 반영한다.
   */
  function onTurnEnd(fullText: string, r: number) {
    _stopDrain()
    if (_pendingId !== null) {
      const b = bubbles.value.find(b => b.id === _pendingId)
      if (b) {
        b.content = fullText   // 드리프트 없이 완성본으로 확정
        b.isTyping = false
      }
      _pendingId = null
    }
    currentTurn.value = { speaker: null, partial_text: '', turn_id: null, round: r }
  }

  /** 4. wait_for_user: 입력창 열기, idle 타이머 시작 */
  function onWaitForUser(r: number) {
    isLoading.value = false
    round.value = r
    inputEnabled.value = true
    _startIdleTimer()
  }

  /** 5. is_final: 세션 종료 */
  function onFinal() {
    isLoading.value = false
    isFinal.value = true
    inputEnabled.value = false
    _stopIdleTimer()
    _stopDrain()
  }

  /** 6. error: 에러 메시지 표시 */
  function onError(msg?: string) {
    isLoading.value = false
    error.value = msg ?? '토의 응답을 생성하지 못했어요. 다시 시도해주세요.'
  }

  /** 7. 구형 단일 이벤트 (close 발화 — speaker+content 형식) */
  function onLegacyMessage(speaker: Speaker, content: string, r: number) {
    isLoading.value = false
    bubbles.value.push({ id: _nextId(), speaker, content, round: r })
    round.value = r
  }

  /** 8. round_change (데모 모드 전용) */
  function onRoundChange(toRound: number) {
    round.value = toRound
  }

  /** 학생 발화 추가 (로컬 즉시 반영) */
  function addUserBubble(content: string, r: number) {
    bubbles.value.push({ id: _nextId(), speaker: 'user', content, round: r })
    inputEnabled.value = false
    _stopIdleTimer()
  }

  function reset() {
    bubbles.value = []
    currentTurn.value = { speaker: null, partial_text: '', turn_id: null, round: 1 }
    inputEnabled.value = false
    round.value = 1
    isFinal.value = false
    error.value = null
    isLoading.value = false
    _idCounter = 0
    _pendingId = null
    _stopIdleTimer()
    _stopDrain()
  }

  return {
    bubbles,
    currentTurn,
    inputEnabled,
    userIdleSeconds,
    round,
    isFinal,
    error,
    isLoading,
    startLoading,
    onTurnStart,
    onToken,
    onTurnEnd,
    onWaitForUser,
    onFinal,
    onError,
    onLegacyMessage,
    onRoundChange,
    addUserBubble,
    reset,
  }
})

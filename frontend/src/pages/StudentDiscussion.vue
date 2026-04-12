<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useStudentStore } from '@/stores/student'
import { useDiscussionStore } from '@/stores/discussion'
import { useDiscussionStream } from '@/composables/useDiscussionStream'
import { API_BASE_URL } from '@/api/config'
import apiClient from '@/api/client'
import DiscussionHeader from '@/components/discussion/DiscussionHeader.vue'
import DiscussionMessageList from '@/components/discussion/DiscussionMessageList.vue'
import DiscussionInput from '@/components/discussion/DiscussionInput.vue'

const MAX_TOPICS = 3

const router = useRouter()
const sessionStore = useSessionStore()
const studentStore = useStudentStore()
const ds = useDiscussionStore()

const inputText = ref('')
const isSending = ref(false)  // POST /turns 전송 중 (이중 제출 방지)
const showTurnModal = ref(false)
let turnModalTimer: ReturnType<typeof setTimeout> | null = null

// 학생 발화턴 모달: inputEnabled true 전환 시 표시
watch(() => ds.inputEnabled, (enabled) => {
  if (enabled && !ds.isFinal) {
    showTurnModal.value = true
    if (turnModalTimer) clearTimeout(turnModalTimer)
    turnModalTimer = setTimeout(() => { showTurnModal.value = false }, 2000)
  }
})

const studentName = computed(() => studentStore.student?.name ?? '나')
const canInterrupt = computed(() => ds.canInterrupt)

const { connect, sendTurn } = useDiscussionStream(sessionStore.sessionId ?? '')

// ── abandon beacon ─────────────────────────────────────────────
function sendAbandonBeacon() {
  if (!sessionStore.sessionId || ds.isFinal) return
  navigator.sendBeacon(
    `${API_BASE_URL}/student/sessions/${sessionStore.sessionId}/abandon`,
    new Blob([JSON.stringify({ token: studentStore.token ?? '' })], { type: 'application/json' }),
  )
}

onMounted(() => {
  if (!sessionStore.sessionId) { router.replace('/student/home'); return }
  ds.reset()
  window.addEventListener('beforeunload', sendAbandonBeacon)
  window.addEventListener('pagehide', sendAbandonBeacon)
  connect()  // GET SSE 지속 연결 시작
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', sendAbandonBeacon)
  window.removeEventListener('pagehide', sendAbandonBeacon)
})

// ── isFinal → 결과 화면 이동 ──────────────────────────────────
watch(() => ds.isFinal, (val) => { if (val) setTimeout(endSession, 1500) })

// ── 학생 발화 전송 ─────────────────────────────────────────────
async function handleSend() {
  if (isSending.value) return
  const content = inputText.value.trim()
  if (!content || ds.isFinal) return

  const isInterrupt = canInterrupt.value && !ds.inputEnabled
  if (!isInterrupt && !ds.inputEnabled) return   // 명시적 대기도 아니고 끼어들기도 아님

  isSending.value = true
  ds.addUserBubble(content, ds.round, isInterrupt)
  sessionStore.addDiscussionMessage({ speaker: 'user', content, round: ds.round })
  inputText.value = ''

  await sendTurn(content, isInterrupt)   // POST /discussion/turns
  isSending.value = false
}

async function endSession() {
  try {
    const res = await apiClient.post(`/student/sessions/${sessionStore.sessionId}/end`)
    studentStore.updateStudent({ streak_count: res.data.streak_count })
    sessionStore.setScores(res.data)
    router.push('/student/result')
  } catch {
    router.push('/student/home')
  }
}
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden" style="background: #F9FAFB;">

    <DiscussionHeader
      :title="sessionStore.passage?.title ?? 'AI 그룹 토의'"
      :round="ds.round"
      :max-rounds="MAX_TOPICS"
    />

    <DiscussionMessageList
      :messages="ds.bubbles"
      :is-loading="ds.isLoading"
      :is-done="ds.isFinal"
      :error="ds.error"
      :student-name="studentName"
    />

    <DiscussionInput
      v-model="inputText"
      :waiting-for-user="ds.inputEnabled"
      :interrupt-enabled="canInterrupt"
      :is-done="ds.isFinal"
      :idle-seconds="ds.userIdleSeconds"
      @send="handleSend"
    />

    <!-- 학생 발화턴 강조 모달 -->
    <Transition name="turn-modal">
      <div
        v-if="showTurnModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
        style="background: rgba(7, 17, 31, 0.45); backdrop-filter: blur(4px);"
        @click="showTurnModal = false"
      >
        <div
          class="flex flex-col items-center gap-3 px-10 py-8 rounded-3xl shadow-lg"
          style="background: white;"
          @click.stop
        >
          <div
            class="w-16 h-16 rounded-full flex items-center justify-center"
            style="background: #EBF4FF;"
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#3182F6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 18.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z"/>
              <path d="M12 8v4l2.5 1.5"/>
            </svg>
          </div>
          <p class="text-xl font-bold" style="color: #191F28;">내 차례예요!</p>
          <p class="text-sm" style="color: #8B95A1;">의견을 입력해 주세요</p>
        </div>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
.turn-modal-enter-active {
  transition: opacity 0.25s ease;
}
.turn-modal-enter-active > div {
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.turn-modal-leave-active {
  transition: opacity 0.35s ease;
}
.turn-modal-enter-from {
  opacity: 0;
}
.turn-modal-enter-from > div {
  transform: scale(0.8);
}
.turn-modal-leave-to {
  opacity: 0;
}
</style>

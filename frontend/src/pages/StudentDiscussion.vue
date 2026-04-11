<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
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

const studentName = computed(() => studentStore.student?.name ?? '나')

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
  if (!content || !ds.inputEnabled || ds.isFinal) return

  isSending.value = true
  ds.addUserBubble(content, ds.round)
  sessionStore.addDiscussionMessage({ speaker: 'user', content, round: ds.round })
  inputText.value = ''

  await sendTurn(content)   // POST /discussion/turns → SSE 오케스트레이터 깨우기
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
      :is-done="ds.isFinal"
      :idle-seconds="ds.userIdleSeconds"
      @send="handleSend"
    />

  </div>
</template>

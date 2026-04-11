<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useStudentStore } from '@/stores/student'
import apiClient from '@/api/client'
import { API_BASE_URL } from '@/api/config'
import DiscussionHeader from '@/components/discussion/DiscussionHeader.vue'
import DiscussionMessageList from '@/components/discussion/DiscussionMessageList.vue'
import DiscussionInput from '@/components/discussion/DiscussionInput.vue'
import { type DisplayMessage, type Speaker } from '@/components/discussion/types'

const MAX_TOPICS = 3

const router = useRouter()
const sessionStore = useSessionStore()
const studentStore = useStudentStore()

const messages = ref<DisplayMessage[]>([])
const inputText = ref('')
const isLoading = ref(false)
const waitingForUser = ref(false)
const isDone = ref(false)
const discussionError = ref<string | null>(null)
const round = ref(1)
const currentSpeaker = ref<Speaker | null>(null)
const messageListRef = ref<InstanceType<typeof DiscussionMessageList> | null>(null)

let msgIdCounter = 0
const nextId = () => ++msgIdCounter
let pendingMsgId: number | null = null

const studentName = computed(() => studentStore.student?.name ?? '나')

onMounted(() => {
  if (!sessionStore.sessionId) {
    router.replace('/student/home')
    return
  }
  window.addEventListener('beforeunload', sendAbandonBeacon)
  window.addEventListener('pagehide', sendAbandonBeacon)
  callDiscussion('')
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', sendAbandonBeacon)
  window.removeEventListener('pagehide', sendAbandonBeacon)
})

function sendAbandonBeacon() {
  if (!sessionStore.sessionId || isDone.value) return
  const blob = new Blob(
    [JSON.stringify({ token: studentStore.token ?? '' })],
    { type: 'application/json' },
  )
  navigator.sendBeacon(
    `${API_BASE_URL}/student/sessions/${sessionStore.sessionId}/abandon`,
    blob,
  )
}

async function callDiscussion(userContent: string) {
  if (!sessionStore.sessionId) return
  isLoading.value = true
  waitingForUser.value = false
  discussionError.value = null

  const token = studentStore.token

  try {
    const response = await fetch(`${API_BASE_URL}/student/sessions/${sessionStore.sessionId}/discussion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content: userContent }),
    })

    if (!response.ok || !response.body) {
      isLoading.value = false
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        let event: Record<string, unknown>
        try { event = JSON.parse(raw) } catch { continue }

        if (event.event === 'turn_start') {
          // 스트리밍 시작 — 빈 메시지 버블 생성
          currentSpeaker.value = event.speaker as Speaker
          const id = nextId()
          pendingMsgId = id
          messages.value.push({
            id,
            speaker: event.speaker as Speaker,
            content: '',
            round: event.round as number,
          })
          round.value = event.round as number
          await messageListRef.value?.scrollToBottom()
        } else if (event.event === 'token') {
          // 토큰 단위로 메시지 내용 추가
          if (pendingMsgId !== null) {
            const msg = messages.value.find(m => m.id === pendingMsgId)
            if (msg) {
              msg.content += event.text as string
              await messageListRef.value?.scrollToBottom()
            }
          }
        } else if (event.event === 'turn_end') {
          // 스트리밍 완료 — 최종 텍스트로 확정 (토큰 누적과 동일하지만 보정)
          if (pendingMsgId !== null) {
            const msg = messages.value.find(m => m.id === pendingMsgId)
            if (msg && event.full_text) msg.content = event.full_text as string
            pendingMsgId = null
          }
          await messageListRef.value?.scrollToBottom()
        } else if (event.speaker && event.content) {
          // close 발화: 구형 단일 이벤트 형식 (moderator_close)
          currentSpeaker.value = event.speaker as Speaker
          messages.value.push({
            id: nextId(),
            speaker: event.speaker as Speaker,
            content: event.content as string,
            round: event.round as number,
          })
          round.value = event.round as number
          await messageListRef.value?.scrollToBottom()
        } else if (event.next_speaker === 'user') {
          currentSpeaker.value = 'user'
          isLoading.value = false
          waitingForUser.value = true
          round.value = event.round as number
          await messageListRef.value?.scrollToBottom()
        } else if (event.error) {
          isLoading.value = false
          waitingForUser.value = false
          currentSpeaker.value = null
          discussionError.value = '토의 응답을 생성하지 못했어요. 다시 시도해주세요.'
          await messageListRef.value?.scrollToBottom()
        } else if (event.is_final) {
          isLoading.value = false
          isDone.value = true
          currentSpeaker.value = null
          await messageListRef.value?.scrollToBottom()
          setTimeout(() => endSession(), 1500)
        }
      }
    }
  } catch {
    isLoading.value = false
    discussionError.value = '토의 연결에 실패했어요. 다시 시도해주세요.'
  }
}

async function abandonSession() {
  if (!sessionStore.sessionId || isDone.value) return
  const token = studentStore.token
  try {
    await fetch(`${API_BASE_URL}/student/sessions/${sessionStore.sessionId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch {
    // 명시적 이탈 요청 실패는 무시
  }
}

async function handleSend() {
  if (!inputText.value.trim() || !waitingForUser.value || isDone.value) return

  const content = inputText.value.trim()
  messages.value.push({
    id: nextId(),
    speaker: 'user',
    content,
    round: round.value,
  })
  sessionStore.addDiscussionMessage({ speaker: 'user', content, round: round.value })
  currentSpeaker.value = null
  inputText.value = ''
  await messageListRef.value?.scrollToBottom()

  await callDiscussion(content)
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
      :round="round"
      :max-rounds="MAX_TOPICS"
    />

    <!-- 메시지 트랜스크립트 -->
    <DiscussionMessageList
      ref="messageListRef"
      :messages="messages"
      :is-loading="isLoading"
      :is-done="isDone"
      :error="discussionError"
      :student-name="studentName"
    />

    <!-- 입력 바 -->
    <DiscussionInput
      v-model="inputText"
      :waiting-for-user="waitingForUser"
      :is-done="isDone"
      @send="handleSend"
    />

  </div>

</template>

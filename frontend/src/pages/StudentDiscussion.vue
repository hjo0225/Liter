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
import { type DisplayMessage, type Speaker, SPEAKERS } from '@/components/discussion/types'

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

const lastMessageBySpeaker = computed(() => {
  const result: Partial<Record<Speaker, string>> = {}
  for (const msg of messages.value) {
    result[msg.speaker] = msg.content
  }
  return result
})

const speakerKeys = Object.keys(SPEAKERS) as Speaker[]

onMounted(() => {
  if (!sessionStore.sessionId) {
    router.replace('/student/home')
    return
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
  callDiscussion('')
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

function handleBeforeUnload() {
  void abandonSession(true)
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

        if (event.speaker) {
          currentSpeaker.value = event.speaker as Speaker
          await new Promise<void>(res => setTimeout(res, 1500 + Math.random() * 1000))
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

async function abandonSession(keepalive = false) {
  if (!sessionStore.sessionId || isDone.value) return
  const token = studentStore.token
  try {
    await fetch(`${API_BASE_URL}/student/sessions/${sessionStore.sessionId}`, {
      method: 'DELETE',
      keepalive,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch {
    // 페이지 이탈 중 요청 실패는 무시
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
  <div class="h-screen flex flex-col overflow-hidden" style="background: #0d0d1a;">

    <DiscussionHeader
      :title="sessionStore.passage?.title ?? 'AI 그룹 토의'"
      :round="round"
      :max-rounds="MAX_TOPICS"
    />

    <!-- 참여자 타일 그리드 -->
    <div class="grid grid-cols-2 gap-2 px-3 pt-3 pb-2 flex-shrink-0">
      <div
        v-for="key in speakerKeys"
        :key="key"
        class="relative flex flex-col items-center justify-center rounded-2xl py-4 px-3 transition-all duration-300"
        :style="{
          background: '#1a1a2e',
          border: currentSpeaker === key
            ? `2px solid ${SPEAKERS[key].color}`
            : '2px solid #2a2a3e',
          boxShadow: currentSpeaker === key
            ? `0 0 20px ${SPEAKERS[key].color}55, inset 0 0 20px ${SPEAKERS[key].color}11`
            : 'none',
          minHeight: '140px',
        }"
      >
        <!-- 발언 중 표시 -->
        <div
          v-if="currentSpeaker === key"
          class="absolute top-2 right-2 flex gap-0.5"
        >
          <span
            v-for="i in 3"
            :key="i"
            class="w-1 h-3 rounded-full animate-pulse"
            :style="{ background: SPEAKERS[key].color, animationDelay: `${(i - 1) * 0.15}s` }"
          />
        </div>

        <!-- 아바타 -->
        <div
          class="w-14 h-14 rounded-full flex items-center justify-center text-white font-bold mb-2 flex-shrink-0"
          :style="{
            background: currentSpeaker === key
              ? SPEAKERS[key].color
              : `${SPEAKERS[key].color}88`,
            fontSize: key === 'user' ? '13px' : '16px',
            transition: 'background 0.3s',
          }"
        >
          {{ SPEAKERS[key].emoji }}
        </div>

        <!-- 이름 -->
        <span class="text-sm font-semibold mb-1" :style="{ color: currentSpeaker === key ? 'white' : '#9ca3af' }">
          {{ SPEAKERS[key].name }}
        </span>

        <!-- 마지막 메시지 미리보기 -->
        <p
          v-if="lastMessageBySpeaker[key]"
          class="text-xs text-center leading-relaxed"
          :style="{
            color: currentSpeaker === key ? '#d1d5db' : '#4b5563',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }"
        >
          {{ lastMessageBySpeaker[key] }}
        </p>
        <div v-else class="flex gap-1 mt-1">
          <span
            v-for="i in 3"
            :key="i"
            class="w-1.5 h-1.5 rounded-full"
            style="background: #2a2a3e;"
          />
        </div>
      </div>
    </div>

    <!-- 메시지 트랜스크립트 -->
    <DiscussionMessageList
      ref="messageListRef"
      :messages="messages"
      :is-loading="isLoading"
      :is-done="isDone"
      :error="discussionError"
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

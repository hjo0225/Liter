<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useStudentStore } from '@/stores/student'
import apiClient from '@/api/client'

const router = useRouter()
const sessionStore = useSessionStore()
const studentStore = useStudentStore()

type Speaker = 'moderator' | 'peer_a' | 'peer_b' | 'user'

interface DisplayMessage {
  id: number
  speaker: Speaker
  content: string
  round: number
}

const SPEAKERS: Record<Speaker, { name: string; emoji: string; color: string; bg: string; textColor: string }> = {
  moderator: { name: '모더레이터', emoji: 'M', color: '#7C3AED', bg: '#EDE9FE', textColor: '#5B21B6' },
  peer_a:    { name: '민지',       emoji: 'A', color: '#059669', bg: '#D1FAE5', textColor: '#065F46' },
  peer_b:    { name: '준서',       emoji: 'B', color: '#D97706', bg: '#FEF3C7', textColor: '#92400E' },
  user:      { name: '나',         emoji: '나', color: '#1B438A', bg: '#EBF0FC', textColor: '#081830' },
}

const messages = ref<DisplayMessage[]>([])
const inputText = ref('')
const isLoading = ref(false)
const waitingForUser = ref(false)
const isDone = ref(false)
const round = ref(1)
const chatRef = ref<HTMLDivElement | null>(null)

let msgIdCounter = 0
const nextId = () => ++msgIdCounter

onMounted(() => {
  if (!sessionStore.sessionId) {
    router.replace('/student/home')
    return
  }
  // 토의 시작 (첫 호출: content 없음)
  callDiscussion('')
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

function handleBeforeUnload() {
  if (sessionStore.sessionId && !isDone.value) {
    navigator.sendBeacon(`http://localhost:8000/api/v1/student/sessions/${sessionStore.sessionId}`)
  }
}

async function scrollToBottom() {
  await nextTick()
  chatRef.value?.scrollTo({ top: chatRef.value.scrollHeight, behavior: 'smooth' })
}

async function callDiscussion(userContent: string) {
  if (!sessionStore.sessionId) return
  isLoading.value = true
  waitingForUser.value = false

  const token = studentStore.token
  const base = 'http://localhost:8000/api/v1'

  try {
    const response = await fetch(`${base}/student/sessions/${sessionStore.sessionId}/discussion`, {
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
          // AI 발화 메시지
          await new Promise<void>(res => setTimeout(res, 400 + Math.random() * 300))
          messages.value.push({
            id: nextId(),
            speaker: event.speaker as Speaker,
            content: event.content as string,
            round: event.round as number,
          })
          round.value = event.round as number
          await scrollToBottom()
        } else if (event.next_speaker === 'user') {
          isLoading.value = false
          waitingForUser.value = true
          round.value = event.round as number
          await scrollToBottom()
        } else if (event.is_final) {
          isLoading.value = false
          isDone.value = true
          await scrollToBottom()
          // 세션 종료 처리
          setTimeout(() => endSession(), 1500)
        }
      }
    }
  } catch {
    isLoading.value = false
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
  inputText.value = ''
  await scrollToBottom()

  await callDiscussion(content)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

async function endSession() {
  try {
    const res = await apiClient.post(`/student/sessions/${sessionStore.sessionId}/end`)
    sessionStore.setScores(res.data)
    router.push('/student/result')
  } catch {
    router.push('/student/home')
  }
}
</script>

<template>
  <div class="min-h-screen flex items-start justify-center" style="background: #F8FAFF;">
    <div class="w-full max-w-md min-h-screen flex flex-col" style="background: white;">

      <!-- ── 헤더 ── -->
      <div style="border-bottom: 1px solid #EBF0FC;">
        <div class="flex items-center justify-between px-4 py-3">
          <span class="text-sm font-bold truncate pr-2" style="color: #112B5C; max-width: 200px;">
            {{ sessionStore.passage?.title ?? 'AI 그룹 토의' }}
          </span>
          <span
            class="text-xs px-2.5 py-1 rounded-full shrink-0 font-bold"
            style="background: #EBF0FC; color: #1B438A;"
          >
            {{ round }} / 10라운드
          </span>
        </div>

        <!-- 참여자 -->
        <div class="flex gap-2 px-4 pb-3 flex-wrap">
          <div
            v-for="(s, key) in SPEAKERS"
            :key="key"
            class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
            :style="{ background: s.bg, color: s.textColor }"
          >
            <div
              class="w-4 h-4 rounded-full flex items-center justify-center text-white"
              :style="{ background: s.color, fontSize: '9px', fontWeight: '800' }"
            >
              {{ s.emoji }}
            </div>
            {{ s.name }}
          </div>
        </div>

        <!-- 진행 바 -->
        <div style="height: 3px; background: #EBF0FC;">
          <div
            :style="{ width: `${(round / 10) * 100}%`, height: '100%', background: '#1B438A', borderRadius: '2px', transition: 'width 0.3s' }"
          />
        </div>
        <div class="text-right px-4 py-1">
          <span class="text-xs" style="color: #93B2E8;">3 / 3단계 — AI 그룹 토의</span>
        </div>
      </div>

      <!-- ── 채팅 영역 ── -->
      <div
        ref="chatRef"
        class="flex-1 overflow-y-auto flex flex-col gap-4 px-4 py-4"
        style="background: #F8FAFF;"
      >
        <template v-for="msg in messages" :key="msg.id">
          <div
            class="flex flex-col gap-1"
            :class="msg.speaker === 'user' ? 'items-end' : 'items-start'"
          >
            <!-- 발화자 이름 (user 제외) -->
            <div v-if="msg.speaker !== 'user'" class="flex items-center gap-1.5 ml-2">
              <div
                class="w-5 h-5 rounded-full flex items-center justify-center text-white"
                :style="{ background: SPEAKERS[msg.speaker].color, fontSize: '9px', fontWeight: '800' }"
              >
                {{ SPEAKERS[msg.speaker].emoji }}
              </div>
              <span class="text-xs" style="color: #93B2E8; font-weight: 500;">
                {{ SPEAKERS[msg.speaker].name }}
              </span>
            </div>

            <!-- 말풍선 -->
            <div
              class="px-4 py-3 text-sm leading-relaxed"
              :style="{
                background: msg.speaker === 'user' ? '#1B438A' : 'white',
                color: msg.speaker === 'user' ? 'white' : '#081830',
                border: msg.speaker === 'user' ? 'none' : '1px solid #EBF0FC',
                borderRadius: msg.speaker === 'user' ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                alignSelf: msg.speaker === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '78%',
              }"
            >
              {{ msg.content }}
            </div>
          </div>
        </template>

        <!-- 로딩 점 -->
        <div v-if="isLoading" class="flex items-center gap-2">
          <div
            class="flex gap-1.5 px-4 py-3 rounded-2xl"
            style="background: white; border: 1px solid #EBF0FC;"
          >
            <span
              v-for="i in 3"
              :key="i"
              class="w-2 h-2 rounded-full animate-bounce"
              :style="{ background: '#C0D0F6', animationDelay: `${(i - 1) * 0.15}s` }"
            />
          </div>
        </div>

        <!-- 토의 완료 -->
        <div v-if="isDone" class="text-center py-4">
          <div class="text-3xl mb-2">🎉</div>
          <p class="text-sm font-bold" style="color: #1B438A;">
            토의가 완료됐어요! 결과를 확인해요...
          </p>
        </div>
      </div>

      <!-- ── 입력 영역 ── -->
      <div class="px-4 py-4 border-t" style="border-color: #EBF0FC; background: white;">
        <p
          v-if="waitingForUser && !isDone"
          class="text-xs text-center mb-2 font-semibold"
          style="color: #2653AC;"
        >
          💬 지금 내 의견을 말할 차례예요!
        </p>
        <div class="flex gap-2">
          <input
            v-model="inputText"
            type="text"
            :placeholder="waitingForUser && !isDone ? '내 의견을 입력해요...' : '상대방의 발언을 기다리는 중...'"
            :disabled="!waitingForUser || isDone"
            @keydown="handleKeydown"
            class="flex-1 px-4 py-3 rounded-2xl outline-none text-sm transition-all"
            :style="{
              border: `1.5px solid ${waitingForUser && !isDone ? '#1B438A' : '#EBF0FC'}`,
              background: waitingForUser && !isDone ? '#F8FAFF' : '#F0F4FD',
              color: '#081830',
            }"
          />
          <button
            @click="handleSend"
            :disabled="!waitingForUser || !inputText.trim() || isDone"
            class="w-11 h-11 rounded-full flex items-center justify-center shrink-0 transition-all"
            :style="{
              background: waitingForUser && inputText.trim() && !isDone ? '#1B438A' : '#C0D0F6',
            }"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import apiClient from '@/api/client'

const router = useRouter()
const sessionStore = useSessionStore()

// ──────────────────── MCQ 상태 ────────────────────
const selectedChoice = ref<number | null>(null)
const submitting = ref(false)
const answerError = ref<string | null>(null)

const currentQuestion = computed(() => sessionStore.questions[sessionStore.currentQuestionIndex])

watch(() => sessionStore.currentQuestionIndex, () => {
  selectedChoice.value = null
  answerError.value = null
})

// ──────────────────── 헬퍼 ────────────────────
const difficultyStars = computed(() => {
  const d = sessionStore.passage?.difficulty ?? 1
  return d === 1 ? '★☆☆' : d === 2 ? '★★☆' : '★★★'
})

const typeLabel = computed(() => {
  const map: Record<string, string> = {
    info: '사실 확인',
    reasoning: '추론',
    vocabulary: '어휘',
  }
  return currentQuestion.value ? map[currentQuestion.value.type] ?? '' : ''
})

const choicePrefix = ['①', '②', '③']

// ──────────────────── 이탈 감지 ────────────────────
function handleBeforeUnload() {
  if (sessionStore.sessionId) {
    const base = 'http://localhost:8000/api/v1'
    const url = `${base}/student/sessions/${sessionStore.sessionId}`
    navigator.sendBeacon(url)
  }
}

onMounted(() => {
  if (!sessionStore.sessionId) {
    router.replace('/student/home')
    return
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// ──────────────────── 지문 읽기 액션 ────────────────────
function handleFinishedReading() {
  sessionStore.goToMcq()
}

function handleBackToReading() {
  sessionStore.phase = 'reading'
  selectedChoice.value = null
  answerError.value = null
}

function handleExitSession() {
  sessionStore.reset()
  router.push('/student/home')
}

// ──────────────────── 객관식 답 제출 ────────────────────
async function handleConfirm() {
  if (selectedChoice.value === null || !currentQuestion.value) return
  submitting.value = true
  answerError.value = null
  try {
    await apiClient.post(`/student/sessions/${sessionStore.sessionId}/answer`, {
      question_index: currentQuestion.value.index,
      selected_index: selectedChoice.value,
    })
    sessionStore.recordAnswer(sessionStore.currentQuestionIndex, selectedChoice.value)
    sessionStore.nextQuestion()
    if (sessionStore.phase === 'discussion') {
      router.push('/student/discussion')
    }
  } catch {
    answerError.value = '답변 저장에 실패했어요. 다시 시도해주세요.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen" style="background: #F8FAFF;">

    <!-- ════════════════ 지문 읽기 ════════════════ -->
    <template v-if="sessionStore.phase === 'reading' && sessionStore.passage">
      <div class="max-w-lg mx-auto px-4 pt-6 pb-28 flex flex-col gap-4">
        <!-- 상단 -->
        <div class="flex items-center justify-between">
          <button
            @click="handleExitSession"
            class="flex items-center gap-1 text-sm font-medium transition-all"
            style="color: #5A7AB8;"
          >
            ← 홈으로
          </button>
          <div class="flex items-center gap-2">
            <span
              class="text-xs font-bold px-3 py-1 rounded-full"
              style="background: #EBF0FC; color: #1B438A;"
            >
              {{ sessionStore.passage.genre }}
            </span>
            <span class="text-sm font-bold" style="color: #1B438A;">{{ difficultyStars }}</span>
          </div>
        </div>

        <!-- 제목 -->
        <h1 class="font-black text-xl leading-tight" style="color: #081830;">
          {{ sessionStore.passage.title }}
        </h1>

        <div style="border-bottom: 1px solid #EBF0FC;" />

        <!-- 지문 본문 -->
        <p
          class="text-base leading-8 whitespace-pre-wrap"
          style="color: #081830;"
        >
          {{ sessionStore.passage.content }}
        </p>
      </div>

      <!-- 고정 하단 버튼 -->
      <div class="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style="background: #F8FAFF; border-top: 1px solid #EBF0FC;">
        <div class="max-w-lg mx-auto">
          <button
            @click="handleFinishedReading"
            class="w-full py-4 rounded-2xl font-bold text-lg text-white"
            style="background: #1B438A;"
          >
            다 읽었어요 →
          </button>
        </div>
      </div>
    </template>

    <!-- ════════════════ 객관식 문항 ════════════════ -->
    <template v-else-if="sessionStore.phase === 'mcq' && currentQuestion">
      <div class="max-w-lg mx-auto px-4 pt-6 pb-28 flex flex-col gap-4">
        <!-- 헤더 -->
        <div class="flex items-center justify-between">
          <span class="font-black text-base" style="color: #1B438A;">
            문제 {{ sessionStore.currentQuestionIndex + 1 }} / 3
          </span>
          <div class="flex items-center gap-2">
            <span
              class="text-xs font-bold px-3 py-1 rounded-full"
              style="background: #EBF0FC; color: #1B438A;"
            >
              {{ typeLabel }}
            </span>
            <span class="text-sm font-bold" style="color: #1B438A;">{{ difficultyStars }}</span>
          </div>
        </div>

        <!-- 지문 미리보기 -->
        <div
          class="rounded-xl p-4 max-h-40 overflow-y-auto text-sm leading-relaxed"
          style="background: #EBF0FC; color: #081830;"
        >
          {{ sessionStore.passage?.content }}
        </div>

        <!-- 질문 -->
        <p class="font-bold text-base leading-snug" style="color: #081830;">
          {{ currentQuestion.text }}
        </p>

        <!-- 선택지 -->
        <div class="flex flex-col gap-2">
          <button
            v-for="(choice, i) in currentQuestion.choices"
            :key="i"
            @click="selectedChoice = i"
            class="w-full text-left px-4 py-3.5 rounded-xl border-2 flex items-center gap-3 transition-all"
            :style="{
              borderColor: selectedChoice === i ? '#1B438A' : '#EBF0FC',
              background: selectedChoice === i ? '#EBF0FC' : 'white',
            }"
          >
            <span class="font-black text-lg shrink-0" style="color: #1B438A; width: 24px;">
              {{ choicePrefix[i] }}
            </span>
            <span class="text-sm leading-snug" style="color: #081830;">{{ choice }}</span>
          </button>
        </div>

        <!-- 에러 -->
        <p v-if="answerError" class="text-sm" style="color: #DC2626;">{{ answerError }}</p>
      </div>

      <!-- 고정 하단 버튼 -->
      <div class="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style="background: #F8FAFF; border-top: 1px solid #EBF0FC;">
        <div class="max-w-lg mx-auto flex gap-3">
          <button
            @click="handleBackToReading"
            class="flex-1 py-3.5 rounded-2xl font-bold border-2 transition-all"
            style="color: #1B438A; border-color: #1B438A; background: white;"
          >
            이전 단계
          </button>
          <button
            @click="handleConfirm"
            :disabled="selectedChoice === null || submitting"
            class="flex-1 py-3.5 rounded-2xl font-bold text-white transition-all"
            :style="{
              background: selectedChoice !== null && !submitting ? '#1B438A' : '#CBD5E1',
              cursor: selectedChoice !== null && !submitting ? 'pointer' : 'not-allowed',
            }"
          >
            {{ submitting ? '저장 중...' : '확인' }}
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

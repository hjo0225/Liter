<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useStudentStore } from '@/stores/student'
import apiClient from '@/api/client'
import { API_BASE_URL } from '@/api/config'

const router = useRouter()
const sessionStore = useSessionStore()
const studentStore = useStudentStore()

// ──────────────────── MCQ 상태 ────────────────────
const selectedChoice = ref<number | null>(null)
const submitting = ref(false)
const answerError = ref<string | null>(null)
const feedbackCorrectIndex = ref<number | null>(null)
const feedbackIsCorrect = ref<boolean | null>(null)

const currentQuestion = computed(() => sessionStore.questions[sessionStore.currentQuestionIndex])

watch(() => sessionStore.currentQuestionIndex, () => {
  selectedChoice.value = null
  answerError.value = null
  feedbackCorrectIndex.value = null
  feedbackIsCorrect.value = null
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
  void abandonSession(true)
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

async function abandonSession(keepalive = false) {
  if (!sessionStore.sessionId) return
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

// ──────────────────── 지문 읽기 액션 ────────────────────
function handleFinishedReading() {
  sessionStore.goToMcq()
}

function handleBackToReading() {
  sessionStore.phase = 'reading'
  selectedChoice.value = null
  answerError.value = null
}

async function handleExitSession() {
  await abandonSession()
  sessionStore.reset()
  router.push('/student/home')
}

// ──────────────────── 객관식 답 제출 ────────────────────
async function handleConfirm() {
  if (selectedChoice.value === null || !currentQuestion.value) return
  submitting.value = true
  answerError.value = null
  try {
    const { data } = await apiClient.post(`/student/sessions/${sessionStore.sessionId}/answer`, {
      question_index: currentQuestion.value.index,
      selected_index: selectedChoice.value,
    })
    sessionStore.recordAnswer(sessionStore.currentQuestionIndex, selectedChoice.value)

    // 피드백 표시 후 다음으로 이동
    feedbackIsCorrect.value = data.is_correct
    feedbackCorrectIndex.value = data.correct_index
    await new Promise(resolve => setTimeout(resolve, 900))

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

    <!-- 스텝 인디케이터 -->
    <div class="sticky top-0 z-10 border-b" style="background: #F8FAFF; border-color: #EBF0FC;">
      <div class="max-w-lg mx-auto px-4 py-3 flex items-center justify-center gap-2 text-xs font-bold">
        <span :style="sessionStore.phase === 'reading' ? 'color: #1B438A;' : 'color: #93B2E8;'">① 읽기</span>
        <span style="color: #CBD5E1;">—</span>
        <span :style="sessionStore.phase === 'mcq' ? 'color: #1B438A;' : 'color: #93B2E8;'">② 문제풀기</span>
        <span style="color: #CBD5E1;">—</span>
        <span style="color: #93B2E8;">③ 토의</span>
        <span style="color: #CBD5E1;">—</span>
        <span style="color: #93B2E8;">④ 결과</span>
      </div>
    </div>

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

        <!-- 질문 -->
        <p class="font-bold text-base leading-snug" style="color: #081830;">
          {{ currentQuestion.text }}
        </p>

        <!-- 선택지 -->
        <div class="flex flex-col gap-2">
          <button
            v-for="(choice, i) in currentQuestion.choices"
            :key="i"
            @click="feedbackIsCorrect === null && (selectedChoice = i)"
            :disabled="feedbackIsCorrect !== null"
            class="w-full text-left px-4 py-3.5 rounded-xl border-2 flex items-center gap-3 transition-all duration-300"
            :style="feedbackIsCorrect !== null
              ? i === feedbackCorrectIndex
                ? 'border-color: #16A34A; background: #DCFCE7;'
                : i === selectedChoice && !feedbackIsCorrect
                  ? 'border-color: #DC2626; background: #FEE2E2;'
                  : 'border-color: #EBF0FC; background: white; opacity: 0.5;'
              : selectedChoice === i
                ? 'border-color: #1B438A; background: #EBF0FC;'
                : 'border-color: #EBF0FC; background: white;'"
          >
            <span class="font-black text-lg shrink-0" :style="{
              color: feedbackIsCorrect !== null
                ? i === feedbackCorrectIndex ? '#16A34A' : i === selectedChoice ? '#DC2626' : '#93B2E8'
                : '#1B438A',
              width: '24px'
            }">
              {{ feedbackIsCorrect !== null && i === feedbackCorrectIndex ? '✓' : feedbackIsCorrect !== null && i === selectedChoice ? '✗' : choicePrefix[i] }}
            </span>
            <span class="text-base leading-snug" style="color: #081830;">{{ choice }}</span>
          </button>
        </div>

        <!-- 피드백 메시지 -->
        <div v-if="feedbackIsCorrect !== null" class="text-center text-base font-bold py-1" :style="feedbackIsCorrect ? 'color: #16A34A;' : 'color: #DC2626;'">
          {{ feedbackIsCorrect ? '정답이에요! 🎉' : '틀렸어요. 정답을 확인해보세요.' }}
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
            :disabled="selectedChoice === null || submitting || feedbackIsCorrect !== null"
            class="flex-1 py-3.5 rounded-2xl font-bold text-white transition-all"
            :style="{
              background: selectedChoice !== null && !submitting && feedbackIsCorrect === null ? '#1B438A' : '#CBD5E1',
              cursor: selectedChoice !== null && !submitting && feedbackIsCorrect === null ? 'pointer' : 'not-allowed',
            }"
          >
            {{ submitting ? '확인 중...' : feedbackIsCorrect !== null ? '다음으로 이동 중...' : '확인' }}
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

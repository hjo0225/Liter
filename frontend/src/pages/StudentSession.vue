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
const questionShownAt = ref<string | null>(null)

const currentQuestion = computed(() => sessionStore.questions[sessionStore.currentQuestionIndex])

watch(() => sessionStore.currentQuestionIndex, () => {
  selectedChoice.value = null
  answerError.value = null
  feedbackCorrectIndex.value = null
  feedbackIsCorrect.value = null
  questionShownAt.value = new Date().toISOString()
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
function sendAbandonBeacon() {
  if (!sessionStore.sessionId) return
  const blob = new Blob(
    [JSON.stringify({ token: studentStore.token ?? '' })],
    { type: 'application/json' },
  )
  navigator.sendBeacon(
    `${API_BASE_URL}/student/sessions/${sessionStore.sessionId}/abandon`,
    blob,
  )
}

onMounted(() => {
  if (!sessionStore.sessionId) {
    router.replace('/student/home')
    return
  }
  if (sessionStore.phase === 'discussion') {
    router.replace('/student/discussion')
    return
  }
  if (sessionStore.phase === 'done') {
    router.replace('/student/result')
    return
  }
  if (sessionStore.phase === 'mcq' && !questionShownAt.value) {
    questionShownAt.value = new Date().toISOString()
  }
  window.addEventListener('beforeunload', sendAbandonBeacon)
  window.addEventListener('pagehide', sendAbandonBeacon)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', sendAbandonBeacon)
  window.removeEventListener('pagehide', sendAbandonBeacon)
})

async function abandonSession() {
  if (!sessionStore.sessionId) return
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

// ──────────────────── 지문 읽기 액션 ────────────────────
function handleFinishedReading() {
  sessionStore.goToMcq()
  questionShownAt.value = new Date().toISOString()
}

function handleBackToReading() {
  sessionStore.setPhase('reading')
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
      shown_at: questionShownAt.value,
      answered_at: new Date().toISOString(),
    })
    sessionStore.recordAnswer(currentQuestion.value.index, selectedChoice.value)

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
  <div class="min-h-screen" style="background: #F9FAFB;">

    <!-- 포커스 헤더 -->
    <nav class="sticky top-0 z-10 border-b" style="background: rgba(255,255,255,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-color: #E5E8EB;">
      <div class="max-w-2xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
        <!-- 로고 -->
        <img src="/service_logo.png" alt="토도독" class="h-10 w-auto flex-shrink-0" />

        <!-- 스텝 인디케이터 -->
        <div class="flex items-center gap-1.5 text-sm font-bold">
          <div class="flex items-center gap-1.5">
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :style="sessionStore.phase === 'reading' ? 'background: #3182F6;' : 'background: #00C471;'"
            />
            <span :style="sessionStore.phase === 'reading' ? 'color: #3182F6;' : 'color: #00C471;'">읽기</span>
          </div>
          <span style="color: #E5E8EB;">—</span>
          <div class="flex items-center gap-1.5">
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :style="sessionStore.phase === 'mcq' ? 'background: #3182F6;' : 'background: #E5E8EB;'"
            />
            <span :style="sessionStore.phase === 'mcq' ? 'color: #3182F6;' : 'color: #8B95A1;'">문제</span>
          </div>
          <span style="color: #E5E8EB;">—</span>
          <div class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full flex-shrink-0" style="background: #E5E8EB;" />
            <span style="color: #8B95A1;">토의</span>
          </div>
          <span style="color: #E5E8EB;">—</span>
          <div class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full flex-shrink-0" style="background: #E5E8EB;" />
            <span style="color: #8B95A1;">결과</span>
          </div>
        </div>

        <!-- 나가기 버튼 -->
        <button
          @click="handleExitSession"
          class="flex-shrink-0 text-sm font-semibold px-3 py-1.5 rounded-full transition-colors"
          style="color: #8B95A1; background: #F2F4F6;"
        >
          나가기 ✕
        </button>
      </div>
    </nav>

    <!-- ════════════════ 지문 읽기 ════════════════ -->
    <template v-if="sessionStore.phase === 'reading' && sessionStore.passage">
      <div class="max-w-lg mx-auto px-4 pt-6 pb-32 flex flex-col gap-4">
        <!-- 메타 chip: 장르 + 난이도 -->
        <div class="flex items-center gap-2">
          <span
            class="text-sm font-bold px-3 py-1 rounded-full"
            style="background: #EEF3FF; color: #3182F6;"
          >
            {{ sessionStore.passage.genre }}
          </span>
          <span
            class="text-sm font-bold px-3 py-1 rounded-full"
            style="background: #FFF4E5; color: #FF9500;"
          >
            {{ difficultyStars }}
          </span>
        </div>

        <!-- 제목 -->
        <h1 class="font-black text-xl leading-tight" style="color: #191F28;">
          {{ sessionStore.passage.title }}
        </h1>

        <!-- 지문 박스 -->
        <div class="rounded-2xl" style="background: #F9FAFB; padding: 24px; border: 1px solid #E5E8EB;">
          <p
            class="text-base whitespace-pre-wrap"
            style="color: #4E5968; line-height: 1.8;"
          >
            {{ sessionStore.passage.content }}
          </p>
        </div>
      </div>

      <!-- 고정 하단 버튼 -->
      <div class="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style="background: #fff; border-top: 1px solid #E5E8EB;">
        <div class="max-w-lg mx-auto">
          <button
            @click="handleFinishedReading"
            class="w-full py-4 rounded-2xl font-bold text-lg text-white"
            style="background: #3182F6;"
          >
            다 읽었어요 →
          </button>
        </div>
      </div>
    </template>

    <!-- ════════════════ 객관식 문항 ════════════════ -->
    <template v-else-if="sessionStore.phase === 'mcq' && currentQuestion">
      <div class="max-w-lg mx-auto px-4 pt-5 pb-28 flex flex-col gap-5">

        <!-- 상단: dot progress(3칸) + 메타 chips -->
        <div class="flex items-center gap-3">
          <div class="flex gap-1.5 flex-1">
            <div
              v-for="n in 3"
              :key="n"
              class="flex-1 rounded-full"
              :style="[
                'height: 4px; transition: background 0.15s;',
                n - 1 < sessionStore.currentQuestionIndex
                  ? 'background: #00C471;'
                  : n - 1 === sessionStore.currentQuestionIndex
                    ? 'background: #3182F6;'
                    : 'background: #E5E8EB;'
              ].join('')"
            />
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-xs font-bold px-3 py-1 rounded-full" style="background: #EEF3FF; color: #3182F6;">
              {{ typeLabel }}
            </span>
            <span class="text-sm font-bold" style="color: #FF9500;">{{ difficultyStars }}</span>
          </div>
        </div>

        <!-- 문제 번호 라벨 + 질문 -->
        <div class="flex flex-col gap-1.5">
          <span class="font-bold" style="font-size: 15px; color: #3182F6;">
            문제 {{ sessionStore.currentQuestionIndex + 1 }}
          </span>
          <p class="font-bold text-lg leading-snug" style="color: #191F28;">
            {{ currentQuestion.text }}
          </p>
        </div>

        <!-- 선택지: 기본 / 선택 / 정답·오답 3상태 -->
        <div class="flex flex-col gap-2">
          <button
            v-for="(choice, i) in currentQuestion.choices"
            :key="i"
            @click="feedbackIsCorrect === null && (selectedChoice = i)"
            :disabled="feedbackIsCorrect !== null"
            class="w-full text-left px-4 py-3.5 rounded-xl border-2 flex items-center gap-3"
            style="transition: all 0.15s;"
            :style="feedbackIsCorrect !== null
              ? i === feedbackCorrectIndex
                ? 'border-color: #00C471; background: #E8F9F1; color: #00C471;'
                : i === selectedChoice && !feedbackIsCorrect
                  ? 'border-color: #F04452; background: #FDECEE; color: #F04452;'
                  : 'border-color: #E5E8EB; background: white; color: #8B95A1; opacity: 0.45;'
              : selectedChoice === i
                ? 'border-color: #3182F6; background: #EEF3FF; color: #3182F6;'
                : 'border-color: #E5E8EB; background: white; color: #191F28;'"
          >
            <span class="font-black text-lg shrink-0" style="width: 24px;">
              {{ feedbackIsCorrect !== null && i === feedbackCorrectIndex ? '✓' : feedbackIsCorrect !== null && i === selectedChoice && !feedbackIsCorrect ? '✗' : choicePrefix[i] }}
            </span>
            <span class="text-base leading-snug font-semibold">{{ choice }}</span>
          </button>
        </div>

        <!-- 피드백 박스 -->
        <div
          v-if="feedbackIsCorrect !== null"
          class="text-center text-base font-bold py-4 rounded-xl"
          :style="feedbackIsCorrect
            ? 'background: #E8F9F1; color: #00C471;'
            : 'background: #FDECEE; color: #F04452;'"
        >
          {{ feedbackIsCorrect ? '정답이에요! 🎉' : '아쉬워요. 다시 한 번 지문을 떠올려봐요.' }}
        </div>

        <!-- 에러 -->
        <p v-if="answerError" class="text-base" style="color: #F04452;">{{ answerError }}</p>
      </div>

      <!-- 고정 하단 버튼 -->
      <div class="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style="background: #fff; border-top: 1px solid #E5E8EB;">
        <div class="max-w-lg mx-auto flex gap-3">
          <button
            @click="handleBackToReading"
            class="flex-1 py-3.5 rounded-2xl font-bold border-2"
            style="color: #3182F6; border-color: #3182F6; background: white; transition: all 0.15s;"
          >
            이전 단계
          </button>
          <button
            @click="handleConfirm"
            :disabled="selectedChoice === null || submitting || feedbackIsCorrect !== null"
            class="flex-1 py-3.5 rounded-2xl font-bold text-white"
            style="transition: all 0.15s;"
            :style="{
              background: selectedChoice !== null && !submitting && feedbackIsCorrect === null ? '#3182F6' : '#E5E8EB',
              color: selectedChoice !== null && !submitting && feedbackIsCorrect === null ? 'white' : '#8B95A1',
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

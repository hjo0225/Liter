<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useStudentStore } from '@/stores/student'

const router = useRouter()
const sessionStore = useSessionStore()
const studentStore = useStudentStore()

const animated = ref(false)

onMounted(() => {
  if (!sessionStore.scores) {
    router.replace('/student/home')
    return
  }
  setTimeout(() => { animated.value = true }, 300)
})

const scores = computed(() => sessionStore.scores)
const scoreItems = computed(() => [
  { name: '추론력', emoji: '🧠', score: scores.value?.score_reasoning ?? 0, color: '#2653AC' },
  { name: '어휘력', emoji: '📝', score: scores.value?.score_vocabulary ?? 0, color: '#4170CC' },
  { name: '맥락파악', emoji: '🔍', score: scores.value?.score_context ?? 0, color: '#1B438A' },
])

const avg = computed(() => {
  if (!scores.value) return 0
  return ((scores.value.score_reasoning + scores.value.score_vocabulary + scores.value.score_context) / 3)
})

const levelLabel = computed(() => {
  const a = avg.value
  if (a >= 8) return '상급 🌟'
  if (a >= 5) return '중급 📊'
  return '초급 📗'
})

const questionTypeLabel: Record<string, string> = {
  info: '정보 파악',
  reasoning: '추론',
  vocabulary: '어휘',
}

function goHome() {
  sessionStore.reset()
  router.push('/student/home')
}

function goNextSession() {
  sessionStore.reset()
  router.push('/student/home')
}
</script>

<template>
  <div class="min-h-screen flex items-start justify-center" style="background: #F8FAFF;">
    <div class="w-full max-w-md min-h-screen flex flex-col pb-8" style="background: white;">

      <!-- ── 헤더 배너 ── -->
      <div
        class="px-5 py-8 text-center"
        style="background: linear-gradient(160deg, #04112B, #1B438A);"
      >
        <div class="text-5xl mb-3">🏆</div>
        <h2 class="text-lg mb-1 font-extrabold" style="color: white;">
          세션 완료!
        </h2>
        <p class="text-sm" style="color: #80A0E8;">
          오늘도 정말 잘했어요, {{ studentStore.student?.name ?? '학생' }}님 👏
        </p>

        <!-- Streak 뱃지 -->
        <div
          v-if="scores?.streak_count"
          class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-full"
          style="background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2);"
        >
          <span>🔥</span>
          <span class="text-sm font-bold" style="color: #FDE68A;">
            {{ scores.streak_count }}일 streak 달성!
          </span>
        </div>
      </div>

      <div class="px-5 py-5 space-y-5">

        <!-- ── 이번 세션 평균 ── -->
        <div
          class="rounded-2xl p-5"
          style="background: #EBF0FC; border: 1px solid #C8D9F6;"
        >
          <div class="flex items-center justify-between">
            <div>
              <div class="text-xs mb-1 font-semibold" style="color: #5A7AB8;">이번 세션 평균</div>
              <div class="text-4xl font-black" style="color: #1B438A;">{{ avg.toFixed(1) }}</div>
              <div class="text-xs mt-1" style="color: #2653AC;">/ 10점</div>
            </div>
            <div class="text-right">
              <div
                class="px-3 py-1.5 rounded-xl text-sm mb-2 font-bold"
                style="background: #FEF3E2; color: #B06000;"
              >
                {{ levelLabel }}
              </div>
            </div>
          </div>
        </div>

        <!-- ── 영역별 점수 ── -->
        <div
          class="rounded-2xl p-5"
          style="background: white; border: 1px solid #EBF0FC;"
        >
          <h3 class="text-sm mb-4 font-extrabold" style="color: #112B5C;">영역별 점수</h3>

          <!-- 카드 3개 -->
          <div class="grid grid-cols-3 gap-3 mb-4">
            <div
              v-for="s in scoreItems"
              :key="s.name"
              class="text-center py-4 rounded-xl"
              style="background: #F8FAFF;"
            >
              <div class="text-xl mb-1">{{ s.emoji }}</div>
              <div class="text-2xl font-black" :style="{ color: s.color }">{{ s.score.toFixed(1) }}</div>
              <div class="text-xs mt-1" style="color: #93B2E8;">{{ s.name }}</div>
            </div>
          </div>

          <!-- 바 차트 -->
          <div class="space-y-3">
            <div v-for="(s, i) in scoreItems" :key="s.name">
              <div class="flex justify-between text-xs mb-1.5">
                <span class="font-semibold" style="color: #112B5C;">{{ s.emoji }} {{ s.name }}</span>
                <span class="font-bold" :style="{ color: s.color }">{{ s.score.toFixed(1) }} / 10</span>
              </div>
              <div class="h-2 rounded-full" style="background: #EBF0FC;">
                <div
                  class="h-full rounded-full transition-all duration-700"
                  :style="{
                    width: animated ? `${s.score * 10}%` : '0%',
                    background: s.color,
                    transitionDelay: `${0.3 + i * 0.1}s`,
                  }"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- ── 객관식 결과 ── -->
        <div
          v-if="scores?.question_results?.length"
          class="rounded-2xl p-5"
          style="background: white; border: 1px solid #EBF0FC;"
        >
          <h3 class="text-sm mb-4 font-extrabold" style="color: #112B5C;">객관식 결과</h3>
          <div class="space-y-3">
            <div
              v-for="q in scores.question_results"
              :key="q.question_index"
              class="flex items-center gap-3 p-3 rounded-xl"
              :style="{
                background: q.is_correct ? '#F0FDF4' : '#FEF2F2',
                border: `1px solid ${q.is_correct ? '#BBF7D0' : '#FECACA'}`,
              }"
            >
              <div
                class="w-7 h-7 rounded-full flex items-center justify-center text-sm shrink-0"
                :style="{ background: q.is_correct ? '#16A34A' : '#DC2626' }"
              >
                <span class="text-white font-bold">{{ q.is_correct ? '✓' : '✗' }}</span>
              </div>
              <div>
                <div
                  class="text-xs font-bold"
                  :style="{ color: q.is_correct ? '#166534' : '#991B1B' }"
                >
                  {{ questionTypeLabel[q.question_type] ?? q.question_type }}
                </div>
                <div class="text-xs mt-0.5" style="color: #4B5563;">{{ q.question_text }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── AI 피드백 ── -->
        <div
          v-if="scores?.feedback"
          class="rounded-2xl p-5"
          style="background: #EBF0FC; border: 1px solid #C8D9F6;"
        >
          <div class="text-xs mb-2 font-bold" style="color: #2653AC;">💡 AI 학습 피드백</div>
          <p class="text-sm leading-relaxed" style="color: #163674;">{{ scores.feedback }}</p>
        </div>

        <!-- ── 버튼 ── -->
        <div class="space-y-3">
          <button
            @click="goNextSession"
            class="w-full py-3.5 rounded-xl text-white text-sm font-bold transition-all"
            style="background: #1B438A;"
          >
            홈으로 돌아가기 →
          </button>
          <button
            @click="goHome"
            class="w-full py-3.5 rounded-xl text-sm font-semibold transition-all"
            style="background: #EBF0FC; color: #1B438A;"
          >
            홈으로 돌아가기
          </button>
        </div>

      </div>
    </div>
  </div>
</template>

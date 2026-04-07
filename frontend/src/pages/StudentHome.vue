<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  BookOpenText,
  CalendarRange,
  Flame,
  LogOut,
  Target,
  Trophy,
} from 'lucide-vue-next'
import { useStudentStore } from '@/stores/student'
import { useSessionStore } from '@/stores/session'
import apiClient from '@/api/client'

interface StudentMeResponse {
  name: string
  level: number
  streak_count: number
  today_session_count: number
  classroom_name?: string | null
  weak_areas?: string[]
  recent_average_score?: number | null
  weekly_completed_count?: number
  total_completed_count?: number
}

interface FocusCard {
  label: string
  desc: string
  icon: string
}

const router = useRouter()
const studentStore = useStudentStore()
const sessionStore = useSessionStore()

const me = ref<StudentMeResponse | null>(null)
const todayCount = ref(0)
const loading = ref(true)
const starting = ref(false)
const error = ref<string | null>(null)

const studentName = computed(() => me.value?.name ?? studentStore.student?.name ?? '')
const streakCount = computed(() => me.value?.streak_count ?? studentStore.student?.streak_count ?? 0)
const level = computed(() => me.value?.level ?? studentStore.student?.level ?? 2)
const weakAreas = computed(() => me.value?.weak_areas ?? [])
const recentAverage = computed(() => me.value?.recent_average_score ?? null)
const weeklyCompletedCount = computed(() => me.value?.weekly_completed_count ?? 0)
const totalCompletedCount = computed(() => me.value?.total_completed_count ?? 0)
const classroomName = computed(() => me.value?.classroom_name ?? '우리 학급')
const limitReached = computed(() => todayCount.value >= 3)
const sessionsLeft = computed(() => Math.max(0, 3 - todayCount.value))
const progressPercent = computed(() => Math.min(100, (todayCount.value / 3) * 100))

const focusMap: Record<string, FocusCard> = {
  info: {
    label: '정보 찾기',
    desc: '지문에서 근거 문장을 다시 찾는 연습을 해보세요.',
    icon: '🔎',
  },
  reasoning: {
    label: '추론하기',
    desc: '왜 그런지 한 문장 더 덧붙이며 답해보면 좋아요.',
    icon: '🧠',
  },
  vocabulary: {
    label: '어휘 이해',
    desc: '모르는 단어를 앞뒤 문장과 함께 읽어 보세요.',
    icon: '📝',
  },
}
const defaultFocus: FocusCard = {
  label: '추론하기',
  desc: '왜 그런지 한 문장 더 덧붙이며 답해보면 좋아요.',
  icon: '🧠',
}

const levelLabel = computed(() => ({ 1: '기초', 2: '성장', 3: '도약' }[level.value] ?? '성장'))
const focusCard = computed<FocusCard>(() => {
  const area = weakAreas.value[0]
  if (area && focusMap[area]) return focusMap[area]
  return defaultFocus
})
const statusMessage = computed(() => {
  if (limitReached.value) {
    return '오늘 학습을 모두 완료했어요. 내일 streak를 이어가면 됩니다.'
  }
  if (todayCount.value === 0) {
    return '첫 세션을 시작하면 오늘의 추천 지문과 토의가 열립니다.'
  }
  return `오늘 ${sessionsLeft.value}번 더 도전할 수 있어요. 지금 이어서 하면 흐름이 끊기지 않습니다.`
})
const scoreTone = computed(() => {
  if (recentAverage.value === null) return { tone: '#496F9F', bg: '#E8F0FB' }
  if (recentAverage.value >= 7) return { tone: '#0F8A5F', bg: '#DAF5E8' }
  if (recentAverage.value >= 5) return { tone: '#B86A00', bg: '#FFF1D6' }
  return { tone: '#CC3D3D', bg: '#FFE1E1' }
})

const quickStats = computed(() => [
  {
    label: '최근 평균',
    value: recentAverage.value !== null ? `${recentAverage.value.toFixed(1)}점` : '기록 대기',
    icon: Trophy,
    tone: scoreTone.value.tone,
    bg: scoreTone.value.bg,
  },
  {
    label: '이번 주 완료',
    value: `${weeklyCompletedCount.value}회`,
    icon: CalendarRange,
    tone: '#1F5FFF',
    bg: '#DCE8FF',
  },
  {
    label: '누적 세션',
    value: `${totalCompletedCount.value}회`,
    icon: BookOpenText,
    tone: '#0F1F38',
    bg: '#E8F0FB',
  },
])

onMounted(async () => {
  try {
    const { data } = await apiClient.get<StudentMeResponse>('/student/me')
    me.value = data
    todayCount.value = data.today_session_count
    studentStore.updateStudent({
      name: data.name,
      level: data.level,
      streak_count: data.streak_count,
    })
  } catch {
    error.value = '학생 정보를 불러오지 못했어요.'
  } finally {
    loading.value = false
  }
})

async function handleStart() {
  if (limitReached.value) return
  error.value = null
  starting.value = true
  try {
    const { data } = await apiClient.post('/student/sessions')
    sessionStore.startSession(data)
    router.push('/student/session')
  } catch (e: any) {
    if (e.response?.status === 429) {
      todayCount.value = 3
    } else {
      error.value = '학습을 시작할 수 없어요. 잠시 후 다시 시도해주세요.'
    }
  } finally {
    starting.value = false
  }
}

function handleLogout() {
  studentStore.logout()
  router.push('/student/join')
}
</script>

<template>
  <div class="min-h-screen">
    <nav class="border-b border-white/50 bg-white/70 backdrop-blur-xl">
      <div class="mx-auto flex h-18 max-w-6xl items-center justify-between px-5 md:px-6">
        <div class="flex items-center gap-3">
          <img src="@/assets/logo.png" class="h-10 w-10 object-contain" alt="토도독 로고" />
          <div>
            <div class="brand-font text-2xl font-bold" style="color: var(--ink-900)">토도독</div>
            <div class="text-xs font-medium" style="color: var(--ink-500)">{{ classroomName }}</div>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <div class="hidden rounded-full px-3 py-2 text-sm font-semibold md:block" style="background: var(--ink-100); color: var(--ink-700)">
            {{ studentName }}
          </div>
          <button
            class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold"
            style="background: white; color: var(--ink-700); border: 1px solid var(--ink-100)"
            @click="handleLogout"
          >
            <LogOut :size="16" />
            나가기
          </button>
        </div>
      </div>
    </nav>

    <main class="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-6 md:px-6 md:py-8">
      <section class="mesh-hero section-shell overflow-hidden rounded-[32px] px-6 py-7 text-white md:px-8 md:py-8">
        <div class="relative z-10 grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div class="fade-rise">
            <div class="pill mb-4" style="background: rgba(255, 255, 255, 0.14); color: #d7e5ff">
              <Flame :size="14" />
              {{ streakCount }}일 연속 학습 중
            </div>
            <h1 class="mb-3 text-3xl font-bold tracking-wide md:text-5xl">
              {{ studentName }}님,
              <br />
              오늘도 읽고 생각할 준비가 됐어요.
            </h1>
            <p class="max-w-xl text-sm leading-6 md:text-base" style="color: #d3e1fb">
              {{ statusMessage }}
            </p>

            <div class="mt-6 flex flex-wrap gap-3">
              <button
                v-if="!limitReached"
                class="btn-primary inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-bold"
                :disabled="starting || loading"
                @click="handleStart"
              >
                {{ starting ? '준비 중...' : '학습 시작' }}
                <ArrowRight :size="16" />
              </button>
              <div
                class="inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold"
                style="background: rgba(255, 255, 255, 0.1); color: #d7e5ff; border: 1px solid rgba(255, 255, 255, 0.14)"
              >
                <Target :size="16" />
                현재 레벨: {{ levelLabel }}
              </div>
            </div>

            <p v-if="error" class="mt-4 text-sm font-medium" style="color: #ffd4d4">{{ error }}</p>
          </div>

          <div class="fade-rise-delay glass-panel flex flex-col gap-4 p-5 md:p-6" style="color: var(--ink-900)">
            <div class="flex items-start justify-between gap-4">
              <div>
                <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Today mission</div>
                <div class="mt-2 display-font text-4xl font-bold">{{ todayCount }}/3</div>
                <div class="mt-1 text-sm font-medium" style="color: var(--ink-700)">오늘 진행한 세션</div>
              </div>
              <div
                class="grid h-16 w-16 place-items-center rounded-full"
                :style="{
                  background: `conic-gradient(var(--accent) ${progressPercent}%, rgba(199, 216, 236, 0.75) ${progressPercent}% 100%)`,
                }"
              >
                <div class="grid h-12 w-12 place-items-center rounded-full bg-white text-xs font-bold" style="color: var(--ink-700)">
                  {{ sessionsLeft }}회
                </div>
              </div>
            </div>

            <div class="space-y-2">
              <div v-for="slot in 3" :key="slot" class="flex items-center gap-3 rounded-2xl px-3 py-3" style="background: rgba(232, 240, 251, 0.8)">
                <div
                  class="h-3 w-3 rounded-full"
                  :style="{ background: slot <= todayCount ? 'var(--accent)' : 'var(--ink-200)' }"
                />
                <div class="text-sm font-semibold" style="color: var(--ink-700)">
                  {{ slot <= todayCount ? `${slot}번째 세션 완료` : `${slot}번째 세션 대기` }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="grid gap-4 md:grid-cols-3">
        <article
          v-for="stat in quickStats"
          :key="stat.label"
          class="soft-card flex items-center gap-4 p-5"
        >
          <div class="grid h-12 w-12 place-items-center rounded-2xl" :style="{ background: stat.bg, color: stat.tone }">
            <component :is="stat.icon" :size="22" />
          </div>
          <div>
            <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">{{ stat.label }}</div>
            <div class="metric-value mt-1 text-2xl" style="color: var(--ink-900)">{{ stat.value }}</div>
          </div>
        </article>
      </section>

      <section class="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <article class="soft-card p-6">
          <div class="mb-4 flex items-center justify-between gap-4">
            <div>
              <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Recommended focus</div>
              <h2 class="mt-2 text-2xl font-bold" style="color: var(--ink-900)">오늘의 학습 포인트</h2>
            </div>
            <div class="grid h-14 w-14 place-items-center rounded-2xl text-2xl" style="background: var(--accent-soft)">
              {{ focusCard.icon }}
            </div>
          </div>

          <div class="rounded-[24px] p-5" style="background: linear-gradient(135deg, #eef4ff 0%, #ffffff 100%); border: 1px solid var(--ink-100)">
            <div class="display-font text-2xl font-bold" style="color: var(--ink-900)">{{ focusCard.label }}</div>
            <p class="mt-2 text-sm leading-6" style="color: var(--ink-700)">
              {{ focusCard.desc }}
            </p>

            <div class="mt-5 flex flex-wrap gap-2">
              <span
                v-for="area in weakAreas.length ? weakAreas : ['reasoning']"
                :key="area"
                class="pill"
                style="background: white; color: var(--ink-700); border: 1px solid var(--ink-100)"
              >
                {{ focusMap[area]?.icon ?? '📘' }}
                {{ focusMap[area]?.label ?? area }}
              </span>
            </div>
          </div>
        </article>

        <article class="soft-card p-6">
          <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Study rhythm</div>
          <h2 class="mt-2 text-2xl font-bold" style="color: var(--ink-900)">이번 주 페이스</h2>

          <div class="mt-5 space-y-4">
            <div>
              <div class="mb-2 flex items-center justify-between text-sm font-semibold" style="color: var(--ink-700)">
                <span>이번 주 진행</span>
                <span>{{ weeklyCompletedCount }}/7</span>
              </div>
              <div class="h-3 rounded-full" style="background: var(--ink-100)">
                <div
                  class="h-full rounded-full"
                  :style="{ width: `${Math.min(100, (weeklyCompletedCount / 7) * 100)}%`, background: 'linear-gradient(90deg, #1f5fff, #4a7cff)' }"
                />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl p-4" style="background: var(--ink-100)">
                <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">학습 레벨</div>
                <div class="mt-2 display-font text-3xl font-bold" style="color: var(--ink-900)">{{ levelLabel }}</div>
              </div>
              <div class="rounded-2xl p-4" style="background: var(--accent-soft)">
                <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">연속 기록</div>
                <div class="mt-2 display-font text-3xl font-bold" style="color: var(--accent-strong)">{{ streakCount }}일</div>
              </div>
            </div>

            <div
              class="rounded-[24px] p-4 text-sm leading-6"
              :style="{ background: limitReached ? 'var(--success-soft)' : 'var(--warning-soft)', color: limitReached ? 'var(--success-strong)' : 'var(--warning-strong)' }"
            >
              {{ limitReached ? '오늘 목표를 모두 채웠어요. 회복과 반복이 다음 성장 포인트입니다.' : '지금 한 번 더 시작하면 오늘 루틴을 완성할 수 있어요.' }}
            </div>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

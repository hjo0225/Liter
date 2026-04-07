<template>
  <div class="min-h-screen">
    <nav class="border-b border-white/60 bg-white/75 backdrop-blur-xl">
      <div class="mx-auto flex h-18 max-w-7xl items-center justify-between px-5 md:px-6">
        <div class="flex items-center gap-4">
          <button
            @click="router.push('/teacher/classrooms')"
            class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold"
            style="background: var(--ink-100); color: var(--ink-700)"
          >
            <ChevronLeft :size="16" />
            학급 목록
          </button>
          <div class="flex items-center gap-3">
            <img src="@/assets/logo.png" class="h-10 w-10 object-contain" alt="토도독 로고" />
            <div>
              <div class="brand-font text-2xl font-bold" style="color: var(--ink-900)">토도독</div>
              <div class="text-xs font-medium" style="color: var(--ink-500)">{{ dashboard?.classroom_name ?? '학급' }}</div>
            </div>
          </div>
        </div>

        <div v-if="dashboard" class="hidden rounded-full px-4 py-2 text-sm font-semibold lg:block" style="background: var(--accent-soft); color: var(--accent-strong)">
          오늘 완료 {{ dashboard.summary.completed_today }}명
        </div>
      </div>
    </nav>

    <div v-if="loading" class="mx-auto flex h-80 max-w-7xl items-center justify-center px-6">
      <div class="soft-card rounded-[28px] px-8 py-6 text-sm font-semibold" style="color: var(--ink-500)">
        대시보드 데이터를 불러오는 중입니다.
      </div>
    </div>

    <main v-else-if="dashboard" class="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-6 md:px-6 md:py-8">
      <section class="mesh-hero section-shell overflow-hidden rounded-[32px] px-6 py-7 text-white md:px-8 md:py-8">
        <div class="relative z-10 grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
          <div class="fade-rise">
            <div class="pill mb-4" style="background: rgba(255,255,255,0.12); color: #d7e5ff">
              <ShieldAlert :size="14" />
              즉시 확인 필요 {{ dashboard.summary.attention_count }}명
            </div>
            <h1 class="text-3xl font-bold md:text-5xl">
              {{ dashboard.classroom_name }}
              <br />
              오늘의 학습 신호를 한눈에 확인하세요.
            </h1>
            <p class="mt-3 max-w-2xl text-sm leading-6 md:text-base" style="color: #d3e1fb">
              참여율, 최근 평균 점수, 취약 영역 분포를 기준으로 학생 개입 우선순위를 바로 정할 수 있게 구성했습니다.
            </p>

            <div class="mt-6 flex flex-wrap gap-3">
              <button
                class="btn-primary inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-bold"
                @click="activeFilter = 'attention'"
              >
                주의 학생 보기
                <ArrowRight :size="16" />
              </button>
              <div class="inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold" style="background: rgba(255,255,255,0.1); color: #d7e5ff; border: 1px solid rgba(255,255,255,0.14)">
                <Users :size="16" />
                전체 학생 {{ dashboard.summary.total_students }}명
              </div>
            </div>
          </div>

          <div class="fade-rise-delay glass-panel flex flex-col gap-4 p-5 md:p-6" style="color: var(--ink-900)">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Participation</div>
                <div class="mt-2 display-font text-4xl font-bold">{{ participationPercent }}%</div>
                <div class="mt-1 text-sm font-medium" style="color: var(--ink-700)">오늘 세션 시작 비율</div>
              </div>
              <div
                class="grid h-16 w-16 place-items-center rounded-full"
                :style="{
                  background: `conic-gradient(var(--accent) ${participationPercent}%, rgba(199,216,236,0.7) ${participationPercent}% 100%)`,
                }"
              >
                <div class="grid h-12 w-12 place-items-center rounded-full bg-white text-xs font-bold" style="color: var(--ink-700)">
                  {{ dashboard.summary.active_today }}명
                </div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl p-4" style="background: rgba(232, 240, 251, 0.9)">
                <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">완료</div>
                <div class="metric-value mt-2 text-3xl" style="color: var(--ink-900)">{{ dashboard.summary.completed_today }}</div>
              </div>
              <div class="rounded-2xl p-4" style="background: rgba(255, 241, 214, 0.92)">
                <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">미완료</div>
                <div class="metric-value mt-2 text-3xl" style="color: var(--warning-strong)">{{ pendingTodayCount }}</div>
              </div>
            </div>

            <div class="rounded-[24px] p-4 text-sm leading-6" style="background: rgba(255,255,255,0.72); border: 1px solid var(--ink-100); color: var(--ink-700)">
              {{ attentionMessage }}
            </div>
          </div>
        </div>
      </section>

      <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article v-for="card in summaryCards" :key="card.label" class="soft-card p-5">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">{{ card.label }}</div>
              <div class="metric-value mt-2 text-3xl" style="color: var(--ink-900)">{{ card.value }}</div>
              <p class="mt-2 text-sm" style="color: var(--ink-700)">{{ card.desc }}</p>
            </div>
            <div class="grid h-12 w-12 place-items-center rounded-2xl" :style="{ background: card.bg, color: card.color }">
              <component :is="card.icon" :size="22" />
            </div>
          </div>
        </article>
      </section>

      <section class="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <article class="soft-card p-6">
          <div class="mb-4 flex items-center justify-between gap-4">
            <div>
              <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Weak area map</div>
              <h2 class="mt-2 text-2xl font-bold" style="color: var(--ink-900)">취약 영역 분포</h2>
            </div>
            <div class="rounded-full px-3 py-2 text-xs font-bold" style="background: var(--ink-100); color: var(--ink-700)">
              상위 {{ dashboard.weak_area_summary.length }}개
            </div>
          </div>

          <div v-if="dashboard.weak_area_summary.length" class="space-y-3">
            <div
              v-for="item in dashboard.weak_area_summary"
              :key="item.area"
              class="rounded-[22px] p-4"
              style="background: linear-gradient(135deg, #f7faff 0%, #edf4ff 100%); border: 1px solid var(--ink-100)"
            >
              <div class="mb-2 flex items-center justify-between gap-3">
                <div class="text-sm font-bold" style="color: var(--ink-900)">{{ areaLabel(item.area) }}</div>
                <div class="text-sm font-semibold" style="color: var(--ink-700)">{{ item.count }}명</div>
              </div>
              <div class="h-2 rounded-full" style="background: white">
                <div
                  class="h-full rounded-full"
                  :style="{ width: `${studentRatio(item.count)}%`, background: 'linear-gradient(90deg, #1f5fff, #4a7cff)' }"
                />
              </div>
            </div>
          </div>

          <div v-else class="rounded-[24px] p-6 text-sm font-semibold" style="background: var(--success-soft); color: var(--success-strong)">
            현재 취약 영역으로 분류된 학생이 없습니다.
          </div>
        </article>

        <article class="soft-card p-6">
          <div class="mb-4 flex items-center justify-between gap-4">
            <div>
              <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Roster overview</div>
              <h2 class="mt-2 text-2xl font-bold" style="color: var(--ink-900)">학생 분포</h2>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="f in filterTabs"
                :key="f.key"
                @click="activeFilter = f.key"
                class="rounded-full px-4 py-2 text-sm font-semibold transition-all"
                :style="{
                  background: activeFilter === f.key ? 'var(--ink-900)' : 'var(--ink-100)',
                  color: activeFilter === f.key ? 'white' : 'var(--ink-700)',
                }"
              >
                {{ f.label }}
              </button>
            </div>
          </div>

          <div class="grid gap-3 md:grid-cols-3">
            <div
              v-for="levelCard in levelCards"
              :key="levelCard.label"
              class="rounded-[22px] p-4"
              :style="{ background: levelCard.bg, color: levelCard.color }"
            >
              <div class="text-xs font-bold uppercase tracking-[0.16em] opacity-70">{{ levelCard.label }}</div>
              <div class="metric-value mt-2 text-3xl">{{ levelCard.value }}</div>
              <div class="mt-2 text-sm font-semibold opacity-80">{{ levelCard.desc }}</div>
            </div>
          </div>
        </article>
      </section>

      <section class="soft-card overflow-hidden">
        <div class="flex flex-col gap-4 border-b px-5 py-5 md:flex-row md:items-center md:justify-between" style="border-color: var(--ink-100)">
          <div>
            <div class="text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Student list</div>
            <h2 class="mt-2 text-2xl font-bold" style="color: var(--ink-900)">개입 우선순위 학생 목록</h2>
          </div>
          <div class="rounded-full px-4 py-2 text-sm font-semibold" style="background: var(--ink-100); color: var(--ink-700)">
            현재 {{ filteredStudents.length }}명 표시 중
          </div>
        </div>

        <div class="hidden gap-4 px-5 py-3 md:grid" style="grid-template-columns: 2fr 1fr 1fr 1.3fr 1fr 90px 36px; background: #f7faff">
          <span
            v-for="h in ['학생', '레벨', '오늘 상태', '취약 영역', '최근 평균', '세션 수', '']"
            :key="h"
            class="text-xs font-bold uppercase tracking-[0.16em]"
            style="color: var(--ink-500)"
          >
            {{ h }}
          </span>
        </div>

        <div>
          <div
            v-for="student in filteredStudents"
            :key="student.id"
            class="grid cursor-pointer gap-4 border-b px-5 py-4 transition-colors hover:bg-slate-50 md:items-center"
            style="grid-template-columns: 1fr; border-color: var(--ink-100)"
            @click="openModal(student)"
          >
            <div class="grid gap-4 md:items-center" style="grid-template-columns: 1fr">
              <div class="grid gap-4 md:items-center" style="grid-template-columns: 2fr 1fr 1fr 1.3fr 1fr 90px 36px">
                <div class="flex items-center gap-3">
                  <div
                    class="grid h-10 w-10 place-items-center rounded-2xl text-sm font-bold text-white"
                    :style="{ background: student.needs_attention ? '#cc3d3d' : '#1f5fff' }"
                  >
                    {{ student.name[0] }}
                  </div>
                  <div>
                    <div class="text-sm font-bold" style="color: var(--ink-900)">{{ student.name }}</div>
                    <div class="text-xs font-medium" style="color: var(--ink-500)">
                      {{ student.completed_sessions }}회 완료 · streak {{ student.streak_count }}일
                    </div>
                  </div>
                </div>

                <div @click.stop>
                  <button
                    @click="toggleLevelEdit(student.id)"
                    class="rounded-full px-3 py-2 text-xs font-bold"
                    :style="{ background: levelStyle(student.level).bg, color: levelStyle(student.level).color }"
                  >
                    {{ student.teacher_override_level ? '수동 ' : '' }}{{ levelLabel(student.level) }}
                  </button>
                  <div v-if="editingLevelId === student.id" class="mt-2 flex gap-1">
                    <button
                      v-for="l in ([1, 2, 3] as Array<1 | 2 | 3>)"
                      :key="l"
                      @click="setLevel(student, l)"
                      class="rounded-full px-2 py-1 text-xs font-bold"
                      :style="{ background: levelStyle(l).bg, color: levelStyle(l).color }"
                    >
                      {{ levelLabel(l) }}
                    </button>
                  </div>
                </div>

                <div>
                  <span
                    class="rounded-full px-3 py-2 text-xs font-bold"
                    :style="student.today_completed ? 'background: var(--success-soft); color: var(--success-strong)' : 'background: var(--warning-soft); color: var(--warning-strong)'"
                  >
                    {{ student.today_completed ? '완료' : '대기' }}
                  </span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="tag in student.weak_areas.length ? student.weak_areas.slice(0, 2) : ['healthy']"
                    :key="tag"
                    class="rounded-full px-3 py-1.5 text-xs font-semibold"
                    :style="tag === 'healthy' ? 'background: var(--success-soft); color: var(--success-strong)' : 'background: var(--ink-100); color: var(--ink-700)'"
                  >
                    {{ tag === 'healthy' ? '양호' : areaLabel(tag) }}
                  </span>
                </div>

                <div class="text-sm font-bold" :style="{ color: scoreColor(student.recent_avg) }">
                  {{ student.recent_avg !== null ? `${student.recent_avg.toFixed(1)}점` : '기록 없음' }}
                </div>

                <div class="text-sm font-semibold" style="color: var(--ink-700)">
                  {{ student.completed_sessions }}회
                </div>

                <div class="hidden justify-end md:flex">
                  <ChevronRight :size="16" color="#8da9cc" />
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredStudents.length === 0" class="px-5 py-14 text-center text-sm font-semibold" style="color: var(--ink-500)">
            현재 조건에 맞는 학생이 없습니다.
          </div>
        </div>
      </section>
    </main>

    <div
      v-if="selectedStudent"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      style="background: rgba(7, 17, 31, 0.56); backdrop-filter: blur(8px)"
      @click.self="selectedStudent = null"
    >
      <div class="w-full max-w-2xl rounded-[32px] bg-white p-6 md:p-7" style="box-shadow: var(--shadow-lg); max-height: 90vh; overflow: auto">
        <div class="mb-5 flex items-start justify-between gap-4">
          <div class="flex items-center gap-4">
            <div class="grid h-14 w-14 place-items-center rounded-2xl text-lg font-bold text-white" style="background: linear-gradient(135deg, #1f5fff, #10294b)">
              {{ selectedStudent.name[0] }}
            </div>
            <div>
              <h3 class="text-2xl font-bold" style="color: var(--ink-900)">{{ selectedStudent.name }}</h3>
              <div class="mt-2 flex flex-wrap gap-2">
                <span class="rounded-full px-3 py-2 text-xs font-bold" :style="{ background: levelStyle(selectedStudent.level).bg, color: levelStyle(selectedStudent.level).color }">
                  {{ levelLabel(selectedStudent.level) }}
                </span>
                <span
                  class="rounded-full px-3 py-2 text-xs font-bold"
                  :style="selectedStudent.today_completed ? 'background: var(--success-soft); color: var(--success-strong)' : 'background: var(--warning-soft); color: var(--warning-strong)'"
                >
                  {{ selectedStudent.today_completed ? '오늘 완료' : '오늘 미완료' }}
                </span>
              </div>
            </div>
          </div>

          <button
            class="rounded-full px-3 py-2 text-sm font-semibold"
            style="background: var(--ink-100); color: var(--ink-700)"
            @click="selectedStudent = null"
          >
            닫기
          </button>
        </div>

        <div class="grid gap-4 md:grid-cols-3">
          <div class="rounded-[24px] p-4" style="background: var(--ink-100)">
            <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">최근 평균</div>
            <div class="metric-value mt-2 text-3xl" :style="{ color: scoreColor(selectedStudent.recent_avg) }">
              {{ selectedStudent.recent_avg !== null ? selectedStudent.recent_avg.toFixed(1) : '-' }}
            </div>
          </div>
          <div class="rounded-[24px] p-4" style="background: var(--accent-soft)">
            <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">완료 세션</div>
            <div class="metric-value mt-2 text-3xl" style="color: var(--accent-strong)">{{ selectedStudent.completed_sessions }}</div>
          </div>
          <div class="rounded-[24px] p-4" style="background: var(--warning-soft)">
            <div class="text-xs font-bold uppercase tracking-[0.16em]" style="color: var(--ink-500)">streak</div>
            <div class="metric-value mt-2 text-3xl" style="color: var(--warning-strong)">{{ selectedStudent.streak_count }}일</div>
          </div>
        </div>

        <div class="mt-5 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div class="rounded-[28px] p-5" style="background: #f7faff; border: 1px solid var(--ink-100)">
            <div class="mb-4 text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Recent trend</div>
            <div class="flex h-36 items-end gap-2">
              <template v-if="selectedStudent.score_history.length">
                <div
                  v-for="(item, index) in selectedStudent.score_history"
                  :key="`${item.date}-${index}`"
                  class="flex flex-1 flex-col items-center justify-end gap-2"
                >
                  <div
                    class="w-full rounded-t-[10px]"
                    :style="{ height: `${Math.max(10, (item.avg_score / 10) * 110)}px`, background: 'linear-gradient(180deg, #4a7cff 0%, #1f5fff 100%)' }"
                  />
                  <span class="text-[11px] font-semibold" style="color: var(--ink-500)">{{ formatDateShort(item.date) }}</span>
                </div>
              </template>
              <div v-else class="text-sm font-semibold" style="color: var(--ink-500)">아직 세션 기록이 없습니다.</div>
            </div>
          </div>

          <div class="flex flex-col gap-4">
            <div class="rounded-[28px] p-5" style="background: white; border: 1px solid var(--ink-100)">
              <div class="mb-3 text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Weak areas</div>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="area in (selectedStudent.weak_areas.length ? selectedStudent.weak_areas : ['healthy'])"
                  :key="area"
                  class="rounded-full px-3 py-2 text-sm font-semibold"
                  :style="area === 'healthy' ? 'background: var(--success-soft); color: var(--success-strong)' : 'background: var(--ink-100); color: var(--ink-700)'"
                >
                  {{ area === 'healthy' ? '양호' : areaLabel(area) }}
                </span>
              </div>
            </div>

            <div class="rounded-[28px] p-5" style="background: white; border: 1px solid var(--ink-100)">
              <div class="mb-3 text-xs font-bold uppercase tracking-[0.18em]" style="color: var(--ink-500)">Level control</div>
              <div class="flex gap-2">
                <button
                  v-for="l in ([1, 2, 3] as Array<1 | 2 | 3>)"
                  :key="l"
                  @click="setLevel(selectedStudent, l)"
                  class="flex-1 rounded-2xl py-3 text-sm font-bold"
                  :style="selectedStudent.level === l ? `background: ${levelStyle(l).color}; color: white` : `background: ${levelStyle(l).bg}; color: ${levelStyle(l).color}`"
                >
                  {{ levelLabel(l) }}
                </button>
              </div>
              <p class="mt-3 text-sm leading-6" style="color: var(--ink-500)">
                수동 조정 시 이후 자동 레벨 재배치보다 교사 판단이 우선 적용됩니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Gauge,
  LayoutDashboard,
  ShieldAlert,
  Sparkles,
  Users,
} from 'lucide-vue-next'
import apiClient from '@/api/client'

interface ScoreHistory {
  date: string
  avg_score: number
}

interface StudentItem {
  id: string
  name: string
  level: 1 | 2 | 3
  teacher_override_level: number | null
  weak_areas: string[]
  streak_count: number
  recent_avg: number | null
  needs_attention: boolean
  completed_sessions: number
  today_completed: boolean
  score_history: ScoreHistory[]
}

interface DashboardSummary {
  total_students: number
  active_today: number
  completed_today: number
  average_recent_score: number
  average_streak: number
  attention_count: number
}

interface WeakAreaSummaryItem {
  area: string
  count: number
}

interface Dashboard {
  classroom_name: string
  summary: DashboardSummary
  weak_area_summary: WeakAreaSummaryItem[]
  students: StudentItem[]
}

const router = useRouter()
const route = useRoute()
const classroomId = route.params.classroomId as string

const dashboard = ref<Dashboard | null>(null)
const loading = ref(true)
const activeFilter = ref<'all' | 'attention' | 'high' | 'mid' | 'low'>('all')
const editingLevelId = ref<string | null>(null)
const selectedStudent = ref<StudentItem | null>(null)

const students = computed(() => dashboard.value?.students ?? [])
const participationPercent = computed(() => {
  if (!dashboard.value?.summary.total_students) return 0
  return Math.round((dashboard.value.summary.active_today / dashboard.value.summary.total_students) * 100)
})
const pendingTodayCount = computed(() => {
  if (!dashboard.value) return 0
  return Math.max(0, dashboard.value.summary.total_students - dashboard.value.summary.completed_today)
})
const attentionMessage = computed(() => {
  if (!dashboard.value) return ''
  if (dashboard.value.summary.attention_count === 0) {
    return '현재 즉시 개입이 필요한 학생이 없습니다. 취약 영역 분포를 보며 다음 수업 포인트를 설계하면 됩니다.'
  }
  return `최근 평균이 낮은 학생 ${dashboard.value.summary.attention_count}명이 감지되었습니다. 오늘 미완료 학생과 함께 먼저 점검하는 편이 좋습니다.`
})

const summaryCards = computed(() => {
  if (!dashboard.value) return []
  return [
    {
      label: '최근 평균 점수',
      value: `${dashboard.value.summary.average_recent_score.toFixed(1)}점`,
      desc: '최근 3세션 기준 학급 평균',
      icon: Gauge,
      bg: '#dce8ff',
      color: '#1847bc',
    },
    {
      label: '평균 streak',
      value: `${dashboard.value.summary.average_streak.toFixed(1)}일`,
      desc: '학급 전체 학습 습관의 강도',
      icon: Sparkles,
      bg: '#fff1d6',
      color: '#b86a00',
    },
    {
      label: '오늘 참여',
      value: `${dashboard.value.summary.active_today}명`,
      desc: '세션을 시작한 학생 수',
      icon: Users,
      bg: '#e8f0fb',
      color: '#23426d',
    },
    {
      label: '주의 학생',
      value: `${dashboard.value.summary.attention_count}명`,
      desc: '즉시 피드백이 필요한 학생',
      icon: AlertTriangle,
      bg: '#ffe1e1',
      color: '#cc3d3d',
    },
  ]
})

const filterTabs = computed(() => {
  const roster = students.value
  return [
    { key: 'all' as const, label: `전체 ${roster.length}` },
    { key: 'attention' as const, label: `주의 ${roster.filter((x) => x.needs_attention).length}` },
    { key: 'high' as const, label: `상 ${roster.filter((x) => x.level === 3).length}` },
    { key: 'mid' as const, label: `중 ${roster.filter((x) => x.level === 2).length}` },
    { key: 'low' as const, label: `하 ${roster.filter((x) => x.level === 1).length}` },
  ]
})

const levelCards = computed(() => {
  const roster = students.value
  return [
    {
      label: '상',
      value: `${roster.filter((x) => x.level === 3).length}명`,
      desc: '자율 확장 활동 적합',
      bg: '#daf5e8',
      color: '#0f8a5f',
    },
    {
      label: '중',
      value: `${roster.filter((x) => x.level === 2).length}명`,
      desc: '핵심 수업 유지 구간',
      bg: '#dce8ff',
      color: '#1847bc',
    },
    {
      label: '하',
      value: `${roster.filter((x) => x.level === 1).length}명`,
      desc: '근거 찾기 보강 필요',
      bg: '#ffe1e1',
      color: '#cc3d3d',
    },
  ]
})

const filteredStudents = computed(() => {
  if (activeFilter.value === 'all') return students.value
  if (activeFilter.value === 'attention') return students.value.filter((x) => x.needs_attention)
  if (activeFilter.value === 'high') return students.value.filter((x) => x.level === 3)
  if (activeFilter.value === 'mid') return students.value.filter((x) => x.level === 2)
  return students.value.filter((x) => x.level === 1)
})

function levelStyle(level: 1 | 2 | 3) {
  if (level === 1) return { bg: '#ffe1e1', color: '#cc3d3d' }
  if (level === 2) return { bg: '#fff1d6', color: '#b86a00' }
  return { bg: '#daf5e8', color: '#0f8a5f' }
}

function levelLabel(level: 1 | 2 | 3) {
  return level === 1 ? '하' : level === 2 ? '중' : '상'
}

function areaLabel(area: string) {
  if (area === 'info') return '정보 찾기'
  if (area === 'reasoning') return '추론'
  if (area === 'vocabulary') return '어휘'
  return area
}

function scoreColor(avg: number | null) {
  if (avg === null) return 'var(--ink-500)'
  if (avg >= 7) return 'var(--success-strong)'
  if (avg >= 5) return 'var(--warning-strong)'
  return 'var(--danger-strong)'
}

function studentRatio(count: number) {
  if (!dashboard.value?.summary.total_students) return 0
  return Math.round((count / dashboard.value.summary.total_students) * 100)
}

function formatDateShort(date: string) {
  const d = new Date(date)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function openModal(student: StudentItem) {
  selectedStudent.value = { ...student, score_history: [...student.score_history], weak_areas: [...student.weak_areas] }
  editingLevelId.value = null
}

function toggleLevelEdit(id: string) {
  editingLevelId.value = editingLevelId.value === id ? null : id
}

async function setLevel(student: StudentItem, level: 1 | 2 | 3) {
  try {
    await apiClient.patch(`/teacher/students/${student.id}/level`, { level })
    if (dashboard.value) {
      const target = dashboard.value.students.find((item) => item.id === student.id)
      if (target) {
        target.level = level
        target.teacher_override_level = level
      }
    }
    if (selectedStudent.value?.id === student.id) {
      selectedStudent.value = { ...selectedStudent.value, level, teacher_override_level: level }
    }
    editingLevelId.value = null
  } catch {
    // silent
  }
}

onMounted(async () => {
  try {
    const { data } = await apiClient.get<Dashboard>(`/teacher/classrooms/${classroomId}/dashboard`)
    dashboard.value = data
  } finally {
    loading.value = false
  }
})
</script>

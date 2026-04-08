<template>
  <div class="min-h-screen" style="background-color: #F8FAFF">
    <!-- Navigation -->
    <nav class="sticky top-0 z-50 border-b" style="background-color: white; border-color: #C8D9F6">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div class="brand-badge">
          <div
            class="flex h-11 w-11 items-center justify-center rounded-2xl"
            style="background: linear-gradient(135deg, #EBF0FC, #D4E1FC); color: #1B438A"
          >
            <BookOpenText :size="22" />
          </div>
          <div class="brand-wordmark">토도독</div>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="router.push('/student/join')"
            class="min-w-[112px] px-4 py-2 rounded-lg text-sm transition-all"
            style="background-color: #EBF0FC; color: #1B438A; font-weight: 600"
          >
            학생 로그인
          </button>
          <button
            @click="router.push('/teacher')"
            class="min-w-[112px] px-4 py-2 rounded-lg text-sm text-white transition-all hover:opacity-90"
            style="background-color: #1B438A; font-weight: 600"
          >
            교사 로그인
          </button>
        </div>
      </div>
    </nav>

    <!-- Hero Section -->
    <section
      class="relative overflow-hidden"
      style="background: linear-gradient(135deg, #04112B 0%, #1B438A 60%, #2653AC 100%)"
    >
      <!-- Decorative circles -->
      <div
        class="absolute top-0 right-0 w-96 h-96 rounded-full opacity-10"
        style="background: radial-gradient(circle, #80A0E8, transparent); transform: translate(30%, -30%)"
      />
      <div
        class="absolute bottom-0 left-0 w-64 h-64 rounded-full opacity-10"
        style="background: radial-gradient(circle, #4170CC, transparent); transform: translate(-30%, 30%)"
      />

      <div class="max-w-6xl mx-auto px-6 py-20 md:py-28 relative z-10">
        <div class="max-w-3xl fade-up">
          <div
            class="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-6"
            style="background-color: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2)"
          >
            <Sparkles :size="15" />
            <span class="text-sm" style="color: #C0D0F6; font-weight: 500">멀티에이전트 기반 초개인화 문해력 솔루션</span>
          </div>
          <h1
            class="text-4xl md:text-5xl lg:text-6xl mb-6"
            style="color: white; font-weight: 800; line-height: 1.2; letter-spacing: -1px"
          >
            읽고, 생각하고,<br />
            <span style="color: #80A0E8">함께 토의해요</span>
          </h1>
          <p class="text-lg md:text-xl mb-8 leading-relaxed" style="color: #93B2E8; max-width: 540px">
            초등 4~6학년을 위한 AI 문해력 학습 플랫폼이에요.
            매일 15분, AI 또래 친구들과 함께 지문을 읽고 토의하며 문해력이 자라요.
          </p>
          <div class="flex flex-wrap gap-4">
            <button
              @click="router.push('/student/join')"
              class="flex w-44 items-center justify-between gap-2 px-6 py-3.5 rounded-xl text-white transition-all hover:opacity-90 active:scale-95"
              style="background: linear-gradient(135deg, #2653AC, #4170CC); font-weight: 700; box-shadow: 0 4px 20px rgba(65,112,204,0.4)"
            >
              <span>학생 로그인</span>
              <ArrowRight :size="18" />
            </button>
            <button
              @click="router.push('/teacher')"
              class="flex w-44 items-center justify-between gap-2 px-6 py-3.5 rounded-xl transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.12); border: 1.5px solid rgba(255,255,255,0.25); color: white; font-weight: 600"
            >
              <span>교사 대시보드</span>
              <ChevronRight :size="18" />
            </button>
          </div>
        </div>

      </div>
    </section>

    <!-- Stats -->
    <section class="py-12 border-b" style="background-color: white; border-color: #EBF0FC">
      <div class="max-w-6xl mx-auto px-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div v-for="(stat, i) in stats" :key="i" class="text-center">
            <div
              class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              :style="{ backgroundColor: stat.bg, color: stat.color }"
            >
              <component :is="stat.icon" :size="22" />
            </div>
            <div class="text-2xl" style="font-weight: 800; color: #1B438A">{{ stat.value }}</div>
            <div class="text-sm mt-1" style="color: #5A7AB8">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section id="how-it-works" class="py-20" style="background-color: #F8FAFF">
      <div class="max-w-6xl mx-auto px-6">
        <div class="text-center mb-14">
          <span class="inline-block px-4 py-1.5 rounded-full text-sm mb-4" style="background-color: #EBF0FC; color: #1B438A; font-weight: 600">
            사용 방법
          </span>
          <h2 class="text-3xl" style="color: #081830; font-weight: 800">3단계로 바로 시작해요</h2>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div
            v-for="(step, i) in steps"
            :key="i"
            class="relative scroll-fade"
            :ref="setRef"
          >
            <div
              v-if="i < steps.length - 1"
              class="hidden md:block absolute top-8 left-full w-8 h-0.5 z-10"
              style="background-color: #C0D0F6"
            />
            <div
              class="rounded-2xl p-6 h-full"
              style="background-color: white; border: 1px solid #EBF0FC; box-shadow: 0 2px 16px rgba(27,67,138,0.06)"
            >
              <div
                class="w-10 h-10 rounded-full flex items-center justify-center mb-4 text-sm"
                style="background-color: #1B438A; color: white; font-weight: 800"
              >
                {{ step.num }}
              </div>
              <div
                class="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl"
                :style="{ backgroundColor: step.bg, color: step.color }"
              >
                <component :is="step.icon" :size="26" />
              </div>
              <h3 style="color: #112B5C; font-weight: 700">{{ step.title }}</h3>
              <p class="text-sm mt-2 leading-relaxed" style="color: #5A7AB8">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Session Flow -->
    <section class="py-16" style="background-color: white">
      <div class="max-w-6xl mx-auto px-6">
        <div class="text-center mb-12">
          <span class="inline-block px-4 py-1.5 rounded-full text-sm mb-4" style="background-color: #EBF0FC; color: #1B438A; font-weight: 600">
            세션 구조
          </span>
          <h2 style="color: #081830; font-weight: 800">매 세션, 이렇게 진행돼요</h2>
        </div>
        <div class="flex flex-col md:flex-row items-center justify-center gap-4">
          <template v-for="(item, i) in sessionFlow" :key="i">
            <div v-if="item.isArrow" class="hidden md:flex h-10 w-10 items-center justify-center rounded-full" style="background-color: #F1F5FE; color: #9AB5EA">
              <ArrowRight :size="18" />
            </div>
            <div
              v-else
              class="flex-1 rounded-2xl p-5 text-center"
              style="min-width: 130px"
              :style="{ backgroundColor: item.color, border: `1.5px solid ${item.color === 'transparent' ? 'transparent' : '#C0D0F6'}` }"
            >
              <div
                class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl"
                :style="{ backgroundColor: item.iconBg, color: item.iconColor }"
              >
                <component :is="item.icon" :size="26" />
              </div>
              <div class="text-xs mb-1" :style="{ color: item.textColor, fontWeight: 600, opacity: 0.7 }">{{ item.step }}</div>
              <div class="text-sm" :style="{ color: item.textColor, fontWeight: 700 }">{{ item.title }}</div>
              <div class="text-xs mt-1 whitespace-pre-line" :style="{ color: item.textColor, opacity: 0.65 }">{{ item.desc }}</div>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section id="features" class="py-20" style="background-color: #F8FAFF">
      <div class="max-w-6xl mx-auto px-6">
        <div class="text-center mb-14">
          <span class="inline-block px-4 py-1.5 rounded-full text-sm mb-4" style="background-color: #EBF0FC; color: #1B438A; font-weight: 600">
            핵심 기능
          </span>
          <h2 class="text-3xl" style="color: #081830; font-weight: 800">토도독만의 특별한 점</h2>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="(feature, i) in features"
            :key="i"
            class="rounded-2xl p-6 hover:-translate-y-1 transition-transform"
            style="background-color: white; border: 1px solid #EBF0FC; box-shadow: 0 2px 16px rgba(27,67,138,0.06)"
          >
            <div
              class="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl"
              :style="{ backgroundColor: feature.bg, color: feature.color }"
            >
              <component :is="feature.icon" :size="26" />
            </div>
            <h3 style="color: #112B5C; font-weight: 700">{{ feature.title }}</h3>
            <p class="text-sm mt-2 leading-relaxed" style="color: #5A7AB8">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- For Teachers / For Students -->
    <section class="py-16" style="background-color: white">
      <div class="max-w-6xl mx-auto px-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- For Teachers -->
          <div class="rounded-3xl p-8" style="background: linear-gradient(135deg, #04112B, #1B438A)">
            <div class="mb-5 flex h-16 w-16 items-center justify-center rounded-3xl" style="background-color: rgba(255,255,255,0.14); color: white">
              <GraduationCap :size="30" />
            </div>
            <h3 class="text-xl mb-3" style="color: white; font-weight: 800">교사를 위한 토도독</h3>
            <ul class="space-y-3 mb-8">
              <li v-for="(item, i) in teacherFeatures" :key="i" class="flex items-center gap-2">
                <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background-color: rgba(255,255,255,0.15)">
                  <Check :size="12" class="text-white" />
                </div>
                <span class="text-sm" style="color: #93B2E8">{{ item }}</span>
              </li>
            </ul>
            <button
              @click="router.push('/teacher')"
              class="flex w-full items-center justify-between py-3 px-4 rounded-xl text-sm transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.15); color: white; font-weight: 700; border: 1px solid rgba(255,255,255,0.2)"
            >
              <span>교사 대시보드 시작하기</span>
              <ArrowRight :size="16" />
            </button>
          </div>

          <!-- For Students -->
          <div class="rounded-3xl p-8" style="background: linear-gradient(135deg, #2653AC, #4170CC)">
            <div class="mb-5 flex h-16 w-16 items-center justify-center rounded-3xl" style="background-color: rgba(255,255,255,0.14); color: white">
              <Backpack :size="30" />
            </div>
            <h3 class="text-xl mb-3" style="color: white; font-weight: 800">학생을 위한 토도독</h3>
            <ul class="space-y-3 mb-8">
              <li v-for="(item, i) in studentFeatures" :key="i" class="flex items-center gap-2">
                <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background-color: rgba(255,255,255,0.15)">
                  <Check :size="12" class="text-white" />
                </div>
                <span class="text-sm" style="color: #C0D0F6">{{ item }}</span>
              </li>
            </ul>
            <button
              @click="router.push('/student/join')"
              class="flex w-full items-center justify-between py-3 px-4 rounded-xl text-sm transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.15); color: white; font-weight: 700; border: 1px solid rgba(255,255,255,0.2)"
            >
              <span>학생 로그인</span>
              <ArrowRight :size="16" />
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Banner -->
    <section class="py-20" style="background: linear-gradient(135deg, #EBF0FC, #D4E1FC)">
      <div class="max-w-4xl mx-auto px-6 text-center">
        <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[28px]" style="background: white; color: #1B438A; box-shadow: 0 12px 40px rgba(27,67,138,0.12)">
          <Rocket :size="36" />
        </div>
        <h2 class="text-3xl mb-4" style="color: #081830; font-weight: 800">지금 바로 시작해보세요</h2>
        <p class="text-lg mb-8" style="color: #2653AC">초등 4~6학년 학생의 문해력, 토도독과 함께 키워요.</p>
      </div>
    </section>

    <!-- Footer -->
    <footer class="py-10 border-t" style="background-color: #04112B; border-color: #0C2044">
      <div class="max-w-6xl mx-auto px-6">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4">
          <div class="brand-badge brand-badge--dark">
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl" style="background: rgba(255,255,255,0.08); color: white">
              <BookOpenText :size="20" />
            </div>
            <span class="brand-wordmark brand-wordmark--light">토도독</span>
            <span class="text-xs ml-2" style="color: #5A7AB8">AI 기반 초등 문해력 토의 플랫폼</span>
          </div>
          <div class="text-xs" style="color: #2653AC">© 2026 토도독. 초등 4~6학년 문해력 교육을 위해 만들었어요.</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Backpack,
  BarChart3,
  BookOpenText,
  Check,
  ChevronRight,
  FileText,
  Flame,
  GraduationCap,
  LayoutTemplate,
  LibraryBig,
  MessageCircleMore,
  NotebookPen,
  Rocket,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Target,
  Trophy,
  UserRoundPlus,
} from 'lucide-vue-next'

const router = useRouter()


const stats = [
  { value: '3단계', label: '세션 구조', icon: LayoutTemplate, bg: '#EBF0FC', color: '#1B438A' },
  { value: '10라운드', label: 'AI 토의', icon: MessageCircleMore, bg: '#E8F0FD', color: '#1B438A' },
  { value: '3가지', label: '문해력 측정', icon: BarChart3, bg: '#DDE8FC', color: '#163674' },
  { value: '매일', label: 'streak 갱신', icon: Flame, bg: '#FFF1D6', color: '#B86A00' },
]

const steps = [
  { num: '01', icon: LibraryBig, title: '교사가 학급 코드 발급', desc: '회원가입 후 학급을 생성하면 6자리 고유 코드가 발급돼요.', bg: '#EBF0FC', color: '#1B438A' },
  { num: '02', icon: Smartphone, title: '학생이 코드 입력', desc: '학생은 앱에서 코드와 이름만 입력하면 바로 시작할 수 있어요.', bg: '#E8F0FD', color: '#1B438A' },
  { num: '03', icon: Sparkles, title: 'AI와 함께 매일 학습', desc: '지문 읽기 → 객관식 → AI 토의 순서로 15~20분 세션을 진행해요.', bg: '#DDE8FC', color: '#163674' },
]

interface SessionStep {
  isArrow: boolean
  icon?: Component
  step: string
  title: string
  desc: string
  color: string
  textColor: string
  iconBg: string
  iconColor: string
}

const sessionFlow: SessionStep[] = [
  { isArrow: false, icon: FileText, step: '단계 1', title: '지문 읽기', desc: 'AI 생성 지문\n250~400자', color: '#EBF0FC', textColor: '#1B438A', iconBg: 'rgba(255,255,255,0.7)', iconColor: '#1B438A' },
  { isArrow: true, step: '', title: '', desc: '', color: '', textColor: '', iconBg: '', iconColor: '' },
  { isArrow: false, icon: NotebookPen, step: '단계 2', title: '객관식 문항', desc: '3지선다 3문제\n정보·추론·어휘', color: '#E8F0FD', textColor: '#1B438A', iconBg: 'rgba(255,255,255,0.7)', iconColor: '#1B438A' },
  { isArrow: true, step: '', title: '', desc: '', color: '', textColor: '', iconBg: '', iconColor: '' },
  { isArrow: false, icon: MessageCircleMore, step: '단계 3', title: 'AI 그룹 토의', desc: '또래 AI 3인\n최대 10라운드', color: '#DDE8FC', textColor: '#163674', iconBg: 'rgba(255,255,255,0.72)', iconColor: '#163674' },
  { isArrow: true, step: '', title: '', desc: '', color: '', textColor: '', iconBg: '', iconColor: '' },
  { isArrow: false, icon: Trophy, step: '결과', title: '점수 + streak', desc: '3종 점수 확인\nstreak 갱신', color: '#D4E1FC', textColor: '#112B5C', iconBg: 'rgba(255,255,255,0.76)', iconColor: '#112B5C' },
]

const features = [
  { icon: BookOpenText, title: 'AI 생성 지문', desc: '학생 수준에 딱 맞는 지문을 AI가 실시간으로 만들어요. 뉴스·동화·과학 등 다양한 장르를 경험해요.', bg: '#EBF0FC', color: '#1B438A' },
  { icon: UserRoundPlus, title: '또래 AI 토의', desc: '모더레이터와 또래 AI 친구들과 함께 지문에 대해 토의해요. 자연스럽게 비판적 사고력이 길러져요.', bg: '#E8F0FD', color: '#1B438A' },
  { icon: BarChart3, title: '수준별 맞춤 진단', desc: '추론력·어휘력·맥락파악 3가지 영역을 정밀 분석해요. 교사가 즉시 학급 현황을 파악할 수 있어요.', bg: '#DDE8FC', color: '#163674' },
  { icon: Flame, title: '연속 학습 streak', desc: '매일 꾸준히 학습하면 streak이 쌓여요. 게임처럼 재미있는 학습 습관 형성을 도와줘요.', bg: '#FFF1D6', color: '#B86A00' },
  { icon: Target, title: '취약 영역 포착', desc: '세션마다 학생의 약점을 정밀 추적해요. 교사가 확인이 필요한 학생을 빠르게 찾아낼 수 있어요.', bg: '#FFE6E1', color: '#C6533C' },
  { icon: ShieldCheck, title: '아동 안전 설계', desc: '모든 AI 대화에 아동 안전 지침이 내장되어 있어요. 부적절한 내용은 즉시 차단돼요.', bg: '#DAF5E8', color: '#0F8A5F' },
]

const teacherFeatures = [
  '학급 전체 수준 변화 추이 한눈에',
  '즉시 확인 필요 학생 자동 강조',
  '6자리 코드로 간편하게 학생 참여',
  '지문 난이도 직접 조정 가능',
]

const studentFeatures = [
  '코드만 입력하면 바로 시작',
  'AI 또래 친구들과 함께 토의',
  '매일 streak으로 동기 유지',
  '내 수준에 딱 맞는 지문 제공',
]

function setRef(el: unknown) {
  if (!(el instanceof Element)) return
  const observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0]
      if (!entry) return
      if (entry.isIntersecting) {
        ;(entry.target as HTMLElement).style.opacity = '1'
        ;(entry.target as HTMLElement).style.transform = 'translateY(0)'
        observer.disconnect()
      }
    },
    { threshold: 0.1 },
  )
  observer.observe(el)
}
</script>

<style scoped>
.fade-up {
  animation: fadeUp 0.5s ease forwards;
}

.fade-up-delay {
  animation: fadeUp 0.6s ease 0.2s both;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.scroll-fade {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.4s ease, transform 0.4s ease;
}
</style>

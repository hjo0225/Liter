<template>
  <div class="min-h-screen" style="background-color: #F8FAFF">
    <!-- Navigation -->
    <nav class="sticky top-0 z-50 border-b" style="background-color: white; border-color: #C8D9F6">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <img src="@/assets/logo.png" class="h-10 w-10 object-contain" alt="토도독 로고" />
          <div class="brand-font text-2xl font-bold" style="color: #10294b">토도독</div>
        </div>
        <div class="hidden md:flex items-center gap-8">
          <a href="#features" class="text-sm cursor-pointer hover:opacity-80 transition-opacity" style="color: #5A7AB8; font-weight: 500">기능</a>
          <a href="#how-it-works" class="text-sm cursor-pointer hover:opacity-80 transition-opacity" style="color: #5A7AB8; font-weight: 500">사용 방법</a>
          <a href="#faq" class="text-sm cursor-pointer hover:opacity-80 transition-opacity" style="color: #5A7AB8; font-weight: 500">FAQ</a>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="router.push('/student/join')"
            class="px-4 py-2 rounded-lg text-sm transition-all"
            style="background-color: #EBF0FC; color: #1B438A; font-weight: 600"
          >
            학생 입장 🎒
          </button>
          <button
            @click="router.push('/teacher')"
            class="px-4 py-2 rounded-lg text-sm text-white transition-all hover:opacity-90"
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
            <span class="text-sm">✨</span>
            <span class="text-sm" style="color: #C0D0F6; font-weight: 500">AI 기반 초등 문해력 토의 플랫폼</span>
          </div>
          <h1
            class="text-4xl md:text-5xl lg:text-6xl mb-6"
            style="color: white; font-weight: 800; line-height: 1.2; letter-spacing: -1px"
          >
            읽고, 생각하고,<br />
            <span style="color: #80A0E8">함께 토의해요</span> 📚
          </h1>
          <p class="text-lg md:text-xl mb-8 leading-relaxed" style="color: #93B2E8; max-width: 540px">
            초등 4~6학년을 위한 AI 문해력 학습 플랫폼이에요.
            매일 15분, AI 또래 친구들과 함께 지문을 읽고 토의하며 문해력이 자라요.
          </p>
          <div class="flex flex-wrap gap-4">
            <button
              @click="router.push('/student/join')"
              class="flex items-center gap-2 px-6 py-3.5 rounded-xl text-white transition-all hover:opacity-90 active:scale-95"
              style="background: linear-gradient(135deg, #2653AC, #4170CC); font-weight: 700; box-shadow: 0 4px 20px rgba(65,112,204,0.4)"
            >
              <span>학생으로 시작하기</span>
              <ArrowRight :size="18" />
            </button>
            <button
              @click="router.push('/teacher')"
              class="flex items-center gap-2 px-6 py-3.5 rounded-xl transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.12); border: 1.5px solid rgba(255,255,255,0.25); color: white; font-weight: 600"
            >
              <span>교사 대시보드</span>
              <ChevronRight :size="18" />
            </button>
          </div>
        </div>

        <!-- Hero mockup cards -->
        <div class="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4 fade-up-delay">
          <div
            v-for="(card, i) in heroCards"
            :key="i"
            class="rounded-2xl p-5"
            style="border: 1px solid rgba(255,255,255,0.12); backdrop-filter: blur(10px); background: rgba(255,255,255,0.08)"
          >
            <div class="text-2xl mb-3">{{ card.emoji }}</div>
            <div class="text-xs mb-1" style="color: #80A0E8; font-weight: 500">{{ card.label }}</div>
            <div class="text-lg" style="color: white; font-weight: 700">{{ card.value }}</div>
            <div class="text-xs mt-1" style="color: #6090C8">{{ card.sub }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Stats -->
    <section class="py-12 border-b" style="background-color: white; border-color: #EBF0FC">
      <div class="max-w-6xl mx-auto px-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div v-for="(stat, i) in stats" :key="i" class="text-center">
            <div class="text-2xl mb-2">{{ stat.emoji }}</div>
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
              <div class="text-3xl mb-3">{{ step.emoji }}</div>
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
            <div v-if="item.isArrow" class="hidden md:block text-2xl" style="color: #C0D0F6">→</div>
            <div
              v-else
              class="flex-1 rounded-2xl p-5 text-center"
              style="min-width: 130px"
              :style="{ backgroundColor: item.color, border: `1.5px solid ${item.color === 'transparent' ? 'transparent' : '#C0D0F6'}` }"
            >
              <div class="text-3xl mb-2">{{ item.emoji }}</div>
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
          <h2 class="text-3xl" style="color: #081830; font-weight: 800">토도독만의 특별한 점 ✨</h2>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="(feature, i) in features"
            :key="i"
            class="rounded-2xl p-6 hover:-translate-y-1 transition-transform"
            style="background-color: white; border: 1px solid #EBF0FC; box-shadow: 0 2px 16px rgba(27,67,138,0.06)"
          >
            <div class="text-3xl mb-4">{{ feature.emoji }}</div>
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
            <div class="text-4xl mb-4">👩‍🏫</div>
            <h3 class="text-xl mb-3" style="color: white; font-weight: 800">교사를 위한 토도독</h3>
            <ul class="space-y-3 mb-8">
              <li v-for="(item, i) in teacherFeatures" :key="i" class="flex items-center gap-2">
                <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background-color: rgba(255,255,255,0.15)">
                  <span class="text-xs text-white">✓</span>
                </div>
                <span class="text-sm" style="color: #93B2E8">{{ item }}</span>
              </li>
            </ul>
            <button
              @click="router.push('/teacher')"
              class="w-full py-3 rounded-xl text-sm transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.15); color: white; font-weight: 700; border: 1px solid rgba(255,255,255,0.2)"
            >
              교사 대시보드 시작하기 →
            </button>
          </div>

          <!-- For Students -->
          <div class="rounded-3xl p-8" style="background: linear-gradient(135deg, #2653AC, #4170CC)">
            <div class="text-4xl mb-4">🎒</div>
            <h3 class="text-xl mb-3" style="color: white; font-weight: 800">학생을 위한 토도독</h3>
            <ul class="space-y-3 mb-8">
              <li v-for="(item, i) in studentFeatures" :key="i" class="flex items-center gap-2">
                <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style="background-color: rgba(255,255,255,0.15)">
                  <span class="text-xs text-white">✓</span>
                </div>
                <span class="text-sm" style="color: #C0D0F6">{{ item }}</span>
              </li>
            </ul>
            <button
              @click="router.push('/student/join')"
              class="w-full py-3 rounded-xl text-sm transition-all hover:opacity-90 active:scale-95"
              style="background-color: rgba(255,255,255,0.15); color: white; font-weight: 700; border: 1px solid rgba(255,255,255,0.2)"
            >
              학생으로 입장하기 →
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Banner -->
    <section class="py-20" style="background: linear-gradient(135deg, #EBF0FC, #D4E1FC)">
      <div class="max-w-4xl mx-auto px-6 text-center">
        <div class="text-5xl mb-6">🚀</div>
        <h2 class="text-3xl mb-4" style="color: #081830; font-weight: 800">지금 바로 시작해보세요</h2>
        <p class="text-lg mb-8" style="color: #2653AC">초등 4~6학년 학생의 문해력, 토도독과 함께 키워요.</p>
        <div class="flex flex-wrap justify-center gap-4">
          <button
            @click="router.push('/teacher')"
            class="px-8 py-4 rounded-xl text-white text-sm transition-all hover:opacity-90 active:scale-95"
            style="background-color: #1B438A; font-weight: 700; box-shadow: 0 4px 20px rgba(27,67,138,0.3)"
          >
            교사로 시작하기 👩‍🏫
          </button>
          <button
            @click="router.push('/student/join')"
            class="px-8 py-4 rounded-xl text-sm transition-all hover:opacity-90 active:scale-95"
            style="background-color: white; color: #1B438A; font-weight: 700; border: 2px solid #C0D0F6"
          >
            학생으로 입장하기 🎒
          </button>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="py-10 border-t" style="background-color: #04112B; border-color: #0C2044">
      <div class="max-w-6xl mx-auto px-6">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <img src="@/assets/logo.png" class="h-9 w-9 object-contain" alt="토도독 로고" />
            <span class="brand-font text-2xl font-bold" style="color: white">토도독</span>
            <span class="text-xs ml-2" style="color: #5A7AB8">AI 기반 초등 문해력 토의 플랫폼</span>
          </div>
          <div class="text-xs" style="color: #2653AC">© 2026 토도독. 초등 4~6학년 문해력 교육을 위해 만들었어요.</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight, ChevronRight } from 'lucide-vue-next'

const router = useRouter()

const heroCards = [
  { emoji: '🔥', label: '연속 학습', value: '7일 streak', sub: '이번 주 최고 기록!' },
  { emoji: '📝', label: '오늘의 점수', value: '추론력 8.2', sub: '상위 15% 달성' },
  { emoji: '👩‍🏫', label: '학급 현황', value: '24명 참여', sub: '5학년 2반' },
]

const stats = [
  { value: '3단계', label: '세션 구조', emoji: '📚' },
  { value: '10라운드', label: 'AI 토의', emoji: '💬' },
  { value: '3가지', label: '문해력 측정', emoji: '📈' },
  { value: '매일', label: 'streak 갱신', emoji: '🔥' },
]

const steps = [
  { num: '01', emoji: '🏫', title: '교사가 학급 코드 발급', desc: '회원가입 후 학급을 생성하면 6자리 고유 코드가 발급돼요.' },
  { num: '02', emoji: '📱', title: '학생이 코드 입력', desc: '학생은 앱에서 코드와 이름만 입력하면 바로 시작할 수 있어요.' },
  { num: '03', emoji: '✨', title: 'AI와 함께 매일 학습', desc: '지문 읽기 → 객관식 → AI 토의 순서로 15~20분 세션을 진행해요.' },
]

interface SessionStep {
  isArrow: boolean
  emoji: string
  step: string
  title: string
  desc: string
  color: string
  textColor: string
}

const sessionFlow: SessionStep[] = [
  { isArrow: false, emoji: '📄', step: '단계 1', title: '지문 읽기', desc: 'AI 생성 지문\n250~400자', color: '#EBF0FC', textColor: '#1B438A' },
  { isArrow: true, emoji: '', step: '', title: '', desc: '', color: '', textColor: '' },
  { isArrow: false, emoji: '✏️', step: '단계 2', title: '객관식 문항', desc: '3지선다 3문제\n정보·추론·어휘', color: '#E8F0FD', textColor: '#1B438A' },
  { isArrow: true, emoji: '', step: '', title: '', desc: '', color: '', textColor: '' },
  { isArrow: false, emoji: '💬', step: '단계 3', title: 'AI 그룹 토의', desc: '또래 AI 3인\n최대 10라운드', color: '#DDE8FC', textColor: '#163674' },
  { isArrow: true, emoji: '', step: '', title: '', desc: '', color: '', textColor: '' },
  { isArrow: false, emoji: '🏆', step: '결과', title: '점수 + streak', desc: '3종 점수 확인\nstreak 갱신', color: '#D4E1FC', textColor: '#112B5C' },
]

const features = [
  { emoji: '📖', title: 'AI 생성 지문', desc: '학생 수준에 딱 맞는 지문을 AI가 실시간으로 만들어요. 뉴스·동화·과학 등 다양한 장르를 경험해요.' },
  { emoji: '🗣️', title: '또래 AI 토의', desc: '모더레이터와 또래 AI 친구들과 함께 지문에 대해 토의해요. 자연스럽게 비판적 사고력이 길러져요.' },
  { emoji: '📊', title: '수준별 맞춤 진단', desc: '추론력·어휘력·맥락파악 3가지 영역을 정밀 분석해요. 교사가 즉시 학급 현황을 파악할 수 있어요.' },
  { emoji: '🔥', title: '연속 학습 streak', desc: '매일 꾸준히 학습하면 streak이 쌓여요. 게임처럼 재미있는 학습 습관 형성을 도와줘요.' },
  { emoji: '🎯', title: '취약 영역 포착', desc: '세션마다 학생의 약점을 정밀 추적해요. 교사가 확인이 필요한 학생을 빠르게 찾아낼 수 있어요.' },
  { emoji: '🛡️', title: '아동 안전 설계', desc: '모든 AI 대화에 아동 안전 지침이 내장되어 있어요. 부적절한 내용은 즉시 차단돼요.' },
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

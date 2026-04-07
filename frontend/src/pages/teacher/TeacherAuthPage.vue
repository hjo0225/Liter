<script setup lang="ts">
import { ref, computed, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Eye, EyeOff, ArrowLeft } from 'lucide-vue-next'
import apiClient from '@/api/client'
import { useTeacherStore } from '@/stores/teacher'

const router = useRouter()
const teacherStore = useTeacherStore()

// ── Tab ───────────────────────────────────────────────────────────────────────
type Tab = 'login' | 'signup' | 'verify'
const tab = ref<Tab>('login')

// ── Login ─────────────────────────────────────────────────────────────────────
const email = ref('')
const password = ref('')

// ── Signup ────────────────────────────────────────────────────────────────────
const signupEmail = ref('')
const signupPw = ref('')
const signupName = ref('')

// ── OTP ───────────────────────────────────────────────────────────────────────
const verifyCode = ref(['', '', '', '', '', ''])
const verifyRefs = ref<HTMLInputElement[]>([])
const otpFilled = computed(() => verifyCode.value.every((c) => c !== ''))

// ── UI ────────────────────────────────────────────────────────────────────────
const showPw = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

// ── Countdown timer (9:45 = 585s) ────────────────────────────────────────────
const timerSeconds = ref(0)
let timerInterval: ReturnType<typeof setInterval> | null = null

const timerDisplay = computed(() => {
  const m = Math.floor(timerSeconds.value / 60)
  const s = timerSeconds.value % 60
  return `${m}:${s.toString().padStart(2, '0')}`
})

function startTimer() {
  timerSeconds.value = 585
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    if (timerSeconds.value > 0) timerSeconds.value--
    else clearInterval(timerInterval!)
  }, 1000)
}

// ── Resend cooldown ───────────────────────────────────────────────────────────
const resendCooldown = ref(0)
let resendInterval: ReturnType<typeof setInterval> | null = null

function startResendCooldown(seconds = 60) {
  resendCooldown.value = seconds
  if (resendInterval) clearInterval(resendInterval)
  resendInterval = setInterval(() => {
    if (resendCooldown.value > 0) resendCooldown.value--
    else clearInterval(resendInterval!)
  }, 1000)
}

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

function decodeJwt(token: string): Record<string, any> {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
  } catch { return {} }
}

// ── API handlers ──────────────────────────────────────────────────────────────
async function handleLogin() {
  error.value = null
  loading.value = true
  try {
    const { data } = await apiClient.post('/auth/teacher/login', {
      email: email.value,
      password: password.value,
    })
    const payload = decodeJwt(data.access_token)
    teacherStore.setAuth(data.access_token, {
      id: payload.sub ?? '',
      email: email.value,
      name: payload.user_metadata?.name ?? '',
    })
    router.push('/teacher/classrooms')
  } catch (e: any) {
    if (e.response?.status === 403 && e.response?.data?.detail === 'EMAIL_NOT_VERIFIED') {
      signupEmail.value = email.value
      tab.value = 'verify'
      startTimer()
    } else {
      error.value = '이메일 또는 비밀번호가 올바르지 않습니다.'
    }
  } finally {
    loading.value = false
  }
}

async function handleSignup() {
  error.value = null
  loading.value = true
  try {
    await apiClient.post('/auth/teacher/signup', {
      email: signupEmail.value,
      password: signupPw.value,
      name: signupName.value,
    })
    tab.value = 'verify'
    startTimer()
    startResendCooldown(60)
  } catch (e: any) {
    error.value = '이미 사용 중인 이메일입니다.'
  } finally {
    loading.value = false
  }
}

async function handleVerify() {
  error.value = null
  loading.value = true
  try {
    const { data } = await apiClient.post('/auth/teacher/verify', {
      email: signupEmail.value || email.value,
      token: verifyCode.value.join(''),
    })
    const payload = decodeJwt(data.access_token)
    teacherStore.setAuth(data.access_token, {
      id: payload.sub ?? '',
      email: signupEmail.value || email.value,
      name: payload.user_metadata?.name ?? signupName.value,
    })
    router.push('/teacher/classrooms')
  } catch (e: any) {
    error.value = '인증번호가 올바르지 않습니다.'
    verifyCode.value = ['', '', '', '', '', '']
    nextTick(() => verifyRefs.value[0]?.focus())
  } finally {
    loading.value = false
  }
}

async function handleResend() {
  if (resendCooldown.value > 0) return
  try {
    await apiClient.post('/auth/teacher/resend', {
      email: signupEmail.value || email.value,
    })
    startResendCooldown(60)
    startTimer()
    showToast('인증번호를 재전송했습니다.')
  } catch (e: any) {
    if (e.response?.status === 429) {
      const retryAfter = parseInt(e.response.headers['retry-after'] ?? '60')
      startResendCooldown(retryAfter)
      showToast('잠시 후 다시 시도해주세요.')
    } else {
      showToast('재전송에 실패했습니다.')
    }
  }
}

// ── OTP input ─────────────────────────────────────────────────────────────────
function handleVerifyInput(i: number, e: Event) {
  const char = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(-1)
  verifyCode.value[i] = char
  if (char && i < 5) nextTick(() => verifyRefs.value[i + 1]?.focus())
}

function handleVerifyKeyDown(i: number, e: KeyboardEvent) {
  if (e.key === 'Backspace') {
    if (verifyCode.value[i]) {
      verifyCode.value[i] = ''
    } else if (i > 0) {
      verifyCode.value[i - 1] = ''
      nextTick(() => verifyRefs.value[i - 1]?.focus())
    }
  }
}

function onOtpPaste(e: ClipboardEvent) {
  e.preventDefault()
  const digits = (e.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, 6)
  digits.split('').forEach((d, i) => { verifyCode.value[i] = d })
  nextTick(() => verifyRefs.value[Math.min(digits.length, 5)]?.focus())
}

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (resendInterval) clearInterval(resendInterval)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4" style="background-color: #F8FAFF;">

    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toast"
        class="fixed top-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm font-semibold text-white shadow-lg whitespace-nowrap"
        style="background: #1B438A;"
      >
        {{ toast }}
      </div>
    </Transition>

    <div class="w-full max-w-md">

      <!-- Header -->
      <div class="flex items-center justify-between mb-8">
        <button
          class="flex items-center gap-1 text-sm"
          style="color: #5A7AB8;"
          @click="router.push('/')"
        >
          <ArrowLeft :size="16" />
          홈으로
        </button>
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background-color: #1B438A;">
            <span class="text-sm">📖</span>
          </div>
          <span class="text-xl" style="font-weight: 800; color: #1B438A; letter-spacing: -0.5px;">리터</span>
        </div>
      </div>

      <!-- Card -->
      <div
        class="rounded-3xl overflow-hidden bg-white"
        style="box-shadow: 0 4px 32px rgba(27,67,138,0.1); border: 1px solid #EBF0FC;"
      >
        <!-- Tab bar (login / signup only) -->
        <div v-if="tab !== 'verify'" class="flex border-b" style="border-color: #EBF0FC;">
          <button
            v-for="t in (['login', 'signup'] as const)"
            :key="t"
            class="flex-1 py-4 text-sm relative transition-all"
            :style="tab === t
              ? 'color: #1B438A; font-weight: 700;'
              : 'color: #93B2E8; font-weight: 500;'"
            @click="tab = t; error = null"
          >
            {{ t === 'login' ? '로그인' : '회원가입' }}
            <div
              v-if="tab === t"
              class="absolute bottom-0 left-0 right-0 h-0.5"
              style="background-color: #1B438A;"
            />
          </button>
        </div>

        <div class="p-8">
          <Transition name="slide" mode="out-in">

            <!-- ── LOGIN ───────────────────────────────────────────────────── -->
            <div v-if="tab === 'login'" key="login">
              <div class="text-center mb-8">
                <div class="text-4xl mb-3">👩‍🏫</div>
                <h2 class="text-xl" style="color: #081830; font-weight: 800;">교사 로그인</h2>
                <p class="text-sm mt-1" style="color: #5A7AB8;">대시보드로 이동합니다</p>
              </div>

              <div class="space-y-4">
                <div>
                  <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">이메일</label>
                  <input
                    v-model="email"
                    type="email"
                    placeholder="teacher@school.edu"
                    class="w-full px-4 py-3 rounded-xl outline-none text-sm transition-colors"
                    style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                    @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                    @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                  />
                </div>
                <div>
                  <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">비밀번호</label>
                  <div class="relative">
                    <input
                      v-model="password"
                      :type="showPw ? 'text' : 'password'"
                      placeholder="비밀번호 입력"
                      class="w-full px-4 py-3 pr-12 rounded-xl outline-none text-sm transition-colors"
                      style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                      @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                      @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                      @keydown.enter="handleLogin"
                    />
                    <button
                      type="button"
                      class="absolute right-3 top-1/2 -translate-y-1/2"
                      style="color: #93B2E8;"
                      @click="showPw = !showPw"
                    >
                      <EyeOff v-if="showPw" :size="18" />
                      <Eye v-else :size="18" />
                    </button>
                  </div>
                </div>
                <button class="text-xs text-right w-full" style="color: #2653AC; font-weight: 500;">
                  비밀번호를 잊으셨나요?
                </button>
              </div>

              <p v-if="error" class="mt-3 text-xs text-center" style="color: #DC2626;">{{ error }}</p>

              <button
                class="w-full py-3.5 rounded-xl text-white text-sm mt-6 transition-all"
                :style="loading ? 'background-color: #C0D0F6; opacity: 0.7;' : 'background-color: #1B438A;'"
                :disabled="loading"
                style="font-weight: 700;"
                @click="handleLogin"
              >
                {{ loading ? '로그인 중...' : '로그인 →' }}
              </button>
            </div>

            <!-- ── SIGNUP ───────────────────────────────────────────────────── -->
            <div v-else-if="tab === 'signup'" key="signup">
              <div class="text-center mb-8">
                <div class="text-4xl mb-3">✨</div>
                <h2 class="text-xl" style="color: #081830; font-weight: 800;">교사 회원가입</h2>
                <p class="text-sm mt-1" style="color: #5A7AB8;">이메일 인증 후 바로 시작해요</p>
              </div>

              <div class="space-y-4">
                <div>
                  <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">이름</label>
                  <input
                    v-model="signupName"
                    type="text"
                    placeholder="예: 박민준"
                    class="w-full px-4 py-3 rounded-xl outline-none text-sm transition-colors"
                    style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                    @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                    @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                  />
                </div>
                <div>
                  <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">이메일</label>
                  <input
                    v-model="signupEmail"
                    type="email"
                    placeholder="teacher@school.edu"
                    class="w-full px-4 py-3 rounded-xl outline-none text-sm transition-colors"
                    style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                    @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                    @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                  />
                </div>
                <div>
                  <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">비밀번호</label>
                  <div class="relative">
                    <input
                      v-model="signupPw"
                      :type="showPw ? 'text' : 'password'"
                      placeholder="8자 이상"
                      minlength="8"
                      class="w-full px-4 py-3 pr-12 rounded-xl outline-none text-sm transition-colors"
                      style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                      @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                      @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                    />
                    <button
                      type="button"
                      class="absolute right-3 top-1/2 -translate-y-1/2"
                      style="color: #93B2E8;"
                      @click="showPw = !showPw"
                    >
                      <EyeOff v-if="showPw" :size="18" />
                      <Eye v-else :size="18" />
                    </button>
                  </div>
                </div>
              </div>

              <p v-if="error" class="mt-3 text-xs text-center" style="color: #DC2626;">{{ error }}</p>

              <button
                class="w-full py-3.5 rounded-xl text-white text-sm mt-6 transition-all"
                :style="signupEmail && signupPw && signupName && !loading
                  ? 'background-color: #1B438A;'
                  : 'background-color: #C0D0F6; cursor: not-allowed;'"
                :disabled="loading || !signupEmail || !signupPw || !signupName"
                style="font-weight: 700;"
                @click="handleSignup"
              >
                {{ loading ? '처리 중...' : '인증 메일 받기 →' }}
              </button>
            </div>

            <!-- ── VERIFY ──────────────────────────────────────────────────── -->
            <div v-else key="verify">
              <button
                class="flex items-center gap-1 mb-6 text-sm"
                style="color: #5A7AB8;"
                @click="tab = 'signup'; error = null"
              >
                <ArrowLeft :size="16" />
                돌아가기
              </button>

              <div class="text-center mb-8">
                <div class="text-4xl mb-3">📧</div>
                <h2 class="text-xl" style="color: #081830; font-weight: 800;">이메일 인증</h2>
                <p class="text-sm mt-2" style="color: #5A7AB8;">
                  <span style="color: #1B438A; font-weight: 700;">{{ signupEmail || email }}</span>으로<br />
                  인증번호 6자리를 발송했어요
                </p>
              </div>

              <!-- OTP cells -->
              <div class="flex justify-center gap-2 mb-2">
                <input
                  v-for="(char, i) in verifyCode"
                  :key="i"
                  :ref="(el) => { if (el) verifyRefs[i] = el as HTMLInputElement }"
                  type="text"
                  inputmode="numeric"
                  maxlength="1"
                  :value="char"
                  class="w-11 text-center rounded-xl outline-none text-xl transition-all"
                  :style="char
                    ? 'border: 2px solid #1B438A; background-color: #EBF0FC; color: #081830; font-weight: 800; height: 52px;'
                    : 'border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830; font-weight: 800; height: 52px;'"
                  @input="handleVerifyInput(i, $event)"
                  @keydown="handleVerifyKeyDown(i, $event)"
                  @paste="onOtpPaste"
                />
              </div>

              <!-- Timer & resend -->
              <div class="flex items-center justify-center gap-2 mb-6">
                <span class="text-xs" style="color: #93B2E8;">
                  유효시간
                  <span
                    :style="timerSeconds < 60 ? 'color: #DC2626; font-weight: 700;' : 'color: #DC2626; font-weight: 700;'"
                  >{{ timerDisplay }}</span>
                </span>
                <span style="color: #EBF0FC;">|</span>
                <button
                  class="text-xs"
                  :style="resendCooldown > 0
                    ? 'color: #93B2E8; cursor: not-allowed; font-weight: 600;'
                    : 'color: #2653AC; font-weight: 600; cursor: pointer;'"
                  :disabled="resendCooldown > 0"
                  @click="handleResend"
                >
                  {{ resendCooldown > 0 ? `재발송 (${resendCooldown}초)` : '재발송' }}
                </button>
              </div>

              <p v-if="error" class="text-xs text-center mb-3" style="color: #DC2626;">{{ error }}</p>

              <button
                class="w-full py-3.5 rounded-xl text-white text-sm transition-all"
                :style="otpFilled && !loading
                  ? 'background-color: #1B438A;'
                  : 'background-color: #C0D0F6; cursor: not-allowed;'"
                :disabled="!otpFilled || loading"
                style="font-weight: 700;"
                @click="handleVerify"
              >
                {{ loading ? '인증 중...' : '인증 완료 →' }}
              </button>
            </div>

          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.slide-enter-from {
  opacity: 0;
  transform: translateX(10px);
}
.slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}
</style>

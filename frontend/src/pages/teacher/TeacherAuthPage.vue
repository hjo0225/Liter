<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Eye, EyeOff, ArrowLeft } from 'lucide-vue-next'
import apiClient from '@/api/client'
import { useTeacherStore } from '@/stores/teacher'

const router = useRouter()
const teacherStore = useTeacherStore()

// ── Tab ───────────────────────────────────────────────────────────────────────
type Tab = 'login' | 'signup'
const tab = ref<Tab>('login')

// ── Login ─────────────────────────────────────────────────────────────────────
const email = ref('')
const password = ref('')

// ── Signup ────────────────────────────────────────────────────────────────────
const signupEmail = ref('')
const signupPw = ref('')
const signupName = ref('')

// ── UI ────────────────────────────────────────────────────────────────────────
const showPw = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
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
    teacherStore.setAuth(data.access_token, {
      id: data.user_id,
      email: data.email,
      name: data.name,
    })
    router.push('/teacher/classrooms')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    error.value = detail || '로그인에 실패했습니다.'
  } finally {
    loading.value = false
  }
}

async function handleSignup() {
  error.value = null
  loading.value = true
  try {
    const { data } = await apiClient.post('/auth/teacher/signup', {
      email: signupEmail.value,
      password: signupPw.value,
      name: signupName.value,
    })
    teacherStore.setAuth(data.access_token, {
      id: data.user_id,
      email: data.email,
      name: data.name,
    })
    showToast('회원가입이 완료되었습니다.')
    router.push('/teacher/classrooms')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    if (detail === '이미 가입된 이메일입니다.') {
      error.value = detail
    } else if (detail === '비밀번호는 최소 8자 이상이어야 합니다.') {
      error.value = detail
    } else if (detail === 'email rate limit exceeded') {
      error.value = '인증 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.'
    } else if (typeof detail === 'string' && detail) {
      error.value = detail
    } else if (!e.response) {
      error.value = '서버에 연결할 수 없습니다. 네트워크를 확인해 주세요.'
    } else {
      error.value = '회원가입에 실패했습니다. 잠시 후 다시 시도해 주세요.'
    }
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
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
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl text-2xl" style="background: linear-gradient(135deg, #1f5fff, #10294b)">📚</div>
          <div class="brand-font text-2xl font-bold" style="color: #10294b">토도독</div>
        </div>
      </div>

      <!-- Card -->
      <div
        class="rounded-3xl overflow-hidden bg-white"
        style="box-shadow: 0 4px 32px rgba(27,67,138,0.1); border: 1px solid #EBF0FC;"
      >
        <!-- Tab bar -->
        <div class="flex border-b" style="border-color: #EBF0FC;">
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
                <p class="text-sm mt-1" style="color: #5A7AB8;">가입 즉시 바로 시작할 수 있어요</p>
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
                {{ loading ? '처리 중...' : '회원가입 →' }}
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

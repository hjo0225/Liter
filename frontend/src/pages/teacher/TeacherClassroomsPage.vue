<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Plus, Copy, Check, ChevronRight, LogOut, Users } from 'lucide-vue-next'
import apiClient from '@/api/client'
import { useTeacherStore } from '@/stores/teacher'

const router = useRouter()
const teacherStore = useTeacherStore()

// ── State ─────────────────────────────────────────────────────────────────────
interface Classroom {
  id: string
  name: string
  join_code: string
  student_count: number
}

const classrooms = ref<Classroom[]>([])
const loading = ref(true)
const copiedCode = ref<string | null>(null)
const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const createError = ref<string | null>(null)

// ── Stats ─────────────────────────────────────────────────────────────────────
const totalStudents = computed(() => classrooms.value.reduce((s, c) => s + c.student_count, 0))

// ── API ───────────────────────────────────────────────────────────────────────
async function fetchClassrooms() {
  loading.value = true
  try {
    const { data } = await apiClient.get('/teacher/classrooms')
    classrooms.value = data
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim() || creating.value) return
  createError.value = null
  creating.value = true
  try {
    await apiClient.post('/teacher/classrooms', { name: newName.value.trim() })
    // 목록 재조회로 student_count 등 최신 상태 반영
    await fetchClassrooms()
    newName.value = ''
    showCreate.value = false
  } catch (e: any) {
    if (axios.isAxiosError(e)) {
      const detail = e.response?.data?.detail
      createError.value = typeof detail === 'string' ? detail : '학급 생성에 실패했습니다.'
    } else {
      createError.value = '학급 생성에 실패했습니다.'
    }
  } finally {
    creating.value = false
  }
}

function handleCopy(code: string) {
  navigator.clipboard.writeText(code)
  copiedCode.value = code
  setTimeout(() => { copiedCode.value = null }, 2000)
}

async function handleLogout() {
  try {
    await apiClient.post('/auth/teacher/logout')
  } catch (e) {
    console.error('Teacher logout failed', e)
  } finally {
    teacherStore.logout()
    router.push('/teacher')
  }
}

function openCreate() {
  newName.value = ''
  createError.value = null
  showCreate.value = true
}

onMounted(fetchClassrooms)
</script>

<template>
  <div class="min-h-screen" style="background-color: #F8FAFF;">

    <!-- Nav -->
    <nav class="sticky top-0 z-40 border-b bg-white" style="border-color: #EBF0FC;">
      <div class="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
        <!-- Logo -->
        <button class="flex items-center gap-3" @click="router.push('/')">
          <img src="@/assets/logo.png" class="h-10 w-10 object-contain" alt="토도독 로고" />
          <div class="brand-font text-2xl font-bold" style="color: #10294b">토도독</div>
          <span class="px-2.5 py-1 rounded-full text-xs" style="background-color: #EBF0FC; color: #1B438A; font-weight: 600;">
            교사 대시보드
          </span>
        </button>

        <!-- User -->
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2">
            <div
              class="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm"
              style="background-color: #2653AC; font-weight: 700;"
            >
              {{ teacherStore.teacher?.name?.[0] ?? '선' }}
            </div>
            <span class="text-sm hidden sm:block" style="color: #112B5C; font-weight: 600;">
              {{ teacherStore.teacher?.name ?? '선생님' }}
            </span>
          </div>
          <button class="flex items-center gap-1 text-sm" style="color: #93B2E8;" @click="handleLogout">
            <LogOut :size="16" />
            <span class="hidden sm:block">로그아웃</span>
          </button>
        </div>
      </div>
    </nav>

    <div class="max-w-5xl mx-auto px-6 py-8">

      <!-- Page Header -->
      <div class="flex items-center justify-between mb-8">
        <div>
          <h1 class="text-2xl" style="color: #081830; font-weight: 800;">학급 관리</h1>
          <p class="text-sm mt-1" style="color: #5A7AB8;">학급을 생성하고 학생들을 초대해요</p>
        </div>
        <button
          class="flex items-center gap-2 px-5 py-3 rounded-xl text-white text-sm transition-opacity hover:opacity-90"
          style="background-color: #1B438A; font-weight: 700;"
          @click="openCreate"
        >
          <Plus :size="18" />
          새 학급 만들기
        </button>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        <div
          v-for="(stat, i) in [
            { emoji: '🏫', label: '전체 학급', value: classrooms.length },
            { emoji: '👥', label: '전체 학생', value: totalStudents },
          ]"
          :key="i"
          class="rounded-2xl p-5 bg-white"
          style="border: 1px solid #EBF0FC;"
        >
          <div class="text-2xl mb-2">{{ stat.emoji }}</div>
          <div class="text-2xl" style="font-weight: 900; color: #1B438A;">{{ stat.value }}</div>
          <div class="text-xs mt-1" style="color: #5A7AB8;">{{ stat.label }}</div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin" style="border-color: #C0D0F6; border-top-color: #1B438A;" />
      </div>

      <!-- Empty state -->
      <div v-else-if="classrooms.length === 0" class="text-center py-20">
        <div class="text-5xl mb-4">🏫</div>
        <h3 class="text-lg font-bold" style="color: #112B5C;">아직 학급이 없어요</h3>
        <p class="text-sm mt-2 mb-6" style="color: #5A7AB8;">새 학급을 만들어 학생들을 초대해보세요!</p>
        <button
          class="px-6 py-3 rounded-xl text-white text-sm"
          style="background-color: #1B438A; font-weight: 700;"
          @click="openCreate"
        >
          첫 학급 만들기 +
        </button>
      </div>

      <!-- Classroom list -->
      <TransitionGroup v-else name="list" tag="div" class="space-y-4">
        <div
          v-for="cls in classrooms"
          :key="cls.id"
          class="rounded-2xl p-6 bg-white"
          style="border: 1px solid #EBF0FC; box-shadow: 0 2px 12px rgba(27,67,138,0.05);"
        >
          <div class="flex flex-col md:flex-row gap-6">

            <!-- Info -->
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style="background-color: #EBF0FC;">
                  🏫
                </div>
                <div>
                  <h3 class="font-bold" style="color: #081830;">{{ cls.name }}</h3>
                </div>
              </div>

              <div class="flex flex-wrap gap-3 mb-5">
                <div class="flex items-center gap-1.5 text-sm" style="color: #5A7AB8;">
                  <Users :size="14" />
                  <span style="font-weight: 500;">{{ cls.student_count }}명</span>
                </div>
              </div>

              <!-- Join Code -->
              <div
                class="inline-flex flex-col items-center px-6 py-4 rounded-2xl"
                style="background: linear-gradient(135deg, #EBF0FC, #DDE8FC); border: 2px dashed #93B2E8;"
              >
                <div class="text-xs mb-2" style="color: #5A7AB8; font-weight: 600;">학급 코드</div>
                <div class="text-3xl tracking-widest" style="font-weight: 900; color: #1B438A; letter-spacing: 8px;">
                  {{ cls.join_code }}
                </div>
                <button
                  class="flex items-center gap-1.5 mt-2 px-3 py-1.5 rounded-lg text-xs transition-all"
                  :style="copiedCode === cls.join_code
                    ? 'background-color: #D1FAE5; color: #065F46; font-weight: 600;'
                    : 'background-color: white; color: #2653AC; font-weight: 600;'"
                  @click="handleCopy(cls.join_code)"
                >
                  <Check v-if="copiedCode === cls.join_code" :size="13" />
                  <Copy v-else :size="13" />
                  {{ copiedCode === cls.join_code ? '복사됨!' : '코드 복사' }}
                </button>
              </div>
            </div>

            <!-- Action -->
            <div class="flex md:flex-col gap-3 md:items-end justify-end">
              <button
                class="flex items-center gap-2 px-5 py-3 rounded-xl text-white text-sm transition-opacity hover:opacity-90"
                style="background-color: #1B438A; font-weight: 700;"
                @click="router.push(`/teacher/dashboard/${cls.id}`)"
              >
                대시보드 보기
                <ChevronRight :size="16" />
              </button>
            </div>

          </div>
        </div>
      </TransitionGroup>

    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <Transition name="backdrop">
        <div
          v-if="showCreate"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
          style="background-color: rgba(4,17,43,0.6); backdrop-filter: blur(4px);"
          @click.self="showCreate = false"
        >
          <Transition name="modal" appear>
            <div
              v-if="showCreate"
              class="rounded-3xl p-8 w-full max-w-md bg-white"
            >
              <div class="text-3xl mb-4">🏫</div>
              <h2 class="text-xl mb-2" style="color: #081830; font-weight: 800;">새 학급 만들기</h2>
              <p class="text-sm mb-6" style="color: #5A7AB8;">학급을 생성하면 6자리 코드가 자동 발급돼요</p>

              <div class="mb-6">
                <label class="text-xs block mb-2" style="color: #5A7AB8; font-weight: 600;">학급 이름</label>
                <input
                  v-model="newName"
                  type="text"
                  placeholder="예: 5학년 2반"
                  autofocus
                  class="w-full px-4 py-3 rounded-xl outline-none text-sm transition-colors"
                  style="border: 2px solid #EBF0FC; background-color: #F8FAFF; color: #081830;"
                  @focus="($event.target as HTMLInputElement).style.borderColor = '#1B438A'"
                  @blur="($event.target as HTMLInputElement).style.borderColor = '#EBF0FC'"
                  @keydown.enter="handleCreate"
                />
                <p v-if="createError" class="mt-2 text-xs" style="color: #DC2626;">{{ createError }}</p>
              </div>

              <div class="flex gap-3">
                <button
                  class="flex-1 py-3 rounded-xl text-sm"
                  style="background-color: #EBF0FC; color: #1B438A; font-weight: 600;"
                  @click="showCreate = false"
                >
                  취소
                </button>
                <button
                  class="flex-1 py-3 rounded-xl text-white text-sm transition-all"
                  :style="newName.trim() && !creating
                    ? 'background-color: #1B438A; font-weight: 700;'
                    : 'background-color: #C0D0F6; font-weight: 700; cursor: not-allowed;'"
                  :disabled="!newName.trim() || creating"
                  @click="handleCreate"
                >
                  {{ creating ? '생성 중...' : '만들기 →' }}
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
.list-enter-active,
.list-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.list-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.backdrop-enter-active,
.backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.backdrop-enter-from,
.backdrop-leave-to {
  opacity: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  transform: scale(0.92);
}
</style>

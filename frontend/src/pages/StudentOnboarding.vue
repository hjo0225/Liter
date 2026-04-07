<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import apiClient from '@/api/client'

const router = useRouter()
const studentStore = useStudentStore()

const joinCode = ref('')
const name = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

// 자동 대문자
watch(joinCode, (val) => {
  joinCode.value = val.toUpperCase()
})

const canSubmit = computed(() => joinCode.value.length === 6 && name.value.trim().length > 0)

async function handleJoin() {
  if (!canSubmit.value) return
  error.value = null
  loading.value = true
  try {
    const { data } = await apiClient.post('/auth/student/join', {
      join_code: joinCode.value,
      name: name.value.trim(),
    })
    studentStore.setAuth(data.access_token, {
      id: data.student_id,
      name: name.value.trim(),
      level: 2,
      streak_count: 0,
    })
    router.push('/student/home')
  } catch (e: any) {
    if (e.response?.status === 404) {
      error.value = '올바른 학급 코드를 입력해주세요.'
    } else {
      error.value = '오류가 발생했습니다. 다시 시도해주세요.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center px-4" style="background: #F8FAFF;">
    <!-- 로고 -->
    <div class="mb-8 flex items-center gap-3">
      <div class="flex h-10 w-10 items-center justify-center rounded-xl text-2xl" style="background: linear-gradient(135deg, #1f5fff, #10294b)">📚</div>
      <div class="brand-font text-2xl font-bold" style="color: var(--ink-900)">토도독</div>
    </div>

    <!-- 카드 -->
    <div class="w-full max-w-sm rounded-2xl p-8 shadow-sm" style="background: white; border: 1px solid #EBF0FC;">
      <div class="text-center mb-6">
        <div class="text-4xl mb-3">🎒</div>
        <h1 class="font-black text-2xl mb-1" style="color: #081830;">학생 로그인</h1>
        <p class="text-sm" style="color: #5A7AB8;">선생님이 알려준 코드와 이름을 입력하세요</p>
      </div>

      <form @submit.prevent="handleJoin" class="flex flex-col gap-4">
        <!-- 학급 코드 -->
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-semibold" style="color: #081830;">학급 코드</label>
          <input
            v-model="joinCode"
            type="text"
            maxlength="6"
            placeholder="ABCD12"
            class="w-full px-4 py-3 rounded-xl border-2 text-center font-black text-xl tracking-widest outline-none transition-all"
            :style="{
              borderColor: joinCode.length === 6 ? '#1B438A' : '#EBF0FC',
              color: '#081830',
              background: '#F8FAFF',
            }"
          />
        </div>

        <!-- 이름 -->
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-semibold" style="color: #081830;">이름</label>
          <input
            v-model="name"
            type="text"
            placeholder="예: 김민준"
            maxlength="20"
            class="w-full px-4 py-3 rounded-xl border-2 outline-none transition-all"
            :style="{
              borderColor: name.trim().length > 0 ? '#1B438A' : '#EBF0FC',
              color: '#081830',
              background: '#F8FAFF',
            }"
          />
        </div>

        <!-- 에러 -->
        <p v-if="error" class="text-sm text-center" style="color: #DC2626;">{{ error }}</p>

        <!-- 버튼 -->
        <button
          type="submit"
          :disabled="!canSubmit || loading"
          class="w-full py-3.5 rounded-xl font-bold text-white transition-all mt-1"
          :style="{
            background: canSubmit && !loading ? '#1B438A' : '#CBD5E1',
            cursor: canSubmit && !loading ? 'pointer' : 'not-allowed',
          }"
        >
          {{ loading ? '확인 중...' : '로그인 →' }}
        </button>
      </form>
    </div>
  </div>
</template>

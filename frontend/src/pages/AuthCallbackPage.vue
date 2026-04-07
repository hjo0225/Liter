<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { supabase } from '@/lib/supabase'
import { useTeacherStore } from '@/stores/teacher'

const router = useRouter()
const teacherStore = useTeacherStore()

const loading = ref(true)
const error = ref<string | null>(null)

function fallbackName(email?: string | null, rawName?: string | null) {
  if (rawName?.trim()) return rawName
  if (!email) return '선생님'
  return email.split('@')[0] || '선생님'
}

async function resolveSessionFromCallback() {
  const url = new URL(window.location.href)
  const code = url.searchParams.get('code')

  if (code) {
    const exchanged = await supabase.auth.exchangeCodeForSession(code)
    if (exchanged.error) throw exchanged.error
    if (exchanged.data.session) return exchanged.data.session
  }

  const { data, error: sessionError } = await supabase.auth.getSession()
  if (sessionError) throw sessionError
  return data.session
}

onMounted(async () => {
  try {
    const session = await resolveSessionFromCallback()
    if (!session?.access_token || !session.user) {
      throw new Error('Session not found in callback')
    }

    teacherStore.setAuth(session.access_token, {
      id: session.user.id,
      email: session.user.email ?? '',
      name: fallbackName(session.user.email, session.user.user_metadata?.name as string | null | undefined),
    })

    router.replace('/teacher/classrooms')
  } catch (err) {
    console.error('Failed to finalize auth callback', err)
    error.value = '이메일 인증 처리에 실패했습니다. 다시 로그인해 주세요.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-6" style="background-color: #F8FAFF;">
    <div
      class="w-full max-w-md rounded-3xl bg-white p-8 text-center"
      style="box-shadow: 0 4px 32px rgba(27,67,138,0.1); border: 1px solid #EBF0FC;"
    >
      <div class="text-4xl mb-4">📧</div>
      <h1 class="text-xl mb-2" style="color: #081830; font-weight: 800;">이메일 인증 처리 중</h1>
      <p v-if="loading" class="text-sm" style="color: #5A7AB8;">인증 정보를 확인하고 있습니다.</p>
      <div v-else-if="error" class="space-y-4">
        <p class="text-sm" style="color: #DC2626;">{{ error }}</p>
        <button
          class="w-full rounded-xl py-3 text-sm text-white"
          style="background-color: #1B438A; font-weight: 700;"
          @click="router.replace('/teacher')"
        >
          로그인 페이지로 이동
        </button>
      </div>
    </div>
  </div>
</template>

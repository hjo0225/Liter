<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { SPEAKERS, type DisplayMessage } from './types'

const props = defineProps<{
  messages: DisplayMessage[]
  isLoading: boolean
  isDone: boolean
  error: string | null
  studentName?: string
}>()

const chatRef = ref<HTMLDivElement | null>(null)

function _scrollToBottom(smooth = true) {
  if (!chatRef.value) return
  chatRef.value.scrollTo({ top: chatRef.value.scrollHeight, behavior: smooth ? 'smooth' : 'instant' })
}

// 새 bubble 추가 → smooth scroll
watch(() => props.messages.length, async () => {
  await nextTick()
  _scrollToBottom(true)
})

// 스트리밍 토큰 → 마지막 bubble content 변경 시 instant scroll (jitter 방지)
watch(() => props.messages.at(-1)?.content, async () => {
  await nextTick()
  _scrollToBottom(false)
})

// 타이핑 인디케이터 → 토큰 전환 시 scroll
watch(() => props.messages.at(-1)?.isTyping, async () => {
  await nextTick()
  _scrollToBottom(false)
})

// 로딩 점 추가/제거 시
watch(() => props.isLoading, async () => {
  await nextTick()
  _scrollToBottom(true)
})

// 부모에서 직접 호출이 필요한 경우를 위해 노출 유지
async function scrollToBottom() {
  await nextTick()
  _scrollToBottom(true)
}

defineExpose({ scrollToBottom })
</script>

<template>
  <div
    ref="chatRef"
    class="flex-1 overflow-y-auto px-4 py-4 space-y-4"
    style="background: #F9FAFB;"
  >
    <template v-for="msg in messages" :key="msg.id">
      <!-- 내 메시지: 오른쪽 정렬 -->
      <div v-if="msg.speaker === 'user'" class="flex justify-end gap-2 items-end">
        <div
          class="max-w-[75%] rounded-2xl px-4 py-3 text-[17px] leading-relaxed font-medium"
          style="background: #3182F6; color: #fff; border-radius: 14px 14px 4px 14px;"
        >
          {{ msg.content }}
        </div>
        <div
          class="w-9 h-9 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0"
          style="background: #3182F6; font-size: 14px;"
        >
          {{ (props.studentName ?? '나')[0] }}
        </div>
      </div>

      <!-- AI 참여자: 왼쪽 정렬 -->
      <div v-else class="flex gap-2 items-start">
        <div
          class="w-9 h-9 rounded-full flex items-center justify-center font-bold flex-shrink-0"
          :style="{ background: SPEAKERS[msg.speaker].bg, color: SPEAKERS[msg.speaker].textColor, fontSize: '15px' }"
        >
          {{ SPEAKERS[msg.speaker].emoji }}
        </div>
        <div class="flex flex-col gap-1">
          <span class="text-sm font-bold" :style="{ color: SPEAKERS[msg.speaker].color }">
            {{ SPEAKERS[msg.speaker].name }}
          </span>
          <div
            class="max-w-[75%] text-[17px] leading-relaxed"
            style="background: #fff; border: 1.5px solid #E5E8EB; border-radius: 14px 14px 14px 4px; padding: 12px 16px; color: #4E5968;"
          >
            <!-- 타이핑 인디케이터: 말풍선 안 3개 점 -->
            <template v-if="msg.isTyping">
              <span
                v-for="i in 3"
                :key="i"
                class="inline-block w-1.5 h-1.5 rounded-full mx-0.5 animate-bounce"
                :style="{ background: SPEAKERS[msg.speaker].color, animationDelay: `${(i - 1) * 0.18}s` }"
              />
            </template>
            <template v-else-if="msg.content">{{ msg.content }}</template>
            <!-- 스트리밍 중 아직 텍스트 없음 → 커서 표시 -->
            <span v-else class="inline-block w-2 h-4 bg-current opacity-60 animate-pulse" />
          </div>
        </div>
      </div>
    </template>

    <!-- 연결 중 / 디렉터 대기 → 로딩 점 -->
    <div v-if="isLoading" class="flex items-center gap-2 pl-11">
      <span
        v-for="i in 3"
        :key="i"
        class="w-2 h-2 rounded-full animate-bounce"
        :style="{ background: '#3182F6', animationDelay: `${(i - 1) * 0.15}s` }"
      />
    </div>

    <!-- 토의 완료 -->
    <div v-if="isDone" class="text-center py-4">
      <div class="text-2xl mb-1">🎉</div>
      <p class="text-base font-bold" style="color: #3182F6;">토의 완료! 결과를 확인해요...</p>
    </div>

    <p v-if="error" class="text-base text-center font-semibold" style="color: #F04452;">
      {{ error }}
    </p>
  </div>
</template>

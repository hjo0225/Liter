<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  modelValue: string
  waitingForUser: boolean
  isDone: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
}>()

const focused = ref(false)

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    emit('send')
  }
}
</script>

<template>
  <div
    class="px-4 py-3 flex-shrink-0"
    style="background: #04112B; border-top: 1px solid #1B3A6B;"
  >
    <!-- 내 차례 알림 -->
    <p
      v-if="waitingForUser && !isDone"
      class="text-xs text-center mb-2 font-semibold"
      style="color: #60a5fa;"
    >
      💬 지금 내 의견을 말할 차례예요!
    </p>

    <div class="flex gap-2 items-center">
      <!-- 마이크 아이콘 (데코) -->
      <div
        class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
        :style="{ background: waitingForUser && !isDone ? '#1B438A' : '#0E2449' }"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          :stroke="waitingForUser && !isDone ? '#C0D0F6' : '#2653AC'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      </div>

      <!-- 입력 필드 -->
      <input
        :value="modelValue"
        type="text"
        :placeholder="waitingForUser && !isDone ? '내 의견을 입력해요...' : '상대방의 발언을 기다리는 중...'"
        :disabled="!waitingForUser || isDone"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown="handleKeydown"
        @focus="focused = true"
        @blur="focused = false"
        class="flex-1 px-4 py-2.5 rounded-xl outline-none text-sm transition-colors"
        :style="{
          background: '#0E2449',
          border: `1.5px solid ${focused && waitingForUser && !isDone ? '#2653AC' : '#1B3A6B'}`,
          color: waitingForUser && !isDone ? '#EBF0FC' : '#2653AC',
        }"
      />

      <!-- 전송 버튼 -->
      <button
        @click="emit('send')"
        :disabled="!waitingForUser || !modelValue.trim() || isDone"
        class="w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-all"
        :style="{
          background: waitingForUser && modelValue.trim() && !isDone ? '#2653AC' : '#0E2449',
          border: `1.5px solid ${waitingForUser && modelValue.trim() && !isDone ? '#2653AC' : '#1B3A6B'}`,
        }"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>
</template>

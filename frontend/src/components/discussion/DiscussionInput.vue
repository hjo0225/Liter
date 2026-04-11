<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  modelValue: string
  waitingForUser: boolean
  interruptEnabled: boolean   // P9: AI 발화 중 끼어들기 가능
  isDone: boolean
  idleSeconds?: number
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
    style="background: #fff; border-top: 1px solid #E5E8EB;"
  >
    <!-- 내 차례 알림 -->
    <p
      v-if="waitingForUser && !isDone && (idleSeconds ?? 0) < 15"
      class="text-sm text-center mb-2 font-semibold"
      style="color: #3182F6;"
    >
      💬 지금 내 의견을 말할 차례예요!
    </p>

    <!-- 침묵 15~29초 → 부드러운 1차 힌트 -->
    <p
      v-else-if="waitingForUser && !isDone && (idleSeconds ?? 0) >= 15 && (idleSeconds ?? 0) < 30"
      class="text-sm text-center mb-2"
      style="color: #8B95A1;"
    >
      괜찮아요, 천천히 생각해도 돼요 🙂
    </p>

    <!-- 침묵 30~89초 → 선생님이 한 번 더 물어봤어요 -->
    <p
      v-else-if="waitingForUser && !isDone && (idleSeconds ?? 0) >= 30 && (idleSeconds ?? 0) < 90"
      class="text-sm text-center mb-2"
      style="color: #FF9500;"
    >
      💬 선생님이 한 번 더 여쭤봤어요 — 편하게 말해줘요!
    </p>

    <!-- 침묵 90초 → 곧 자동으로 넘어가요 -->
    <p
      v-else-if="waitingForUser && !isDone && (idleSeconds ?? 0) >= 90"
      class="text-sm text-center mb-2"
      style="color: #F04452;"
    >
      ⏳ 잠시 후 자동으로 다음 단계로 넘어가요
    </p>

    <!-- P9: 끼어들기 가능 힌트 -->
    <p
      v-else-if="interruptEnabled && !isDone"
      class="text-sm text-center mb-2 font-medium"
      style="color: #FF9500;"
    >
      ✋ 지금 끼어들 수 있어요! 말하면 AI가 받아쳐줄 거예요
    </p>

    <div class="flex gap-2 items-center">
      <!-- 입력 필드 -->
      <input
        :value="modelValue"
        type="text"
        :placeholder="
          isDone ? '토의가 끝났어요.' :
          waitingForUser ? '내 의견을 입력해요...' :
          interruptEnabled ? '지금 말해봐요! (끼어들기)' :
          '상대방의 발언을 기다리는 중...'
        "
        :disabled="(!waitingForUser && !interruptEnabled) || isDone"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown="handleKeydown"
        @focus="focused = true"
        @blur="focused = false"
        class="flex-1 px-4 py-3 rounded-xl outline-none text-base transition-colors"
        :style="{
          background: '#F9FAFB',
          border: `1.5px solid ${
            focused && !isDone && (waitingForUser || interruptEnabled)
              ? (interruptEnabled && !waitingForUser ? '#FF9500' : '#3182F6')
              : '#E5E8EB'
          }`,
          color: (waitingForUser || interruptEnabled) && !isDone ? '#191F28' : '#8B95A1',
        }"
      />

      <!-- 전송 버튼 -->
      <button
        @click="emit('send')"
        :disabled="(!waitingForUser && !interruptEnabled) || !modelValue.trim() || isDone"
        class="px-5 py-3 rounded-xl font-bold text-base shrink-0 transition-all"
        :style="{
          background:
            (waitingForUser || interruptEnabled) && modelValue.trim() && !isDone
              ? (interruptEnabled && !waitingForUser ? '#FF9500' : '#3182F6')
              : '#E5E8EB',
          color:
            (waitingForUser || interruptEnabled) && modelValue.trim() && !isDone
              ? 'white'
              : '#8B95A1',
          cursor:
            (waitingForUser || interruptEnabled) && modelValue.trim() && !isDone
              ? 'pointer'
              : 'not-allowed',
        }"
      >
        {{ interruptEnabled && !waitingForUser ? '끼어들기' : '전송' }}
      </button>
    </div>
  </div>
</template>

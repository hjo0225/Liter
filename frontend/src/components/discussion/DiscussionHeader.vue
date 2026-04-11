<script setup lang="ts">
defineProps<{
  title: string
  round: number
  maxRounds: number
}>()
</script>

<template>
  <div
    class="flex-shrink-0"
    style="background: #04112B; border-bottom: 1px solid #1B3A6B;"
  >
    <!-- 스텝 인디케이터 -->
    <div class="flex items-center justify-center gap-2 px-4 py-2 text-xs font-bold" style="border-bottom: 1px solid #1B3A6B;">
      <span style="color: #5A7AB8;">① 읽기</span>
      <span style="color: #1B3A6B;">—</span>
      <span style="color: #5A7AB8;">② 문제풀기</span>
      <span style="color: #1B3A6B;">—</span>
      <span style="color: #80A0E8;">③ 토의</span>
      <span style="color: #1B3A6B;">—</span>
      <span style="color: #5A7AB8;">④ 결과</span>
    </div>
    <!-- 제목 + 라운드 -->
    <div class="flex items-center justify-between px-4 py-2.5">
      <div class="flex items-center gap-2 min-w-0">
        <div class="w-2 h-2 rounded-full animate-pulse flex-shrink-0" style="background: #22c55e;" />
        <span class="text-sm font-semibold text-white truncate">{{ title }}</span>
      </div>
      <span
        class="text-xs px-3 py-1 rounded-full font-bold flex-shrink-0 ml-3"
        style="background: #7C3A00; color: #FFD0A0;"
      >
        라운드 {{ round }} / {{ maxRounds }}
      </span>
    </div>
  </div>
</template>

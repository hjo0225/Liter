<script setup lang="ts">
defineProps<{
  title: string
  round: number
  maxRounds: number
}>()
</script>

<template>
  <div
    class="flex items-center justify-between px-4 py-3 flex-shrink-0"
    style="background: #12122a; border-bottom: 1px solid #2a2a3e;"
  >
    <!-- 제목 -->
    <div class="flex items-center gap-2 min-w-0">
      <div class="w-2 h-2 rounded-full animate-pulse flex-shrink-0" style="background: #22c55e;" />
      <span class="text-sm font-semibold text-white truncate">{{ title }}</span>
    </div>

    <!-- 우측 뱃지들 -->
    <div class="flex items-center gap-2 flex-shrink-0 ml-3">
      <span class="text-xs font-medium" style="color: #6b7280;">3 / 3단계</span>
      <span
        class="text-xs px-3 py-1 rounded-full font-bold"
        style="background: #1e3a6e; color: #60a5fa;"
      >
        주제 {{ round }} / {{ maxRounds }}
      </span>
    </div>
  </div>
</template>

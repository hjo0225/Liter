<script setup lang="ts">
defineProps<{
  title: string
  round: number
  maxRounds: number
}>()
</script>

<template>
  <nav
    class="flex-shrink-0 border-b"
    style="background: rgba(255,255,255,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-color: #E5E8EB;"
  >
    <!-- 메인 헤더 행 -->
    <div class="px-4 h-16 flex items-center justify-between gap-3">
      <!-- 로고 -->
      <img src="/service_logo.png" alt="토도독" class="h-10 w-auto flex-shrink-0" />

      <!-- 스텝 인디케이터 -->
      <div class="flex items-center gap-1.5 text-sm font-bold">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full flex-shrink-0" style="background: #00C471;" />
          <span style="color: #00C471;">읽기</span>
        </div>
        <span style="color: #E5E8EB;">—</span>
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full flex-shrink-0" style="background: #00C471;" />
          <span style="color: #00C471;">문제</span>
        </div>
        <span style="color: #E5E8EB;">—</span>
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full animate-pulse flex-shrink-0" style="background: #3182F6;" />
          <span style="color: #3182F6;">토의</span>
        </div>
        <span style="color: #E5E8EB;">—</span>
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full flex-shrink-0" style="background: #E5E8EB;" />
          <span style="color: #8B95A1;">결과</span>
        </div>
      </div>

      <!-- 라운드 chip -->
      <span
        class="text-sm px-3 py-1.5 rounded-full font-bold flex-shrink-0"
        style="background: #FFF4E5; color: #FF9500;"
      >
        {{ round }} / {{ maxRounds }}
      </span>
    </div>

    <!-- 토론 주제 서브행 -->
    <div class="px-4 pb-2.5 flex items-center gap-2">
      <span class="text-sm font-semibold truncate" style="color: #4E5968;">💬 {{ title }}</span>
    </div>
  </nav>
</template>

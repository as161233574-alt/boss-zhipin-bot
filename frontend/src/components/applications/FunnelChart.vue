<script setup lang="ts">
import type { FunnelStage } from '@/stores/applications'

defineProps<{ data: FunnelStage[] }>()

const colors = ['bg-blue-500', 'bg-indigo-500', 'bg-purple-500', 'bg-pink-500', 'bg-green-500']
</script>

<template>
  <div class="rounded-lg border border-border bg-card p-4">
    <div class="mb-3 text-sm font-medium">转化漏斗</div>
    <div v-if="data.length === 0" class="py-8 text-center text-xs text-muted-foreground">暂无数据</div>
    <div v-else class="space-y-2">
      <div v-for="(stage, i) in data" :key="i" class="flex items-center gap-3">
        <div class="w-16 text-right text-xs text-muted-foreground">{{ stage.label }}</div>
        <div class="flex-1">
          <div
            class="h-6 rounded-md transition-all"
            :class="colors[i % colors.length]"
            :style="{ width: `${Math.max(stage.rate, 5)}%` }"
          />
        </div>
        <div class="w-20 text-right">
          <span class="text-sm font-medium">{{ stage.count }}</span>
          <span class="ml-1 text-xs text-muted-foreground">{{ stage.rate }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

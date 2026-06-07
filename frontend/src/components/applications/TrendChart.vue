<script setup lang="ts">
import { computed } from 'vue'
import type { TrendPoint } from '@/stores/applications'

const props = defineProps<{ data: TrendPoint[] }>()

const maxVal = computed(() => {
  const all = props.data.flatMap(d => [d.applied, d.replied])
  return Math.max(...all, 1)
})

const chartHeight = 120
const barWidth = 32
const gap = 8
const chartWidth = computed(() => props.data.length * (barWidth * 2 + gap + 16))

function barH(val: number) {
  return (val / maxVal.value) * chartHeight
}
</script>

<template>
  <div class="rounded-lg border border-border bg-card p-4">
    <div class="mb-3 text-sm font-medium">7天趋势</div>
    <div v-if="data.length === 0" class="py-8 text-center text-xs text-muted-foreground">暂无数据</div>
    <div v-else class="overflow-x-auto">
      <svg :width="chartWidth" :height="chartHeight + 30" class="block">
        <g v-for="(d, i) in data" :key="i" :transform="`translate(${i * (barWidth * 2 + gap + 16) + 8}, 0)`">
          <!-- Applied bar -->
          <rect
            :y="chartHeight - barH(d.applied)"
            :width="barWidth"
            :height="barH(d.applied)"
            rx="3"
            class="fill-blue-500"
          />
          <!-- Replied bar -->
          <rect
            :x="barWidth + gap"
            :y="chartHeight - barH(d.replied)"
            :width="barWidth"
            :height="barH(d.replied)"
            rx="3"
            class="fill-green-500"
          />
          <!-- Date label -->
          <text
            :x="barWidth + gap / 2"
            :y="chartHeight + 16"
            text-anchor="middle"
            class="fill-muted-foreground text-[10px]"
          >
            {{ d.date.slice(5) }}
          </text>
        </g>
      </svg>
      <div class="mt-2 flex items-center justify-end gap-4 text-xs text-muted-foreground">
        <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded-full bg-blue-500" />投递</span>
        <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded-full bg-green-500" />回复</span>
      </div>
    </div>
  </div>
</template>

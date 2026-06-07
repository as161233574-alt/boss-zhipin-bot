<script setup lang="ts">
import { computed } from 'vue'
import type { AppStats } from '@/stores/applications'
import { Send, MessageSquare, TrendingUp, Users } from '@lucide/vue'

const props = defineProps<{ stats: AppStats | null }>()

const cards = computed(() => [
  { label: '今日投递', value: props.stats?.today_applied ?? 0, icon: Send, color: 'text-blue-500' },
  { label: '总投递', value: props.stats?.total_applied ?? 0, icon: TrendingUp, color: 'text-green-500' },
  { label: '回复率', value: `${props.stats?.reply_rate ?? 0}%`, icon: MessageSquare, color: 'text-purple-500' },
  { label: '总回复', value: props.stats?.total_replied ?? 0, icon: Users, color: 'text-orange-500' },
])
</script>

<template>
  <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
    <div v-for="card in cards" :key="card.label" class="rounded-lg border border-border bg-card p-4">
      <div class="flex items-center justify-between">
        <span class="text-xs text-muted-foreground">{{ card.label }}</span>
        <component :is="card.icon" class="h-4 w-4" :class="card.color" />
      </div>
      <div class="mt-2 text-2xl font-semibold">{{ card.value }}</div>
    </div>
  </div>
</template>

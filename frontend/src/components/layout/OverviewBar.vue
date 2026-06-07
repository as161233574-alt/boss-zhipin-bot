<script setup lang="ts">
import { computed } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { useConversationsStore } from '@/stores/conversations'
import { useSystemStore } from '@/stores/system'
import { useCountUp } from '@/composables/useCountUp'
import { Send, Clock, MessageSquare, Activity, Target, Wifi, WifiOff } from '@lucide/vue'

const appsStore = useApplicationsStore()
const convStore = useConversationsStore()
const systemStore = useSystemStore()

const todayCount = useCountUp(() => appsStore.stats?.today_applications ?? 0, { duration: 800, delay: 100 })
const followupCount = useCountUp(() => appsStore.stats?.pending ?? 0, { duration: 800, delay: 200 })
const convCount = useCountUp(() => convStore.conversations?.length ?? 0, { duration: 800, delay: 300 })
const repliedCount = useCountUp(() => appsStore.stats?.replied ?? 0, { duration: 800, delay: 250 })

const systemRunning = computed(() => systemStore.status?.browser_running ?? false)
const monitorRunning = computed(() => systemStore.status?.monitor_running ?? false)

const metrics = computed(() => [
  { label: '今日投递', value: todayCount.value, icon: Send, color: 'text-success', bg: 'bg-success/10', isText: false },
  { label: '已回复', value: repliedCount.value, icon: MessageSquare, color: 'text-info', bg: 'bg-info/10', isText: false },
  { label: '待跟进', value: followupCount.value, icon: Clock, color: followupCount.value > 0 ? 'text-warning' : 'text-muted-foreground', bg: followupCount.value > 0 ? 'bg-warning/10' : 'bg-muted', isText: false },
  { label: '活跃会话', value: convCount.value, icon: Target, color: 'text-primary', bg: 'bg-primary/10', isText: false },
  { label: '浏览器', value: systemRunning.value ? '运行中' : '已停止', icon: systemRunning.value ? Wifi : WifiOff, color: systemRunning.value ? 'text-success' : 'text-muted-foreground', bg: systemRunning.value ? 'bg-success/10' : 'bg-muted', isText: true },
])
</script>

<template>
  <div class="relative border-b border-border bg-card/50 px-6 py-2 noise">
    <!-- Scroll fade edges -->
    <div class="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-card/80 to-transparent pointer-events-none z-10" />
    <div class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-card/80 to-transparent pointer-events-none z-10" />

    <div class="flex items-center gap-1 overflow-x-auto">
      <div
        v-for="m in metrics"
        :key="m.label"
        class="flex items-center gap-2 rounded-lg px-3 py-1.5 transition-colors duration-200 hover:bg-accent/50 shrink-0"
      >
        <div class="flex h-6 w-6 items-center justify-center rounded-md" :class="m.bg">
          <component :is="m.icon" class="h-3.5 w-3.5" :class="m.color" />
        </div>
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-muted-foreground">{{ m.label }}</span>
          <span class="text-sm font-semibold tabular-nums" :class="m.color">{{ m.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

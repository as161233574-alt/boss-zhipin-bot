<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '@/stores/system'
import { Globe, Radio, Calendar } from '@lucide/vue'

defineProps<{ collapsed: boolean }>()

const systemStore = useSystemStore()

const browserOk = computed(() => systemStore.status?.browser_running ?? false)
const monitorOk = computed(() => systemStore.status?.monitor_running ?? false)
const schedulerOk = computed(() => systemStore.status?.scheduler_running ?? false)

interface StatusItem {
  label: string
  icon: typeof Globe
  ok: boolean
  activeTitle: string
  inactiveTitle: string
}

const statusItems = computed<StatusItem[]>(() => [
  { label: '浏览器', icon: Globe, ok: browserOk.value, activeTitle: '浏览器已连接', inactiveTitle: '浏览器未连接' },
  { label: '消息监听', icon: Radio, ok: monitorOk.value, activeTitle: '监听运行中', inactiveTitle: '监听已停止' },
  { label: '调度器', icon: Calendar, ok: schedulerOk.value, activeTitle: '调度器运行中', inactiveTitle: '调度器已停止' },
])
</script>

<template>
  <div class="border-t border-border p-3 space-y-1">
    <div
      v-for="item in statusItems"
      :key="item.label"
      class="flex items-center gap-2 text-xs rounded-md px-1 py-1 transition-colors duration-200 hover:bg-accent/50"
      :title="collapsed ? (item.ok ? item.activeTitle : item.inactiveTitle) : undefined"
    >
      <span class="relative flex h-2 w-2 shrink-0">
        <span
          v-if="item.ok"
          class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-40"
        />
        <span
          class="relative inline-flex h-2 w-2 rounded-full transition-colors duration-300"
          :class="item.ok ? 'bg-success' : 'bg-muted-foreground/30'"
        />
      </span>
      <component
        :is="item.icon"
        v-if="collapsed"
        class="h-3.5 w-3.5 text-muted-foreground"
      />
      <span v-else class="text-muted-foreground transition-colors duration-200" :class="item.ok ? 'text-success' : ''">
        {{ item.label }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useSystemStore } from '@/stores/system'
import { useAppStore } from '@/stores/app'
import ThemeToggle from './ThemeToggle.vue'
import { PanelLeftClose, PanelLeftOpen, Play, Square, RefreshCw, Wifi, WifiOff, Loader2, Search, Search as SearchIcon, FileText, MessageSquare, Smartphone, FileUser, Bot, Settings } from '@lucide/vue'

defineProps<{ wsConnected: boolean }>()
defineEmits<{ 'toggle-sidebar': []; 'open-command-palette': [] }>()

const route = useRoute()
const systemStore = useSystemStore()
const appStore = useAppStore()

const title = computed(() => (route.meta?.title as string) || 'BOSS 自动化')
const isRunning = computed(() => systemStore.status?.browser_running ?? false)

const pageIcon = computed(() => {
  const icons: Record<string, any> = {
    search: SearchIcon,
    applications: FileText,
    chat: MessageSquare,
    wechat: Smartphone,
    resume: FileUser,
    agents: Bot,
    settings: Settings,
  }
  return icons[route.name as string] || SearchIcon
})
</script>

<template>
  <header class="flex h-14 items-center justify-between border-b border-border surface-overlay px-4">
    <div class="flex items-center gap-3">
      <button
        @click="$emit('toggle-sidebar')"
        class="group rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-all duration-200"
      >
        <PanelLeftClose v-if="!appStore.sidebarCollapsed" class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
        <PanelLeftOpen v-else class="h-4 w-4 transition-transform duration-200 group-hover:scale-110" />
      </button>
      <div class="flex items-center gap-2">
        <component :is="pageIcon" class="h-4 w-4 text-muted-foreground" />
        <h1 class="text-sm font-semibold tracking-tight">{{ title }}</h1>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <!-- Command palette trigger -->
      <button
        @click="$emit('open-command-palette')"
        class="hidden sm:inline-flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground transition-all duration-200 hover:bg-accent hover:text-foreground hover:border-primary/20"
      >
        <Search class="h-3.5 w-3.5" />
        <span>搜索命令...</span>
        <kbd class="ml-1 rounded border border-border px-1 py-0.5 text-[10px] font-mono">⌘K</kbd>
      </button>
      <!-- WS Status with pulse -->
      <span class="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs" :class="wsConnected ? 'text-success' : 'text-muted-foreground'">
        <span class="relative flex h-2 w-2">
          <span v-if="wsConnected" class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40" :class="'bg-success'" />
          <span class="relative inline-flex h-2 w-2 rounded-full" :class="wsConnected ? 'bg-success' : 'bg-muted-foreground/40'" />
        </span>
        <Wifi v-if="wsConnected" class="h-3.5 w-3.5" />
        <WifiOff v-else class="h-3.5 w-3.5" />
      </span>

      <!-- Start/Stop button -->
      <button
        v-if="!isRunning"
        @click="systemStore.startSystem()"
        :disabled="systemStore.loading"
        class="group inline-flex items-center gap-1.5 rounded-lg gradient-primary px-3.5 py-1.5 text-xs font-medium text-primary-foreground transition-all duration-200 hover:shadow-md hover:shadow-primary/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none btn-glow"
      >
        <Loader2 v-if="systemStore.loading" class="h-3.5 w-3.5 animate-spin" />
        <Play v-else class="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110" />
        启动
      </button>
      <button
        v-else
        @click="systemStore.stopSystem()"
        :disabled="systemStore.loading"
        class="group inline-flex items-center gap-1.5 rounded-lg bg-destructive px-3.5 py-1.5 text-xs font-medium text-destructive-foreground transition-all duration-200 hover:shadow-md hover:shadow-destructive/20 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none"
      >
        <Loader2 v-if="systemStore.loading" class="h-3.5 w-3.5 animate-spin" />
        <Square v-else class="h-3.5 w-3.5 transition-transform duration-200 group-hover:scale-110" />
        停止
      </button>

      <!-- Relogin -->
      <button
        @click="systemStore.relogin()"
        class="group rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-all duration-200"
        title="重新登录"
      >
        <RefreshCw class="h-4 w-4 transition-transform duration-300 group-hover:rotate-180" />
      </button>

      <ThemeToggle />
    </div>
  </header>
</template>

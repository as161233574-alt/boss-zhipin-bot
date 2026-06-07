<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  Search, FileText, MessageSquare, Smartphone,
  FileUser, Bot, Settings, Activity
} from '@lucide/vue'
import SidebarStatus from './SidebarStatus.vue'
import { computed } from 'vue'
import { useApplicationsStore } from '@/stores/applications'
import { useConversationsStore } from '@/stores/conversations'

defineProps<{ collapsed: boolean }>()

const route = useRoute()
const router = useRouter()
const appsStore = useApplicationsStore()
const convStore = useConversationsStore()

const navItems = [
  { name: 'search', label: '岗位搜索', icon: Search },
  { name: 'applications', label: '投递记录', icon: FileText, badge: () => appsStore.stats?.followup_count },
  { name: 'chat', label: '聊天管理', icon: MessageSquare, badge: () => convStore.conversations?.filter(c => c.unread_count > 0).length },
  { name: 'wechat', label: '微信记录', icon: Smartphone },
  { name: 'resume', label: '简历优化', icon: FileUser },
  { name: 'agents', label: 'Agent', icon: Bot },
  { name: 'settings', label: '系统设置', icon: Settings },
]

const activeIndex = computed(() => navItems.findIndex(i => i.name === route.name))

function navigate(name: string) {
  router.push({ name })
}
</script>

<template>
  <aside
    class="relative flex h-screen flex-col border-r border-border bg-sidebar-background transition-[width] duration-300 ease-[var(--ease-out-quart)] noise"
    :class="collapsed ? 'w-16' : 'w-56'"
  >
    <!-- Logo -->
    <div class="flex h-14 items-center gap-2.5 border-b border-border px-4 gradient-surface overflow-hidden">
      <div class="relative group/logo">
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg gradient-primary transition-transform duration-300 hover:scale-110 shadow-md relative z-10">
          <Activity class="h-4 w-4 text-primary-foreground transition-transform duration-500 group-hover/logo:rotate-12" />
        </div>
        <!-- Breathing glow ring -->
        <div class="absolute inset-0 rounded-lg bg-primary/20 animate-pulse-soft -z-0 scale-110" />
      </div>
      <Transition name="fade-text">
        <span v-if="!collapsed" class="text-sm font-bold tracking-tight truncate gradient-text">BOSS 自动化</span>
      </Transition>
    </div>

    <!-- Navigation -->
    <nav class="relative flex-1 space-y-0.5 p-2 overflow-visible">
      <!-- Animated active indicator -->
      <div
        v-if="activeIndex >= 0"
        class="absolute left-2 right-2 h-9 rounded-lg bg-sidebar-accent shadow-sm transition-all duration-300 ease-[var(--ease-out-quart)]"
        :style="{ top: `${activeIndex * 36 + 8}px` }"
      />

      <button
        v-for="(item, idx) in navItems"
        :key="item.name"
        @click="navigate(item.name)"
        class="group/nav relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200 active:scale-95"
        :class="route.name === item.name
          ? 'text-sidebar-accent-foreground font-medium'
          : 'text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/40'"
      >
        <!-- Active left accent -->
        <div
          v-if="route.name === item.name"
          class="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-primary transition-all duration-300"
        />
        <component
          :is="item.icon"
          class="h-4 w-4 shrink-0 transition-transform duration-200"
          :class="route.name === item.name ? 'scale-110' : ''"
        />
        <Transition name="fade-text">
          <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
        </Transition>
        <span
          v-if="!collapsed && item.badge && item.badge() > 0"
          class="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-bold text-primary-foreground animate-bounce-in"
        >
          {{ item.badge() }}
        </span>
        <!-- Tooltip when collapsed -->
        <div
          v-if="collapsed"
          class="absolute left-full ml-2 z-50 whitespace-nowrap rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background opacity-0 pointer-events-none group-hover/nav:opacity-100 transition-all duration-200 -translate-x-1 group-hover/nav:translate-x-0 shadow-lg"
        >
          {{ item.label }}
          <div class="absolute left-0 top-1/2 -translate-x-1 -translate-y-1/2 w-2 h-2 bg-foreground rotate-45" />
        </div>
      </button>
    </nav>

    <!-- Status -->
    <SidebarStatus :collapsed="collapsed" />
  </aside>
</template>

<style scoped>
.fade-text-enter-active {
  transition: opacity 200ms ease-out 80ms;
}
.fade-text-leave-active {
  transition: opacity 120ms ease-in;
}
.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
}
</style>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import { Sun, Moon } from '@lucide/vue'

const appStore = useAppStore()
</script>

<template>
  <button
    @click="appStore.toggleTheme()"
    class="group relative rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-all duration-200 overflow-hidden"
    :title="appStore.theme === 'dark' ? '切换为亮色' : '切换为暗色'"
  >
    <Transition name="theme-icon" mode="out-in">
      <Sun v-if="appStore.theme === 'dark'" key="sun" class="h-4 w-4" />
      <Moon v-else key="moon" class="h-4 w-4" />
    </Transition>
  </button>
</template>

<style scoped>
.theme-icon-enter-active {
  transition: all 250ms var(--ease-spring);
}
.theme-icon-leave-active {
  transition: all 150ms ease-in;
}
.theme-icon-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.5);
}
.theme-icon-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.5);
}
</style>

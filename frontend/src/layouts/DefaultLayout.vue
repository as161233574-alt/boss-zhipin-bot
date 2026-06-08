<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import ToastContainer from '@/components/shared/ToastContainer.vue'
import CommandPalette from '@/components/shared/CommandPalette.vue'
import OverviewBar from '@/components/layout/OverviewBar.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useSystemStatus } from '@/composables/useSystemStatus'
import { useKeyboard } from '@/composables/useKeyboard'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const { connected } = useWebSocket()
useSystemStatus()

const commandPaletteOpen = ref(false)
const mainEl = ref<HTMLElement>()
const mouseX = ref(50)
const mouseY = ref(50)

useKeyboard({
  onCommandPalette: () => { commandPaletteOpen.value = true },
  onEscape: () => { commandPaletteOpen.value = false },
})

function onMainMouseMove(e: MouseEvent) {
  if (!mainEl.value) return
  const rect = mainEl.value.getBoundingClientRect()
  mouseX.value = ((e.clientX - rect.left) / rect.width) * 100
  mouseY.value = ((e.clientY - rect.top) / rect.height) * 100
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background">
    <AppSidebar :collapsed="appStore.sidebarCollapsed" />
    <div class="flex flex-1 flex-col overflow-hidden min-w-0">
      <AppHeader :ws-connected="connected" @toggle-sidebar="appStore.toggleSidebar()" @open-command-palette="commandPaletteOpen = true" />
      <OverviewBar />
      <main ref="mainEl" class="flex-1 overflow-y-auto relative dot-pattern" @mousemove="onMainMouseMove">
        <!-- Ambient gradient mesh background -->
        <div class="pointer-events-none fixed inset-0 z-0 overflow-hidden">
          <div
            class="absolute w-[600px] h-[600px] rounded-full opacity-[0.03] blur-[100px] transition-all duration-[2000ms] ease-out"
            :style="{
              background: 'radial-gradient(circle, oklch(0.55 0.18 280), transparent 70%)',
              left: `${mouseX * 0.3}%`,
              top: `${mouseY * 0.3}%`,
              transform: 'translate(-50%, -50%)'
            }"
          />
          <div
            class="absolute w-[400px] h-[400px] rounded-full opacity-[0.02] blur-[80px]"
            style="background: radial-gradient(circle, oklch(0.62 0.17 155), transparent 70%); right: 10%; top: 20%"
          />
          <div
            class="absolute w-[300px] h-[300px] rounded-full opacity-[0.02] blur-[60px]"
            style="background: radial-gradient(circle, oklch(0.75 0.15 75), transparent 70%); left: 20%; bottom: 10%"
          />
        </div>

        <div class="relative z-10 mx-auto max-w-7xl h-full p-4 md:p-6 flex flex-col">
          <RouterView v-slot="{ Component, route }">
            <Transition name="page" mode="out-in">
              <component :is="Component" :key="route.path" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>
    <ToastContainer />
    <CommandPalette :open="commandPaletteOpen" @close="commandPaletteOpen = false" />
  </div>
</template>

<style scoped>
.page-enter-active {
  transition: opacity 300ms var(--ease-out-quart), transform 300ms var(--ease-out-quart);
}
.page-leave-active {
  transition: opacity 150ms ease-in, transform 150ms ease-in;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.995);
}
</style>

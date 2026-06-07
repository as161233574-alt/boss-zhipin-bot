<script setup lang="ts">
import { useToast } from '@/composables/useToast'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from '@lucide/vue'
import { computed } from 'vue'

const { toasts, remove } = useToast()

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap = {
  success: 'border-l-success bg-success/5 text-success',
  error: 'border-l-destructive bg-destructive/5 text-destructive',
  warning: 'border-l-warning bg-warning/5 text-warning',
  info: 'border-l-info bg-info/5 text-info',
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto flex items-start gap-3 rounded-lg border border-l-4 glass px-4 py-3 shadow-lg min-w-[300px] max-w-[420px]"
          :class="colorMap[toast.type]"
        >
          <component :is="iconMap[toast.type]" class="mt-0.5 h-4 w-4 shrink-0" />
          <p class="flex-1 text-sm text-foreground">{{ toast.message }}</p>
          <button
            @click="removeToast(toast.id)"
            class="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  transition: all 300ms var(--ease-out-quart);
}
.toast-leave-active {
  transition: all 200ms ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%) scale(0.95);
}
.toast-move {
  transition: transform 300ms var(--ease-out-quart);
}
</style>

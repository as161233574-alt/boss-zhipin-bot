<script setup lang="ts">
import { computed } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { Loader2, Zap } from '@lucide/vue'

const jobsStore = useJobsStore()

const progress = computed(() => jobsStore.scoreProgress)
const percent = computed(() => progress.value && progress.value.total > 0
  ? Math.round((progress.value.current / progress.value.total) * 100)
  : 0
)
</script>

<template>
  <Transition name="status">
    <div
      v-if="progress"
      class="overflow-hidden rounded-xl border border-info/20 glass"
    >
      <div class="p-4">
        <div class="flex items-center gap-3 text-sm">
          <div class="relative">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-info/10">
              <Loader2 class="h-5 w-5 text-info animate-spin" />
            </div>
            <!-- Pulse ring -->
            <div class="absolute inset-0 rounded-xl bg-info/10 animate-ping opacity-30" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <Zap class="h-3.5 w-3.5 text-info" />
              <span class="font-semibold text-info">批量评分中</span>
              <span class="rounded-full bg-info/10 px-2 py-0.5 text-[10px] font-bold text-info tabular-nums">
                {{ progress.current }}/{{ progress.total }}
              </span>
            </div>
            <div class="mt-0.5 text-xs text-muted-foreground truncate">
              {{ progress.job_title }}
            </div>
          </div>
          <div class="text-right shrink-0">
            <div class="text-lg font-bold tabular-nums text-info">{{ percent }}%</div>
          </div>
        </div>

        <!-- Progress bar -->
        <div class="mt-3 h-2.5 overflow-hidden rounded-full bg-info/10">
          <div
            class="h-full rounded-full bg-gradient-to-r from-info to-chart-2 transition-all duration-500 ease-[var(--ease-out-quart)] relative"
            :style="{ width: `${percent}%` }"
          >
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/25 to-transparent animate-[shimmer_1.5s_infinite]" />
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.status-enter-active {
  transition: all 400ms var(--ease-out-quart);
}
.status-leave-active {
  transition: all 250ms ease-in;
}
.status-enter-from {
  opacity: 0;
  transform: translateY(-8px);
  max-height: 0;
}
.status-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
@keyframes shimmer {
  from { transform: translateX(-100%); }
  to { transform: translateX(100%); }
}
</style>
